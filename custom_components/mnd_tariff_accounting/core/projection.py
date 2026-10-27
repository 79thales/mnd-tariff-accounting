"""Projekce neměnného účetního archivu do aktuálních výsledků panelu.

Běží bez HA a sítě, v adaptéru se volá v executoru. Neúplné náklady se
nepovyšují na úplné saldo a budoucí smluvní konec není dnešní měření.
"""

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from .accounting import active_versions, calculate, invoice_settlement
from .billing import billing_view
from .common import DataError, instant, local_day, wire
from .live import anchor_comparisons
from .metering import Reading, active_readings, consumption_intervals, current_state
from .own_billing import own_billing_view
from .temporal_accounting import boundary


def evaluate_place(place_id: str, place: dict, zone: str, now: datetime | None = None) -> dict:
    """Čistý výpočet jednoho místa nad neměnnou revizí; chybějící nastavení není nula."""
    settings = place["settings"]
    now = instant(now or datetime.now(timezone.utc))
    today = local_day(now, zone)
    archived = active_readings([Reading.parse(r) for r in place["readings"]])
    readings = [
        r for r in archived if r.date <= today and (not r.observed_at or r.observed_at <= now)
    ]
    excluded_future = len(archived) - len(readings)
    if any(r.observed_at and local_day(r.observed_at, zone) != r.date for r in readings):
        raise DataError("reading_date_time_mismatch")
    segment = settings.get("segment", "")
    relevant = [r for r in readings if not segment or r.segment == segment]
    mnd = sorted((r for r in relevant if r.source == "mnd"), key=lambda r: r.date)
    result = {
        "status": "needs_configuration",
        "latest_mnd": mnd[-1].value if mnd else None,
        "latest_mnd_date": mnd[-1].date if mnd else None,
        "reading_count": len(readings),
        "archive_revision": None,
        "cloud_status": "not_connected",
        "meter_comparisons": anchor_comparisons(place_id, place, zone),
        "forecast_comparisons": place.get("comparisons", []),
    }
    # Čtecí dokladový přehled funguje i bez ručně vyplněné místní knihy.
    # Jeho chyba nesmí vymazat odečty ani ukazovat neznámý náklad jako nulu.
    try:
        result["billing"] = billing_view(place, now, zone)
    except DataError as error:
        result["billing"] = {
            "status": "incomplete",
            "warnings": [str(error)],
            "months": [],
            "series": {},
        }
    if (
        mnd
        and len(
            {
                r.value
                for r in mnd
                if r.date == mnd[-1].date and r.observed_at == mnd[-1].observed_at
            }
        )
        > 1
    ):
        result["latest_mnd"] = None
    latest_import = next(
        (item["raw"] for item in reversed(place["imports"]) if item.get("raw")), {}
    )
    deposit = place.get("portal_evidence", {}).get("deposit")
    if isinstance(deposit, dict):
        result["current_deposit_czk"] = deposit.get("ADV_VALUE")
        result["recommended_deposit_czk"] = deposit.get("ADV_BALANCE")
        notice = deposit.get("ACTION_TEXT")
        result["mnd_assessment"] = notice.get("code") if isinstance(notice, dict) else None
        result["deposit_acquired_at"] = (
            place.get("portal_evidence", {}).get("acquired_at", {}).get("deposit")
        )
    elif isinstance(latest_import.get("Deposit"), dict):
        result["current_deposit_czk"] = latest_import["Deposit"].get("CurrentCzk")
        result["recommended_deposit_czk"] = latest_import["Deposit"].get("RecommendedCzk")
        supplier = latest_import["Deposit"]
        for source, key in (
            ("Assessment", "mnd_assessment"),
            ("PaymentStatus", "mnd_payment_status"),
        ):
            text = supplier.get(source)
            result[key] = text if isinstance(text, str) and len(text) <= 255 else None
        result["deposit_acquired_at"] = supplier.get("RetrievedAt")
    snapshots = sorted(place["snapshots"], key=lambda row: instant(row["retrieved_at"]))
    if snapshots and snapshots[-1].get("periods"):
        graph = snapshots[-1]["periods"][-1]
        result.update(
            mnd_forecast_mwh=graph.get("PortalTotalMwh"),
            mnd_readings_mwh=graph.get("ReadingsMwh"),
            mnd_past_estimate_mwh=graph.get("PastEstimateMwh"),
            mnd_future_estimate_mwh=graph.get("FutureEstimateMwh"),
            forecast_period_from=graph.get("From"),
            forecast_period_to=graph.get("To"),
        )
    invoices = active_versions(place["invoices"])
    if invoices:
        last_invoice = max(invoices, key=lambda i: i["to"])
        settlement = invoice_settlement(last_invoice, place["events"], place["invoices"])
        result.update(
            invoice_result_czk=settlement["result"], invoice_remaining_czk=settlement["remaining"]
        )
    if not segment and relevant:
        segment = max(relevant, key=lambda r: r.date).segment
    state = {"value": None, "reason": "meter_segment_missing"}
    if segment:
        samples = [
            s
            for s in place["samples"]
            if s.get("segment") == segment
            and (
                not settings.get("source_registry_id")
                or s.get("entity") == settings["source_registry_id"]
            )
        ]
        try:
            if settings.get("calibration") and instant(settings["calibration"]["at"]) > now:
                raise DataError("future_calibration")
            state = current_state(
                readings,
                [s for s in samples if instant(s["at"]) <= now]
                if settings.get("source_mode") == "sensor"
                else [],
                settings.get("calibration") if settings.get("source_mode") == "sensor" else None,
                place=place_id,
                segment=segment,
                zone=zone,
                source_mode=settings.get("source_mode", "manual"),
            )
        except DataError as err:
            # Vadné místní měření nezničí doložené odečty a historickou fakturu.
            state = {"value": None, "reason": str(err)}
        result.update(
            current_meter=state.get("value"),
            current_at=state.get("at"),
            measurement_reason=state.get("reason"),
            measurement_source=state.get("source"),
        )
        # Odvozený senzorový stav je výpočet, nikoli nový fyzický odečet MND.
        # Přidává se pouze do neměnného pracovního snímku, archiv se nepřepisuje.
        # Přesné okamžiky se oceňují na UTC ose. Pouhé datum zůstává datem
        # a smíšená časová hranice se neprohlásí za přesné hodinové měření.
        if state.get("reason") == "derived_state" and state.get("at"):
            readings.append(
                Reading.parse(
                    {
                        "id": "projection:sensor",
                        "place": place_id,
                        "meter": next(
                            (r.meter for r in reversed(relevant) if r.segment == segment), segment
                        ),
                        "segment": segment,
                        "date": local_day(state["at"], zone),
                        "value": state["value"],
                        "observed_at": state["at"],
                        "source": "sensor",
                    }
                )
            )
    # Vlastní výhled používá dodavatelské období, ne volitelné období ruční
    # evidence. Poškozené podklady nesmějí skrýt samotný přehled dodavatele.
    try:
        result["own_billing"] = own_billing_view(
            place_id, place, result.get("billing", {}), state, now, zone
        )
    except DataError as error:
        result["own_billing"] = {"status": "incomplete", "reason": str(error), "balance_czk": None}
    if not settings.get("period_from") or not settings.get("period_to"):
        return wire(result)
    intervals = consumption_intervals(readings, place_id)
    chunks = []
    for row in intervals:
        if not row["from"]:
            continue
        first, last = row["from_at"] or row["from"], row["observed_at"] or row["date"]
        if boundary(first, zone) >= boundary(last, zone):
            continue
        chunks.append(
            {
                "from": first,
                "to": last,
                "m3": row["consumption_m3"],
                "complete": row["consumption_m3"] is not None,
                "estimated": row["estimated"],
                "time_uncertain": bool(row["from_at"]) != bool(row["observed_at"]),
            }
        )
    # Konec určuje doložený okamžik měření nebo uzavřené potvrzené vyúčtování.
    # Budoucí smluvní konec sám nevytváří dosud vzniklé náklady.
    endpoints = [r.observed_at or r.date for r in readings]
    endpoints += [i["to"] for i in invoices if boundary(i["to"], zone) <= now]
    measurement_end = max(
        endpoints, key=lambda value: boundary(value, zone), default=settings["period_from"]
    )
    calculation_end = min(
        (settings["period_to"], measurement_end), key=lambda value: boundary(value, zone)
    )
    if boundary(calculation_end, zone) <= boundary(settings["period_from"], zone):
        result.update(status="incomplete", complete=False, warnings=["consumption_gap"])
        return wire(result)
    result.update(
        calculate(
            start=settings["period_from"],
            end=calculation_end,
            segments=chunks,
            tariffs=place["tariffs"],
            conversions=place["conversions"],
            events=place["events"],
            invoices=place["invoices"],
            opening_credit=settings.get("opening_credit"),
            payments_complete=settings.get("payments_complete", False),
            allow_linear=settings.get("allow_linear", False),
            zone=zone,
            ledger_end=settings["period_to"],
            as_of=today,
        )
    )
    result["evaluated_from"] = settings["period_from"]
    # Přesná místní půlnoc je zároveň datumová hranice pro navazující prognózu.
    end_in_zone = boundary(calculation_end, zone).astimezone(ZoneInfo(zone))
    result["evaluated_to"] = (
        end_in_zone.date() if end_in_zone.time() == time.min else calculation_end
    )
    result["status"] = "complete" if result["complete"] else "incomplete"
    if excluded_future:
        result["warnings"].append("future_readings_excluded")
    return wire(result)
