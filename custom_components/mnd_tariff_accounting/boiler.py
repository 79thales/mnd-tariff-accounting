"""Nativní čtecí napojení kotle: registry, stavy a místní Recorder.

Žádné relé ani služba topení se neovládá. Registr UUID přežije přejmenování;
stavy se čtou z hass, účet MND a archiv finančních transakcí se nemění.
"""

import asyncio
from datetime import datetime, time, timedelta
from functools import partial
from zoneinfo import ZoneInfo

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from sqlalchemy.exc import SQLAlchemyError

from .core.boiler import ENERGY_UNITS, POWER_UNITS, demand_value, electrical_value, energy_period
from .core.common import DataError


def sources(hass, settings):
    """Resolve pouze explicitně vybraných entit; nikdy automaticky první zásuvka."""
    registry = er.async_get(hass)
    result = {}
    for kind in ("power", "energy", "demand"):
        source = registry.async_get(
            settings.get(f"boiler_{kind}_registry_id") or settings.get(f"boiler_{kind}_entity", "")
        )
        result[kind] = source.entity_id if source else None
    return result


def validated_settings(hass, existing, record):
    """Serverová validace výběru; vypnutí zachová výběr i při výpadku zařízení.

    UUID z klienta se nebere jako autorita. Nové či zapínané zdroje musí mít
    odpovídající jednotku a doménu; kumulativní energie také state_class.
    Chyba předchází transakci, takže nepřepíše dosavadní platné nastavení.
    """
    record = dict(record)
    for kind in ("power", "energy", "demand"):
        record.pop(f"boiler_{kind}_registry_id", None)
    merged = {**existing, **record}
    registry = er.async_get(hass)
    for kind, units in (("power", POWER_UNITS), ("energy", ENERGY_UNITS), ("demand", None)):
        field, regfield = f"boiler_{kind}_entity", f"boiler_{kind}_registry_id"
        # Vypínací formulář může uchovat již přejmenovaný/odpojený zdroj.
        entity = merged.get(field, "")
        if not isinstance(entity, str) or len(entity) > 255 or entity != entity.strip():
            raise DataError("invalid_boiler_entity")
        source = registry.async_get(entity) if entity else None
        if not source and entity == existing.get(field):
            source = registry.async_get(existing.get(regfield, ""))
        state = hass.states.get(source.entity_id) if source else None
        changed = field in record and record[field] != existing.get(field, "")
        must_validate = bool(entity) and (changed or merged.get("boiler_enabled"))
        if must_validate:
            if source is None or state is None:
                raise DataError("boiler_source_unavailable")
            if units is not None and (
                source.domain != "sensor"
                or state.attributes.get("unit_of_measurement") not in units
            ):
                raise DataError(
                    "incompatible_boiler_energy"
                    if kind == "energy"
                    else "incompatible_boiler_sensor"
                )
            if kind == "energy" and state.attributes.get("state_class") not in (
                "total",
                "total_increasing",
            ):
                raise DataError("incompatible_boiler_energy")
            if kind == "demand" and source.domain not in ("switch", "binary_sensor", "climate"):
                raise DataError("incompatible_boiler_demand")
        if field in record or merged.get("boiler_enabled"):
            record[regfield] = source.id if source else existing.get(regfield) if entity else None
            if source:
                record[field] = source.entity_id
    return record


def live_values(hass, settings):
    """Okamžité W/kWh a požadavek; mez platnosti v sekundách, bez zápisu I/O."""
    if not settings.get("boiler_enabled", False):
        return {"enabled": False}
    entities = sources(hass, settings)
    result = {"enabled": True, "entities": entities}
    for kind in ("power", "energy"):
        state = hass.states.get(entities[kind]) if entities[kind] else None
        at = (
            (getattr(state, "last_reported", None) or state.last_updated).isoformat()
            if state
            else None
        )
        result[kind] = electrical_value(
            state.state if state else None,
            state.attributes.get("unit_of_measurement") if state else None,
            at,
            dt_util.utcnow(),
            energy=kind == "energy",
            max_age=settings.get("boiler_max_age", 900),
        )
    demand = hass.states.get(entities["demand"]) if entities["demand"] else None
    result["demand"] = demand_value(demand.state, demand.attributes) if demand else None
    return result


