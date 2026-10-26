"""Skutečný HA: validace, UUID přejmenování, izolace a čtecí Recorder cesta.

Používají se pouze syntetické entity. Rozhraní HA a registr jsou skutečné;
jen výsledky statistického dotazu mají řízená data, aby test nezávisel na
reálné domácnosti ani na době běhu agregátoru Recorderu.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mnd_tariff_accounting.boiler import async_energy_summary
from custom_components.mnd_tariff_accounting.const import DOMAIN
from custom_components.mnd_tariff_accounting.core.common import DataError

PLACE = "27ZG000Z0000000X"


async def ready(hass):
    """Samostatný importní účet: žádná portálová relace ani síť MND."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic boiler",
        unique_id="synthetic-boiler",
        data={
            "account_id": "synthetic-boiler",
            "mode": "import",
            "places": [{"id": PLACE, "name": "Synthetic"}],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    source_entry = MockConfigEntry(domain="test", data={})
    source_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    source = registry.async_get_or_create(
        "sensor",
        "test",
        "synthetic-boiler-power",
        suggested_object_id="synthetic_boiler_power",
        config_entry=source_entry,
    )
    return entry, registry, source


async def test_boiler_validation_rename_and_disable_preserve_meter(hass):
    entry, registry, source = await ready(hass)
    coordinator = entry.runtime_data
    hass.states.async_set(source.entity_id, "0.094", {"unit_of_measurement": "kW"})
    await coordinator.async_edit(
        PLACE,
        "boiler",
        {
            "boiler_enabled": True,
            "boiler_power_entity": source.entity_id,
            "boiler_power_registry_id": "forged-client-id",
        },
        coordinator.repository.data["revision"],
    )
    settings = coordinator.repository.data["places"][PLACE]["settings"]
    assert settings["boiler_power_registry_id"] == source.id
    assert coordinator.data[PLACE]["boiler"]["power"]["value"] == "94.000"
    renamed = registry.async_update_entity(
        source.entity_id, new_entity_id="sensor.renamed_boiler_power"
    )
    hass.states.async_set(renamed.entity_id, "0", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await coordinator.async_recompute()
    assert coordinator.data[PLACE]["boiler"]["power"]["value"] == "0"
    hass.states.async_set(renamed.entity_id, "unavailable", {"unit_of_measurement": "W"})
    await coordinator.async_recompute()
    assert coordinator.data[PLACE]["boiler"]["power"]["value"] is None
    await coordinator.async_edit(
        PLACE, "boiler", {"boiler_enabled": False}, coordinator.repository.data["revision"]
    )
    assert settings["boiler_power_registry_id"] == source.id
    assert coordinator.data[PLACE]["boiler"] == {"enabled": False}
    # Zdroj zůstává původním měřením; integrace do něj nic nezapisuje.
    assert hass.states.get(renamed.entity_id).state == "unavailable"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_incompatible_boiler_source_fails_before_archive_transaction(hass):
    entry, registry, source = await ready(hass)
    coordinator = entry.runtime_data
    hass.states.async_set(source.entity_id, "10", {"unit_of_measurement": "m³"})
    revision = coordinator.repository.data["revision"]
    with pytest.raises(DataError, match="incompatible_boiler_sensor"):
        await coordinator.async_edit(
            PLACE,
            "boiler",
            {"boiler_enabled": True, "boiler_power_entity": source.entity_id},
            revision,
        )
    assert coordinator.repository.data["revision"] == revision
    assert not coordinator.repository.data["places"][PLACE]["settings"].get("boiler_enabled")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unrelated_registry_event_does_not_rebuild_boiler_subscriptions(hass):
    entry, registry, source = await ready(hass)
    coordinator = entry.runtime_data
    hass.states.async_set(source.entity_id, "94", {"unit_of_measurement": "W"})
    await coordinator.async_edit(
        PLACE,
        "boiler",
        {"boiler_enabled": True, "boiler_power_entity": source.entity_id},
        coordinator.repository.data["revision"],
    )
    with patch.object(coordinator, "_subscribe_sources") as subscribe:
        coordinator._registry_changed(SimpleNamespace(data={"entity_id": "sensor.unrelated"}))
        subscribe.assert_not_called()
    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize("entity", [[], {}, True, 42, " sensor.synthetic_power"])
async def test_invalid_boiler_entity_type_has_stable_error_without_write(hass, entity):
    entry, registry, source = await ready(hass)
    coordinator = entry.runtime_data
    revision = coordinator.repository.data["revision"]
    with pytest.raises(DataError, match="invalid_boiler_entity"):
        await coordinator.async_edit(
            PLACE,
            "boiler",
            {"boiler_power_entity": entity},
            revision,
        )
    assert coordinator.repository.data["revision"] == revision
    await hass.config_entries.async_unload(entry.entry_id)


async def test_waiting_energy_summary_does_not_query_after_unload(hass):
    entry, registry, source = await ready(hass)
    coordinator = entry.runtime_data
    hass.config.components.add("recorder")
    coordinator._boiler_energy_lock = asyncio.Lock()
    coordinator._boiler_energy_cache = {}
    await coordinator._boiler_energy_lock.acquire()
    settings = {"boiler_enabled": True, "boiler_energy_entity": source.entity_id}
    task = asyncio.create_task(async_energy_summary(coordinator, settings))
    await asyncio.sleep(0)
    coordinator._closed = True
    coordinator._boiler_energy_lock.release()
    assert await task == {"quality": "closed", "today": None, "month": None}
    hass.config.components.discard("recorder")
    await hass.config_entries.async_unload(entry.entry_id)


async def test_boiler_energy_is_read_on_demand_and_cached_without_mnd_call(hass):
    entry, registry, source = await ready(hass)
    coordinator = entry.runtime_data
    settings = {
        "boiler_enabled": True,
        "boiler_energy_entity": source.entity_id,
        "boiler_energy_registry_id": source.id,
    }
    hass.config.components.add("recorder")
    executor = SimpleNamespace(
        async_add_executor_job=AsyncMock(side_effect=hass.async_add_executor_job)
    )
    metadata = {source.entity_id: (1, {"unit_of_measurement": "Wh", "has_sum": True})}
    with (
        patch("homeassistant.components.recorder.get_instance", return_value=executor),
        patch("homeassistant.components.recorder.statistics.get_metadata", return_value=metadata),
        patch(
            "homeassistant.components.recorder.statistics.statistics_during_period",
            return_value={source.entity_id: []},
        ) as query,
    ):
        first = await async_energy_summary(coordinator, settings)
        second = await async_energy_summary(coordinator, settings)
        assert first == second
        assert first["today"]["value_kwh"] is None
        assert first["month"]["value_kwh"] is None
        assert query.call_count == 1
        assert coordinator.cloud_status == "not_connected"
    hass.config.components.discard("recorder")
    await hass.config_entries.async_unload(entry.entry_id)
