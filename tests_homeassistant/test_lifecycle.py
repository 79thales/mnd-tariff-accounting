"""Lifecycle, Store, registry a formuláře proti skutečné verzi HA z CI matice.

Pouze syntetická data v dočasné konfiguraci. Nespouští zákaznické MND ani
neinstaluje integraci do provozního HA. Používá standardní HA fixtures;
samostatný test obejde mock_storage a ověří skutečný zápis v dočasné složce.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import CoreState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mnd_tariff_accounting.const import DOMAIN
from custom_components.mnd_tariff_accounting.core.common import DataError
from custom_components.mnd_tariff_accounting.storage import ConfirmedStore

PLACE = "27ZG000Z0000000X"
# Uloženo před aktivací fixture mock_storage, abychom samostatně ověřili
# i skutečný atomický zápis na disk, nikoli pouze paměťové úložiště pluginu.
_REAL_STORE_WRITE = Store._async_write_data


def entry():
    return MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic MND",
        unique_id="synthetic-profile",
        data={
            "account_id": "synthetic-account",
            "mode": "import",
            "places": [{"id": PLACE, "name": "Synthetic"}],
        },
    )


async def test_import_config_flow_and_duplicate(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_profile"}
    )
    assert result["step_id"] == "import_profile"
    with patch("custom_components.mnd_tariff_accounting.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Synthetic", "profile_id": "profile-1", "supply_point": PLACE},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["mode"] == "import"


async def test_abandoned_cloud_flow_can_resume_after_authenticated_confirmation(hass):
    """Pád mobilu po přihlášení nevyžaduje restart celé domácnosti."""
    portal = AsyncMock()
    portal.login.return_value = [{"PARTNER_ID": 7}]
    portal.profile.return_value = {"InaId": "synthetic-account"}
    portal.supply_points.return_value = [
        {"CPE_EAN": PLACE, "CP_ID": 7, "CONT_ID": 8, "CP_NAME": "Synthetic", "CUSTA_ID": 9}
    ]

    async def login():
        flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        await hass.config_entries.flow.async_configure(flow["flow_id"], {"next_step_id": "cloud"})
        return await hass.config_entries.flow.async_configure(
            flow["flow_id"],
            {"username": "synthetic@example.invalid", "password": "synthetic", "remember": False},
        )

    with patch(
        "custom_components.mnd_tariff_accounting.config_flow.PortalClient", return_value=portal
    ):
        first = await login()
        assert first["step_id"] == "places"
        second = await login()
        assert second["step_id"] == "resume"
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {"confirm": True}
        )
        assert second["step_id"] == "places"
        assert first["flow_id"] not in [
            f["flow_id"] for f in hass.config_entries.flow.async_progress()
        ]
        with patch("custom_components.mnd_tariff_accounting.async_setup_entry", return_value=True):
            result = await hass.config_entries.flow.async_configure(
                second["flow_id"], {"places": [PLACE]}
            )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_device_configuration_and_hidden_admin_panel(hass):
    from homeassistant.components.frontend import DATA_PANELS

    from custom_components.mnd_tariff_accounting.api import _place_device

    selected = entry()
    selected.add_to_hass(hass)
    assert await hass.config_entries.async_setup(selected.entry_id)
    device = _place_device(hass, selected, PLACE)
    assert device.configuration_url.startswith("homeassistant://mnd-tariff-accounting?")
    assert f"place={PLACE}" in device.configuration_url
    assert hass.data[DATA_PANELS]["mnd-tariff-accounting"].sidebar_title is None
    await hass.config_entries.async_unload(selected.entry_id)


async def test_finance_refresh_repairs_customer_identity_and_preserves_data_on_failure(hass):
    """Živé HA adaptéry, syntetické portálové odpovědi, žádné bankovní operace."""
    from custom_components.mnd_tariff_accounting.portal import PortalError

    selected = entry()
    selected.add_to_hass(hass)
    assert await hass.config_entries.async_setup(selected.entry_id)
    coordinator = selected.runtime_data
    source = {"partner_id": 1, "cp_id": 7, "contract_id": 8, "customer_id": None}
    await coordinator.repository.transact(
        lambda data: data["places"][PLACE].update(
            settings={"portal": source},
            portal_evidence={"details": {"CPE_EAN": PLACE, "CP_ID": 7, "CUSTA_ID": 9}},
        )
    )
    portal = AsyncMock()
    advance = {
        "ADVI_ID": 1,
        "CP_ID": 7,
        "CUSTA_ID": 9,
        "ADVI_DATE": "2026-01-15",
        "ADVI_SUMTOTAL": "1000",
        "ADVI_BALANCE": "750",
        "CURRENCY": {"code": "CZK"},
        "PayInfo": [{"PAY_DATE": "2026-01-14", "PAY_AMOUNT": "250"}],
    }
    portal.finance_list.side_effect = [
        {"rows": [advance], "complete": True},
        {"rows": [], "complete": True},
    ]
    portal.finance_detail.return_value = advance
    coordinator.portal = portal
    assert await coordinator._refresh_finance(PLACE, source) == []
    saved = coordinator.repository.data["places"][PLACE]
    assert saved["settings"]["portal"]["customer_id"] == 9
    assert saved["portal_evidence"]["advances"]["rows"][0]["paid"] == "250"
    portal.finance_list.side_effect = PortalError("portal_unavailable")
    assert await coordinator._refresh_finance(PLACE, source)
    saved = coordinator.repository.data["places"][PLACE]
    assert saved["portal_evidence"]["advances"]["rows"][0]["paid"] == "250"
    assert saved["portal_evidence"]["errors"]["advances"]["reason"] == "portal_unavailable"
    await hass.config_entries.async_unload(selected.entry_id)


async def test_setup_entities_store_reload_and_unload(hass):
    selected = entry()
    selected.add_to_hass(hass)
    assert await hass.config_entries.async_setup(selected.entry_id)
    await hass.async_block_till_done()
    coordinator = selected.runtime_data
    assert coordinator.repository.data["places"][PLACE]["readings"] == []
    assert coordinator.data[PLACE]["latest_mnd"] is None
    revision = coordinator.repository.data["revision"]
    await coordinator.async_edit(
        PLACE,
        "readings",
        {
            "id": "manual-1",
            "meter": "0001",
            "value": "1000.5",
            "observed_at": "2026-01-01T12:00:00+01:00",
        },
        revision,
    )
    assert coordinator.repository.data["places"][PLACE]["readings"][0]["value"] == "1000.5"
    assert await hass.config_entries.async_reload(selected.entry_id)
    await hass.async_block_till_done()
    assert len(selected.runtime_data.repository.data["places"][PLACE]["readings"]) == 1
    reloaded = selected.runtime_data
    assert await hass.config_entries.async_unload(selected.entry_id)
    assert coordinator._closed and reloaded._closed


async def test_store_failure_is_not_successful_commit(hass):
    selected = entry()
    selected.add_to_hass(hass)
    assert await hass.config_entries.async_setup(selected.entry_id)
    coordinator = selected.runtime_data
    before = coordinator.repository.data["revision"]
    # Plugin nahrazuje základní _async_write_data. Chybu proto vstříkneme
    # do tohoto rozhraní pod naším ConfirmedStore, aby se ověřil jeho převod.
    with patch.object(Store, "_async_write_data", side_effect=WriteError("synthetic disk failure")):
        with pytest.raises(HomeAssistantError, match="mnd_archive_write_failed"):
            await coordinator.repository.transact(lambda data: data.update(marker=True))
    assert coordinator.repository.data["revision"] == before
    assert "marker" not in coordinator.repository.data
    await hass.config_entries.async_unload(selected.entry_id)


async def test_real_atomic_store_writes_disk_and_propagates_failure(hass, tmp_path):
    """Skutečný soubor v dočasné složce; pád zapisovače nezmění uložený obsah."""
    store = ConfirmedStore(
        hass,
        1,
        "mnd.synthetic-disk",
        private=True,
        atomic_writes=True,
        serialize_in_event_loop=False,
    )
    target = tmp_path / "archive.json"
    store.path = str(target)
    with patch.object(Store, "_async_write_data", _REAL_STORE_WRITE):
        await store.async_save({"revision": 1})
        assert json.loads(target.read_text())["data"] == {"revision": 1}
        with patch.object(
            store, "_write_prepared_data", side_effect=WriteError("synthetic full disk")
        ):
            with pytest.raises(HomeAssistantError, match="mnd_archive_write_failed"):
                await store.async_save({"revision": 2})
        assert json.loads(target.read_text())["data"] == {"revision": 1}


async def test_unknown_archive_version_refuses_setup_without_erasing(hass):
    selected = entry()
    selected.add_to_hass(hass)
    with patch(
        "custom_components.mnd_tariff_accounting.coordinator.ConfirmedStore.async_load",
        return_value={"schema_version": 999},
    ):
        assert not await hass.config_entries.async_setup(selected.entry_id)


async def test_stopping_store_finishes_write_before_acknowledgement(hass):
    store = ConfirmedStore(hass, 1, "mnd.synthetic-stopping", private=True)
    hass.set_state(CoreState.stopping)
    with patch.object(store, "_async_write_data") as writer:
        await store.async_save({"revision": 42})
    writer.assert_awaited_once()
    assert writer.await_args.args[0]["data"]["revision"] == 42
    assert store._data is None
    hass.set_state(CoreState.not_running)


async def test_read_only_store_cannot_acknowledge_accounting_commit(hass):
    store = ConfirmedStore(hass, 1, "mnd.synthetic-read-only", private=True)
    store.make_read_only()
    with pytest.raises(HomeAssistantError, match="mnd_archive_read_only"):
        await store.async_save({"revision": 42})


async def test_invalid_grid_is_atomic_and_does_not_emit_source_states(hass):
    selected = entry()
    selected.add_to_hass(hass)
    assert await hass.config_entries.async_setup(selected.entry_id)
    coordinator = selected.runtime_data
    await coordinator.async_edit(
        PLACE,
        "settings",
        {"period_from": "2026-01-01", "period_to": "2026-03-01"},
        coordinator.repository.data["revision"],
    )
    before = coordinator.repository.data["revision"]
    with pytest.raises(DataError):
        await coordinator.async_edit(
            PLACE,
            "advance_grid",
            {
                "id": "grid-op",
                "rows": [
                    {"month": "2026-01", "prescribed": "500"},
                    {"month": "2026-02", "prescribed": "-1"},
                ],
            },
            before,
        )
    assert coordinator.repository.data["revision"] == before
    assert coordinator.repository.data["places"][PLACE]["events"] == []
    await hass.config_entries.async_unload(selected.entry_id)
