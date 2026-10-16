"""Skutečné HA rozhraní: oprávnění, izolace Overview a registry měřidla.

Síť míří jen na testovací HTTP server. Účet MND ani provozní HA se
nepoužívají; původní stavy cizího senzoru nesmí místní účetnictví měnit.
"""

from collections.abc import Mapping

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mnd_tariff_accounting.const import DOMAIN

PLACE = "27ZG000Z0000000X"


async def ready(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic MND",
        unique_id="synthetic-interfaces",
        data={
            "account_id": "synthetic-account",
            "mode": "import",
            "places": [{"id": PLACE, "name": "Synthetic"}],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_non_admin_cannot_read_or_mutate_private_websocket(
    hass, hass_ws_client, hass_read_only_access_token
):
    selected = await ready(hass)
    client = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    for i, action in enumerate(("entries", "summary", "edit"), 1):
        await client.send_json(
            {
                "id": i,
                "type": DOMAIN + "/command",
                "action": action,
                "entry_id": selected.entry_id,
                "place": PLACE,
                "payload": {"section": "settings", "record": {"opening_credit": "900"}},
            }
        )
        response = await client.receive_json()
        assert not response["success"]
        assert response["error"]["code"] == "unauthorized"
    assert (
        "opening_credit" not in selected.runtime_data.repository.data["places"][PLACE]["settings"]
    )
    await hass.config_entries.async_unload(selected.entry_id)


@pytest.mark.parametrize(
    "route,method", [("backup", "get"), ("artifact", "get"), ("import", "post")]
)
async def test_non_admin_cannot_download_or_upload_documents(
    hass, hass_client, hass_read_only_access_token, route, method
):
    selected = await ready(hass)
    client = await hass_client(hass, access_token=hass_read_only_access_token)
    url = f"/api/{DOMAIN}/{route}/{selected.entry_id}/{PLACE}"
    if route == "artifact":
        url += "/" + "0" * 64
    response = await getattr(client, method)(url)
    assert response.status == 403
    await hass.config_entries.async_unload(selected.entry_id)


async def test_admin_summary_and_unknown_entry_are_separate(hass, hass_ws_client):
    selected = await ready(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": DOMAIN + "/command",
            "action": "summary",
            "entry_id": selected.entry_id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"]["places"] == [{"id": PLACE, "name": "Synthetic"}]
    assert response["result"]["results"][PLACE]["current_meter"] is None
    await client.send_json(
        {
            "id": 2,
            "type": DOMAIN + "/command",
            "action": "summary",
            "entry_id": "does-not-exist",
        }
    )
    response = await client.receive_json()
    assert not response["success"] and response["error"]["code"] == "entry_not_loaded"
    await hass.config_entries.async_unload(selected.entry_id)


async def test_setup_keeps_existing_overview_and_serves_only_code(hass, hass_client):
    assert await async_setup_component(hass, "frontend", {})
    lovelace = hass.data["lovelace"]
    dashboards = lovelace["dashboards"] if isinstance(lovelace, Mapping) else lovelace.dashboards
    overview = dashboards[None]
    original = {"title": "Synthetic home", "views": [{"path": "home", "cards": []}]}
    await overview.async_save(original)
    selected = await ready(hass)
    assert await overview.async_load(False) == original
    client = await hass_client(hass)
    response = await client.get(f"/{DOMAIN}/mnd-panel.js")
    assert response.status == 200
    text = await response.text()
    assert '"mnd-accounting-panel"' in text
    assert PLACE not in text
    await hass.config_entries.async_reload(selected.entry_id)
    assert await overview.async_load(False) == original
    await hass.config_entries.async_unload(selected.entry_id)


async def test_registry_rename_keeps_uuid_and_records_intermediate_reset(hass):
    selected = await ready(hass)
    coordinator = selected.runtime_data
    source_entry = MockConfigEntry(domain="test", data={})
    source_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    source = registry.async_get_or_create(
        "sensor",
        "test",
        "synthetic-meter",
        suggested_object_id="synthetic_gas",
        config_entry=source_entry,
    )
    attributes = {"unit_of_measurement": "m³", "state_class": "total_increasing"}
    hass.states.async_set(source.entity_id, "100", attributes)
    await coordinator.async_edit(
        PLACE,
        "settings",
        {
            "source_mode": "sensor",
            "source_entity": source.entity_id,
            "source_registry_id": source.id,
            "segment": "0001",
        },
        coordinator.repository.data["revision"],
    )
    # Dvě události uvnitř debounce okna nesmějí přepsat mezilehlý reset.
    hass.states.async_set(source.entity_id, "2", attributes)
    hass.states.async_set(source.entity_id, "3", attributes)
    await hass.async_block_till_done()
    renamed = registry.async_update_entity(source.entity_id, new_entity_id="sensor.renamed_gas")
    await hass.async_block_till_done()
    hass.states.async_set(renamed.entity_id, "4", attributes)
    await hass.async_block_till_done()
    await coordinator.async_flush_samples()
    samples = coordinator.repository.data["places"][PLACE]["samples"]
    assert {"100", "2", "3", "4"}.issubset({row["value"] for row in samples})
    assert all(row["entity"] == source.id for row in samples)
    assert hass.states.get(renamed.entity_id).state == "4"
    await hass.config_entries.async_unload(selected.entry_id)


async def test_service_rejects_non_admin_context(hass, hass_read_only_user):
    selected = await ready(hass)
    coordinator = selected.runtime_data
    revision = coordinator.repository.data["revision"]
    with pytest.raises(HomeAssistantError, match="administrator_required"):
        await hass.services.async_call(
            DOMAIN,
            "record_reading",
            {
                "entry_id": selected.entry_id,
                "place": PLACE,
                "meter": "0001",
                "value": "500",
                "observed_at": "2026-01-01T00:00:00Z",
            },
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    assert coordinator.repository.data["revision"] == revision
    await hass.config_entries.async_unload(selected.entry_id)
