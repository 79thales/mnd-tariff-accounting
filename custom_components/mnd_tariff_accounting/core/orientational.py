"""Výslovně orientační spojení nepravidelných odečtů MND a měření HA."""

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from .billing import own_outcome_from_energy, selected_profile
from .common import DataError, day, decimal, instant, local_day
from .metering import Reading, active_readings, validate_samples


def _points(place, place_id, segment, today):
    """Denní MND body; konflikty a neověřené instalace přerušují interpolaci.

    Opakované shodné dokladové řádky jsou jeden bod, odhad MND není měření.
    Různé hodnoty téhož dne zůstanou bariérou, nikoli náhodně zvoleným bodem.
    """
    grouped = {}
    for row in active_readings([Reading.parse(r) for r in place.get("readings", [])]):
        if row.place != place_id or row.segment != segment or row.source != "mnd":
            continue
        if row.estimated or row.date > today:
            continue
        grouped.setdefault(row.date, []).append(row)
    result = []
    for date, rows in sorted(grouped.items()):
        identities = {(r.meter, r.value) for r in rows}
        physical = all("odeč" in r.method.lower() for r in rows)
        result.append({"date": date, "meter": rows[0].meter, "value": rows[0].value,
                       "valid": len(identities) == 1 and physical})
    return result


def _season(profile, points, meter, today, end):
    """Měsíční průměry HA doplněné lineárním rozdělením odečtů MND.

    Interval MND [den A, den B) rozdělujeme rovnoměrně jen mezi dvěma
    fyzickými odečty téhož měřidla, nejvýše 62 dnů od sebe. Tyto dny jsou
    odhad, nikoli nová měření. U každého budoucího měsíce požadujeme aspoň
    sedm dostupných dnů v posledních 365 dnech; jde o výslovnou ochrannou
    hranici, nikoli důkaz reprezentativnosti. HA celé dny mají přednost.
    """
    interpolated = {}
    for a, b in zip(points, points[1:]):
        count = (b["date"] - a["date"]).days
        if not (a["valid"] and b["valid"] and a["meter"] == b["meter"] == meter):
            continue
        if not 0 < count <= 62 or b["value"] < a["value"]:
            continue
        amount = (b["value"] - a["value"]) / Decimal(count)
        for offset in range(count):
            date = a["date"] + timedelta(days=offset)
            if today - timedelta(days=365) <= date < today:
                interpolated[date] = amount
    selected = {}
    for i in range(1, 366):
        date = today - timedelta(days=i)
        row = profile.get(date)
        if row and row.get("complete") is True and not row.get("estimated") and row.get("m3") is not None:
            selected[date] = (decimal(row["m3"], nonnegative=True), "ha")
        elif date in interpolated:
            selected[date] = (interpolated[date], "mnd_estimate")
    needed = {(today + timedelta(days=i)).month for i in range((end - today).days)}
    months = {}
    for month in needed:
        rows = [item for date, item in selected.items() if date.month == month]
        if len(rows) < 7:
            return None, {"missing_months": sorted(m for m in needed if sum(d.month == m for d in selected) < 7)}
        months[month] = sum((v for v, _ in rows), Decimal(0)) / Decimal(len(rows))
    return months, {"sample_days": len(selected), "interpolated_days": sum(s == "mnd_estimate" for _, s in selected.values()),
                    "month_days": {str(m): sum(d.month == m for d in selected) for m in sorted(needed)}}


def _live_tail(place, cutoff, now, zone):
    """Přičte jen doložený přírůstek od poslední uzavřené hodiny.

    Nedostupný stav, reset nebo chybějící předchozí vzorek ponechají výsledek
    k času uzavřené hodiny. Hodinová statistika a přírůstek se nepřekrývají.
    """
    settings = place["settings"]
    source, segment = settings.get("source_registry_id"), settings.get("segment")
    samples = [s for s in place.get("samples", []) if s.get("entity") == source
               and s.get("segment") == segment and instant(s["at"]) <= now]
    before = [instant(s["at"]) for s in samples if instant(s["at"]) <= cutoff]
    if not before:
        return Decimal(0), cutoff, "baseline_missing"
    earliest = max(before)
    # Starý vzorek není důkazem, že do hranice statistiky nepřibyly pulsy.
    # Hodinová mez pouze odmítá nedoloženou návaznost, neovládá plynoměr.
    if cutoff - earliest > timedelta(hours=1):
        return Decimal(0), cutoff, "baseline_missing"
    try:
        ordered = validate_samples([s for s in samples if instant(s["at"]) >= earliest],
                                   entity=source, segment=segment)
        if not ordered or ordered[0]["value"] is None:
            return Decimal(0), cutoff, "baseline_missing"
        previous = ordered[0]["value"]
        for sample in ordered:
            if sample["value"] is None or sample.get("continuity") is False:
                return Decimal(0), cutoff, "sensor_gap"
            if sample["value"] < previous:
                return Decimal(0), cutoff, "sensor_reset"
            previous = sample["value"]
        last = ordered[-1]
        if last["at"] <= cutoff or local_day(last["at"], zone) != local_day(now, zone):
            return Decimal(0), cutoff, "awaiting_new_sample"
        return last["value"] - ordered[0]["value"], last["at"], "current"
    except DataError:
        return Decimal(0), cutoff, "sensor_gap"


