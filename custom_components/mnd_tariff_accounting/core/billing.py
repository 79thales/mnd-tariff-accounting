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


def forecast_payments(place, start, end, today):
    """Doložené úhrady a očekávané dosud nesplatné zálohy v Kč.

    Období je [start, end), příslušnost určuje splatnost předpisu MND.
    Skutečná úhrada se počítá ke svému datu a jen jednou; předčasná či
    vyšší úhrada sníží zbývající část pouze jejího vlastního předpisu.
    Minulý nesplacený předpis nepředstíráme jako budoucí platbu: vyžaduje
    rozhodnutí uživatele, proto výhled zůstane neúplný. Neúplný seznam,
    chybějící částky, zastaralé detaily ani neevidované kredity/vratky nelze
    považovat za nulu. Funkce nic neukládá a nemění zdrojovou evidenci.
    """
    evidence = place.get("portal_evidence", {}).get("advances")
    result = {
        "paid_czk": None,
        "remaining_czk": None,
        "expected_czk": None,
        "complete": False,
        "reason": "advances_missing",
    }
    if not evidence or evidence.get("list_complete") is not True:
        return result
    paid = Decimal(0)
    remaining = Decimal(0)
    overdue = False
    for row in evidence.get("rows", []):
        if not row.get("due"):
            return {**result, "reason": "advance_due_missing"}
        due = day(row["due"])
        if not start <= due < end:
            continue
        if (
            row.get("payments_known") is not True
            or row.get("payments_stale", False)
            or row.get("prescribed") is None
        ):
            return {**result, "reason": "advance_details_incomplete"}
        prescribed = decimal(row["prescribed"], nonnegative=True)
        row_paid = sum(
            (
                decimal(payment["amount"], nonnegative=True)
                for payment in row.get("payments", [])
                if day(payment["date"]) <= today
            ),
            Decimal(0),
        )
        paid += row_paid
        outstanding = max(prescribed - row_paid, Decimal(0))
        if due < today and outstanding:
            overdue = True
        elif due >= today:
            remaining += outstanding
    # Chybějící měsíce pokryjeme jen při doložené pravidelnosti: dva sousední
    # předpisy mají stejný den i aktuální výši zálohy MND. Takto odvozené
    # částky jsou předpokládané platby, včetně minulých měsíců; nejsou skutečně
    # uhrazené ani předpis od dodavatele. Příchod dokladu předpoklad odstraní.
    assumed = []
    deposit = place.get("portal_evidence", {}).get("deposit") or {}
    amount = decimal(deposit.get("ADV_VALUE"), optional=True, nonnegative=True)
    rows = evidence.get("rows", [])
    by_month = {}
    for row in rows:
        if row.get("due"):
            due = day(row["due"])
            by_month.setdefault((due.year, due.month), []).append(row)
    days = set()
    if amount:
        for (year, month), previous_rows in sorted(by_month.items()):
            next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
            following_rows = by_month.get((next_year, next_month), [])
            if len(previous_rows) != 1 or len(following_rows) != 1:
                continue
            before, after = previous_rows[0], following_rows[0]
            before_due, after_due = day(before["due"]), day(after["due"])
            if (before_due.day == after_due.day
                and decimal(before.get("prescribed"), optional=True) == amount
                and decimal(after.get("prescribed"), optional=True) == amount):
                days.add(before_due.day)
    if len(days) == 1:
        due_day = next(iter(days))
        month = start.replace(day=1)
        while month < end:
            if (month.year, month.month) not in by_month and due_day <= calendar.monthrange(month.year, month.month)[1]:
                assumed_due = month.replace(day=due_day)
                if start <= assumed_due < end:
                    remaining += amount
                    assumed.append({"date": assumed_due.isoformat(), "amount": money(amount)})
            month = month.replace(year=month.year + 1, month=1) if month.month == 12 else month.replace(month=month.month + 1)
    # Místní a dodavatelské převody/vratky nelze automaticky sloučit bez
    # prokázaného přiřazení; zadržet celkový výsledek místo dvojího účtování.
    ambiguous_events = any(
        row.get("role") in {"refund", "credit", "debit", "transfer_in", "transfer_out"}
        for row in place.get("events", [])
    )
    reason = "overdue_advance" if overdue else "credit_or_refund_unresolved" if ambiguous_events else None
    return {
        "paid_czk": money(paid),
        "remaining_czk": money(remaining),
        "expected_czk": money(paid + remaining) if reason is None else None,
        "complete": reason is None,
        "reason": reason,
        "assumed_advances": assumed,
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


def own_outcome_from_energy(place, start, end, through, actual_mwh, future_mwh, today):
    """Ocení předem ověřené energetické vstupy vlastního modelu v MWh a Kč.

    Funkce nestanovuje metodu ani pokrytí měření: volající smí dodat MWh až
    po ověření totožnosti měřidla, návaznosti na MND, převodu a oddělení
    minulého a budoucího úseku. Chybějící hodnota zůstává None. Doložené
    originální faktury mají přednost díky společnému cost_evidence; jejich
    nesoulad s hranicí zastaví odhad místo dvojího přičtení. Používá se
    pouze existující platný cenový doklad, budoucí regulovaná sazba má
    stávající varování. Neúplné platby nikdy nevytvoří výsledný přeplatek.
    """
    actual = decimal(actual_mwh, optional=True, nonnegative=True)
    future = decimal(future_mwh, optional=True, nonnegative=True)
    total = actual + future if actual is not None and future is not None else None
    costs = cost_evidence(place, start, end, through, actual, total)
    payments = forecast_payments(place, start, end, today)
    result = {
        "actual_mwh": actual,
        "future_mwh": future,
        "total_mwh": total,
        "known_cost_czk": costs.get("known_cost_czk"),
        "forecast_cost_czk": costs.get("forecast_cost_czk"),
        "paid_czk": payments["paid_czk"],
        "remaining_payments_czk": payments["remaining_czk"],
        "expected_payments_czk": payments["expected_czk"],
        "balance_czk": None,
        "confirmed_invoice": costs.get("confirmed_invoice", False),
        "warnings": costs.get("warnings", []),
        "payment_reason": payments["reason"],
        "assumed_advances": payments.get("assumed_advances", []),
    }
    # Potvrzená faktura se zobrazí zvlášť, nikoli jako vlastní prognóza.
    if (
        not result["confirmed_invoice"]
        and result["forecast_cost_czk"] is not None
        and payments["complete"]
    ):
        result["balance_czk"] = money(
            payments["expected_czk"] - result["forecast_cost_czk"]
        )
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
