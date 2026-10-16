"""Ocenění přesných okamžiků nad stejným účetním modelem jako denní engine.

Denní doklad zůstává datem. Pro kalendářní platnost ceny se jeho hranice
interpretuje místní půlnocí, ale smíšený den/přesný čas zůstává nejistý.
Přírůstky plynu se nikdy neodvozují z délky dne bez výslovné volby odhadu.
"""

from __future__ import annotations

import calendar
from datetime import datetime, time, timedelta
from decimal import Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

from .accounting import ZERO, _vat, active_versions, ledger_totals
from .common import DataError, day, decimal, instant, money


def has_time(value):
    return isinstance(value, datetime) or (isinstance(value, str) and "T" in value)


def boundary(value, zone):
    """UTC osa respektuje místní půlnoci, DST a skutečné offsety uživatele."""
    if has_time(value):
        return instant(value)
    return instant(datetime.combine(day(value), time.min, ZoneInfo(zone)))


def _number(value):
    with localcontext() as context:
        context.prec = 160
        return Decimal(value.numerator) / value.denominator


def _money(value):
    cents = abs(value) * 100
    whole, remainder = divmod(cents.numerator, cents.denominator)
    if remainder * 2 >= cents.denominator:
        whole += 1
    return money(Decimal(whole if value >= 0 else -whole) / 100)


