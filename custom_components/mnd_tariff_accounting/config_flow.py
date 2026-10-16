"""Konfigurace importního účtu a nativních zdrojů, bez REST tokenu k HA."""

from __future__ import annotations

import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .const import DOMAIN, PANEL_PATH
from .core.common import DataError, fingerprint, identity
from .core.portal_mapping import supply_point
from .portal import AuthenticationRequired, PortalClient, PortalError


class MndConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Importní profil začíná bez osobních údajů a neměnných cenových předpokladů."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(step_id="user", menu_options=["import_profile", "cloud"])

    async def async_step_import_profile(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                place = identity(user_input["supply_point"])
            except DataError:
                errors["supply_point"] = "invalid_supply_point"
            else:
                account_id = str(uuid.uuid4())
                await self.async_set_unique_id(user_input["profile_id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input["name"],
                    data={
                        "account_id": account_id,
                        "profile_id": user_input["profile_id"],
                        "mode": "import",
                        "places": [{"id": place, "name": user_input["name"]}],
                    },
                )
        return self.async_show_form(
            step_id="import_profile",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default="MND"): str,
                    vol.Required("profile_id"): str,
                    vol.Required("supply_point"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_cloud(self, user_input=None):
        """Uživatel zadá přístupy do HA formuláře; výpisy a archiv je neobsahují.

        Bez volby remember se zachová pouze relace v paměti a po restartu
        je vyžadováno nové přihlášení. MFA a odlišné schéma neobcházíme.
        """
        errors = {}
        if user_input is not None:
            portal = PortalClient(async_get_clientsession(self.hass))
            try:
                partners = await portal.login(user_input["username"], user_input["password"])
                profile = await portal.profile(partners[0]["PARTNER_ID"])
                if not isinstance(profile, dict) or profile.get("InaId") is None:
                    raise PortalError("portal_schema_changed")
                account_id = fingerprint(["mnd_account", str(profile["InaId"])])
                if self.context.get("source") == "reauth":
                    entry = self._get_reauth_entry()
                    if entry.data["account_id"] != account_id:
                        return self.async_abort(reason="wrong_account")
                    self.hass.data.setdefault(DOMAIN + "_sessions", {})[account_id] = portal
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            "username": user_input["username"],
                            "password": user_input["password"] if user_input["remember"] else None,
                        },
                    )
                await self.async_set_unique_id(account_id)
                self._abort_if_unique_id_configured()
                places = []
                for partner in partners:
                    rows = await portal.supply_points(partner["PARTNER_ID"])
                    for row in rows:
                        mapped = supply_point(row, partner["PARTNER_ID"])
                        if not mapped["id"].isdigit():
                            places.append(mapped)
                if not places:
                    raise DataError("no_gas_places")
                self._cloud = {
                    "portal": portal,
                    "places": places,
                    "account_id": account_id,
                    "username": user_input["username"],
                    "password": user_input["password"] if user_input["remember"] else None,
                }
                return await self.async_step_places()
            except AuthenticationRequired:
                errors["base"] = "invalid_auth"
            except (PortalError, DataError):
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Required("remember", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_places(self, user_input=None):
        choices = {
            place["id"]: place["name"] + " · " + place["id"] for place in self._cloud["places"]
        }
        if user_input is not None:
            selected = [p for p in self._cloud["places"] if p["id"] in user_input["places"]]
            if selected:
                data = {
                    key: value
                    for key, value in self._cloud.items()
                    if key not in ("portal", "places")
                }
                data.update(mode="cloud", places=selected)
                self.hass.data.setdefault(DOMAIN + "_sessions", {})[data["account_id"]] = (
                    self._cloud["portal"]
                )
                return self.async_create_entry(title="MND", data=data)
        return self.async_show_form(
            step_id="places",
            data_schema=vol.Schema(
                {
                    vol.Required("places"): cv.multi_select(choices),
                }
            ),
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_cloud()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MndOptionsFlow()


class MndOptionsFlow(config_entries.OptionsFlow):
    """Formuláře účtů jsou v panelu; options nabízí jednoznačnou navigaci."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(self.config_entry.options))
        return self.async_show_form(
            step_id="init",
            description_placeholders={
                "panel_url": f"/{PANEL_PATH}?entry_id={self.config_entry.entry_id}",
            },
            data_schema=vol.Schema({}),
        )
