"""Stručné výsledky pro dashboard; celé účetní dokumenty nejsou atributy entit."""

from datetime import date
from decimal import Decimal

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PANEL_PATH

SENSORS = {
    "current_flow_m3h": ("m³/h", "volume_flow_rate", None),
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
    "billing_paid_czk": ("CZK", "monetary", None),
    "billing_plan_czk": ("CZK", "monetary", None),
    "billing_cost_czk": ("CZK", "monetary", None),
    "billing_forecast_cost_czk": ("CZK", "monetary", None),
    "billing_forecast_balance_czk": ("CZK", "monetary", None),
    "billing_actual_mwh": ("MWh", "energy", None),
    "billing_forecast_mwh": ("MWh", "energy", None),
    "billing_volume_m3": ("m³", "gas", None),
    "own_forecast_balance_czk": ("CZK", "monetary", None),
    "own_forecast_cost_czk": ("CZK", "monetary", None),
    "own_forecast_mwh": ("MWh", "energy", None),
    "own_actual_mwh": ("MWh", "energy", None),
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
            configuration_url=(
                f"homeassistant://{PANEL_PATH}?entry_id="
                f"{coordinator.entry.entry_id}&place={place_id}&tab=editor"
            ),
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
        if self.key.startswith("own_"):
            own = data.get("own_billing", {})
            return {
                "period_from": own.get("period_from"),
                "period_to_exclusive": own.get("period_to"),
                "measured_at": own.get("measured_at"),
                "calculated_at": own.get("calculated_at"),
                "quality": own.get("status"),
                "reason": own.get("reason"),
                "method": own.get("method"),
                "profile_complete_days": own.get("profile_complete_days"),
                "profile_required_days": own.get("profile_required_days"),
                "profile_missing_months": own.get("profile_missing_months"),
                "interpolated_days": own.get("interpolated_days"),
                "month_days": own.get("month_days"),
                # Počty uvádějí kvalitu výhledu bez vydávání předpokladů za platbu.
                "assumed_advance_count": len(own.get("assumed_advances") or []),
                "history_conflict_count": len(own.get("history_conflicts") or []),
                "boundary_estimated": own.get("boundary_estimated"),
                "history_source_assumed": own.get("history_source_assumed"),
                "live_status": own.get("live_status"),
                "conversion_estimated": own.get("conversion_estimated"),
                "intraday_estimated": own.get("intraday_estimated"),
                "warnings": own.get("warnings"),
            }
        if self.key.startswith("billing_"):
            billing = data.get("billing", {})
            return {
                "period_from": billing.get("from"),
                "period_to": billing.get("to"),
                "source": billing.get("source"),
                "confirmed_invoice": billing.get("confirmed_invoice"),
                "estimated": ("forecast" in self.key and not billing.get("confirmed_invoice"))
                or (self.key == "billing_cost_czk" and billing.get("known_cost_estimated", False)),
                "complete": billing.get("known_cost_complete")
                if self.key == "billing_cost_czk"
                else None,
                "meaning": "supplier_billing_period",
            }
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
        if self.key == "current_flow_m3h":
            return {"reported_at": data.get("flow_at"), "quality": data.get("flow_status")}
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
