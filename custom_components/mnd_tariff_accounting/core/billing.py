"""Čtecí přehled skutečného účetního období MND bez ručního přepisu plateb.

Předpis, úhrada, původní faktura a prognóza jsou různé zdroje. Tento výpočet
nemění místní účetní knihu. Používá Decimal pro Kč a uchovává neznámé hodnoty;
grafům vrací doložené body a výslovně označené spojnice budoucího výhledu.
"""

import calendar
from datetime import timedelta
from decimal import Decimal

from .common import DataError, day, decimal, instant, local_day, money, wire


def select_period(place, today):
    """Volí aktuální období dodavatele, nikoli kalendářní rok počítače.

    Při souběhu dvou různých aktuálních intervalů se nesmí libovolně vybrat
    jeden. Nastavené místní období je záloha pouze pro importní režim bez MND.
    Původní From/To z portálu se zachovají i pro porovnání prognóz.
    """
    snapshots = sorted(place.get("snapshots", []), key=lambda s: instant(s["retrieved_at"]))
    for snapshot in reversed(snapshots):
        rows = [r for r in snapshot["periods"] if day(r["From"]) <= today < day(r["To"])]
        if len(rows) > 1:
            raise DataError("billing_period_ambiguous")
        if rows:
            return {**rows[0], "source": "mnd", "snapshot_at": snapshot["retrieved_at"]}
    settings = place["settings"]
    if settings.get("period_from") and settings.get("period_to"):
        return {
            "From": settings["period_from"],
            "To": settings["period_to"],
            "source": "configured",
        }
    return None


def finance_for_period(place, start, end, today):
    """Sečte doklady splatné ve vybraném období a jejich skutečné PayInfo.

    Úhrada může mít jiné datum než předpis. Její průběh je schodový podle
    skutečného dne přijetí; budoucí platba se neúčtuje. Doklad patří období
    podle splatnosti MND, částka se nedělí poměrem dnů. Místní kopie týchž
    událostí se nepřičítá podruhé a nevyžaduje se její ruční potvrzení pro čtení.
    """
    evidence = place.get("portal_evidence", {}).get("advances")
    if evidence is None:
        return {
            "paid_czk": None,
            "planned_czk": None,
            "payments_complete": False,
            "plan_complete": False,
            "payments": [],
            "prescriptions": [],
        }
    rows = [r for r in evidence["rows"] if r.get("due") and start <= day(r["due"]) < end]
    payments, prescriptions = [], []
    known = bool(evidence.get("list_complete"))
    plan_known = known
    for row in rows:
        known &= row.get("payments_known") is True and not row.get("payments_stale", False)
        plan_known &= row.get("prescribed") is not None
        if row.get("prescribed") is not None:
            prescriptions.append({"date": row["due"], "amount": decimal(row["prescribed"])})
        for payment in row.get("payments", []):
            if day(payment["date"]) <= today:
                payments.append({"date": payment["date"], "amount": decimal(payment["amount"])})
    paid = sum((p["amount"] for p in payments), Decimal(0))
    planned = sum((p["amount"] for p in prescriptions), Decimal(0))
    return {
        "paid_czk": money(paid) if known or payments else None,
        "planned_czk": money(planned) if plan_known else None,
        "payments_complete": known,
        "plan_complete": plan_known,
        "payments": payments,
        "prescriptions": prescriptions,
    }


def selected_profile(place):
    """Jediný kompatibilní profil pro hlavní souhrny i měsíční graf.

    Zdroj, měřicí segment a převod pulsů se nesmějí mezi pohledy lišit.
    Rozporné profily shodného dne se odmítnou místo výběru náhodné hodnoty.
    """
    settings = place["settings"]
    source = settings.get("history_registry_id") or settings.get("source_registry_id")
    profile = {}
    for row in place.get("daily_profile", []):
        if source and row.get("entity") != source:
            continue
        if settings.get("segment") and row.get("segment") != settings["segment"]:
            continue
        if row.get("original_unit") in ("pulse", "pulses", "imp") and decimal(
            row.get("volume_per_unit_m3"), optional=True
        ) != decimal(settings.get("history_unit_m3"), optional=True):
            # Změna faktoru nezmění již uložené přírůstky. Po novém importu
            # se obnoví ve správné jednotce; stará řada se zatím nepoužije.
            continue
        current = day(row["date"])
        if current in profile and profile[current] != row:
            raise DataError("billing_profile_conflict")
        profile[current] = row
    return profile


