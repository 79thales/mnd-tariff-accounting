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
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, POLL_HOURS, SOURCE_DEBOUNCE_SECONDS
from .core.archive import Repository, apply_import, new_place
from .core.backup import parse_native, parse_zip, restore_place
from .core.common import DataError, day, decimal, fingerprint, identity, load_json, local_day, wire
from .core.finance import finance_rows, merge_finance
from .core.forecast import add_snapshot
from .core.importer import parse_v1
from .core.invoice_pdf import parse_invoice_pdf
from .core.live import flow_value
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
        self._flow_debounce = None
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
        # Čerstvost průtoku musí vypršet i bez dalšího pulsu. Minutový
        # přepočet nevolá síť a unload ho spolehlivě odpojí.
        self._clock_unsubscribe = async_track_time_interval(
            self.hass, self._clock_recompute, timedelta(minutes=1)
        )
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
            flow = registry.async_get(
                settings.get("flow_registry_id") or settings.get("flow_entity", "")
            )
            if flow:

                @callback
                def flow_changed(_event):
                    if self._flow_debounce is None and not self._closed:
                        self._flow_debounce = async_call_later(self.hass, 1, self._flow_recompute)

                self._unsubscribers.append(
                    async_track_state_change_event(self.hass, [flow.entity_id], flow_changed)
                )
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

    async def _flow_recompute(self, _now):
        self._flow_debounce = None
        if not self._closed:
            await self.async_recompute()

    async def _clock_recompute(self, _now):
        if not self._closed:
            # Dotažení posledních hodin neprovádí síťový polling MND. Jedna
            # úloha načte nejvýše tři místní dny a nezasahuje do probíhajícího
            # úplného importu. Unload ji zruší před uzavřením archivu.
            tick = asyncio.get_running_loop().time()
            if (
                "recorder" in self.hass.config.components
                and tick - getattr(self, "_profile_last_tick", 0) >= 600
                and not (self.history.task and not self.history.task.done())
                and not (getattr(self, "_profile_task", None) and not self._profile_task.done())
            ):
                self._profile_last_tick = tick
                self._profile_task = self.entry.async_create_background_task(
                    self.hass, self._refresh_recent_profiles(), "mnd-local-profile-refresh"
                )
            await self.async_recompute()

    async def _refresh_recent_profiles(self):
        """Po 10 minutách obnoví i neúplný dnešní sloupec; mezera není nula."""
        from .recorder import async_read_history

        today = dt_util.as_local(dt_util.utcnow()).date()
        for place_id, place in self.repository.data["places"].items():
            if not (
                place["settings"].get("history_registry_id")
                or place["settings"].get("source_registry_id")
            ) or not place["settings"].get("segment"):
                continue
            try:
                async with asyncio.timeout(45):
                    await async_read_history(
                        self, place_id, today - timedelta(days=2), today + timedelta(days=1)
                    )
            except (DataError, KeyError, TimeoutError):
                # Předchozí profil zůstává. Neúspěšné čtení se nepřepíše
                # prázdnými dny a další periodický běh může pokračovat.
                continue

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
            flow = registry.async_get(settings.get("flow_registry_id", ""))
            flow_affected = settings.get("flow_entity") in affected or (
                flow and flow.entity_id in affected
            )
            if (
                not flow_affected
                and settings.get("source_entity") not in affected
                and (not current or current.entity_id not in affected)
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
                    # Finanční zdroje jsou nezávislé na grafu a odečtech.
                    # Chyba jednoho seznamu nesmaže starší platné doklady.
                    failures.extend(await self._refresh_finance(place_id, source))
                    failures.extend(await self._refresh_billing_documents(place_id))
                self.cloud_status = "partial" if failures else "connected"
            except AuthenticationRequired:
                self.cloud_status = "reauth_required"
                self.entry.async_start_reauth(self.hass)
            except (PortalError, DataError) as err:
                self.cloud_status = str(err)

    async def _refresh_billing_documents(self, place_id):
        """Ověří originály pro aktuální období a aktuální ceník MND.

        Poslední faktura poskytuje také doložený daňový kontext domácnosti.
        Ostatní faktury se načítají jen při průniku s vybraným obdobím.
        Nezměněné ověřené revize se neparsují znovu. Každý originál se uloží
        samostatně, takže selhání pozdějšího dokumentu neztratí hotovou práci.
        PDF zůstávají soukromá; čtení nepotvrzuje ruční účetní knihu.
        """
        from .core.billing import select_period
        from .core.mnd_documents import current_price, invoice_from_text, pdf_text, tariff_from_text

        place = self.repository.data["places"][place_id]
        evidence = place.get("portal_evidence", {})
        invoices = evidence.get("invoices", {}).get("rows", [])
        documents = evidence.get("documents", [])
        details = evidence.get("details", {})
        if not invoices:
            return []
        latest = max(invoices, key=lambda r: r["to_inclusive"])
        period = select_period(place, local_day(dt_util.utcnow(), self.hass.config.time_zone))
        selected = [latest] + [
            r
            for r in invoices
            if r["id"] != latest["id"]
            and period
            and day(r["from"]) < day(period["To"])
            and day(period["From"]) <= day(r["to_inclusive"])
        ]
        current = [d for d in documents if d.get("TYPE") == "PRNOW"]
        context = fingerprint(
            [
                [r["revision"] for r in selected],
                current,
                details.get("BusinessAlgorithm"),
                details.get("CPE_CONS_AVE_YEAR"),
            ]
        )
        if place.get("billing_documents_context") == context:
            return []
        at = dt_util.utcnow().isoformat()
        try:
            parsed_invoices = []
            for row in selected:
                cached = next(
                    (
                        i
                        for i in place.get("invoice_evidence", [])
                        if i["id"] == row["id"]
                        and i.get("revision") == row["revision"]
                        and i.get("verified")
                    ),
                    None,
                )
                if cached:
                    parsed_invoices.append(cached)
                    continue
                content, name = await self.portal.invoice_pdf(row["id"])
                text = await self.hass.async_add_executor_job(pdf_text, content)
                invoice = await self.hass.async_add_executor_job(
                    invoice_from_text, text, place_id, row
                )
                sha = await self.hass.async_add_executor_job(
                    put_artifact, self.artifact_root, content
                )
                invoice.update(artifact=sha, revision=row["revision"])

                def save_invoice(data):
                    item = data["places"][place_id]
                    item["invoice_evidence"] = [
                        i for i in item.get("invoice_evidence", []) if i["id"] != invoice["id"]
                    ] + [invoice]
                    if not any(a["id"] == sha for a in item["artifacts"]):
                        item["artifacts"].append(
                            {"id": sha, "filename": name, "source": "mnd", "acquired_at": at}
                        )

                await self.repository.transact(save_invoice)
                parsed_invoices.append(invoice)
            if len(current) != 1 or not details.get("CPE_CONS_AVE_YEAR"):
                raise DataError("mnd_current_tariff_unavailable")
            source = place["settings"]["portal"]
            content, name = await self.portal.download_contract(
                source["cp_id"], source["contract_id"], current[0]
            )
            text = await self.hass.async_add_executor_job(pdf_text, content)
            parsed = await self.hass.async_add_executor_job(
                tariff_from_text, text, details["CPE_CONS_AVE_YEAR"]
            )
            price = await self.hass.async_add_executor_job(
                current_price, details, current[0], parsed, parsed_invoices[0]
            )
            sha = await self.hass.async_add_executor_job(put_artifact, self.artifact_root, content)

            def save_price(data):
                item = data["places"][place_id]
                item["price_evidence"] = {**price, "artifact": sha, "acquired_at": at}
                item["billing_documents_context"] = context
                if not any(a["id"] == sha for a in item["artifacts"]):
                    item["artifacts"].append(
                        {"id": sha, "filename": name, "source": "mnd", "acquired_at": at}
                    )
                item.setdefault("portal_evidence", {}).setdefault("errors", {}).pop(
                    "billing_documents", None
                )

            await self.repository.transact(save_price)
            return []
        except AuthenticationRequired:
            raise
        except (PortalError, DataError) as error:
            reason = str(error)
            await self.repository.transact(
                lambda data: (
                    data["places"][place_id]
                    .setdefault("portal_evidence", {})
                    .setdefault("errors", {})
                    .update(billing_documents={"reason": reason, "attempted_at": at})
                )
            )
            return [reason]

    async def _refresh_finance(self, place_id, source):
        """Načte historii a detaily se skutečnými úhradami, nejvýše 120 s/druh.

        Zákaznické ID smí doplnit jen ověřený detail stejného místa. Surová
        data a revize zůstávají v private Store. Rozpracovaný prefix se
        uchová, úplnost detailů je výslovná a další refresh může pokračovat.
        """
        failures = []
        place = self.repository.data["places"][place_id]
        detail = place.get("portal_evidence", {}).get("details", {})
        source = dict(source)
        if source.get("customer_id") is None:
            if (
                detail.get("CPE_EAN") != place_id
                or detail.get("CP_ID") != source["cp_id"]
                or detail.get("CUSTA_ID") is None
            ):
                return ["portal_customer_identity_missing"]
            source["customer_id"] = detail["CUSTA_ID"]
            await self.repository.transact(
                lambda data: data["places"][place_id]["settings"]["portal"].update(
                    customer_id=source["customer_id"]
                )
            )
        for kind in ("advances", "invoices"):
            at = dt_util.utcnow().isoformat()
            previous = place.get("portal_evidence", {}).get(kind, {})
            try:
                listing = await self.portal.finance_list(
                    kind, source["partner_id"], source["customer_id"], source["cp_id"]
                )
                raw_rows, all_details = [], True
                cached = {r["list_hash"]: r["detail"] for r in previous.get("cached", [])}
                new_cache = []
                deadline = asyncio.get_running_loop().time() + 120
                rows_to_read = listing["rows"]
                cursor = previous.get("cursor", 0) % max(1, len(rows_to_read))
                attempts = 0
                rows_to_read = rows_to_read[cursor:] + rows_to_read[:cursor]
                for row in rows_to_read:
                    reference = fingerprint(row)
                    raw = cached.get(reference)
                    # I nezměněný součet dokladu může mít opravené datum
                    # platby. Detaily pravidelně obnovujeme po dávkách;
                    # kurzor zajistí, že starší řádky nevyhladoví.
                    if attempts < 40 and asyncio.get_running_loop().time() < deadline:
                        attempts += 1
                        key = "ADVI_ID" if kind == "advances" else "IVA_ID"
                        try:
                            fetched = await self.portal.finance_detail(kind, row[key])
                            if str(fetched.get(key, row[key])) != str(row[key]):
                                raise DataError("portal_finance_document_mismatch")
                            raw = {**row, **fetched}
                        except AuthenticationRequired:
                            raise
                        except (PortalError, KeyError):
                            all_details = False
                    if raw is None:
                        raw, all_details = row, False
                    else:
                        new_cache.append({"list_hash": reference, "detail": raw})
                    raw_rows.append(raw)
                rows = finance_rows(kind, raw_rows, source)
                all_details = all_details and all(r["payments_known"] for r in rows)

                def commit(data):
                    evidence = data["places"][place_id].setdefault("portal_evidence", {})
                    old = evidence.get(kind, {})
                    history = old.get("revisions", [])
                    changed = {r["id"]: r for r in rows}
                    history = history + [
                        {"at": at, "row": r}
                        for r in old.get("rows", [])
                        if r["id"] in changed and r["revision"] != changed[r["id"]]["revision"]
                    ]
                    evidence[kind] = {
                        "rows": merge_finance(old.get("rows", []), rows),
                        "cached": new_cache,
                        "revisions": history,
                        "list_complete": listing["complete"],
                        "details_complete": all_details,
                        "cursor": (cursor + attempts) % max(1, len(rows_to_read)),
                        "details_refreshed_all": attempts == len(rows_to_read),
                        "acquired_at": at,
                    }
                    evidence.setdefault("errors", {}).pop(kind, None)

                await self.repository.transact(commit)
                if not all_details or not listing["complete"]:
                    failures.append("portal_finance_partial")
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
                        .update({kind: {"reason": reason, "attempted_at": at}})
                    )
                )
        return failures

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
                    billing = result.get("billing", {})
                    for sensor, key in {
                        "billing_paid_czk": "paid_czk",
                        "billing_plan_czk": "planned_czk",
                        "billing_cost_czk": "known_cost_czk",
                        "billing_forecast_cost_czk": "forecast_cost_czk",
                        "billing_forecast_balance_czk": "forecast_balance_czk",
                        "billing_actual_mwh": "actual_mwh",
                        "billing_forecast_mwh": "forecast_mwh",
                        "billing_volume_m3": "known_volume_m3",
                    }.items():
                        results[place_id][sensor] = billing.get(key)
                    settings = place["settings"]
                    registry = er.async_get(self.hass)
                    flow = registry.async_get(
                        settings.get("flow_registry_id") or settings.get("flow_entity", "")
                    )
                    state = self.hass.states.get(flow.entity_id) if flow else None
                    results[place_id].update(
                        flow_value(
                            state.state if state else None,
                            state.attributes.get("unit_of_measurement") if state else None,
                            (
                                getattr(state, "last_reported", None) or state.last_updated
                            ).isoformat()
                            if state
                            else None,
                            dt_util.utcnow(),
                            settings.get("flow_max_age", 900),
                        )
                    )
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
        if getattr(self, "_profile_task", None) and not self._profile_task.done():
            self._profile_task.cancel()
            try:
                await self._profile_task
            except asyncio.CancelledError:
                pass
        if getattr(self, "_clock_unsubscribe", None):
            self._clock_unsubscribe()
        if self._flow_debounce:
            self._flow_debounce()
            self._flow_debounce = None
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
