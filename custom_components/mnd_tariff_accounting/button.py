"""Akce zařízení: přepočet a navigace do panelu/generátoru."""

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, PANEL_PATH


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [
            MndButton(entry.runtime_data, place, key)
            for place in entry.runtime_data.repository.data["places"]
            for key in ("recompute", "generate_dashboard")
        ]
    )


class MndButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, place, key):
        self.coordinator, self.place, self.key = coordinator, place, key
        account = coordinator.entry.data["account_id"]
        self._attr_unique_id = f"{account}:{place}:{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{account}:{place}")})
        self._attr_icon = (
            "mdi:view-dashboard-edit" if key == "generate_dashboard" else "mdi:calculator"
        )

    @property
    def extra_state_attributes(self):
        if self.key == "generate_dashboard":
            return {
                "panel_url": f"/{PANEL_PATH}?entry_id={self.coordinator.entry.entry_id}&place={self.place}&tab=dashboard"
            }
        return None

    async def async_press(self):
        # Backend tlačítko nemůže navigovat konkrétní prohlížeč. Otevře proto
        # v HA trvalou notifikaci s odkazem na správný účet, místo a generátor.
        # Neprovádí zápis Overview; ten potvrdí uživatel v náhledu panelu.
        if self.key == "recompute":
            await self.coordinator.async_recompute()
        else:
            from homeassistant.components import persistent_notification

            url = self.extra_state_attributes["panel_url"]
            persistent_notification.async_create(
                self.hass,
                f"[Generate dashboard]({url}) — náhled a přidání MND do Overview.",
                title="MND · Generate dashboard",
                notification_id=f"{DOMAIN}_dashboard_{self.coordinator.entry.entry_id}_{self.place}",
            )