def monthly_measurements(place, start, end, today):
    """Měsíční sloupce z HA; neúplné hodnoty nejsou úplným odběrem MND.

    Použije jediný vybraný zdroj. Prázdný měsíc zůstává None; částečný měsíc
    respektuje skutečný účetní interval a nesčítá původní a odvozený senzor.
    """
    profile = selected_profile(place)
    current = start.replace(day=1)
    months = []
    stop = min(end, today + timedelta(days=1))
    while current < stop:
        next_month = (current.replace(day=28) + timedelta(days=4)).replace(day=1)
        left, right = max(start, current), min(end, next_month)
        required = [
            left + timedelta(days=i)
            for i in range((min(right, today + timedelta(days=1)) - left).days)
        ]
        values = []
        complete = right <= today and left == current and right == next_month
        for date in required:
            row = profile.get(date)
            complete &= row is not None and row.get("complete") is True
            amount = row.get("m3") if row and row.get("complete") else (row or {}).get("known_m3")
            if amount is not None:
                values.append(decimal(amount, nonnegative=True))
        months.append(
            {
                "month": current.isoformat()[:7],
                "from": left,
                "to": right,
                "m3": sum(values, Decimal(0)) if values else None,
                "complete": bool(complete),
                "measured_days": len(values),
                "expected_days": len(required),
                "source": "ha_statistics",
            }
        )
        current = next_month
    return months


def fixed_cost(price, start, end):
    """Kč/měsíc se dělí skutečnými kalendářními dny, bez elektrických tarifů."""
    amount = decimal(price["fixed_month"])
    return sum(
        (
            amount
            / calendar.monthrange(
                (start + timedelta(days=i)).year, (start + timedelta(days=i)).month
            )[1]
            for i in range(max(0, (end - start).days))
        ),
        Decimal(0),
    )


def _steps(rows, start, end):
    """Peněžní graf má body podle skutečných dnů, nikoli jen měsíční součty."""
    grouped = {}
    for row in rows:
        date = max(day(row["date"]), start)
        if date <= end:
            grouped[date] = grouped.get(date, Decimal(0)) + row["amount"]
    points, total = [{"date": start, "value": Decimal(0)}], Decimal(0)
    for date in sorted(grouped):
        total += grouped[date]
        points.append({"date": date, "value": money(total)})
    points.append({"date": end, "value": money(total)})
    return points


def _unbilled(start, end, invoices):
    """Vrátí nevyúčtované úseky [od, do); originální faktury nikdy nekrátí.

    Překryv originálů bez doloženého vztahu opravy je nejednoznačný.
    Nesmějí se sečíst ani potichu vybírat podle pořadí.
    """
    cursor, gaps = start, []
    for invoice in invoices:
        left, right = day(invoice["from"]), day(invoice["to"])
        if left < cursor or right <= left:
            raise DataError("billing_invoice_overlap")
        if cursor < left:
            gaps.append((cursor, min(left, end)))
        cursor = right
    if cursor < end:
        gaps.append((cursor, end))
    return [(a, b) for a, b in gaps if a < b]


def cost_evidence(place, start, end, through, energy, forecast):
    """Originál nahradí model přesně ve svém vlastním intervalu.

    Pro zbytek používáme rozdíl souhrnné energie MND a fakturovaných MWh.
    Bez energie faktury nelze bezpečně ocenit zbytek podruhé. Stálé platby
    se počítají pouze za nepokryté dny. Doklad přesahující hranici období
    se nepřiděluje poměrem dnů. Neúplný doložený součet je označen a
    nevytváří zdánlivě úplný výhled přeplatku.
    """
    invoices = sorted(
        [
            i
            for i in place.get("invoice_evidence", [])
            if i.get("verified") and start <= day(i["from"]) < day(i["to"]) <= end
        ],
        key=lambda i: day(i["from"]),
    )
    warnings = []
    if any(
        i.get("verified")
        and day(i["from"]) < end
        and start < day(i["to"])
        and not start <= day(i["from"]) < day(i["to"]) <= end
        for i in place.get("invoice_evidence", [])
    ):
        return {
            "known_cost_czk": None,
            "forecast_cost_czk": None,
            "known_cost_complete": False,
            "confirmed_invoice": False,
            "invoice_count": len(invoices),
            "warnings": ["invoice_boundary_mismatch"],
        }
    gaps = _unbilled(start, end, invoices)
    original_cost = sum((decimal(i["cost_czk"]) for i in invoices), Decimal(0))
    result = {
        "known_cost_czk": original_cost if invoices else None,
        "forecast_cost_czk": None,
        "known_cost_complete": False,
        "confirmed_invoice": False,
        "warnings": warnings,
        "invoice_count": len(invoices),
        "known_cost_estimated": False,
    }
    if invoices and not gaps:
        result.update(
            known_cost_czk=money(original_cost),
            forecast_cost_czk=money(original_cost),
            confirmed_invoice=True,
            known_cost_complete=True,
            actual_through=end,
        )
        if all(i.get("invoice_result_czk") is not None for i in invoices):
            result["invoice_result_czk"] = money(
                sum((decimal(i["invoice_result_czk"]) for i in invoices), Decimal(0))
            )
        if all(i.get("energy_mwh") is not None for i in invoices):
            result["actual_mwh"] = sum((decimal(i["energy_mwh"]) for i in invoices), Decimal(0))
            result["forecast_mwh"] = result["actual_mwh"]
        return result
    if invoices and (
        not through or any(day(i["to"]) > through or i.get("energy_mwh") is None for i in invoices)
    ):
        warnings.append("invoice_energy_boundary_missing")
        return result
    billed_energy = sum((decimal(i["energy_mwh"]) for i in invoices), Decimal(0))
    if any(value is not None and value < billed_energy for value in (energy, forecast)):
        warnings.append("invoice_energy_exceeds_period")
        return result
    price = place.get("price_evidence")
    if not price or not price.get("verified"):
        warnings.append("verified_price_missing")
        return result
    first = day(price["from"])
    last = day(price["to"]) if price.get("to") else end
    regulated_to = day(price["regulatory_to"])
    known_gaps = _unbilled(start, through, invoices) if through else []
    if (
        through
        and energy is not None
        and all(first <= a and b <= min(last, regulated_to) for a, b in known_gaps)
    ):
        result["known_cost_czk"] = money(
            original_cost
            + (energy - billed_energy) * decimal(price["variable_mwh"])
            + sum((fixed_cost(price, a, b) for a, b in known_gaps), Decimal(0))
        )
        result["known_cost_complete"] = True
        result["known_cost_estimated"] = (
            any(a.day != 1 or b.day != 1 for a, b in known_gaps)
            and decimal(price["fixed_month"]) != 0
        )
        if result["known_cost_estimated"]:
            warnings.append("fixed_calendar_proration_assumed")
    if forecast is not None and all(first <= a and b <= last for a, b in gaps):
        result["forecast_cost_czk"] = money(
            original_cost
            + (forecast - billed_energy) * decimal(price["variable_mwh"])
            + sum((fixed_cost(price, a, b) for a, b in gaps), Decimal(0))
        )
        if any(b > regulated_to for _, b in gaps):
            warnings.append("future_regulated_price_assumed")
    else:
        warnings.append("price_period_not_covered")
    return result


