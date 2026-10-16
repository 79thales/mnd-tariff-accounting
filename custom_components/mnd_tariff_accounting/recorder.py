"""Nativní pouze čtecí adaptér Recorderu; původní statistiky se nikdy nemění."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from functools import partial
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.statistics import get_metadata, statistics_during_period
from homeassistant.helpers import entity_registry as er

from .core.common import DataError, day, fingerprint, wire
from .core.statistics import daily_profile


async def async_read_history(coordinator, place_id, start, end, job_cursor=None):
    """Nejvýše 7 dní na jeden blok mimo event loop, v pásmu konfigurace HA.

    Vrací skutečně dostupné reportované stavy a samostatně agregáty. Chybějící
    Recorder nebo změna jednotek se odmítne, nikoli nahradí nulovou spotřebou.
    Registry ID přežije přejmenování entity. Agregáty nenahrazují přesný čas.
    """
    hass = coordinator.hass
    settings = coordinator.repository.data["places"][place_id]["settings"]
    source = er.async_get(hass).async_get(settings.get("source_registry_id", ""))
    if source is None:
        raise DataError("source_registry_missing")
    first, last = day(start), day(end)
    if not 0 < (last - first).days <= 7:
        raise DataError("history_block_limit")
    zone = ZoneInfo(hass.config.time_zone)
    left = datetime.combine(first, time.min, zone)
    right = datetime.combine(last, time.min, zone)

    def read():
        metadata = get_metadata(hass, statistic_ids={source.entity_id})
        info = metadata.get(source.entity_id)
        if (
            not info
            or info[1].get("unit_of_measurement") not in ("m³", "m3")
            or not info[1].get("has_sum")
        ):
            raise DataError("source_statistics_incompatible")
        statistics = statistics_during_period(
            hass,
            left - timedelta(hours=1),
            right,
            {source.entity_id},
            "hour",
            None,
            {"state", "sum", "change"},
        )
        history = get_significant_states(
            hass,
            left,
            right,
            entity_ids=[source.entity_id],
            significant_changes_only=False,
            minimal_response=False,
        )
        samples = []
        for state in history.get(source.entity_id, []):
            sample = {
                "entity": source.id,
                "segment": settings["segment"],
                "unit": state.attributes.get("unit_of_measurement"),
                "state_class": state.attributes.get("state_class"),
                "at": state.last_updated.isoformat(),
                "value": state.state if state.state not in ("unknown", "unavailable") else None,
                "continuity": True,
                "time_basis": "reported",
            }
            samples.append(sample)
        return statistics.get(source.entity_id, []), samples

    rows, samples = await get_instance(hass).async_add_executor_job(partial(read))
    profile = await hass.async_add_executor_job(daily_profile, rows, hass.config.time_zone)

    def commit(data):
        place = data["places"][place_id]
        # Opravený záznam shodného klíče nahradí stejný interval, nepřičítá se.
        existing = {fingerprint([s["entity"], s["segment"], s["at"]]): s for s in place["samples"]}
        existing.update({fingerprint([s["entity"], s["segment"], s["at"]]): s for s in samples})
        place["samples"] = list(existing.values())
        daily = {r["date"]: r for r in place.get("daily_profile", [])}
        for row in profile:
            if first <= day(row["date"]) < last:
                daily[row["date"]] = wire(
                    {**row, "entity": source.id, "segment": settings["segment"]}
                )
        place["daily_profile"] = list(daily.values())
        if job_cursor is not None:
            data["job"]["cursor"] = job_cursor
            data["job"]["completed_blocks"] = data["job"].get("completed_blocks", 0) + 1

    await coordinator.repository.transact(commit)
    await coordinator.async_recompute()
    return {
        "samples": len(samples),
        "days": len(profile),
        "complete_days": sum(row["complete"] for row in profile),
    }
