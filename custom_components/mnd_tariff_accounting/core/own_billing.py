"""Vlastní výhled založený na měření; neúplný podklad nikdy není nula."""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from .accounting import active_versions
from .billing import own_outcome_from_energy, selected_profile
from .common import DataError, day, decimal, instant, local_day
from .forecast import seasonal_forecast
from .metering import Reading, active_readings, validate_samples


def history_binding_matches(settings):
    """Ověří výslovné potvrzení dvojice zdrojů včetně segmentu a faktoru.

    Potvrzení platí pouze pro právě uložené registry entity; přejmenování
    entity ho nezneplatní, změna zdroje, segmentu nebo m³/puls ano. Prázdný
    historický zdroj znamená totožný zdroj a další potvrzení nepotřebuje.
    """
    source = settings.get("source_registry_id")
    history = settings.get("history_registry_id") or source
    if not source or not settings.get("segment"):
        return False
    if history == source:
        return True
    binding = settings.get("history_binding")
    if not isinstance(binding, dict):
        return False
    try:
        factor = decimal(settings.get("history_unit_m3"), optional=True, nonnegative=True)
        if factor is not None and factor == 0:
            return False
        return (
            binding.get("source") == source
            and binding.get("history") == history
            and binding.get("segment") == settings.get("segment")
            and decimal(binding.get("factor"), optional=True)
            == factor
        )
    except DataError:
        return False


