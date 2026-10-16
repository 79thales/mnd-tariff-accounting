"""Ocenění plynu a účetní kniha nezávislá na Home Assistantu.

Spotřební intervaly mají hranice [od, do), m³ a doložené pokrytí. Tarifní
přechod bez měřeného rozdělení odmítne přesnou cenu; lineární odhad je jen
výslovná volba. Faktura nahrazuje předběžný náklad téhož uzavřeného období.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction

from .common import DataError, day, decimal, money, period

ZERO = Decimal(0)
ROLES = {
    "payment",
    "prescribed",
    "assumed_paid",
    "refund",
    "credit",
    "debit",
    "transfer_in",
    "transfer_out",
}


def active_versions(records: list[dict]) -> list[dict]:
    """Neměnná ID a jednoznačné opravy; nejasné větvení ani cyklus se neúčtuje."""
    indexed = {}
    for item in records:
        key = item.get("id")
        if not isinstance(key, str) or not key:
            raise DataError("record_id_required")
        if key in indexed and indexed[key] != item:
            raise DataError("immutable_record_conflict")
        indexed[key] = item
    replaced = set()
    for item in indexed.values():
        old = item.get("supersedes")
        if not old:
            continue
        if old not in indexed or old in replaced:
            raise DataError("invalid_revision")
        cursor, visited = item, set()
        while cursor:
            if cursor["id"] in visited:
                raise DataError("revision_cycle")
            visited.add(cursor["id"])
            cursor = indexed.get(cursor.get("supersedes"))
        previous = indexed[old]
        if any(item.get(k) != previous.get(k) for k in ("place", "from", "to", "role")):
            raise DataError("revision_scope_mismatch")
        replaced.add(old)
    return [item for key, item in indexed.items() if key not in replaced]


def ledger_totals(events: list[dict], start: date, end: date, *, as_of=None) -> dict:
    """Součty pouze explicitně přiřazených událostí; předpis nikdy není úhrada.

    Vyšší/částečná úhrada je platná. Nejisté párování bez stabilního odkazu
    zůstává neúplné. Převod kreditu vyžaduje ID protistrany a směr.
    """
    totals = dict.fromkeys(ROLES, ZERO)
    warnings = []
    active = active_versions(events)
    indexed = {row["id"]: row for row in active}
    for event in active:
        role = event.get("role")
        if role not in ROLES:
            raise DataError("invalid_ledger_role")
        amount = decimal(event.get("amount"), nonnegative=True)
        if (
            as_of
            and event.get("date")
            and role not in ("prescribed", "assumed_paid")
            and day(event["date"]) > day(as_of)
        ):
            continue
        if not event.get("from") or not event.get("to"):
            warnings.append("unassigned_payment")
            continue
        left, right = period(event["from"], event["to"])
        if right <= start or left >= end:
            continue
        if left < start or right > end:
            warnings.append("payment_period_overlap")
            continue
        if role.startswith("transfer_") and not event.get("counterpart"):
            raise DataError("transfer_counterpart_required")
        if role.startswith("transfer_"):
            other = indexed.get(event["counterpart"])
            if (
                not other
                or other.get("counterpart") != event["id"]
                or other.get("role")
                != ("transfer_in" if role == "transfer_out" else "transfer_out")
                or decimal(other.get("amount"), nonnegative=True) != amount
            ):
                warnings.append("transfer_matching_required")
                continue
        if event.get("verification") == "unmatched":
            warnings.append("payment_matching_required")
            continue
        totals[role] += amount
    return {**totals, "warnings": sorted(set(warnings))}


def _span(item: dict, start: date, end: date):
    left, right = period(item["from"], item["to"])
    return max(start, left), min(end, right)


def _vat(tariff: dict) -> Decimal | None:
    if tariff.get("includes_vat") is True:
        return Decimal(1)
    if tariff.get("includes_vat") is False:
        rate = decimal(tariff.get("vat_percent"), optional=True, nonnegative=True)
        return None if rate is None else 1 + rate / 100
    return None


def _one(records: list[dict], left: date, right: date) -> dict | None:
    matched = [r for r in records if day(r["from"]) <= left and day(r["to"]) >= right]
    return matched[0] if len(matched) == 1 else None


def _validate_intervals(records: list[dict]):
    for record in records:
        period(record["from"], record["to"])


def calculate(
    *,
    start,
    end,
    segments: list[dict],
    tariffs: list[dict],
    conversions: list[dict],
    events: list[dict],
    opening_credit=None,
    payments_complete=False,
    allow_linear=False,
    invoices: list[dict] | None = None,
    zone="UTC",
    ledger_end=None,
    as_of=None,
) -> dict:
    """Vypočte známé náklady, úplnost a saldo; neznámá hodnota zůstane None.

    Segment představuje souvisle doložené m³ stejného měřidla. Při mezeře,
    překryvu nebo chybějící ceně lze vrátit známou část, ne plné saldo.
    Stálé platby se integrují samostatně po kalendářních dnech právě jednou.
    Závěrečné zaokrouhlení Kč používá pravidlo reference AwayFromZero.
    """
    from .temporal_accounting import calculate_time, has_time

    if (
        has_time(start)
        or has_time(end)
        or any(
            has_time(row.get(key))
            for row in segments + tariffs + conversions + (invoices or [])
            for key in ("from", "to")
        )
    ):
        return calculate_time(
            start=start,
            end=end,
            segments=segments,
            tariffs=tariffs,
            conversions=conversions,
            events=events,
            opening_credit=opening_credit,
            payments_complete=payments_complete,
            allow_linear=allow_linear,
            invoices=invoices,
            zone=zone,
            ledger_end=ledger_end,
            as_of=as_of,
        )
    start, end = period(start, end)
    for group in (segments, tariffs, conversions):
        _validate_intervals(group)
    tariff_versions = active_versions(tariffs) if all(t.get("id") for t in tariffs) else tariffs
    conversions = (
        active_versions(conversions) if all(c.get("id") for c in conversions) else conversions
    )
    active_tariffs = [t for t in tariff_versions if t.get("role", "current") != "alternative"]
    confirmed = [i for i in active_versions(invoices or []) if i.get("confirmed") is True]
    invoice_ranges = []
    # Poměry dnů v měsíci mají často nekonečný desetinný rozvoj. Racionální
    # mezisoučet nad přesnými Decimal vstupy zabrání tomu, aby 31 dílů stálé
    # platby změnilo směr zaokrouhlení přesné poloviny haléře. Výstup je Decimal.
    cost, energy, volume = Fraction(0), ZERO, ZERO
    any_cost, complete, energy_complete, volume_complete, estimated = False, True, True, True, False
    warnings = set()
    for invoice in confirmed:
        left, right = period(invoice["from"], invoice["to"])
        if right <= start or left >= end:
            continue
        if left < start or right > end:
            warnings.add("invoice_period_overlap")
            complete = False
            continue
        if any(a < right and b > left for a, b in invoice_ranges):
            raise DataError("overlapping_invoices")
        invoice_ranges.append((left, right))
        cost += Fraction(decimal(invoice["cost"], nonnegative=True))
        any_cost = True
    # Jednotná denní osa je zde pro kontrolu pokrytí, nikoli odhad spotřeby.
    days = [start + timedelta(days=i) for i in range((end - start).days)]
    cover = {d: 0 for d in days}
    for segment in segments:
        left, right = _span(segment, start, end)
        if left >= right:
            continue
        original_left, original_right = period(segment["from"], segment["to"])
        if left != original_left or right != original_right:
            complete = volume_complete = energy_complete = False
            warnings.add("unmeasured_period_boundary")
            continue
        amount = decimal(segment.get("m3"), optional=True, nonnegative=True)
        segment_days = [d for d in days if left <= d < right]
        if any(cover[d] for d in segment_days):
            raise DataError("overlapping_consumption")
        if amount is None or segment.get("complete") is not True:
            complete = volume_complete = energy_complete = False
            warnings.add("consumption_gap")
            continue
        for d in segment_days:
            cover[d] += 1
        volume += amount
        estimated |= bool(segment.get("estimated", False))
        boundaries = {left, right}
        for record in active_tariffs + conversions:
            for key in ("from", "to"):
                boundary = day(record[key])
                if left < boundary < right:
                    boundaries.add(boundary)
        for a, b in invoice_ranges:
            for boundary in (a, b):
                if left < boundary < right:
                    boundaries.add(boundary)
        ordered = sorted(boundaries)
        if len(ordered) > 2 and not allow_linear:
            # I při změně pouze cen může být energie při jediném převodu známá.
            conversion = _one(conversions, left, right)
            if conversion and decimal(conversion.get("kwh_per_m3"), optional=True) is not None:
                coefficient = decimal(conversion["kwh_per_m3"])
                if coefficient <= 0:
                    raise DataError("invalid_conversion")
                energy += amount * coefficient / 1000
            else:
                energy_complete = False
            complete = False
            warnings.add("measured_tariff_boundary_required")
            continue
        if len(ordered) > 2:
            estimated = True
            warnings.add("linear_allocation_estimate")
        for a, b in zip(ordered, ordered[1:]):
            part = amount * Decimal((b - a).days) / Decimal((right - left).days)
            exact_part = Fraction(amount) * Fraction((b - a).days, (right - left).days)
            conversion = _one(conversions, a, b)
            factor = decimal(conversion.get("kwh_per_m3"), optional=True) if conversion else None
            if factor is None or factor <= 0:
                energy_complete = complete = False
                warnings.add("conversion_missing_or_overlap")
                part_energy = None
            else:
                part_energy = part * factor / 1000
                energy += part_energy
                estimated |= bool(conversion.get("estimated", False))
            # Účetní část fakturovaného intervalu se nepřičítá znovu.
            if any(x <= a and y >= b for x, y in invoice_ranges):
                continue
            tariff = _one(active_tariffs, a, b)
            if tariff is None:
                complete = False
                warnings.add("tariff_missing_or_overlap")
                continue
            vat = _vat(tariff)
            rates = [
                decimal(tariff.get(k), optional=True, nonnegative=True)
                for k in ("commodity", "other")
            ]
            if vat is None or None in rates or tariff.get("all_components_known") is not True:
                complete = False
                warnings.add("price_incomplete")
            if vat is not None and part_energy is not None and any(r is not None for r in rates):
                cost += (
                    exact_part
                    * Fraction(factor)
                    / 1000
                    * sum((Fraction(r) for r in rates if r is not None), Fraction(0))
                    * Fraction(vat)
                )
                any_cost = True
    if any(n != 1 for n in cover.values()):
        volume_complete = energy_complete = complete = False
        warnings.add("consumption_gap")
    for current in days:
        if any(a <= current < b for a, b in invoice_ranges):
            continue
        tariff = _one(active_tariffs, current, current + timedelta(days=1))
        if tariff is None:
            complete = False
            warnings.add("tariff_missing_or_overlap")
            continue
        fixed = decimal(tariff.get("fixed"), optional=True, nonnegative=True)
        vat = _vat(tariff)
        month_start = current.replace(day=1)
        month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        whole = (
            start <= month_start
            and end >= month_end
            and day(tariff["from"]) <= month_start
            and day(tariff["to"]) >= month_end
        )
        if fixed is None or vat is None:
            complete = False
            warnings.add("fixed_price_missing")
        elif fixed and not whole and tariff.get("prorate_fixed") is not True:
            complete = False
            warnings.add("fixed_proration_unknown")
        else:
            cost += (
                Fraction(fixed)
                / calendar.monthrange(current.year, current.month)[1]
                * Fraction(vat)
            )
            any_cost = True
    totals = ledger_totals(events, start, day(ledger_end) if ledger_end else end, as_of=as_of)
    warnings.update(totals["warnings"])
    opening = decimal(opening_credit, optional=True)
    if opening is None:
        complete = False
        warnings.add("opening_credit_missing")
    if not payments_complete or totals["warnings"]:
        complete = False
        warnings.add("payments_incomplete")
    # Potvrzená faktura sama může prokázat plný náklad i při chybějícím profilu.
    covered_by_invoices = all(any(a <= d < b for a, b in invoice_ranges) for d in days)
    financial_complete = (
        complete
        or (
            covered_by_invoices
            and opening is not None
            and payments_complete
            and not totals["warnings"]
        )
    ) and any_cost
    adjustment = (
        totals["credit"]
        + totals["transfer_in"]
        - totals["debit"]
        - totals["transfer_out"]
        - totals["refund"]
    )
    if any_cost:
        cents = abs(cost) * 100
        whole, remainder = divmod(cents.numerator, cents.denominator)
        if remainder * 2 >= cents.denominator:
            whole += 1
        rounded = money(Decimal(whole if cost >= 0 else -whole) / 100)
    else:
        rounded = None
    balance = (
        money(opening + totals["payment"] + adjustment - rounded) if financial_complete else None
    )
    return {
        "volume_m3": volume if volume_complete else None,
        "known_volume_m3": volume,
        "energy_mwh": energy if energy_complete else None,
        "known_energy_mwh": energy,
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


def invoice_settlement(invoice: dict, settlements: list[dict], invoices=()) -> dict:
    """Původní výsledek zůstává; opravený doklad převezme již provedené vypořádání.

    Platba/vratka patří i k předchozím verzím téže faktury. Podepsaný zbytek
    zahrnuje oba směry toku: stará vratka při opravě na nedoplatek dluh zvýší.
    Nejasně spárovaná úhrada ani nepárový převod nesmějí fakturu uzavřít.
    """
    result = decimal(invoice["result"])
    versions = {row["id"]: row for row in invoices}
    ancestors, cursor = {invoice["id"]}, invoice
    while cursor.get("supersedes"):
        previous = cursor["supersedes"]
        if previous in ancestors:
            raise DataError("invoice_revision_cycle")
        ancestors.add(previous)
        cursor = versions.get(previous, {})
    active = active_versions(settlements)
    indexed = {row["id"]: row for row in active}
    adjustment, complete = ZERO, True
    for event in active:
        if event.get("invoice") not in ancestors or event["role"] in ("prescribed", "assumed_paid"):
            continue
        if event.get("verification") == "unmatched":
            complete = False
            continue
        amount = decimal(event["amount"], nonnegative=True)
        role = event["role"]
        if role.startswith("transfer_"):
            other = indexed.get(event.get("counterpart"))
            if (
                not other
                or other.get("counterpart") != event["id"]
                or other.get("role")
                != ("transfer_in" if role == "transfer_out" else "transfer_out")
                or other.get("verification") == "unmatched"
                or decimal(other["amount"]) != amount
            ):
                complete = False
                continue
        adjustment += amount if role in ("payment", "credit", "transfer_in") else -amount
    signed = result + adjustment
    same_direction = result != 0 and signed * result >= 0
    return {
        "result": result,
        "remaining": abs(signed) if same_direction and complete else ZERO if complete else None,
        "over_settled": abs(signed)
        if not same_direction and complete
        else ZERO
        if complete
        else None,
        "remaining_signed": signed if complete else None,
        "remaining_kind": "surplus" if signed > 0 else "deficit" if signed < 0 else "balanced",
        "settlement_complete": complete,
        "kind": "surplus" if result > 0 else "deficit" if result < 0 else "balanced",
    }