async def async_energy_summary(coordinator, settings):
    """Dnes/měsíc z uzavřených hodin Recorderu, cache nejvýše 5 minut.

    Čte se až při zobrazení detailu/přehledu se zapnutou funkcí. Zámek slučuje
    souběžné karty; cache klíčuje UUID, aktuální entity ID a místní den, takže
    změna zdroje či půlnoc nepřebere předchozí výsledek. Dotaz je v executoru
    Recorderu, timeout 15 s. Chyba vrací nedostupnost, nikdy nulovou energii.
    Cache je pouze v paměti a není zdrojem účetních dat; restart ji obnoví.
    """
    if coordinator._closed:
        return {"quality": "closed", "today": None, "month": None}
    entity = (
        sources(coordinator.hass, settings)["energy"] if settings.get("boiler_enabled") else None
    )
    if not entity:
        return {"quality": "not_configured", "today": None, "month": None}
    hass = coordinator.hass
    if "recorder" not in hass.config.components:
        return {"quality": "recorder_unavailable", "today": None, "month": None}
    now = dt_util.utcnow()
    zone = ZoneInfo(hass.config.time_zone)
    today = now.astimezone(zone).date()
    key = (settings.get("boiler_energy_registry_id"), entity, today, str(zone))
    if not hasattr(coordinator, "_boiler_energy_lock"):
        coordinator._boiler_energy_lock = asyncio.Lock()
        coordinator._boiler_energy_cache = {}
    async with coordinator._boiler_energy_lock:
        # Unload mohl nastat při čekání za jinou kartou. Čtení už nespouštíme.
        if coordinator._closed:
            return {"quality": "closed", "today": None, "month": None}
        cached = coordinator._boiler_energy_cache.get(key)
        tick = asyncio.get_running_loop().time()
        if cached and tick - cached[0] < 300:
            return cached[1]
        left = datetime.combine(today.replace(day=1), time.min, zone)
        midnight = datetime.combine(today, time.min, zone)
        right = midnight + timedelta(days=1)

        def read():
            from homeassistant.components.recorder.statistics import (
                get_metadata,
                statistics_during_period,
            )

            metadata = get_metadata(hass, statistic_ids={entity}).get(entity)
            unit = metadata[1].get("unit_of_measurement") if metadata else None
            if unit not in ENERGY_UNITS or not metadata[1].get("has_sum"):
                raise DataError("incompatible_boiler_statistics")
            rows = statistics_during_period(
                hass,
                left - timedelta(hours=1),
                now,
                {entity},
                "hour",
                None,
                {"state", "sum", "change"},
            )
            data = rows.get(entity, [])
            return {
                "quality": "partial",
                "today": energy_period(data, midnight, right, now, ENERGY_UNITS[unit]),
                "month": energy_period(data, left, right, now, ENERGY_UNITS[unit]),
            }

        try:
            from homeassistant.components.recorder import get_instance

            async with asyncio.timeout(15):
                result = await get_instance(hass).async_add_executor_job(partial(read))
        except (DataError, TimeoutError, KeyError, ValueError, HomeAssistantError, SQLAlchemyError):
            result = {"quality": "unavailable", "today": None, "month": None}
        if coordinator._closed:
            return {"quality": "closed", "today": None, "month": None}
        # Nejvýše jeden výsledek na nakonfigurované místo/zdroj v aktuálním dni.
        coordinator._boiler_energy_cache = {
            k: v for k, v in coordinator._boiler_energy_cache.items() if k[2] == today
        }
        coordinator._boiler_energy_cache[key] = (tick, result)
        return result
