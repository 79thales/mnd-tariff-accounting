"""Průtok a srovnání kotvy; žádné přepisování fyzického zdrojového senzoru."""

from decimal import Decimal

from .common import DataError, decimal, instant, wire
from .metering import Reading, active_readings, current_state

FLOW_UNITS = {
    "m³/h": Decimal(1),
    "m3/h": Decimal(1),
    "L/min": Decimal("0.06"),
    "l/min": Decimal("0.06"),
    "L/h": Decimal("0.001"),
    "l/h": Decimal("0.001"),
    "m³/s": Decimal(3600),
    "m3/s": Decimal(3600),
}


def flow_value(value, unit, reported_at, now, max_age=900):
    """Přesný převod na m³/h; mezera ani starý report není nulový průtok.

    max_age je explicitní počet sekund nakonfigurovaný podle reportování
    zařízení. Senzor hlásící jen změny vyžaduje odpovídající nastavení;
    z času last_changed nelze odvozovat pravidelnou dostupnost.
    """
    result = {"current_flow_m3h": None, "flow_at": reported_at, "flow_status": "unavailable"}
    if value in (None, "unknown", "unavailable"):
        return result
    if unit not in FLOW_UNITS:
        return {**result, "flow_status": "incompatible_unit"}
    try:
        age = (instant(now) - instant(reported_at)).total_seconds()
        amount = decimal(value, nonnegative=True) * FLOW_UNITS[unit]
    except (DataError, TypeError):
        return result
    if age < 0 or age > max_age:
        return {**result, "flow_status": "stale"}
    return wire({**result, "current_flow_m3h": amount, "flow_status": "current"})


def anchor_comparisons(place_id, place, zone):
    """Porovná dřívější lokální kotvu s novým MND bodem před jeho rebasingem.

    Datum bez okamžiku nedokládá souběžný senzorový vzorek. Takový řádek
    má důvod time_unpaired a nevytváří zavádějící číselnou odchylku.
    Vše je odvozené z neměnného archivu, takže opravy zůstávají dohledatelné.
    """
    rows = active_readings([Reading.parse(r) for r in place["readings"]])
    calibration = place["settings"].get("calibration")
    result = []
    for target in sorted(
        (r for r in rows if r.source == "mnd" and not r.estimated), key=lambda r: r.date
    ):
        output = {
            "date": target.date,
            "actual": target.value,
            "expected": None,
            "difference": None,
            "percentage": None,
            "reason": "time_unpaired",
        }
        if target.observed_at and calibration and instant(calibration["at"]) < target.observed_at:
            before = [
                r
                for r in rows
                if r.id != target.id
                and r.segment == target.segment
                and r.observed_at
                and r.observed_at < target.observed_at
            ]
            samples = [
                s
                for s in place["samples"]
                if s.get("segment") == target.segment
                and s.get("entity") == calibration.get("entity")
                and instant(s["at"]) <= target.observed_at
            ]
            try:
                state = current_state(
                    before,
                    samples,
                    calibration,
                    place=place_id,
                    segment=target.segment,
                    zone=zone,
                    source_mode="sensor",
                )
                if state.get("at") == target.observed_at and state.get("value") is not None:
                    expected = state["value"]
                    output.update(
                        expected=expected,
                        difference=target.value - expected,
                        percentage=(target.value - expected) / expected * 100 if expected else None,
                        reason="paired",
                    )
            except DataError as err:
                output["reason"] = str(err)
        result.append(wire(output))
    return result
