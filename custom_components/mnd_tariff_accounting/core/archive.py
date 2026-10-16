"""Transakční doménový archiv: změna se publikuje až po potvrzeném zápisu."""

from __future__ import annotations

import asyncio
import copy

from .accounting import ROLES, active_versions
from .common import DataError, day, decimal, fingerprint, identity, instant, period, wire
from .forecast import add_snapshot
from .metering import Reading, active_readings

SCHEMA_VERSION = 1
SECTIONS = (
    "readings",
    "tariffs",
    "conversions",
    "events",
    "invoices",
    "imports",
    "artifacts",
    "samples",
    "snapshots",
    "audit",
)


def empty_archive(account: str) -> dict:
    """Nová entry nemá potvrzené nuly, ceny ani platby; vlastní účetní identita je stabilní."""
    return {
        "schema_version": SCHEMA_VERSION,
        "account": account,
        "revision": 0,
        "places": {},
        "job": {"status": "idle", "cursor": None},
    }


def new_place(name: str = "") -> dict:
    return {**{key: [] for key in SECTIONS}, "name": name, "settings": {}, "coverage": None}


def validate_archive(data: dict, account: str):
    """Poškozený nebo budoucí archiv se nikdy nezamění za prázdný úspěšný stav."""
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != SCHEMA_VERSION
        or data.get("account") != account
    ):
        raise DataError("archive_incompatible")
    if (
        type(data.get("revision")) is not int
        or data["revision"] < 0
        or not isinstance(data.get("places"), dict)
        or not isinstance(data.get("job"), dict)
        or data["job"].get("status")
        not in {"idle", "running", "paused", "completed", "limited", "cancelled"}
    ):
        raise DataError("archive_invalid")
    for place, content in data["places"].items():
        identity(place)
        if (
            not isinstance(content, dict)
            or any(not isinstance(content.get(s), list) for s in SECTIONS)
            or not isinstance(content.get("settings"), dict)
        ):
            raise DataError("archive_invalid")
        settings = content["settings"]
        if any(not isinstance(record, dict) for section in SECTIONS for record in content[section]):
            raise DataError("archive_invalid_record")
        calibration = settings.get("calibration")
        if calibration is not None:
            if not isinstance(calibration, dict) or any(
                key not in calibration
                for key in ("place", "segment", "entity", "at", "physical", "sensor")
            ):
                raise DataError("invalid_calibration")
            instant(calibration["at"])
            decimal(calibration["physical"], nonnegative=True)
            decimal(calibration["sensor"], nonnegative=True)
        if settings.get("period_from") or settings.get("period_to"):
            period(settings.get("period_from"), settings.get("period_to"))
        decimal(settings.get("opening_credit"), optional=True)
        for key in ("payments_complete", "allow_linear"):
            if key in settings and not isinstance(settings[key], bool):
                raise DataError("archive_invalid_boolean")
        if settings.get("source_mode", "manual") not in ("manual", "sensor"):
            raise DataError("invalid_source_mode")
        rows = [Reading.parse(row) for row in content["readings"]]
        if any(row.place != place for row in rows):
            raise DataError("supply_point_mismatch")
        active_readings(rows)
        active_versions(content["events"])
        active_versions(content["invoices"])
        for section in ("events", "invoices", "tariffs", "conversions"):
            for record in content[section]:
                if record.get("place", place) != place:
                    raise DataError("supply_point_mismatch")
                if record.get("from") or record.get("to"):
                    period(record.get("from"), record.get("to"))
                if section == "events":
                    if record.get("role") not in ROLES:
                        raise DataError("invalid_ledger_role")
                    decimal(record.get("amount"), nonnegative=True)
                    if record.get("date"):
                        day(record["date"])
                elif section == "invoices":
                    period(record.get("from"), record.get("to"))
                    decimal(record.get("cost"), nonnegative=True)
                    decimal(record.get("result"))
                    if record.get("confirmed") is not True:
                        raise DataError("invoice_confirmation_required")
                elif section == "tariffs":
                    for field in ("commodity", "other", "fixed", "vat_percent"):
                        decimal(record.get(field), optional=True, nonnegative=True)
                elif decimal(record.get("kwh_per_m3")) <= 0:
                    raise DataError("invalid_conversion")
        for sample in content["samples"]:
            if not isinstance(sample, dict) or not all(
                key in sample for key in ("at", "entity", "segment")
            ):
                raise DataError("archive_invalid_sample")
            instant(sample["at"])
            decimal(sample.get("value"), optional=True, nonnegative=True)
        for snapshot in content["snapshots"]:
            instant(snapshot.get("retrieved_at"))
            if not isinstance(snapshot.get("periods"), list):
                raise DataError("archive_invalid_snapshot")


