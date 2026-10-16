"""Syntetická regrese nativního Recorder adaptéru a obnovy originálů."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mnd_tariff_accounting.const import DOMAIN
from custom_components.mnd_tariff_accounting.recorder import async_read_history

PLACE = "27ZG000Z0000000X"
PREFIX = "custom_components.mnd_tariff_accounting."


async def ready(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Synthetic",
        unique_id="billing-tests",
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


async def test_pulse_statistics_use_explicit_volume_and_preserve_two_source_series(hass):
    hass.config.set_time_zone("UTC")
    entry = await ready(hass)
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    source = registry.async_get_or_create("sensor", DOMAIN, "synthetic-pulses", config_entry=entry)
    await coordinator.async_edit(
        PLACE,
        "settings",
        {
            "source_registry_id": "derived",
            "history_registry_id": source.id,
            "history_unit_m3": ".01",
            "segment": "synthetic-meter",
        },
        coordinator.repository.data["revision"],
    )
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {
            "start": (first + timedelta(hours=h)).timestamp(),
            "state": 100 + h,
            "sum": 100 + h,
            "change": 1,
        }
        for h in range(-1, 24)
    ]

    # Ověříme skutečnou integrační transakci a denní profil. Databázová
    # hrana má syntetické hodiny; původní statistiky cizí entity se nemění.
    async def executor(func):
        return func()

    recorder = SimpleNamespace(async_add_executor_job=executor)
    with (
        patch(PREFIX + "recorder.get_instance", return_value=recorder),
        patch(
            PREFIX + "recorder.get_metadata",
            return_value={source.entity_id: (1, {"unit_of_measurement": "pulse", "has_sum": True})},
        ),
        patch(PREFIX + "recorder.statistics_during_period", return_value={source.entity_id: rows}),
        patch(PREFIX + "recorder.get_significant_states", return_value={}),
    ):
        result = await async_read_history(coordinator, PLACE, "2026-01-01", "2026-01-02")
    assert result["complete_days"] == 1
    profile = coordinator.repository.data["places"][PLACE]["daily_profile"]
    assert profile[0]["m3"] == "0.24"
    assert profile[0]["entity"] == source.id
    assert profile[0]["original_unit"] == "pulse"
    assert profile[0]["volume_per_unit_m3"] == "0.01"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_document_refresh_keeps_original_and_current_price_with_revision_cache(hass):
    entry = await ready(hass)
    coordinator = entry.runtime_data
    row = {
        "id": "synthetic-invoice",
        "number": "S-1",
        "revision": "synthetic-revision",
        "from": "2026-01-01",
        "to_inclusive": "2026-01-31",
    }
    invoice_text = f"MND {PLACE} S-1\nFakturovaná částka za odběr plynu 1 210 Kč\nCelková platba za dodávku plynu a souvisejících služeb s DPH 1 210 Kč\n1. 1. 2026 - 31. 1. 2026\nPŘEPLATEK 100 Kč\n(TDD): DOM1"
    tariff_text = "MND Ceny platné od 1. 1. 2026\nROČNÍ ODBĚR\nCELKOVÁ CENA\n0 20 121 [100]\n12,10 [10]\n242 [200]\n24,20 [20]\n363 [300]\n36,30 [30]"

    def seed(data):
        place = data["places"][PLACE]
        place["settings"]["portal"] = {"cp_id": 1, "contract_id": 2}
        place["portal_evidence"] = {
            "invoices": {"rows": [row]},
            "documents": [{"TYPE": "PRNOW", "CONT_DATE_FROM": "2026-01-01"}],
            "details": {
                "CPE_CONS_AVE_YEAR": "10",
                "BusinessAlgorithm": {
                    "PriceListUnitPrices": {"Spot": False, "ValidTo": "2028-12-31"}
                },
            },
        }

    await coordinator.repository.transact(seed)
    coordinator.portal.invoice_pdf = AsyncMock(
        return_value=(invoice_text.encode(), "synthetic-invoice.pdf")
    )
    coordinator.portal.download_contract = AsyncMock(
        return_value=(tariff_text.encode(), "synthetic-tariff.pdf")
    )
    with patch(PREFIX + "core.mnd_documents.pdf_text", side_effect=lambda value: value.decode()):
        assert await coordinator._refresh_billing_documents(PLACE) == []
        assert await coordinator._refresh_billing_documents(PLACE) == []
    place = coordinator.repository.data["places"][PLACE]
    assert place["invoice_evidence"][0]["cost_czk"] == "1210"
    assert place["invoice_evidence"][0]["invoice_result_czk"] == "100"
    assert place["price_evidence"]["verified"] is True
    assert len(place["artifacts"]) == 2
    assert not place["invoices"]  # Čtení originálu nepotvrzuje ruční účetnictví.
    assert coordinator.portal.invoice_pdf.await_count == 1
    await hass.config_entries.async_unload(entry.entry_id)
