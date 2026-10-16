"""Odečty, priorita MND a přerušená návaznost měření.

Neprovádí kalibraci faktorem historické odchylky. Dokladové řádky zůstávají
oddělené od logických bodů a rozdíly se sčítají jen ve shodném segmentu.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from .common import DataError, day, decimal, fingerprint, instant, local_day


@dataclass(frozen=True)
class Reading:
    """Neměnná verze odečtu; method, status a source mají odlišný význam.

    `observed_at=None` zachovává pouze den. `supersedes` je doložená vazba
    opravy a neznamená volbu největší hodnoty. Segment se při výměně mění.
    """

    id: str
    place: str
    meter: str
    date: date
    value: Decimal
    source: str
    method: str = ""
    status: str = ""
    observed_at: datetime | None = None
    segment: str = ""
    supersedes: str | None = None
    estimated: bool = False
    evidence: str = ""
    note: str = ""

    @classmethod
    def parse(cls, data: dict, *, now: datetime | None = None) -> Reading:
        """Validuje jeden zápis před transakcí; chybný nebo budoucí stav se neuloží."""
        required = ("id", "place", "meter", "date", "value", "source")
        if any(key not in data for key in required):
            raise DataError("reading_missing_fields")
        if any(
            not isinstance(data[k], str) or not data[k].strip()
            for k in ("id", "place", "meter", "source")
        ):
            raise DataError("reading_invalid_identity")
        if data["source"] not in {"mnd", "manual", "sensor"}:
            raise DataError("invalid_reading_source")
        at = instant(data["observed_at"]) if data.get("observed_at") else None
        if now and at and at > instant(now):
            raise DataError("future_reading")
        return cls(
            id=data["id"],
            place=data["place"],
            meter=data["meter"],
            date=day(data["date"]),
            value=decimal(data["value"], nonnegative=True),
            source=data["source"],
            method=str(data.get("method", "")),
            status=str(data.get("status", "")),
            observed_at=at,
            segment=str(data.get("segment") or data["meter"]),
            supersedes=data.get("supersedes"),
            estimated=bool(data.get("estimated", False)),
            evidence=str(data.get("evidence", "")),
            note=str(data.get("note", "")),
        )

    def dump(self) -> dict:
        return asdict(self)


def active_readings(readings: list[Reading]) -> list[Reading]:
    """Oprava nahrazuje pouze vlastní zdroj/segment; cyklus a více oprav je konflikt.

    Stejné ID s jiným obsahem se odmítá, takže opakovaný import nesmí potichu
    přepsat doklad. Původní revize zůstávají ve vstupním archivu.
    """
    records = {}
    for reading in readings:
        if reading.id in records and records[reading.id] != reading:
            raise DataError("reading_id_conflict")
        records[reading.id] = reading
    replaced = set()
    for reading in records.values():
        if not reading.supersedes:
            continue
        previous = records.get(reading.supersedes)
        if (
            previous is None
            or reading.id == previous.id
            or previous.id in replaced
            or (previous.place, previous.segment, previous.source)
            != (reading.place, reading.segment, reading.source)
            or (reading.source == "mnd" and not reading.evidence)
        ):
            raise DataError("invalid_reading_revision")
        seen = {reading.id}
        item = previous
        while item:
            if item.id in seen:
                raise DataError("reading_revision_cycle")
            seen.add(item.id)
            item = records.get(item.supersedes)
        replaced.add(previous.id)
    return [r for r in records.values() if r.id not in replaced]


def meter_points(readings: list[Reading], place: str) -> list[dict]:
    """Sdružuje datum/okamžik a segment; MND je autorita shodné hranice.

    Neznámý čas se nesrovnává s konkrétní hodinou. Den s více hodnotami MND
    zůstává konfliktní; fakturační status nerozhoduje o přesnosti měření.
    """
    groups = defaultdict(list)
    for reading in active_readings(readings):
        if reading.place == place:
            boundary = reading.observed_at.isoformat() if reading.observed_at else "day"
            groups[(reading.segment, reading.date, boundary)].append(reading)
    result = []
    for (segment, when, boundary), sources in sorted(groups.items()):
        preferred = [r for r in sources if r.source == "mnd"] or sources
        values = {r.value for r in preferred}
        result.append(
            {
                "segment": segment,
                "date": when,
                "boundary": boundary,
                "value": next(iter(values)) if len(values) == 1 else None,
                "source": preferred[0].source,
                "conflict": len(values) != 1,
                "estimated": any(r.estimated for r in preferred),
                "time_uncertain": boundary == "day",
                "sources": [r.id for r in sources],
            }
        )
    return result


def consumption_intervals(readings: list[Reading], place: str) -> list[dict]:
    """Přírůstky mezi body: konflikt/reset přeruší řadu, první hodnota není odběr."""
    previous: dict[str, dict | None] = {}
    output = []
    for point in meter_points(readings, place):
        older = previous.get(point["segment"])
        amount, reason = None, "missing_start"
        if point["conflict"]:
            reason = "reading_conflict"
        elif older and not older["conflict"]:
            # Den a přesný bod téhož dne nemají doložené pořadí.
            if older["date"] == point["date"] and (
                older["time_uncertain"] or point["time_uncertain"]
            ):
                reason = "boundary_time_unknown"
            elif point["value"] < older["value"]:
                reason = "meter_decrease"
            else:
                amount = point["value"] - older["value"]
                reason = (
                    "estimated"
                    if point["estimated"] or older["estimated"]
                    else "reading_difference"
                )
        output.append(
            {
                **point,
                "from": older["date"] if older else None,
                "from_at": older["boundary"] if older and not older["time_uncertain"] else None,
                "observed_at": point["boundary"] if not point["time_uncertain"] else None,
                "interval_time_uncertain": point["time_uncertain"]
                or (older["time_uncertain"] if older else True),
                "estimated": point["estimated"] or (older["estimated"] if older else False),
                "consumption_m3": amount,
                "reason": reason,
            }
        )
        previous[point["segment"]] = None if point["conflict"] else point
    return output


def validate_samples(samples: list[dict], *, entity: str, segment: str) -> list[dict]:
    """Kumulativní m³ se řadí podle času příjmu; reset či nedostupnost nejsou nula.

    Události téhož okamžiku s odlišným obsahem jsou konflikt. Příznak continuity
    zaznamenává doložené přerušení zdroje; samotné last_changed není watchdog.
    """
    parsed = {}
    for sample in samples:
        if sample.get("entity") != entity or sample.get("segment") != segment:
            raise DataError("sample_identity_mismatch")
        value = decimal(sample.get("value"), optional=True, nonnegative=True)
        if value is not None and (
            sample.get("unit") not in ("m³", "m3")
            or sample.get("state_class")
            not in (
                "total",
                "total_increasing",
            )
        ):
            raise DataError("incompatible_sensor")
        at = instant(sample["at"])
        # Při restartu může HA dodat unavailable bez atributů. Není to
        # číselný report s jinou jednotkou: zůstane zaznamenanou mezerou.
        item = {**sample, "at": at, "value": value}
        if at in parsed and parsed[at] != item:
            raise DataError("sample_conflict")
        parsed[at] = item
    return sorted(parsed.values(), key=lambda s: s["at"])


def current_state(
    readings: list[Reading],
    samples: list[dict],
    calibration: dict | None,
    *,
    place: str,
    segment: str,
    zone: str,
    source_mode: str | None = None,
) -> dict:
    """Naváže novější lokální měření na poslední MND kotvu bez dvojí spotřeby.

    Přesná senzorová rebaze vyžaduje vzorek shodného okamžiku. Denní kotva
    zůstane stavem k datu s nejistotou, pokud návaznost nelze doložit. Každý
    pokles nebo nedostupný bod od kotvy zneplatní odvozený současný stav.
    """
    source_mode = source_mode or ("sensor" if samples or calibration else "manual")
    active = [r for r in active_readings(readings) if r.place == place and r.segment == segment]
    mnd = sorted(
        [r for r in active if r.source == "mnd"],
        key=lambda r: (r.date, r.observed_at.isoformat() if r.observed_at else ""),
    )
    anchor = mnd[-1] if mnd else None
    if (
        anchor
        and len(
            {r.value for r in mnd if r.date == anchor.date and r.observed_at == anchor.observed_at}
        )
        > 1
    ):
        return {"value": None, "reason": "reading_conflict"}
    manual = sorted(
        [r for r in active if r.source == "manual"],
        key=lambda r: (r.date, r.observed_at.isoformat() if r.observed_at else ""),
    )
    newer_manual = manual and (
        not anchor
        or manual[-1].date > anchor.date
        or (
            manual[-1].date == anchor.date
            and anchor.observed_at is not None
            and manual[-1].observed_at is not None
            and manual[-1].observed_at > anchor.observed_at
        )
    )
    if source_mode == "manual" and newer_manual:
        latest = manual[-1]
        if anchor and latest.value < anchor.value:
            return {"value": None, "reason": "meter_decrease"}
        return {
            "value": latest.value,
            "at": latest.observed_at or latest.date,
            "source": "manual",
            "reason": "state_at_date",
        }
    base = None
    if calibration and source_mode == "sensor":
        if (calibration.get("place"), calibration.get("segment")) != (place, segment):
            raise DataError("calibration_identity_mismatch")
        at = instant(calibration["at"])
        base = {
            "at": at,
            "value": decimal(calibration["physical"], nonnegative=True),
            "sensor": decimal(calibration["sensor"], nonnegative=True),
        }
    entity = (
        calibration.get("entity")
        if calibration and source_mode == "sensor"
        else (samples[-1].get("entity") if samples else "")
    )
    # Nová souběžná kalibrace smí začít za doloženým resetem či změnou
    # jednotky. Starší nekompatibilní vzorky zůstanou v auditu, ale nesmějí
    # zneplatnit nově založený úsek. MND má přednost na shodné/starší kotvě.
    thresholds = [base["at"]] if base else []
    if anchor and anchor.observed_at:
        thresholds.append(anchor.observed_at)
    threshold = max(thresholds) if thresholds else None
    ordered = validate_samples(
        [s for s in samples if threshold is None or instant(s["at"]) >= threshold],
        entity=entity,
        segment=segment,
    )
    if anchor:
        paired = next(
            (
                s
                for s in ordered
                if anchor.observed_at and s["at"] == anchor.observed_at and s["value"] is not None
            ),
            None,
        )
        if paired and (not base or base["at"] <= anchor.observed_at):
            base = {"at": anchor.observed_at, "value": anchor.value, "sensor": paired["value"]}
        elif not base or (
            base["at"] <= anchor.observed_at
            if anchor.observed_at
            else local_day(base["at"], zone) <= anchor.date
        ):
            return {
                "value": anchor.value,
                "at": anchor.observed_at or anchor.date,
                "source": "mnd",
                "reason": "anchor_time_unpaired",
            }
    if not base:
        return {"value": None, "reason": "calibration_required"}
    tail = [s for s in ordered if s["at"] >= base["at"]]
    last = base["sensor"]
    for sample in tail:
        if sample["value"] is None or sample.get("continuity") is False:
            return {"value": None, "reason": "sensor_gap"}
        if sample["value"] < last:
            return {"value": None, "reason": "sensor_reset"}
        last = sample["value"]
    if not tail:
        return {
            "value": base["value"],
            "at": base["at"],
            "source": "calibration",
            "reason": "no_new_measurement",
        }
    return {
        "value": base["value"] + last - base["sensor"],
        "at": tail[-1]["at"],
        "source": "mnd+sensor" if anchor else "calibration+sensor",
        "reason": "derived_state",
    }


def document_reading(row: dict[str, Any], artifact: str) -> Reading:
    """Mapování C# v1; sémantický klíč zachová status a zamezí opakované spotřebě."""
    fields = {
        "place": row["SupplyPointId"],
        "meter": row["MeterNumber"],
        "date": row["Date"],
        "value": row["MeterStateM3"],
        "source": "mnd",
        "method": row["Method"],
        "status": row["Status"],
    }
    return Reading.parse(
        {
            **fields,
            "id": fingerprint(fields),
            "evidence": artifact,
            "estimated": "odhad" in row["Method"].lower(),
        }
    )