def _strict_own_billing_view(place_id, place, billing, measurement, now, zone):
    """Sestaví vlastní odhad nad existující revizí archivu bez zápisu do HA.

    Účetní hranice jsou místní dny [od, do), plynoměr m³, energie MWh a
    peníze Kč. Přesná kotva na začátku období a navazující odvozený stav
    stejného měřidla jsou nutné: pouhý celkový sloupec MND v MWh nedokládá
    konec intervalu. Historický a živý zdroj musí být totožné nebo mít výslovně potvrzenou
    vazbu obou registry identit, segmentu a převodního faktoru. Denní profil vyžaduje 365
    souvislých úplných dnů; neúplný dnešek se dělí podle skutečné délky dne
    v UTC (23/24/25 hodin). Současný údaj platí jen ke svému vlastnímu času.
    Každé selhání vrátí důvod a částečné údaje, ne odhad dodavatele či nulu.
    """
    result = {"status": "incomplete", "reason": None, "balance_czk": None}

    def missing(reason):
        result["reason"] = reason
        return result

    if not billing.get("from") or not billing.get("to"):
        return missing("billing_period_missing")
    start, end = day(billing["from"]), day(billing["to"])
    now = instant(now)
    today = local_day(now, zone)
    result.update(period_from=start, period_to=end, calculated_at=now)
    if not start <= today < end:
        return missing("period_not_current")
    settings = place["settings"]
    segment = settings.get("segment")
    if not segment:
        return missing("meter_segment_missing")
    # Pokrytí uvádíme i tehdy, když chybí kotva. Uživatel tak vidí další
    # chybějící podklady najednou; pouze dokončené a skutečně měřené dny.
    profile = selected_profile(place)
    required_days = {today - timedelta(days=i) for i in range(1, 366)}
    available_days = {
        date for date, row in profile.items()
        if date in required_days and row.get("complete") is True
        and row.get("estimated") is not True and row.get("m3") is not None
    }
    result.update(
        profile_complete_days=len(available_days),
        profile_required_days=len(required_days),
        profile_missing_months=sorted({date.isoformat()[:7] for date in required_days - available_days}),
    )
    records = active_readings([Reading.parse(row) for row in place.get("readings", [])])
    boundary = datetime.combine(start, time.min, tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    candidates = [
        row for row in records
        if row.place == place_id and row.segment == segment and row.source in {"mnd", "manual"}
        and row.observed_at == boundary and not row.estimated
    ]
    # MND má na shodném okamžiku přednost; přesně datovaný fyzický ruční
    # odečet může založit výpočet, pokud žádná taková kotva MND neexistuje.
    anchors = [row for row in candidates if row.source == "mnd"] or candidates
    if not anchors or len({row.value for row in anchors}) != 1:
        return missing("period_start_reading_unverified")
    # Denní MND bod nelze uměle seřadit před či za přesný ruční odečet.
    if any(
        row.place == place_id and row.segment == segment and row.source == "mnd"
        and row.date == start and row.observed_at is None and row.value != anchors[0].value
        for row in records
    ):
        return missing("reading_time_ambiguous")
    if measurement.get("reason") != "derived_state" or measurement.get("value") is None:
        return missing(measurement.get("reason") or "measurement_unavailable")
    measured_at = instant(measurement.get("at"))
    if measured_at < boundary or measured_at > now or local_day(measured_at, zone) != today:
        return missing("measurement_not_current_day")
    source_id = settings.get("source_registry_id")
    sample_rows = [
        row for row in place.get("samples", [])
        if row.get("entity") == source_id and row.get("segment") == segment
        and instant(row["at"]) <= measured_at
    ]
    predecessors = [instant(row["at"]) for row in sample_rows if instant(row["at"]) <= boundary]
    if not predecessors:
        return missing("sample_history_start_missing")
    sample_start = max(predecessors)
    ordered = validate_samples(
        [row for row in sample_rows if instant(row["at"]) >= sample_start],
        entity=source_id, segment=segment,
    )
    previous_sample = None
    for sample in ordered:
        if sample["value"] is None or sample.get("continuity") is False:
            return missing("sensor_gap")
        if previous_sample is not None and sample["value"] < previous_sample:
            return missing("sensor_reset")
        previous_sample = sample["value"]
    # Jeden segment nesmí potichu zahrnout jiné měřidlo, pokles nebo dvě
    # rozdílné hodnoty v neznámém pořadí téhož dne. Potvrzené odečty
    # jsou silnější důkaz než pozdější lokální projekce.
    relevant = [
        row for row in records
        if row.place == place_id and row.segment == segment and row.source == "mnd"
        and not row.estimated and start <= row.date <= today
        and (row.observed_at is None or row.observed_at <= measured_at)
    ]
    if any(row.meter != anchors[0].meter for row in relevant):
        return missing("meter_changed")
    groups = {}
    for row in relevant:
        groups.setdefault(row.date, []).append(row)
    previous = anchors[0].value
    for _, rows in sorted(groups.items()):
        if len({row.value for row in rows}) > 1 and any(row.observed_at is None for row in rows):
            return missing("reading_time_ambiguous")
        for row in sorted(rows, key=lambda item: item.observed_at or boundary):
            if row.value < previous:
                return missing("meter_decrease")
            previous = row.value
    if decimal(measurement["value"], nonnegative=True) < previous:
        return missing("meter_decrease")
    actual_volume = decimal(measurement["value"], nonnegative=True) - anchors[0].value
    if actual_volume < 0:
        return missing("meter_decrease")
    result.update(actual_m3=actual_volume, measured_at=measured_at)

    # Zdroje mohou být různé entity i u téhož zařízení. Bez doložené vazby
    # nelze pro predikci použít jeden z nich jako historii druhého.
    if not history_binding_matches(settings):
        return missing("history_source_unverified")
    # Přepnutí jednotky téže registry entity může znamenat novou fyzickou
    # řadu. Ani dříve uložený pulsní faktor nedokazuje návaznost obou úseků.
    units = {
        "m3" if row.get("original_unit") in ("m3", "m³") else
        "pulse" if row.get("original_unit") in ("pulse", "pulses", "imp") else
        row.get("original_unit")
        for date, row in profile.items() if date in available_days
    }
    if len(units) > 1 or None in units:
        return missing("history_unit_changed")
    prediction = seasonal_forecast(list(profile.values()), today, end)
    if not prediction["complete"]:
        return missing(prediction["reason"])

    # Po posledním měření už jde o odhad; současný den a budoucnost se
    # nepřekrývají. Odchylku během dne od rovnoměrného modelu přiznáváme.
    tomorrow = datetime.combine(today + timedelta(days=1), time.min, tzinfo=ZoneInfo(zone))
    midnight = datetime.combine(today, time.min, tzinfo=ZoneInfo(zone))
    right, left = instant(tomorrow), instant(midnight)
    seconds_left = Decimal(str((right - measured_at).total_seconds()))
    day_seconds = Decimal(str((right - left).total_seconds()))
    first_day = prediction["daily"][0]["m3"]
    future_volume = prediction["value"] - first_day + first_day * seconds_left / day_seconds
    result.update(
        future_m3=future_volume,
        total_m3=actual_volume + future_volume,
        method=prediction["method"],
        profile_from=prediction["profile_from"],
        profile_to=prediction["profile_to"],
        profile_hash=prediction["profile_hash"],
        intraday_estimated=True,
    )

    conversions = place.get("conversions", [])
    if conversions and all(item.get("id") for item in conversions):
        conversions = active_versions(conversions)
    valid = [row for row in conversions if day(row["from"]) <= start and end <= day(row["to"])]
    if len(valid) != 1:
        return missing("conversion_period_missing_or_ambiguous")
    factor = decimal(valid[0].get("kwh_per_m3"), nonnegative=True)
    if factor == 0:
        raise DataError("invalid_conversion")
    result["conversion_estimated"] = bool(valid[0].get("estimated"))
    result.update(own_outcome_from_energy(
        place, start, end, today, actual_volume * factor / 1000,
        future_volume * factor / 1000, today,
    ))
    if result["confirmed_invoice"]:
        return missing("confirmed_invoice")
    if result["balance_czk"] is None:
        return missing(result.get("payment_reason") or "price_or_payment_incomplete")
    result.update(status="estimated", reason=None)
    return result


def own_billing_view(place_id, place, billing, measurement, now, zone):
    """Upřednostní přesnou návaznost; alternativu vždy označí orientačně.

    Nepravidelné fyzické odečty a předpokládané denní hranice jsou odlišná
    metoda od přesné kotvy. Selhání alternativy ponechá původní důvod a
    nevyrobí nulu; nepřebírá číselnou prognózu spotřeby od dodavatele.
    """
    result = _strict_own_billing_view(place_id, place, billing, measurement, now, zone)
    if result.get("status") == "estimated" or not billing.get("from") or not billing.get("to"):
        return result
    from .orientational import orientational_view

    try:
        alternative = orientational_view(
            place_id, place, billing, now, zone, history_binding_matches(place["settings"])
        )
    except DataError:
        return result
    return alternative or result
