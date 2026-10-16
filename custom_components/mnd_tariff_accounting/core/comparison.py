"""Srovnání prognózy s dokončeným měřením a doloženým převodem na MWh.

Neznámé, odhadnuté či nesouhlasné časové hranice nejsou měřená skutečnost.
Výsledkem je odchylka a původ podkladů, nikdy změna uloženého snapshotu.
"""

from .accounting import active_versions, calculate
from .common import DataError, fingerprint, instant, local_day
from .forecast import compare_forecast
from .metering import Reading, consumption_intervals, current_state
from .temporal_accounting import boundary


def compare_measurement(place_id, place, snapshot, prediction, zone, now):
    """Volající správce výslovně potvrdí shodnou energetickou bázi a hranice."""
    left, right = prediction["From"], prediction["To"]
    end = boundary(right, zone)
    if end > instant(now) or instant(snapshot["retrieved_at"]) >= end:
        raise DataError("actual_period_not_finished_after_snapshot")
    settings = place["settings"]
    segment = settings.get("segment")
    if not segment:
        raise DataError("measurement_segment_required")
    readings = [Reading.parse(row) for row in place["readings"]]
    readings = [
        r
        for r in readings
        if r.segment == segment and boundary(r.observed_at or r.date, zone) <= end
    ]
    if settings.get("source_mode") == "sensor":
        samples = [
            s
            for s in place["samples"]
            if s.get("entity") == settings.get("source_registry_id")
            and s.get("segment") == segment
            and instant(s["at"]) <= end
        ]
        calibration = settings.get("calibration")
        if calibration and instant(calibration["at"]) > end:
            calibration = None
        state = current_state(
            readings,
            samples,
            calibration,
            place=place_id,
            segment=segment,
            zone=zone,
            source_mode="sensor",
        )
        if state.get("reason") == "derived_state" and instant(state["at"]) == end:
            readings.append(
                Reading.parse(
                    {
                        "id": "comparison:sensor",
                        "place": place_id,
                        "meter": segment,
                        "segment": segment,
                        "date": local_day(end, zone),
                        "observed_at": end,
                        "value": state["value"],
                        "source": "sensor",
                    }
                )
            )
    chunks, used = [], set()
    for row in consumption_intervals(readings, place_id):
        if not row["from"]:
            continue
        a, b = row["from_at"] or row["from"], row["observed_at"] or row["date"]
        if (
            boundary(a, zone) >= boundary(b, zone)
            or boundary(b, zone) <= boundary(left, zone)
            or boundary(a, zone) >= end
        ):
            continue
        used.update(row["sources"])
        used.update(r.id for r in readings if r.date == row["from"])
        chunks.append(
            {
                "from": a,
                "to": b,
                "m3": row["consumption_m3"],
                "complete": row["consumption_m3"] is not None,
                "estimated": row["estimated"],
                "time_uncertain": bool(row["from_at"]) != bool(row["observed_at"]),
            }
        )
    if any(
        r.id in used and r.source == "mnd" and (r.estimated or "odeč" not in r.method.lower())
        for r in readings
    ):
        raise DataError("actual_reading_quality_unverified")
    factors = [
        r
        for r in active_versions(place["conversions"])
        if boundary(r["from"], zone) < end and boundary(r["to"], zone) > boundary(left, zone)
    ]
    if not factors or any(not r.get("evidence") or r.get("estimated") for r in factors):
        raise DataError("actual_conversion_evidence_required")
    actual = calculate(
        start=left,
        end=right,
        segments=chunks,
        tariffs=[],
        # Kalkulátor ověřuje řetězec oprav sám; potřebuje i nahrazené verze.
        # Důkaz fyzického převodu výše požadujeme jen od aktivních intervalů.
        conversions=place["conversions"],
        events=[],
        opening_credit="0",
        payments_complete=True,
        zone=zone,
    )
    if (
        actual["energy_mwh"] is None
        or actual["estimated"]
        or any(row["time_uncertain"] for row in chunks)
    ):
        raise DataError("actual_incomplete")
    common = {
        "place": place_id,
        "segments": [segment],
        "from": left,
        "to": right,
        "unit": "MWh",
        "conversion_id": "user_confirmed_compatible_energy_basis",
    }
    result = compare_forecast(
        {**common, "value": prediction["PortalTotalMwh"], "retrieved_at": snapshot["retrieved_at"]},
        {**common, "value": actual["energy_mwh"], "complete": True},
    )
    return {
        **result,
        "actual_mwh": actual["energy_mwh"],
        "actual_source": "documented_measurements",
        "conversion_hash": fingerprint(factors),
        "source_ids": sorted(used),
    }