def billing_view(place, now, zone):
    """Vrátí souhrn i grafy stejného účetního období; nepovyšuje odhad na fakturu.

    Známá spotřeba MND má přednost pro celkový odběr; měsíční HA sloupce jsou
    kontrolní rozpis jiného zdroje. Originální faktura má ve svém rozsahu přednost před
    cenovým modelem. Pro budoucnost je celková prognóza MND oceněna doloženým
    ceníkem; bez měsíční predikce se kreslí jen orientační přerušovaná spojnice.
    """
    today = local_day(now, zone)
    period = select_period(place, today)
    if period is None:
        return {
            "status": "period_missing",
            "paid_czk": None,
            "known_cost_czk": None,
            "months": [],
            "series": {},
            "warnings": ["billing_period_missing"],
        }
    start, end = day(period["From"]), day(period["To"])
    if not 0 < (end - start).days <= 1095:
        raise DataError("billing_period_invalid")
    finance = finance_for_period(place, start, end, today)
    months = monthly_measurements(place, start, end, today)
    result = {
        "status": "partial",
        "from": start,
        "to": end,
        "source": period["source"],
        "snapshot_at": period.get("snapshot_at"),
        "today": today,
        **finance,
        "months": months,
        "known_cost_czk": None,
        "forecast_cost_czk": None,
        "forecast_balance_czk": None,
        "warnings": [],
        "confirmed_invoice": False,
    }
    warnings = result["warnings"]
    energy = decimal(period.get("ReadingsMwh"), optional=True, nonnegative=True)
    forecast = decimal(period.get("PortalTotalMwh"), optional=True, nonnegative=True)
    readings = [
        r
        for r in place.get("readings", [])
        if r.get("source") == "mnd" and start <= day(r["date"]) <= min(today, end)
    ]
    through = max((day(r["date"]) for r in readings), default=None)
    result.update(actual_mwh=energy, forecast_mwh=forecast, actual_through=through)
    costs = cost_evidence(place, start, end, through, energy, forecast)
    warnings.extend(costs.pop("warnings"))
    result.update(costs)
    if result["confirmed_invoice"]:
        result.update(status="confirmed", forecast_balance_czk=costs.get("invoice_result_czk"))
    elif costs["forecast_cost_czk"] is not None and finance["plan_complete"]:
        result["forecast_balance_czk"] = money(finance["planned_czk"] - costs["forecast_cost_czk"])
    if not finance["payments_complete"]:
        warnings.append("payments_partial")
    if any(not m["complete"] for m in months):
        warnings.append("measurement_months_partial")
    series = {
        "paid": _steps(finance["payments"], start, min(today, end))
        if finance["paid_czk"] is not None
        else [],
        "planned": _steps(finance["prescriptions"], start, end)
        if finance["planned_czk"] is not None
        else [],
        "known_cost": [],
        "forecast_cost": [],
    }
    if result["known_cost_czk"] is not None and result.get("actual_through"):
        point = {"date": result["actual_through"], "value": result["known_cost_czk"]}
        series["known_cost"] = [point]
        if result["forecast_cost_czk"] is not None:
            series["forecast_cost"] = [point, {"date": end, "value": result["forecast_cost_czk"]}]
    result["series"] = series
    result["known_volume_m3"] = (
        sum((decimal(m["m3"]) for m in months if m["m3"] is not None), Decimal(0))
        if any(m["m3"] is not None for m in months)
        else None
    )
    result["chart_forecast_interpolation"] = "illustrative_endpoints_only"
    return wire(result)
