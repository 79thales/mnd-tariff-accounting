"""Kontrola hodinových statistik a sestavení pokrytého denního profilu m³.

Hodinové agregáty nejsou důkazem dostupnosti každou sekundu. Poslední stav
hodiny se nevydává za synchronní odečet její koncové sekundy. Profil slouží
pro sezonní odhad; přesné párování fyzické kotvy vyžaduje původní vzorek.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .common import DataError, decimal


def manual_profile(readings, place_id, segment, zone):
    """Sezonní profil z fyzických denních odečtů v přesných místních půlnocích.

    Řídký roční rozdíl se nerozdělí na 365 domněle změřených dnů. MND má
    při shodné hranici přednost; odhad ani smíšené časové hranice se nepřijmou.
    """
    from .common import instant, local_day
    from .metering import Reading, active_readings, consumption_intervals

    rows = active_readings([Reading.parse(row) for row in readings])
    result = []
    for row in consumption_intervals(rows, place_id):
        if (
            row["segment"] != segment
            or not row["from_at"]
            or not row["observed_at"]
            or row["estimated"]
            or row["consumption_m3"] is None
        ):
            continue
        a, b = instant(row["from_at"]), instant(row["observed_at"])
        # Portálový status sám neprokazuje fyzický odečet. Neověřený způsob
        # měření na jedné z obou hranic se nesmí stát skutečným denním profilem.
        if any(
            r.place == place_id
            and r.segment == segment
            and r.observed_at in (a, b)
            and r.source == "mnd"
            and (r.estimated or "odeč" not in r.method.lower())
            for r in rows
        ):
            continue
        first, last = local_day(a, zone), local_day(b, zone)
        if (
            last - first != timedelta(days=1)
            or a.astimezone(ZoneInfo(zone)).time() != time.min
            or b.astimezone(ZoneInfo(zone)).time() != time.min
        ):
            continue
        result.append(
            {
                "date": first.isoformat(),
                "m3": row["consumption_m3"],
                "complete": True,
                "estimated": False,
                "segment": segment,
                "source": "physical_daily_readings",
            }
        )
    return result


def daily_profile(rows: list[dict], zone: str) -> list[dict]:
    """Úplný den má všechny očekávané UTC hodiny včetně 23/25 hodin při DST.

    Neznámá hodnota, mezera, pokles state nebo nesouhlas change/state/sum
    znamená neúplný den. Nula je platná pouze s kompletními agregáty.
    """
    indexed = {}
    for raw in rows:
        start = raw.get("start")
        if not isinstance(start, (int, float)) or start % 3600:
            raise DataError("invalid_statistic_time")
        row = {"start": int(start), "end": int(start) + 3600}
        for key in ("state", "sum", "change"):
            # HA Recorder má float reprezentaci měření. Přechod přes str
            # zachová dodanou přesnost, nepoužívá binární float pro peníze.
            row[key] = decimal(str(raw[key]), optional=True) if raw.get(key) is not None else None
        if start in indexed and indexed[start] != row:
            raise DataError("statistic_conflict")
        indexed[start] = row
    grouped = defaultdict(list)
    tz = ZoneInfo(zone)
    for stamp, row in sorted(indexed.items()):
        current = datetime.fromtimestamp(stamp, timezone.utc).astimezone(tz).date()
        previous = indexed.get(stamp - 3600)
        reason = None
        if any(row[key] is None for key in ("state", "sum", "change")) or row["change"] < 0:
            reason = "statistic_unknown"
        elif previous is None or previous["state"] is None or previous["sum"] is None:
            reason = "statistic_previous_missing"
        elif row["state"] < previous["state"]:
            reason = "statistic_reset"
        elif abs((row["sum"] - previous["sum"]) - row["change"]) > Decimal("0.000001") or abs(
            (row["state"] - previous["state"]) - row["change"]
        ) > Decimal("0.000001"):
            reason = "statistic_delta_mismatch"
        grouped[current].append({**row, "reason": reason})
    result = []
    for current, items in sorted(grouped.items()):
        start = datetime.combine(current, time.min, tz).astimezone(timezone.utc)
        end = datetime.combine(current + timedelta(days=1), time.min, tz).astimezone(timezone.utc)
        expected = set(range(int(start.timestamp()), int(end.timestamp()), 3600))
        reasons = sorted({item["reason"] for item in items if item["reason"]})
        complete = {item["start"] for item in items} == expected and not reasons
        result.append(
            {
                "date": current.isoformat(),
                "m3": sum((item["change"] for item in items), Decimal(0)) if complete else None,
                # I neúplný den může mít doložené přírůstky. Uchováváme je
                # jako známou část, nikdy jako úplný den nebo nulu za mezeru.
                "known_m3": sum(
                    (item["change"] for item in items if not item["reason"]), Decimal(0)
                )
                if any(not item["reason"] for item in items)
                else None,
                "known_hours": sum(not item["reason"] for item in items),
                "complete": complete,
                "estimated": False,
                "expected_hours": len(expected),
                "received_hours": len(items),
                "reasons": reasons,
                "resolution": "hourly_aggregates",
            }
        )
    return result
