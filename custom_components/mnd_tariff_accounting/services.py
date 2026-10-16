"""Pojmenované HA akce nad stejnou transakční cestou jako formuláře.

Účet a místo jsou povinné, žádná volba první entry. Volání s uživatelským
kontextem vyžaduje správce. Interní důvěryhodné automatizace HA mají vlastní
kontext bez uživatele; souběh a idempotenci stále chrání Repository.
"""

import uuid

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .core.common import DataError


async def async_setup_services(hass):
    if hass.services.has_service(DOMAIN, "recompute"):
        return

    async def handle(call):
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise HomeAssistantError("administrator_required")
        from .api import _coordinator

        coordinator = _coordinator(hass, call.data["entry_id"])
        place = call.data["place"]
        if place not in coordinator.repository.data["places"]:
            raise HomeAssistantError("place_not_found")
        try:
            if call.service == "recompute":
                await coordinator.async_recompute()
            elif call.service == "refresh":
                await coordinator.async_refresh_cloud()
                await coordinator.async_recompute()
            elif call.service == "backfill":
                coordinator.history.start(place, max_segments=call.data.get("max_segments", 10))
            elif call.service == "cancel_history":
                await coordinator.history.cancel()
            elif call.service == "record_reading":
                record = {
                    key: value
                    for key, value in call.data.items()
                    if key not in ("entry_id", "place")
                }
                record.setdefault("id", str(uuid.uuid4()))
                await coordinator.async_edit(
                    place, "readings", record, coordinator.repository.data["revision"]
                )
            elif call.service in ("record_payment", "record_invoice", "update_tariff"):
                sections = {
                    "record_payment": "events",
                    "record_invoice": "invoices",
                    "update_tariff": "tariffs",
                }
                await coordinator.async_edit(
                    place,
                    sections[call.service],
                    call.data["record"],
                    coordinator.repository.data["revision"],
                )
        except DataError as err:
            raise HomeAssistantError(str(err)) from err

    base = {vol.Required("entry_id"): str, vol.Required("place"): str}
    for name in ("recompute", "refresh", "cancel_history"):
        hass.services.async_register(DOMAIN, name, handle, schema=vol.Schema(base))
    hass.services.async_register(
        DOMAIN,
        "backfill",
        handle,
        schema=vol.Schema(
            {
                **base,
                vol.Optional("max_segments", default=10): vol.All(int, vol.Range(min=1, max=100)),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "record_reading",
        handle,
        schema=vol.Schema(
            {
                **base,
                vol.Optional("id"): str,
                vol.Required("meter"): str,
                vol.Optional("segment"): str,
                vol.Required("value"): str,
                vol.Required("observed_at"): str,
                vol.Optional("note"): str,
                vol.Optional("supersedes"): str,
            }
        ),
    )
    for name in ("record_payment", "record_invoice", "update_tariff"):
        hass.services.async_register(
            DOMAIN, name, handle, schema=vol.Schema({**base, vol.Required("record"): dict})
        )