def _ratio(part, whole):
    """Poměr UTC délek v celočíselných mikrosekundách, bez float sekund."""
    return Fraction(part // timedelta(microseconds=1), whole // timedelta(microseconds=1))


def calculate_time(
    *,
    start,
    end,
    segments,
    tariffs,
    conversions,
    events,
    opening_credit=None,
    payments_complete=False,
    allow_linear=False,
    invoices=None,
    zone="UTC",
    ledger_end=None,
    as_of=None,
):
    """Přesné m³ mezi skutečnými časy; Kč jako racionální číslo až do haléřů.

    Časová změna sazby/koeficientu vyžaduje mezilehlý stav nebo povolený
    lineární odhad podle sekund. Měsíční paušál se dělí kalendářními dny;
    část právě probíhajícího dne je výslovný odhad, pouze při allow_linear.
    Úhrady se přiřazují celému vybranému fakturačnímu období, ne poměrem času.
    """
    left, right = boundary(start, zone), boundary(end, zone)
    if not timedelta(0) < right - left <= timedelta(days=36600):
        raise DataError("invalid_period")
    warnings = set()
    complete = volume_complete = energy_complete = True
    estimated, any_cost = False, False
    volume = energy = cost = Fraction(0)

    def span(row):
        a, b = boundary(row["from"], zone), boundary(row["to"], zone)
        if a >= b:
            raise DataError("invalid_period")
        return a, b

    def one(rows, a, b):
        found = [r for r in rows if span(r)[0] <= a and span(r)[1] >= b]
        return found[0] if len(found) == 1 else None

    tariff_rows = (
        [r for r in active_versions(tariffs) if r.get("role", "current") != "alternative"]
        if tariffs and all(r.get("id") for r in tariffs)
        else [r for r in tariffs if r.get("role", "current") != "alternative"]
    )
    conversion_rows = (
        active_versions(conversions)
        if conversions and all(r.get("id") for r in conversions)
        else conversions
    )
    for row in tariff_rows + conversion_rows:
        span(row)
    closed = []
    for invoice in active_versions(invoices or []):
        if invoice.get("confirmed") is not True:
            continue
        a, b = span(invoice)
        if b <= left or a >= right:
            continue
        if a < left or b > right:
            complete = False
            warnings.add("invoice_period_overlap")
            continue
        if any(c < b and d > a for c, d in closed):
            raise DataError("overlapping_invoices")
        closed.append((a, b))
        cost += Fraction(decimal(invoice["cost"], nonnegative=True))
        any_cost = True

    ordered = sorted(((span(row), row) for row in segments), key=lambda pair: pair[0][0])
    cursor = left
    for (a, b), row in ordered:
        first, last = max(a, left), min(b, right)
        if first >= last:
            continue
        if first < cursor:
            raise DataError("overlapping_consumption")
        if first > cursor:
            complete = volume_complete = energy_complete = False
            warnings.add("consumption_gap")
        cursor = last
        amount = decimal(row.get("m3"), optional=True, nonnegative=True)
        if amount is None or row.get("complete") is not True:
            complete = volume_complete = energy_complete = False
            warnings.add("consumption_gap")
            continue
        amount = Fraction(amount)
        if first != a or last != b:
            if not allow_linear:
                complete = volume_complete = energy_complete = False
                warnings.add("unmeasured_period_boundary")
                continue
            amount *= _ratio(last - first, b - a)
            estimated = True
        volume += amount
        estimated |= bool(row.get("estimated"))
        uncertain = bool(row.get("time_uncertain"))
        if uncertain:
            warnings.add("boundary_time_unknown")
            estimated = True
            if not allow_linear:
                complete = False
        bounds = {first, last}
        for record in tariff_rows + conversion_rows:
            bounds.update(t for t in span(record) if first < t < last)
        for c, d in closed:
            bounds.update(t for t in (c, d) if first < t < last)
        bounds = sorted(bounds)
        split = len(bounds) > 2
        if split and not allow_linear:
            complete = False
            warnings.add("unmeasured_tariff_boundary")
            factor = one(conversion_rows, first, last)
            if factor:
                energy += amount * Fraction(decimal(factor["kwh_per_m3"], nonnegative=True)) / 1000
            else:
                energy_complete = False
            continue
        estimated |= split
        for c, d in zip(bounds, bounds[1:]):
            part = amount * _ratio(d - c, last - first)
            factor, tariff = one(conversion_rows, c, d), one(tariff_rows, c, d)
            if not factor or decimal(factor.get("kwh_per_m3"), optional=True, nonnegative=True) in (
                None,
                ZERO,
            ):
                complete = energy_complete = False
                warnings.add("conversion_missing_or_overlap")
                continue
            energy_part = part * Fraction(decimal(factor["kwh_per_m3"])) / 1000
            energy += energy_part
            estimated |= bool(factor.get("estimated"))
            if any(x <= c and y >= d for x, y in closed):
                continue
            if not tariff or tariff.get("all_components_known") is not True:
                complete = False
                warnings.add("tariff_missing_or_incomplete")
                continue
            commodity, other, vat = (
                decimal(tariff.get("commodity"), optional=True),
                decimal(tariff.get("other"), optional=True),
                _vat(tariff),
            )
            if (
                commodity is None
                or other is None
                or vat is None
                or (uncertain and not allow_linear)
            ):
                complete = False
                warnings.add("variable_price_missing_or_uncertain")
                continue
            cost += energy_part * (Fraction(commodity) + Fraction(other)) * Fraction(vat)
            any_cost = True
    if cursor < right:
        complete = volume_complete = energy_complete = False
        warnings.add("consumption_gap")

    # Paušál je nezávislý na plynových intervalech. Za každý místní den
    # projdeme jeho skutečnou délku (23/24/25 h), nikdy jej neúčtujeme dvakrát.
    current = left.astimezone(ZoneInfo(zone)).date()
    while boundary(current, zone) < right:
        following = current + timedelta(days=1)
        a, b = max(left, boundary(current, zone)), min(right, boundary(following, zone))
        cuts = {a, b}
        for record in tariff_rows:
            cuts.update(t for t in span(record) if a < t < b)
        for c, d in closed:
            cuts.update(t for t in (c, d) if a < t < b)
        cuts = sorted(cuts)
        for c, d in zip(cuts, cuts[1:]):
            if any(x <= c and y >= d for x, y in closed):
                continue
            tariff = one(tariff_rows, c, d)
            fixed = (
                decimal(tariff.get("fixed"), optional=True, nonnegative=True) if tariff else None
            )
            vat = _vat(tariff) if tariff else None
            month_start = current.replace(day=1)
            month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
            whole = (
                left <= boundary(month_start, zone)
                and right >= boundary(month_end, zone)
                and tariff
                and span(tariff)[0] <= boundary(month_start, zone)
                and span(tariff)[1] >= boundary(month_end, zone)
            )
            if fixed is None or vat is None:
                complete = False
                warnings.add("fixed_price_missing")
                continue
            if fixed and not whole and tariff.get("prorate_fixed") is not True:
                complete = False
                warnings.add("fixed_proration_unknown")
                continue
            fraction = _ratio(d - c, boundary(following, zone) - boundary(current, zone))
            if fixed and fraction != 1:
                if not allow_linear:
                    complete = False
                    warnings.add("fixed_intraday_proration_unknown")
                    continue
                estimated = True
                warnings.add("fixed_intraday_proration_estimated")
            cost += (
                Fraction(fixed)
                * fraction
                / calendar.monthrange(current.year, current.month)[1]
                * Fraction(vat)
            )
            any_cost = True
        current = following
    ledger_start = left.astimezone(ZoneInfo(zone)).date()
    ledger_last = day(ledger_end) if ledger_end else right.astimezone(ZoneInfo(zone)).date()
    if ledger_last <= ledger_start:
        ledger_last = ledger_start + timedelta(days=1)
    totals = ledger_totals(events, ledger_start, ledger_last, as_of=as_of)
    warnings.update(totals["warnings"])
    opening = decimal(opening_credit, optional=True)
    if opening is None:
        complete = False
        warnings.add("opening_credit_missing")
    if not payments_complete or totals["warnings"]:
        complete = False
        warnings.add("payments_incomplete")
    cursor = left
    for a, b in sorted(closed):
        if a > cursor:
            break
        cursor = max(cursor, b)
    financial_complete = any_cost and (
        complete
        or (
            cursor >= right and opening is not None and payments_complete and not totals["warnings"]
        )
    )
    rounded = _money(cost) if any_cost else None
    balance = (
        money(
            opening
            + totals["payment"]
            + totals["credit"]
            + totals["transfer_in"]
            - totals["debit"]
            - totals["transfer_out"]
            - totals["refund"]
            - rounded
        )
        if financial_complete
        else None
    )
    return {
        "volume_m3": _number(volume) if volume_complete else None,
        "known_volume_m3": _number(volume),
        "energy_mwh": _number(energy) if energy_complete else None,
        "known_energy_mwh": _number(energy),
        "known_cost_czk": rounded,
        "paid_czk": money(totals["payment"]),
        "prescribed_czk": money(totals["prescribed"]),
        "assumed_paid_czk": money(totals["assumed_paid"]),
        "balance_czk": balance,
        "surplus_czk": max(balance, ZERO) if balance is not None else None,
        "deficit_czk": max(-balance, ZERO) if balance is not None else None,
        "complete": financial_complete,
        "estimated": estimated,
        "warnings": sorted(warnings),
    }
