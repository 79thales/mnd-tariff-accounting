"""Neměnné prognózy a jejich vyhodnocení proti pozdější skutečnosti."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from .common import DataError, day, decimal, fingerprint, instant, period


def add_snapshot(snapshots: list[dict], snapshot: dict) -> list[dict]:
    """Stejná data mohou sdílet otisk; všechny odlišné časy pozorování zůstávají."""
    instant(snapshot["retrieved_at"])
    item = {**snapshot, "content_hash": fingerprint(snapshot["periods"])}
    for saved in snapshots:
        if saved["retrieved_at"] == item["retrieved_at"]:
            if saved != item:
                raise DataError("snapshot_time_conflict")
            return snapshots
    # Dodatečný import starého JSON nesmí nahradit současný výhled jen tím,
    # že byl nahrán později. Rozhoduje skutečný čas pořízení snapshotu.
    return sorted([*snapshots, item], key=lambda row: instant(row["retrieved_at"]))


def compare_forecast(forecast: dict, actual: dict) -> dict:
    """Porovnává pouze stejné místo, segmenty, období, jednotky a převod.

    Celoroční predikci bez profilu nelze porovnat s nedokončeným rokem.
    Nulová skutečnost je platná; relativní odchylka je v takovém případě None.
    """
    keys = ("place", "segments", "from", "to", "unit", "conversion_id")
    if any(forecast.get(k) != actual.get(k) for k in keys):
        raise DataError("forecast_scope_mismatch")
    period(forecast["from"], forecast["to"])
    if actual.get("complete") is not True or actual.get("estimated") is True:
        raise DataError("actual_incomplete")
    prediction, reality = (
        decimal(forecast["value"], nonnegative=True),
        decimal(actual["value"], nonnegative=True),
    )
    difference = prediction - reality
    return {
        "difference": difference,
        "percentage": difference / reality * 100 if reality else None,
        "denominator": "actual",
        "snapshot_at": forecast.get("retrieved_at"),
    }


def seasonal_forecast(history: list[dict], start, end) -> dict:
    """Odhad z pokrytého ročního denního profilu; chybějící zima není nula.

    Vyžaduje 365 souvislých skutečně změřených dnů před budoucím intervalem.
    Profil podle měsíce bere skutečný počet jeho pokrytých dnů. Neodhaduje
    budoucí cenu, pouze m³; metoda a použitý profil se vrátí s výsledkem.
    """
    start, end = period(start, end)
    rows = {}
    for row in history:
        current = day(row["date"])
        if current >= start or row.get("complete") is not True or row.get("estimated") is True:
            continue
        if current in rows:
            raise DataError("forecast_duplicate_day")
        rows[current] = decimal(row["m3"], nonnegative=True)
    required = {start - timedelta(days=i) for i in range(1, 366)}
    if not required.issubset(rows):
        return {"value": None, "complete": False, "reason": "representative_year_missing"}
    months = {}
    for current in required:
        months.setdefault(current.month, []).append(rows[current])
    profile = {m: sum(values, Decimal(0)) / len(values) for m, values in months.items()}
    value = sum(
        (profile[(start + timedelta(days=i)).month] for i in range((end - start).days)), Decimal(0)
    )
    return {
        "value": value,
        "complete": True,
        "estimated": True,
        "unit": "m³",
        "method": "observed_monthly_daily_mean_v1",
        "profile_from": min(required),
        "profile_to": max(required),
        "profile_hash": fingerprint({str(k): rows[k] for k in sorted(required)}),
        "daily": [
            {
                "from": (start + timedelta(days=i)).isoformat(),
                "to": (start + timedelta(days=i + 1)).isoformat(),
                "m3": profile[(start + timedelta(days=i)).month],
                "complete": True,
                "estimated": True,
            }
            for i in range((end - start).days)
        ],
    }


def project_outcome(current_balance, future_cost, future_payments, remaining_terms):
    """Oddělí průběžné saldo od prognózy a doporučení místní zálohy v Kč.

    Neznámý vstup nevytváří nulu. Doporučení zahrnuje současný kredit/dluh
    a doložený počet zbývajících termínů; neodesílá žádnou změnu do MND.
    """
    from .common import money

    balance = decimal(current_balance, optional=True)
    cost = decimal(future_cost, optional=True, nonnegative=True)
    payments = decimal(future_payments, optional=True, nonnegative=True)
    result = money(balance + payments - cost) if None not in (balance, cost, payments) else None
    advance = (
        money(max(cost - balance, Decimal(0)) / remaining_terms)
        if balance is not None
        and cost is not None
        and isinstance(remaining_terms, int)
        and remaining_terms > 0
        else None
    )
    return {"forecast_balance_czk": result, "recommended_advance_czk": advance, "estimated": True}