class Repository:
    """Jeden zámek entry pro import, opravy i kurzor; I/O zajišťuje adaptér.

    Při cancellation během zápisu se dokončí atomický commit, teprve pak
    se cancellation předá volajícímu. Neúspěšné I/O nezmění paměťový stav.
    Restart načte poslední commit; běžící úloha je pozastavena, ne spuštěna.
    """

    def __init__(self, account: str, saved: dict | None, save):
        self.account, self.save = account, save
        self.lock = asyncio.Lock()
        self.data = copy.deepcopy(saved) if saved is not None else empty_archive(account)
        validate_archive(self.data, account)
        if self.data["job"]["status"] == "running":
            self.data["job"]["status"] = "paused"

    async def transact(self, mutate, *, expected_revision: int | None = None):
        async with self.lock:
            if expected_revision is not None and expected_revision != self.data["revision"]:
                raise DataError("revision_changed")
            candidate = copy.deepcopy(self.data)
            result = mutate(candidate)
            if candidate == self.data:
                return result
            candidate["revision"] += 1
            candidate = wire(candidate)
            validate_archive(candidate, self.account)
            task = asyncio.create_task(self.save(candidate))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                self.data = candidate
                raise
            self.data = candidate
            return result


def merge_records(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int]:
    """Stejné ID je idempotentní; změněný obsah téhož ID vyžaduje explicitní revizi."""
    merged = {row["id"]: row for row in existing}
    count = 0
    for row in wire(incoming):
        key = row["id"]
        if key in merged and merged[key] != row:
            # Jeden sémantický odečet může být doložen dalším originálem.
            before = {k: v for k, v in merged[key].items() if k != "evidence"}
            after = {k: v for k, v in row.items() if k != "evidence"}
            if before != after:
                raise DataError("immutable_record_conflict")
        if key not in merged:
            merged[key] = row
            count += 1
    return list(merged.values()), count


def apply_import(data: dict, parsed: dict, *, name="") -> dict:
    """Volá se uvnitř transakce; raw v1 a původ každého importu se zachová."""
    place = data["places"].setdefault(parsed["place"], new_place(name))
    token = parsed.get("id") or parsed["sha256"]
    if any(item["id"] == token for item in place["imports"]):
        return {"new": 0, "duplicate": True}
    incoming = parsed["readings"]
    rows = [item["reading"].dump() if "reading" in item else item for item in incoming]
    place["readings"], count = merge_records(place["readings"], rows)
    for section in ("tariffs", "events"):
        place[section], _ = merge_records(place[section], parsed.get(section, []))
    for snapshot in parsed.get("snapshots", []):
        place["snapshots"] = add_snapshot(place["snapshots"], wire(snapshot))
    if parsed.get("raw"):
        place["coverage"] = parsed["raw"].get("Coverage")
    place["imports"].append(
        {
            "id": token,
            "raw": parsed.get("raw"),
            "rows": wire([r.get("original") for r in incoming if "original" in r]),
            "rejected": parsed.get("rejected", []),
            "warnings": parsed.get("warnings", []),
        }
    )
    place["audit"].append(
        {
            "id": fingerprint([token, "import"]),
            "action": "import",
            "artifact": token,
            "new_rows": count,
        }
    )
    return {"new": count, "duplicate": False, "rejected": len(parsed.get("rejected", []))}
