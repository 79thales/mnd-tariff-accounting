"""Stručné výsledky pro dashboard; celé účetní dokumenty nejsou atributy entit."""

from datetime import date
from decimal import Decimal

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

SENSORS = {
    "latest_mnd": ("m³", "gas", None),
    "latest_mnd_date": (None, "date", None),
    "current_meter": ("m³", "gas", None),
    "volume_m3": ("m³", "gas", None),
    "energy_mwh": ("MWh", "energy", None),
    "known_cost_czk": ("CZK", "monetary", None),
    "paid_czk": ("CZK", "monetary", None),
    "prescribed_czk": ("CZK", "monetary", None),
    "assumed_paid_czk": ("CZK", "monetary", None),
    "balance_czk": ("CZK", "monetary", None),
    "surplus_czk": ("CZK", "monetary", None),
    "deficit_czk": ("CZK", "monetary", None),
    "status": (None, None, None),
    "cloud_status": (None, None, None),
    "current_deposit_czk": ("CZK", "monetary", None),
    "recommended_deposit_czk": ("CZK", "monetary", None),
    "mnd_assessment": (None, None, None),
    "mnd_payment_status": (None, None, None),
    "mnd_forecast_mwh": ("MWh", "energy", None),
    "mnd_readings_mwh": ("MWh", "energy", None),
    "mnd_past_estimate_mwh": ("MWh", "energy", None),
    "mnd_future_estimate_mwh": ("MWh", "energy", None),
    "invoice_result_czk": ("CZK", "monetary", None),
    "invoice_remaining_czk": ("CZK", "monetary", None),
}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        MndSensor(coordinator, place, key)
        for place in coordinator.repository.data["places"]
        for key in SENSORS
    )


class MndSensor(CoordinatorEntity, SensorEntity):
    """Korekce a změna období smějí snížit hodnotu, proto nejde o total_increasing."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, place_id, key):
        super().__init__(coordinator)
        self.place_id, self.key = place_id, key
        account = coordinator.entry.data["account_id"]
        self._attr_unique_id = f"{account}:{place_id}:{key}"
        self._attr_translation_key = key
        self._attr_native_unit_of_measurement, self._attr_device_class, self._attr_state_class = (
            SENSORS[key]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{account}:{place_id}")},
            name=coordinator.repository.data["places"][place_id]["name"] or "MND",
            manufacturer="Community integration",
            model="Gas accounting",
        )

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.place_id, {}).get(self.key)
        if value is None:
            return None
        if self.key == "latest_mnd_date":
            return date.fromisoformat(value)
        return Decimal(value) if SENSORS[self.key][0] else value

    @property
    def extra_state_attributes(self):
        data = (self.coordinator.data or {}).get(self.place_id, {})
        if self.key.startswith("mnd_"):
            if self.key in ("mnd_assessment", "mnd_payment_status"):
                return {
                    "source": "MND supplier message",
                    "acquired_at": data.get("deposit_acquired_at"),
                    "meaning": "supplier_notice_not_accounting_ledger",
                }
            return {
                "period_from": data.get("forecast_period_from"),
                "period_to": data.get("forecast_period_to"),
                "source": "MND",
                "meaning": "supplier_graph",
            }
        if self.key == "current_meter":
            return {
                "observed_at": data.get("current_at"),
                "quality": data.get("measurement_reason"),
            }
        if self.key in ("known_cost_czk", "balance_czk", "volume_m3", "energy_mwh"):
            return {
                "period_from": data.get("evaluated_from"),
                "period_to_exclusive": data.get("evaluated_to"),
                "estimated": data.get("estimated"),
                "complete": data.get("complete"),
            }
        if self.key != "status":
            return None
        return {
            key: data[key]
            for key in ("warnings", "estimated", "archive_revision", "measurement_reason")
            if key in data
        }