def orientational_view(place_id, place, billing, now, zone, linked):
    """Přibližný vlastní výhled: MND kotvy, navazující HA a zimní profil.

    Počáteční odečet den před obdobím pokládá za jeho počátek; poslední
    dřívější odečet za konec příslušného dne. Oba předpoklady nesou časovou
    nejistotu. Zbývající celé dny a souvislé uzavřené hodiny bere pouze z HA.
    Pokud se novější živé vzorky přeruší, výsledek zůstane k uzavřené hodině.
    Žádný výstup se nezapisuje do účetní knihy ani na portál dodavatele.
    """
    now = instant(now)
    today = local_day(now, zone)
    start, end = day(billing["from"]), day(billing["to"])
    segment = place["settings"].get("segment")
    if not segment or not start <= today < end:
        return None
    profile = selected_profile(place)
    points = _points(place, place_id, segment, today)
    starts = [p for p in points if p["valid"] and p["date"] in (start, start - timedelta(days=1))]
    if not starts:
        return None
    first = max(starts, key=lambda p: p["date"])
    earlier = [p for p in points if p["valid"] and first["date"] < p["date"] < today]
    if not earlier:
        return None
    last = max(earlier, key=lambda p: p["date"])
    between = [p for p in points if first["date"] <= p["date"] <= last["date"]]
    if any(not p["valid"] or p["meter"] != first["meter"] for p in between):
        return None
    if any(b["value"] < a["value"] for a, b in zip(between, between[1:])):
        return None
    actual = last["value"] - first["value"]
    cursor = last["date"] + timedelta(days=1)
    while cursor < today:
        row = profile.get(cursor)
        if not row or row.get("complete") is not True or row.get("estimated") or row.get("m3") is None:
            return None
        actual += decimal(row["m3"], nonnegative=True)
        cursor += timedelta(days=1)
    current = profile.get(today)
    if not current or current.get("known_m3") is None or not current.get("observed_to"):
        return None
    cutoff = instant(current["observed_to"])
    left = instant(datetime.combine(today, time.min, tzinfo=ZoneInfo(zone)))
    right = instant(datetime.combine(today + timedelta(days=1), time.min, tzinfo=ZoneInfo(zone)))
    seconds = (cutoff - left).total_seconds()
    if not 0 < seconds <= (right - left).total_seconds() or cutoff > now:
        return None
    if seconds % 3600 or current.get("known_hours") != int(seconds / 3600) or current.get("reasons"):
        return None
    actual += decimal(current["known_m3"], nonnegative=True)
    tail, measured_at, live_status = _live_tail(place, cutoff, now, zone)
    actual += tail
    averages, coverage = _season(profile, points, first["meter"], today, end)
    if averages is None:
        return None
    fraction = Decimal(str((right - measured_at).total_seconds())) / Decimal(str((right - left).total_seconds()))
    future = averages[today.month] * fraction + sum(
        (averages[(today + timedelta(days=i)).month] for i in range(1, (end - today).days)), Decimal(0)
    )
    conversions = [c for c in place.get("conversions", [])
                   if day(c["from"]) < end and start < day(c["to"])]
    if len(conversions) > 1 or (conversions and not (
        day(conversions[0]["from"]) <= start and end <= day(conversions[0]["to"])
    )):
        return None
    if conversions:
        factor = decimal(conversions[0].get("kwh_per_m3"), nonnegative=True)
        estimated_factor = bool(conversions[0].get("estimated"))
        factor_source = "configured"
    else:
        invoices = [i for i in place.get("invoice_evidence", []) if i.get("verified")
                    and i.get("kwh_per_m3") is not None and day(i["to"]) <= today]
        if not invoices:
            return None
        factor = decimal(max(invoices, key=lambda i: day(i["to"]))["kwh_per_m3"], nonnegative=True)
        estimated_factor = True
        factor_source = "last_invoice"
    if factor <= 0:
        return None
    # Mezivýsledek může obsahovat periodický desetinný rozvoj z dělení dnů.
    # MWh zaokrouhlíme až na 12 desetinných míst; Kč dále zpracuje Decimal.
    precision = Decimal("0.000000000001")
    try:
        actual_mwh = (actual * factor / 1000).quantize(precision)
        future_mwh = (future * factor / 1000).quantize(precision)
    except InvalidOperation as err:
        raise DataError("invalid_number") from err
    result = own_outcome_from_energy(place, start, end, today, actual_mwh, future_mwh, today)
    if result["balance_czk"] is None or result["confirmed_invoice"]:
        return None
    return {**result, "status": "estimated", "reason": None, "period_from": start,
            "period_to": end, "calculated_at": now, "measured_at": measured_at,
            "actual_m3": actual, "future_m3": future, "total_m3": actual + future,
            "method": "mnd_daily_anchor_ha_seasonal_interpolated_v1",
            "mnd_anchor_from": first["date"], "mnd_anchor_to": last["date"],
            "boundary_estimated": True, "history_source_assumed": not linked,
            "conversion_estimated": estimated_factor, "conversion_source": factor_source,
            "intraday_estimated": True, "live_status": live_status, **coverage}
