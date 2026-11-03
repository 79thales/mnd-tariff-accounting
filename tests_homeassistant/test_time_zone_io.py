"""Regrese časových hranic a asynchronního načítání pásma pro Recorder."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfoNotFoundError

import pytest
from homeassistant.util import dt as dt_util

from custom_components.mnd_tariff_accounting.boiler import async_energy_summary
from custom_components.mnd_tariff_accounting.core.common import local_day
from custom_components.mnd_tariff_accounting.recorder import async_read_history
from custom_components.mnd_tariff_accounting.time_zone import async_configured_time_zone

PREFIX = "custom_components.mnd_tariff_accounting."


async def test_configured_zone_supports_local_day_without_loading_again(hass):
    """Předané pásmo zachová datum na hranici dne a chybějící pásmo odmítne."""
    hass.config.time_zone = "Europe/Prague"
    zone = await async_configured_time_zone(hass)
    assert local_day(datetime(2026, 3, 28, 23, 30, tzinfo=timezone.utc), zone).isoformat() == (
        "2026-03-29"
    )
    lookup = AsyncMock(return_value=None)
    with patch(PREFIX + "time_zone.dt_util.async_get_time_zone", lookup):
        with pytest.raises(ZoneInfoNotFoundError):
            await async_configured_time_zone(hass)
    lookup.assert_awaited_once_with("Europe/Prague")


@pytest.mark.parametrize(
    ("day", "next_day", "hours", "month_utc"),
    [("2026-03-29", "2026-03-30", 23, "2026-02-28T23:00:00+00:00"),
     ("2026-10-25", "2026-10-26", 25, "2026-09-30T22:00:00+00:00")],
)
async def test_recorder_and_boiler_dst_boundaries(hass, day, next_day, hours, month_utc):
    """Hodinové syntetické řady ověří hranice, součet a opakované načtení."""
    zone = await dt_util.async_get_time_zone("Europe/Prague")
    assert zone is not None
    hass.config.time_zone = "Europe/Prague"
    left = datetime.fromisoformat(day).replace(tzinfo=zone)
    right = datetime.fromisoformat(next_day).replace(tzinfo=zone)
    utc_left, utc_right = left.astimezone(timezone.utc), right.astimezone(timezone.utc)
    assert (utc_right - utc_left).total_seconds() == hours * 3600
    rows = [
        {"start": (utc_left + timedelta(hours=i)).timestamp(),
         "state": 100 + i, "sum": 100 + i, "change": 1}
        for i in range(-1, hours)
    ]
    source = SimpleNamespace(id="synthetic-id", entity_id="sensor.synthetic")
    registry = SimpleNamespace(async_get=lambda _: source)
    data = {"places": {"place": {"settings": {"history_registry_id": source.id,
            "segment": "meter"}, "samples": [], "daily_profile": []}}}

    async def transact(mutate):
        mutate(data)

    repository = SimpleNamespace(data=data, transact=transact)
    coordinator = SimpleNamespace(hass=hass, repository=repository, _closed=False,
                                  async_recompute=AsyncMock())

    async def executor(job):
        return await hass.async_add_executor_job(job)

    recorder = SimpleNamespace(async_add_executor_job=executor)
    tz_lookup = AsyncMock(return_value=zone)
    hass.config.components.add("recorder")
    try:
        with (
            patch(PREFIX + "recorder.er.async_get", return_value=registry),
            patch(PREFIX + "boiler.er.async_get", return_value=registry),
            patch(PREFIX + "recorder.dt_util.async_get_time_zone", tz_lookup),
            patch(PREFIX + "boiler.dt_util.utcnow", return_value=utc_right),
            patch(PREFIX + "recorder.get_instance", return_value=recorder),
            patch("homeassistant.components.recorder.get_instance", return_value=recorder),
            patch(PREFIX + "recorder.get_metadata", return_value={source.entity_id: (1, {"unit_of_measurement": "m³", "has_sum": True})}),
            patch(PREFIX + "recorder.statistics_during_period", return_value={source.entity_id: rows}) as history_query,
            patch(PREFIX + "recorder.get_significant_states", return_value={}) as states_query,
            patch("homeassistant.components.recorder.statistics.get_metadata", return_value={source.entity_id: (1, {"unit_of_measurement": "kWh", "has_sum": True})}),
            patch("homeassistant.components.recorder.statistics.statistics_during_period", return_value={source.entity_id: rows}) as energy_query,
        ):
            result = await async_read_history(coordinator, "place", day, next_day)
            await async_read_history(coordinator, "place", day, next_day)
            assert result["complete_days"] == 1
            assert len(data["places"]["place"]["daily_profile"]) == 1
            assert data["places"]["place"]["daily_profile"][0]["m3"] == str(hours)
            assert states_query.call_args.args[1:3] == (left, right)
            assert history_query.call_args.args[2] == right
            # Čas těsně před místní půlnocí stále patří testovanému dni.
            with patch(PREFIX + "boiler.dt_util.utcnow", return_value=utc_right - timedelta(seconds=1)):
                energy = await async_energy_summary(coordinator, {"boiler_enabled": True,
                    "boiler_energy_entity": source.entity_id, "boiler_energy_registry_id": source.id})
            assert energy["today"]["expected_closed_hours"] == hours - 1
            assert energy["today"]["value_kwh"] == str(hours - 1)
            assert energy_query.call_args.args[1].astimezone(timezone.utc) == datetime.fromisoformat(month_utc) - timedelta(hours=1)
            assert tz_lookup.await_count == 3
            tz_lookup.assert_awaited_with("Europe/Prague")
    finally:
        hass.config.components.remove("recorder")


async def test_missing_zone_preserves_error_before_recorder_and_transaction(hass):
    """Neznámé pásmo nesmí být nahrazeno pásmem hostitele ani zapsat data."""
    hass.config.time_zone = "Invalid/Zone"
    source = SimpleNamespace(id="id", entity_id="sensor.synthetic")
    coordinator = SimpleNamespace(hass=hass, _closed=False, repository=SimpleNamespace(
        data={"places": {"place": {"settings": {"history_registry_id": "id"}}}},
        transact=AsyncMock()))
    lookup = AsyncMock(return_value=None)
    hass.config.components.add("recorder")
    try:
        with (patch(PREFIX + "recorder.er.async_get", return_value=SimpleNamespace(async_get=lambda _: source)),
              patch(PREFIX + "boiler.er.async_get", return_value=SimpleNamespace(async_get=lambda _: source)),
              patch(PREFIX + "recorder.dt_util.async_get_time_zone", lookup),
              patch(PREFIX + "recorder.get_instance") as get_recorder):
            with pytest.raises(ZoneInfoNotFoundError):
                await async_read_history(coordinator, "place", "2026-01-01", "2026-01-02")
            with pytest.raises(ZoneInfoNotFoundError):
                await async_energy_summary(coordinator, {"boiler_enabled": True, "boiler_energy_entity": source.entity_id})
            assert lookup.await_count == 2
            get_recorder.assert_not_called()
            coordinator.repository.transact.assert_not_awaited()
    finally:
        hass.config.components.remove("recorder")
