"""Čtecí elektrické metriky kotle; nikdy nevstupují do účetnictví plynu.

W/kW a Wh/kWh jsou přesné převody jednotek. Příkon nedokládá hoření ani
spotřebu plynu. Neznámý, starý, záporný či nekompatibilní údaj není nula.
Denní profil níže slouží pouze k zobrazení již získaných měření HA.
"""

from datetime import timedelta
from decimal import Decimal

from .common import DataError, decimal, instant, local_day, wire

POWER_UNITS = {"W": Decimal(1), "kW": Decimal(1000)}
ENERGY_UNITS = {"Wh": Decimal("0.001"), "kWh": Decimal(1)}
BOILER_FIELDS = (
    "boiler_enabled",
    "boiler_power_entity",
    "boiler_power_registry_id",
    "boiler_energy_entity",
    "boiler_energy_registry_id",
    "boiler_demand_entity",
    "boiler_demand_registry_id",
    "boiler_max_age",
)


def electrical_value(value, unit, at, now, *, energy=False, max_age=900):
    """Vrátí W nebo kWh a kvalitu podle času posledního reportu v UTC.

    last_changed nepoužíváme: stejná hodnota může být pravidelně reportována.
    Kumulativní kWh jsou stav čítače, nikoli dnešní spotřeba. Mez platnosti
    nastavuje správce podle skutečné četnosti reportů daného zařízení.
    """
    result = {"value": None, "quality": "unavailable", "reported_at": at}
    if value in (None, "unknown", "unavailable"):
        return result
    units = ENERGY_UNITS if energy else POWER_UNITS
    if unit not in units:
        return {**result, "quality": "incompatible_unit"}
    try:
        amount = decimal(value, nonnegative=True) * units[unit]
        age = (instant(now) - instant(at)).total_seconds()
    except (DataError, TypeError):
        return result
    if age < 0 or age > max_age:
        return {**result, "quality": "stale"}
    return wire({**result, "value": amount, "quality": "current"})


def demand_value(state, attributes=None):
    """Požadavek termostatu, nikoli důkaz plamene; neznámý stav vrací None."""
    if state in (None, "unknown", "unavailable"):
        return None
    action = (attributes or {}).get("hvac_action")
    if action == "heating":
        return True
    if action in ("idle", "off") or state in ("off", "idle"):
        return False
    return True if state == "on" else None


def consumption_summary(place, now, zone):
    """Dnes/měsíc a sedm denních sloupců z jediného vybraného profilu m³.

    Filtr zdroje, segmentu a pulsního koeficientu je shodný s měsíčním grafem.
    Dnešek zůstává neúplný. Údaj data_do je pouze konec přijatého hodinového
    pokrytí, nikoli čas otevření UI. Chybějící dny jsou None; časový horizont
    měsíce nekončí automaticky dodavatelským odečtem.
    """
    from .billing import selected_profile

    today = local_day(now, zone)
    profile = selected_profile(place)

    def period(left, right):
        rows = [profile[d] for d in sorted(profile) if left <= d < right]
        values = [
            decimal(
                r.get("m3") if r.get("complete") else r.get("known_m3"),
                optional=True,
                nonnegative=True,
            )
            for r in rows
        ]
        known = [v for v in values if v is not None]
        # Přesná hranice nových profilů; staré archivy ji nemají, čas nevymýšlíme.
        through = max(
            (
                r["observed_to"]
                for r, value in zip(rows, values, strict=True)
                if value is not None and r.get("observed_to")
            ),
            key=instant,
            default=None,
        )
        return {
            "value_m3": sum(known, Decimal(0)) if known else None,
            "from": left,
            "to": right,
            "observed_to": through,
            "complete": right <= today
            and len(known) == (right - left).days
            and all(r.get("complete") for r in rows),
            "measured_days": len(known),
        }

    days = []
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        days.append({"date": date, **period(date, date + timedelta(days=1))})
    return wire(
        {
            "today": period(today, today + timedelta(days=1)),
            "month": period(today.replace(day=1), today + timedelta(days=1)),
            "days": days,
            "time_zone": zone,
        }
    )


def energy_period(rows, start, end, now, factor):
    """Součet doložených uzavřených hodin v [start,end), výstup v kWh.

    Vstupy jsou hodinové Recorder statistiky v UTC s předchozí hodinou pro
    kontrolu návaznosti. Nesouhlas sum/change, reset state, mezera, záporná
    nebo neznámá hodnota se nepřičtou. Reset se neodhaduje z příkonu. Výstup
    může obsahovat známou část, vždy s jejím pokrytím a časem poslední hodiny.
    """
    left, right, current = instant(start), instant(end), instant(now)
    indexed = {}
    for row in rows:
        stamp = row.get("start")
        if not isinstance(stamp, (int, float)) or stamp % 3600:
            raise DataError("invalid_statistic_time")
        if stamp in indexed and indexed[stamp] != row:
            raise DataError("statistic_conflict")
        indexed[stamp] = row
    values, accepted = [], []
    for stamp, row in sorted(indexed.items()):
        if (
            not left.timestamp() <= stamp < right.timestamp()
            or stamp + 3600 > min(right, current).timestamp()
        ):
            continue
        previous = indexed.get(stamp - 3600)
        try:
            change = decimal(str(row["change"]), nonnegative=True)
            state = decimal(str(row["state"]), nonnegative=True)
            total = decimal(str(row["sum"]))
            old_state = decimal(str(previous["state"]), nonnegative=True)
            old_sum = decimal(str(previous["sum"]))
        except (DataError, KeyError, TypeError):
            continue
        if (
            state < old_state
            or abs(total - old_sum - change) > Decimal("0.000001")
            or abs(state - old_state - change) > Decimal("0.000001")
        ):
            continue
        values.append(change * factor)
        accepted.append(stamp)
    # U pásem s posunem o půl/čtvrt hodiny nelze hodinovým agregátem doložit
    # necelou hraniční hodinu. Součet zahrne jen plně obsažené UTC hodiny.
    first_hour = ((int(left.timestamp()) + 3599) // 3600) * 3600
    last_hour = (int(min(right, current).timestamp()) // 3600) * 3600
    expected = max(0, (last_hour - first_hour) // 3600)
    through = max(accepted) + 3600 if accepted else None
    return wire(
        {
            "value_kwh": sum(values, Decimal(0)) if values else None,
            "known_hours": len(accepted),
            "expected_closed_hours": max(0, expected),
            "complete": right <= current
            and left.timestamp() % 3600 == 0
            and right.timestamp() % 3600 == 0
            and len(accepted) == expected,
            "observed_to": through,
            "from": start,
            "to": end,
        }
    )
