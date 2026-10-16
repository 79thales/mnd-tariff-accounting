"""Validované správcovské zápisy z formulářů a HA akcí.

Není to účet MND: úpravy mění jen místní archiv. Každý záznam má stabilní ID,
čas přijetí a audit; změna již existujícího dokladu vyžaduje novou revizi.
"""

from __future__ import annotations

from datetime import datetime

from .core.accounting import ROLES, active_versions
from .core.archive import merge_records
from .core.common import DataError, day, decimal, fingerprint, instant, local_day, period, wire
from .core.metering import Reading


def _fields(record, allowed, required=()):
    if (
        not isinstance(record, dict)
        or set(record) - set(allowed)
        or any(k not in record for k in required)
    ):
        raise DataError("invalid_form_fields")


def edit_place(data, *, place_id, section, record, now: datetime, zone: str):
    """Transakční mutátor; všechny kontroly proběhnou před potvrzením I/O.

    Nuly se nepředvyplňují. Celý měsíční plán lze uložit jednou transakcí;
    předpis nikdy nevytvoří skutečnou úhradu a částečná platba může být vyšší.
    """
    if place_id not in data["places"]:
        raise DataError("place_not_found")
    place = data["places"][place_id]
    record = dict(record)
    if section == "transfer":
        # Dvě strany převodu se potvrdí v jediné vnější transakci. Nelze
        # vytvořit nový kredit bez odkazu na jeho stejně velký odchod.
        _fields(
            record,
            ("id", "amount", "date", "from", "to", "target_from", "target_to", "invoice", "note"),
            ("id", "amount", "date", "from", "to", "target_from", "target_to"),
        )
        period(record["from"], record["to"])
        period(record["target_from"], record["target_to"])
        outgoing, incoming = fingerprint([record["id"], "out"]), fingerprint([record["id"], "in"])
        for role, key, counterpart, left, right in (
            ("transfer_out", outgoing, incoming, record["from"], record["to"]),
            ("transfer_in", incoming, outgoing, record["target_from"], record["target_to"]),
        ):
            event = {
                "id": key,
                "amount": record["amount"],
                "date": record["date"],
                "role": role,
                "counterpart": counterpart,
                "from": left,
                "to": right,
                "note": record.get("note", ""),
            }
            if role == "transfer_out" and record.get("invoice"):
                event["invoice"] = record["invoice"]
            edit_place(data, place_id=place_id, section="events", record=event, now=now, zone=zone)
    elif section == "advance_grid":
        _fields(record, ("id", "rows"), ("id", "rows"))
        if not isinstance(record["rows"], list) or len(record["rows"]) > 120:
            raise DataError("invalid_advance_grid")
        settings = place["settings"]
        left, right = period(settings.get("period_from"), settings.get("period_to"))
        seen = set()
        for row in record["rows"]:
            _fields(row, ("month", "prescribed", "paid", "paid_on"), ("month",))
            month = day(row["month"] + "-01")
            if month in seen:
                raise DataError("duplicate_advance_month")
            seen.add(month)
            from datetime import timedelta

            following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
            a, b = max(left, month), min(right, following)
            if a >= b:
                raise DataError("advance_month_outside_period")
            for field, role in (("prescribed", "prescribed"), ("paid", "payment")):
                if field not in row or row[field] == "":
                    continue
                amount = decimal(row[field], nonnegative=True)
                older = [
                    event
                    for event in active_versions(place["events"])
                    if event.get("month") == row["month"]
                    and event.get("source") == "monthly_grid"
                    and event["role"] == role
                ]
                if len(older) > 1:
                    raise DataError("advance_grid_conflict")
                paid_on = day(row["paid_on"]).isoformat() if role == "payment" else a.isoformat()
                if (
                    older
                    and decimal(older[0]["amount"]) == amount
                    and older[0].get("date") == paid_on
                ):
                    continue
                if role == "payment" and day(paid_on) > local_day(now, zone):
                    raise DataError("future_payment")
                event = {
                    "id": fingerprint([record["id"], row["month"], role]),
                    "place": place_id,
                    "role": role,
                    "amount": amount,
                    "date": paid_on,
                    "month": row["month"],
                    "from": a.isoformat(),
                    "to": b.isoformat(),
                    "source": "monthly_grid",
                    "verification": "user_confirmed",
                    "supersedes": older[0]["id"] if older else None,
                }
                place["events"], _ = merge_records(place["events"], [wire(event)])
        active_versions(place["events"])
    elif section == "settings":
        allowed = (
            "name",
            "period_from",
            "period_to",
            "opening_credit",
            "payments_complete",
            "allow_linear",
            "source_mode",
            "source_entity",
            "source_registry_id",
            "segment",
        )
        _fields(record, allowed)
        merged = {**place["settings"], **record}
        if "name" in record:
            if not isinstance(record["name"], str) or len(record["name"].strip()) > 160:
                raise DataError("invalid_place_name")
            merged["name"] = record["name"].strip()
            place["name"] = merged["name"]
        if merged.get("period_from") or merged.get("period_to"):
            period(merged.get("period_from"), merged.get("period_to"))
        if "opening_credit" in record:
            merged["opening_credit"] = decimal(record["opening_credit"], optional=True)
        if merged.get("source_mode", "manual") not in ("manual", "sensor"):
            raise DataError("invalid_source_mode")
        for field in ("payments_complete", "allow_linear"):
            if field in record and not isinstance(record[field], bool):
                raise DataError("invalid_boolean")
        place["settings"] = wire(merged)
    elif section == "readings":
        _fields(
            record,
            ("id", "meter", "segment", "value", "observed_at", "note", "supersedes"),
            ("id", "meter", "value", "observed_at"),
        )
        at = instant(record["observed_at"])
        reading = Reading.parse(
            {
                **record,
                "place": place_id,
                "date": local_day(at, zone),
                "source": "manual",
                "method": "Ruční odečet v HA",
            },
            now=now,
        )
        record = wire(reading.dump())
        place["readings"], _ = merge_records(place["readings"], [record])
    elif section == "calibration":
        _fields(
            record,
            ("entity", "segment", "at", "physical", "sensor", "note"),
            ("entity", "segment", "at", "physical", "sensor"),
        )
        if instant(record["at"]) > instant(now):
            raise DataError("future_calibration")
        record.update(
            place=place_id,
            physical=decimal(record["physical"], nonnegative=True),
            sensor=decimal(record["sensor"], nonnegative=True),
        )
        place["settings"]["calibration"] = wire(record)
    elif section in ("tariffs", "conversions"):
        if section == "tariffs":
            _fields(
                record,
                (
                    "id",
                    "name",
                    "from",
                    "to",
                    "commodity",
                    "other",
                    "fixed",
                    "includes_vat",
                    "vat_percent",
                    "all_components_known",
                    "prorate_fixed",
                    "role",
                    "supersedes",
                    "evidence",
                ),
                ("id", "from", "to"),
            )
            for field in ("commodity", "other", "fixed", "vat_percent"):
                record[field] = decimal(record.get(field), optional=True, nonnegative=True)
            for field in ("includes_vat", "all_components_known", "prorate_fixed"):
                if record.get(field) is not None and not isinstance(record[field], bool):
                    raise DataError("invalid_boolean")
            if record.get("role", "current") not in ("current", "subsequent", "alternative"):
                raise DataError("invalid_tariff_role")
        else:
            _fields(
                record,
                ("id", "from", "to", "kwh_per_m3", "estimated", "evidence", "supersedes"),
                ("id", "from", "to", "kwh_per_m3"),
            )
            record["kwh_per_m3"] = decimal(record["kwh_per_m3"])
            if record["kwh_per_m3"] <= 0:
                raise DataError("invalid_conversion")
            if not record.get("evidence"):
                raise DataError("conversion_evidence_required")
        period(record["from"], record["to"])
        record["place"] = place_id
        place[section], _ = merge_records(place[section], [wire(record)])
        active_versions(place[section])
    elif section == "events":
        _fields(
            record,
            (
                "id",
                "amount",
                "date",
                "from",
                "to",
                "role",
                "verification",
                "source",
                "invoice",
                "counterpart",
                "supersedes",
                "note",
            ),
            ("id", "amount", "date", "role"),
        )
        if record["role"] not in ROLES:
            raise DataError("invalid_ledger_role")
        record["amount"] = decimal(record["amount"], nonnegative=True)
        if day(record["date"]) > local_day(now, zone) and record["role"] not in (
            "prescribed",
            "assumed_paid",
        ):
            raise DataError("future_payment")
        if record.get("from") or record.get("to"):
            period(record.get("from"), record.get("to"))
        record.update(
            place=place_id,
            source=record.get("source", "manual"),
            verification=record.get("verification", "user_confirmed"),
        )
        place["events"], _ = merge_records(place["events"], [wire(record)])
        active_versions(place["events"])
    elif section == "invoices":
        _fields(
            record,
            (
                "id",
                "number",
                "from",
                "to",
                "cost",
                "result",
                "confirmed",
                "supersedes",
                "artifact",
                "volume_m3",
                "energy_mwh",
                "included_advances",
                "issued_on",
                "due_on",
                "note",
            ),
            ("id", "number", "from", "to", "cost", "result", "confirmed"),
        )
        if record["confirmed"] is not True:
            raise DataError("invoice_confirmation_required")
        period(record["from"], record["to"])
        if record.get("artifact") and not any(
            a["id"] == record["artifact"] for a in place["artifacts"]
        ):
            raise DataError("invoice_artifact_not_found")
        record.update(
            cost=decimal(record["cost"], nonnegative=True),
            result=decimal(record["result"]),
            place=place_id,
        )
        for key in ("volume_m3", "energy_mwh", "included_advances"):
            if key in record:
                record[key] = decimal(record[key], optional=True, nonnegative=True)
        place["invoices"], _ = merge_records(place["invoices"], [wire(record)])
        active_versions(place["invoices"])
    else:
        raise DataError("invalid_edit_section")
    audit = {
        "section": section,
        "record": wire(record),
        "received_at": now.isoformat(),
        "actor": "administrator",
    }
    audit["id"] = fingerprint(audit)
    place["audit"].append(audit)
    return {"saved": True}
