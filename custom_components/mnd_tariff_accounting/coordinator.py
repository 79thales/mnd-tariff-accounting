"""Koordinace entry: transakce, lokální měření a časované přepočty.

Události senzoru se slučují po 30 s, účetnictví je bez sítě. Každá změna
má revizi; výsledek staršího výpočtu se nepublikuje přes novější data.
Relace cloudu je oddělená od dostupnosti místního archivu.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import logging
from datetime import timedelta
from functools import partial
from pathlib import Path

from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, POLL_HOURS, SOURCE_DEBOUNCE_SECONDS
from .core.archive import Repository, apply_import, new_place
from .core.backup import parse_native, parse_zip, restore_place
from .core.common import DataError, decimal, fingerprint, identity, load_json, wire
from .core.forecast import add_snapshot
from .core.importer import parse_v1
from .core.invoice_pdf import parse_invoice_pdf
from .core.portal_mapping import consumption_periods, portal_readings
from .core.projection import evaluate_place
from .core.xlsx import parse_workbook
from .history import HistoryRunner
from .portal import AuthenticationRequired, PortalClient, PortalError
from .storage import ConfirmedStore, put_artifact

_LOGGER = logging.getLogger(__name__)


class MndCoordinator(DataUpdateCoordinator):
    """Vlastní archiv je zdroj pravdy, chyby cloudu ho nemažou.

    Síťový polling je po šesti hodinách až po připojení účtu. Aktuální
    implementace načítá místa explicitní akcí, dokud nejsou ověřené mapy
    odpovědí jednotlivých zákaznických objektů. Import i měření fungují offline.
    """

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(hours=POLL_HOURS),
        )
        self.entry = entry
        self.store = ConfirmedStore(
            hass,
            1,
            f"{DOMAIN}.archive_{entry.entry_id}",
            private=True,
            atomic_writes=True,
            serialize_in_event_loop=False,
        )
        self.repository = None
        self.portal = PortalClient(async_get_clientsession(hass))
        self.artifact_root = Path(
            hass.config.path(".storage", f"{DOMAIN}_documents", entry.entry_id)
        )
        self._unsubscribers = []
        self._registry_unsubscribe = None
        self._debounce = None
        self._closed = False
        self._pending_samples = {}
        self._recompute_lock = asyncio.Lock()
        self.cloud_status = "not_connected"
        self.history = HistoryRunner(self)
        self._cloud_lock = asyncio.Lock()

    async def async_initialize(self):
        """Původní Store nesmí zmizet při neplatné verzi; setup selže s reason code."""
        existed = await self.hass.async_add_executor_job(Path(self.store.path).exists)
        saved = await self.store.async_load()
        if existed and saved is None:
            raise DataError("archive_corrupt_or_missing")
        self.repository = Repository(self.entry.data["account_id"], saved, self.store.async_save)
        if not self.repository.data["places"]:

            def initial(data):
                for place in self.entry.data.get("places", []):
                    data["places"][identity(place["id"])] = new_place(place.get("name", ""))
                    if self.entry.data.get("mode") == "cloud":
                        data["places"][place["id"]]["settings"]["portal"] = {
                            key: place[key]
                            for key in ("cp_id", "contract_id", "partner_id", "customer_id")
                        }

            await self.repository.transact(initial)
        self._subscribe_sources()
        self._registry_unsubscribe = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._registry_changed
        )
        if self.entry.data.get("mode") == "cloud":
            pending = self.hass.data.get(DOMAIN + "_sessions", {}).pop(
                self.entry.data["account_id"], None
            )
            if pending:
                self.portal = pending
                self.cloud_status = "connected"
            elif self.entry.data.get("password"):
                try:
                    await self.portal.login(
                        self.entry.data["username"], self.entry.data["password"]
                    )
                    self.cloud_status = "connected"
                except AuthenticationRequired:
                    self.cloud_status = "reauth_required"
                    self.entry.async_start_reauth(self.hass)
                except PortalError as err:
                    self.cloud_status = str(err)
            else:
                self.cloud_status = "reauth_required"
                self.entry.async_start_reauth(self.hass)
        await self.async_recompute()
        if self.cloud_status == "connected":
            self.entry.async_create_background_task(
                self.hass, self.async_request_refresh(), "mnd-initial-refresh"
            )

    def _subscribe_sources(self):
        registry = er.async_get(self.hass)
        for place_id, place in self.repository.data["places"].items():
            settings = place["settings"]
            source = registry.async_get(settings.get("source_entity", ""))
            if settings.get("source_registry_id"):
                source = registry.async_get(settings["source_registry_id"])
            if not source or settings.get("source_mode") != "sensor":
                continue

            @callback
            def changed(event, selected=place_id, source_id=source.id):
                self._queue_sample(selected, source_id, event.data.get("new_state"))

            self._unsubscribers.append(
                async_track_state_change_event(self.hass, [source.entity_id], changed)
            )
            self._queue_sample(place_id, source.id, self.hass.states.get(source.entity_id))

    @callback
    def _registry_changed(self, event):
        """Přejmenování entity obnoví odběr podle UUID bez změny měřicího segmentu.

        Registry událost nenahrazuje měření. Při odstranění nebo nedostupném
        stavu se uloží mezera; samotné přejmenování neprovede kalibraci.
        """
        if self._closed:
            return
        affected = {event.data.get("entity_id"), event.data.get("old_entity_id")}
        registry = er.async_get(self.hass)
        for place_id, place in self.repository.data["places"].items():
            settings = place["settings"]
            source_id = settings.get("source_registry_id")
            current = registry.async_get(source_id) if source_id else None
            if settings.get("source_entity") not in affected and (
                not current or current.entity_id not in affected
            ):
                continue
            if current is None and source_id:
                self._queue_sample(place_id, source_id, None)
            for unsubscribe in self._unsubscribers:
                unsubscribe()
            self._unsubscribers.clear()
            self._subscribe_sources()
            break

    def _queue_sample(self, place_id, source_id, state):
        """Zachová i unknown/unavailable a mezilehlý reset; debounce nesmaže události."""
        if self._closed:
            return
        place = self.repository.data["places"][place_id]
        attributes = state.attributes if state else {}
        raw = state.state if state else None
        try:
            value = (
                decimal(raw, optional=True, nonnegative=True)
                if raw not in ("unknown", "unavailable")
                else None
            )
        except DataError:
            # Nenumerický či záporný report je mezera měření. Nezablokuje
            # persistenci dalších událostí a není nahrazen nulovou spotřebou.
            value = None
        sample = {
            "entity": source_id,
            "segment": place["settings"].get("segment", ""),
            "unit": attributes.get("unit_of_measurement"),
            "state_class": attributes.get("state_class"),
            "at": (
                getattr(state, "last_reported", None)
                or getattr(state, "last_updated", None)
                or dt_util.utcnow()
            ).isoformat(),
            "value": str(value) if value is not None else None,
            "continuity": state is not None and value is not None,
        }
        self._pending_samples.setdefault(place_id, []).append(sample)
        if self._debounce is None:
            self._debounce = async_call_later(
                self.hass, SOURCE_DEBOUNCE_SECONDS, self._flush_callback
            )

    async def _flush_callback(self, _now):
        self._debounce = None
        await self.async_flush_samples()

    async def async_flush_samples(self):
        pending, self._pending_samples = self._pending_samples, {}
        if not pending:
            return

        def update(data):
            for place_id, rows in pending.items():
                data["places"][place_id]["samples"].extend(rows)

        try:
            await self.repository.transact(update)
        except BaseException:
            for place_id, rows in pending.items():
                self._pending_samples.setdefault(place_id, [])[0:0] = rows
            raise
        await self.async_recompute()

    async def _async_update_data(self):
        """Pravidelný přepočet je nezávislý na přihlášení a neztrácí poslední import."""
        if self.entry.data.get("mode") == "cloud" and self.portal.authenticated:
            await self.async_refresh_cloud()
        return await self._evaluate()

    async def async_refresh_cloud(self):
        """Jedna relace, ověření místa a nezávislé přijetí jednotlivých podkladů.

        Výpadek grafu nebo dokumentů nezahodí nové validní odečty. Každý díl
        má vlastní skutečný čas pořízení a chybu; starší úspěšný díl zůstává.
        Chyba autentizace zastaví další volání a vyvolá reauth bez smazání archivu.
        """
        async with self._cloud_lock:
            failures = []
            try:
                for place_id, place in self.repository.data["places"].items():
                    source = place["settings"].get("portal")
                    if not source:
                        continue
                    try:
                        rows = await self.portal.supply_points(source["partner_id"])
                        matched = [
                            row
                            for row in rows
                            if row.get("CPE_EAN") == place_id
                            and row.get("CP_ID") == source["cp_id"]
                            and row.get("CONT_ID") == source["contract_id"]
                        ]
                        if len(matched) != 1:
                            raise DataError("portal_place_identity_changed")
                    except AuthenticationRequired:
                        raise
                    except (PortalError, DataError) as err:
                        failures.append(str(err))
                        continue
                    for key, fetch in (
                        ("readings", self.portal.readings),
                        ("consumption", self.portal.consumption),
                        ("details", self.portal.place_details),
                        ("deposit", self.portal.deposit),
                        ("documents", self.portal.contract_documents),
                    ):
                        at = dt_util.utcnow().isoformat()
                        try:
                            raw = await fetch(source["cp_id"], source["contract_id"])
                            normalized, periods, reference = None, None, fingerprint(raw)
                            if key == "readings":
                                normalized = await self.hass.async_add_executor_job(
                                    portal_readings, raw, place_id, reference
                                )
                            elif key == "consumption":
                                periods = await self.hass.async_add_executor_job(
                                    consumption_periods, raw
                                )
                            elif key == "details" and (
                                not isinstance(raw, dict) or raw.get("CPE_EAN") != place_id
                            ):
                                raise DataError("portal_detail_identity_mismatch")

                            def commit(data):
                                item = data["places"][place_id]
                                if normalized is not None:
                                    apply_import(
                                        data,
                                        {
                                            "place": place_id,
                                            "id": reference,
                                            "readings": normalized,
                                            "raw": None,
                                        },
                                    )
                                    item["last_successful_import"] = at
                                if periods is not None:
                                    item["snapshots"] = add_snapshot(
                                        item["snapshots"],
                                        wire(
                                            {
                                                "retrieved_at": at,
                                                "source": "mnd",
                                                "periods": periods,
                                            }
                                        ),
                                    )
                                evidence = item.setdefault("portal_evidence", {})
                                evidence[key] = wire(raw)
                                evidence.setdefault("acquired_at", {})[key] = at
                                evidence.setdefault("errors", {}).pop(key, None)

                            await self.repository.transact(commit)
                        except AuthenticationRequired:
                            raise
                        except (PortalError, DataError) as err:
                            reason = str(err)
                            failures.append(reason)
                            await self.repository.transact(
                                lambda data: (
                                    data["places"][place_id]
                                    .setdefault("portal_evidence", {})
                                    .setdefault("errors", {})
                                    .update({key: {"reason": reason, "attempted_at": at}})
                                )
                            )
                self.cloud_status = "partial" if failures else "connected"
            except AuthenticationRequired:
                self.cloud_status = "reauth_required"
                self.entry.async_start_reauth(self.hass)
            except (PortalError, DataError) as err:
                self.cloud_status = str(err)

    async def _evaluate(self):
        async with self._recompute_lock:
            while True:
                revision = self.repository.data["revision"]
                snapshot = copy.deepcopy(self.repository.data)
                results = {}
                for place_id, place in snapshot["places"].items():
                    try:
                        result = await self.hass.async_add_executor_job(
                            evaluate_place, place_id, place, self.hass.config.time_zone
                        )
                    except DataError as err:
                        result = {"status": "invalid", "warnings": [str(err)]}
                    results[place_id] = {
                        **result,
                        "archive_revision": revision,
                        "cloud_status": self.cloud_status,
                    }
                if revision == self.repository.data["revision"]:
                    # Repairs vysvětluje problém relace, nikoli zákaznické
                    # hodnoty. Archiv i dostupné místní entity zůstávají aktivní.
                    issue = f"cloud_{self.entry.entry_id}"
                    if self.cloud_status not in ("connected", "not_connected"):
                        ir.async_create_issue(
                            self.hass,
                            DOMAIN,
                            issue,
                            is_fixable=False,
                            severity=ir.IssueSeverity.WARNING,
                            translation_key="cloud_unavailable",
                            translation_placeholders={"reason": self.cloud_status},
                        )
                    else:
                        ir.async_delete_issue(self.hass, DOMAIN, issue)
                    return results

    async def async_recompute(self):
        self.async_set_updated_data(await self._evaluate())

    async def async_import(self, place_id, content, filename, *, preview=False, source_meta=None):
        """Parsování a originál jsou v executoru; commit jednoho místa je atomický."""
        if place_id not in self.repository.data["places"]:
            raise DataError("place_not_found")
        if not filename or len(filename) > 240 or any(c in filename for c in ("/", "\\", ":")):
            raise DataError("invalid_document_name")
        if filename.lower().endswith(".xlsx"):
            parser, args = parse_workbook, (content, filename, place_id)
        elif filename.lower().endswith(".zip"):
            parser, args = parse_zip, (content, place_id)
        elif filename.lower().endswith(".pdf"):
            proposal = await self.hass.async_add_executor_job(parse_invoice_pdf, content, place_id)
            if preview:
                return {
                    "rows": 0,
                    "rejected": 0,
                    "warnings": proposal["warnings"],
                    "proposal": wire(proposal),
                    "revision": self.repository.data["revision"],
                }
            parser, args = None, ()
        else:
            raw = await self.hass.async_add_executor_job(load_json, content)
            parser = (
                parse_native
                if isinstance(raw, dict) and raw.get("format") == "mnd-ha-place"
                else parse_v1
            )
            args = (content, place_id)
            if parser is parse_v1:
                args = (content, place_id, self.hass.config.time_zone)
        parsed = (
            await self.hass.async_add_executor_job(parser, *args)
            if parser
            else {
                "place": place_id,
                "id": hashlib.sha256(content).hexdigest(),
                "readings": [],
                "proposal": proposal,
                "artifact_only": True,
            }
        )
        if preview:
            return {
                "rows": len(parsed["readings"]),
                "rejected": len(parsed.get("rejected", [])),
                "warnings": parsed.get("warnings", []),
                "revision": self.repository.data["revision"],
            }
        sha = await self.hass.async_add_executor_job(put_artifact, self.artifact_root, content)
        for document in parsed.get("documents", {}).values():
            await self.hass.async_add_executor_job(put_artifact, self.artifact_root, document)

        def commit(data):
            result = (
                restore_place(data, parsed) if "native" in parsed else apply_import(data, parsed)
            )
            artifact = {
                "id": sha,
                "filename": filename,
                "acquired_at": dt_util.utcnow().isoformat(),
                **(source_meta or {}),
            }
            if parsed.get("proposal"):
                artifact["proposal"] = wire(parsed["proposal"])
            if not any(a["id"] == sha for a in data["places"][place_id]["artifacts"]):
                data["places"][place_id]["artifacts"].append(artifact)
            data["places"][place_id]["last_successful_import"] = artifact["acquired_at"]
            return result

        result = await self.repository.transact(commit)
        await self.async_recompute()
        return {**result, "artifact": sha}

    async def async_edit(self, place_id, section, record, expected_revision):
        """Správcovské formuláře volají jedinou validovanou transakční cestu."""
        from .editing import edit_place

        mutate = partial(
            edit_place,
            place_id=place_id,
            section=section,
            record=record,
            now=dt_util.utcnow(),
            zone=self.hass.config.time_zone,
        )
        result = await self.repository.transact(mutate, expected_revision=expected_revision)
        if section == "settings":
            for unsubscribe in self._unsubscribers:
                unsubscribe()
            self._unsubscribers.clear()
            self._subscribe_sources()
        await self.async_recompute()
        return result

    async def async_close(self):
        self._closed = True
        if self._debounce:
            self._debounce()
            self._debounce = None
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        if self._registry_unsubscribe:
            self._registry_unsubscribe()
            self._registry_unsubscribe = None
        await self.history.cancel()
        await self.async_flush_samples()
        await self.portal.close()
