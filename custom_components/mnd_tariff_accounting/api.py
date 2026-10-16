"""Autentizované rozhraní panelu a dokumentů; oprávnění kontroluje server.

Všechny účetní operace vyžadují správce. Není to veřejný souborový server:
upload má 64 MiB a download přijímá jen ID originálu patřícího vybrané entry.
Klient nezadává cestu serveru ani URL dodavatele.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
from decimal import Decimal
from pathlib import Path

import voluptuous as vol
from aiohttp import web
from homeassistant.components import websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, PANEL_PATH
from .core.accounting import active_versions, calculate, invoice_settlement
from .core.archive import new_place
from .core.backup import backup_document, make_zip
from .core.common import MAX_BYTES, DataError, canonical, fingerprint, identity, wire
from .core.comparison import compare_measurement
from .core.forecast import compare_forecast, project_outcome, seasonal_forecast
from .core.importer import export_csv
from .core.portal_mapping import technical_details
from .dashboard import build_views
from .storage import get_artifact, put_artifact


def _coordinator(hass, entry_id):
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or not getattr(entry, "runtime_data", None):
        raise DataError("entry_not_loaded")
    return entry.runtime_data


async def async_setup_api(hass):
    """Jedna registrace i při souběžném setupu účtů; chyba dovolí pokračovat.

    Dílčí registrace mají vlastní příznaky. Selhání panelu po registraci HTTP
    nezanechá falešné hotovo a další setup se nepokusí zdvojit existující cesty.
    """
    lock = hass.data.setdefault(DOMAIN + "_api_lock", asyncio.Lock())
    async with lock:
        stages = hass.data.setdefault(DOMAIN + "_api_stages", set())
        if "complete" in stages:
            return
        if "handlers" not in stages:
            websocket_api.async_register_command(hass, websocket_command)
            hass.http.register_view(ImportView())
            hass.http.register_view(ArtifactView())
            hass.http.register_view(BackupView())
            stages.add("handlers")
        module = Path(__file__).parent / "frontend/mnd-panel.js"
        digest = await hass.async_add_executor_job(
            lambda: hashlib.sha256(module.read_bytes()).hexdigest()
        )
        url = f"/{DOMAIN}/mnd-panel.js"
        if "static" not in stages:
            await hass.http.async_register_static_paths([StaticPathConfig(url, str(module), False)])
            stages.add("static")
        from homeassistant.components.frontend import add_extra_js_url

        if "resource" not in stages:
            add_extra_js_url(hass, f"{url}?v={digest}")
            stages.add("resource")
        await async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="mnd-accounting-panel",
            # Správa se otevírá z konkrétního zařízení, hlavní přehled je
            # nativní view Overview a zachová jeho horní lištu i na mobilu.
            sidebar_title=None,
            sidebar_icon="mdi:fire",
            require_admin=True,
            module_url=f"{url}?v={digest}",
        )
        stages.add("complete")


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": DOMAIN + "/command",
        vol.Required("action"): str,
        vol.Optional("entry_id"): str,
        vol.Optional("place"): str,
        vol.Optional("payload", default={}): dict,
    }
)
@websocket_api.async_response
async def websocket_command(hass, connection, msg):
    """Whitelist akcí; doménové chyby vrací kód bez finančních hodnot a tajemství."""
    try:
        action = msg["action"]
        payload = msg["payload"]
        if len(canonical(payload)) > 1024 * 1024:
            raise DataError("payload_too_large")
        if action == "entries":
            result = [
                {"id": e.entry_id, "name": e.title}
                for e in hass.config_entries.async_entries(DOMAIN)
            ]
        else:
            coordinator = _coordinator(hass, msg.get("entry_id"))
            repo = coordinator.repository
            place_id = msg.get("place")
            if action == "summary":
                result = {
                    "revision": repo.data["revision"],
                    "places": [
                        {"id": p, "name": v["name"]} for p, v in repo.data["places"].items()
                    ],
                    "results": coordinator.data,
                    "job": repo.data["job"],
                }
            elif action == "add_place":
                selected = identity(payload["id"])

                def add(data):
                    if selected in data["places"]:
                        raise DataError("place_exists")
                    data["places"][selected] = new_place(str(payload.get("name", "MND")))

                await repo.transact(add, expected_revision=payload.get("revision"))
                # Registry zařízení se pro novou sadu míst zřídí stejným setupem.
                await hass.config_entries.async_reload(coordinator.entry.entry_id)
                result = {"saved": True}
            elif action == "detail":
                if place_id not in repo.data["places"]:
                    raise DataError("place_not_found")
                result = {
                    "revision": repo.data["revision"],
                    "place": copy.deepcopy(repo.data["places"][place_id]),
                    "result": coordinator.data.get(place_id, {}),
                }
                device = dr.async_get(hass).async_get_device(
                    identifiers={(DOMAIN, f"{coordinator.entry.data['account_id']}:{place_id}")}
                )
                result["device_url"] = (
                    f"/config/devices/device/{device.id}" if device else "/config/devices"
                )
                visible = result["place"]
                # Cache protokolu není součást běžného čtecího UI. Historie
                # vrací pouze normalizované doklady a stav jejich pokrytí.
                for kind in ("advances", "invoices"):
                    finance = visible.get("portal_evidence", {}).get(kind)
                    if finance:
                        finance.pop("cached", None)
                        finance.pop("revisions", None)
                visible["sample_count"] = len(visible["samples"])
                visible["samples"] = []
                raw_details = visible.get("portal_evidence", {}).get("details")
                visible["technical"] = (
                    technical_details(raw_details) if isinstance(raw_details, dict) else {}
                )
                visible["imports"] = [
                    {k: v for k, v in row.items() if k not in ("raw", "rows")}
                    for row in visible["imports"]
                ]
                registry_id = visible["settings"].get("source_registry_id")
                source = er.async_get(hass).async_get(registry_id) if registry_id else None
                if source:
                    visible["settings"]["source_entity"] = source.entity_id
                flow_id = visible["settings"].get("flow_registry_id")
                flow = er.async_get(hass).async_get(flow_id) if flow_id else None
                if flow:
                    visible["settings"]["flow_entity"] = flow.entity_id
                result["settlements"] = [
                    {
                        "id": i["id"],
                        **invoice_settlement(
                            i,
                            repo.data["places"][place_id]["events"],
                            repo.data["places"][place_id]["invoices"],
                        ),
                    }
                    for i in active_versions(repo.data["places"][place_id]["invoices"])
                ]
            elif action == "edit":
                record = dict(payload["record"])
                if payload["section"] == "calibration" and not record.get("entity"):
                    record["entity"] = repo.data["places"][place_id]["settings"].get(
                        "source_registry_id"
                    )
                    if not record["entity"]:
                        raise DataError("calibration_sensor_required")
                if payload["section"] == "settings" and "flow_entity" in record:
                    from .core.live import FLOW_UNITS

                    entity = record["flow_entity"]
                    source = er.async_get(hass).async_get(entity) if entity else None
                    state = hass.states.get(entity) if entity else None
                    if entity and (
                        source is None
                        or state is None
                        or state.attributes.get("unit_of_measurement") not in FLOW_UNITS
                    ):
                        raise DataError("incompatible_flow_sensor")
                    record["flow_registry_id"] = source.id if source else None
                if payload["section"] == "settings" and record.get("source_mode") == "sensor":
                    source = er.async_get(hass).async_get(record.get("source_entity", ""))
                    state = hass.states.get(record.get("source_entity", ""))
                    if (
                        source is None
                        or state is None
                        or state.attributes.get("unit_of_measurement") not in ("m³", "m3")
                        or state.attributes.get("state_class") not in ("total", "total_increasing")
                    ):
                        raise DataError("incompatible_sensor")
                    record["source_registry_id"] = source.id
                result = await coordinator.async_edit(
                    place_id, payload["section"], record, payload["revision"]
                )
            elif action == "recompute":
                await coordinator.async_recompute()
                result = {"updated": True}
            elif action == "accept_advances":
                from homeassistant.util import dt as dt_util

                from .core.common import local_day
                from .core.finance import accept_advances

                if payload.get("confirm") is not True:
                    raise DataError("finance_allocation_confirmation_required")

                def accept(data):
                    accept_advances(
                        place_id,
                        data["places"][place_id],
                        local_day(dt_util.utcnow(), hass.config.time_zone),
                    )

                result = await repo.transact(accept, expected_revision=payload.get("revision"))
                await coordinator.async_recompute()
            elif action == "cloud_refresh":
                await coordinator.async_refresh_cloud()
                await coordinator.async_recompute()
                result = {"status": coordinator.cloud_status}
            elif action == "readings_export":
                from homeassistant.util import dt as dt_util

                from .core.common import day, local_day

                source = repo.data["places"][place_id]["settings"].get("portal")
                if not source:
                    raise DataError("cloud_place_not_connected")
                left, right = day(payload["start"]), day(payload["end"])
                if right > local_day(dt_util.utcnow(), hass.config.time_zone):
                    raise DataError("future_export_period")
                content, filename = await coordinator.portal.export_readings(
                    source["cp_id"], source["contract_id"], left, right
                )
                result = await coordinator.async_import(
                    place_id,
                    content,
                    filename,
                    source_meta={
                        "origin": "mnd",
                        "requested_from": left.isoformat(),
                        "requested_to": right.isoformat(),
                        "range_inclusive": True,
                    },
                )
                await coordinator.async_recompute()
            elif action == "history_start":
                result = coordinator.history.start(
                    place_id,
                    max_segments=payload.get("max_segments", 10),
                    resume=payload.get("resume", True),
                )
            elif action == "history_cancel":
                await coordinator.history.cancel()
                result = {"status": "paused"}
            elif action == "recorder_history":
                result = coordinator.history.start_local(place_id, payload["start"], payload["end"])
            elif action == "local_forecast":
                place = repo.data["places"][place_id]
                from homeassistant.util import dt as dt_util

                from .core.common import day, local_day

                if day(payload["start"]) < local_day(dt_util.utcnow(), hass.config.time_zone):
                    raise DataError("forecast_requires_future_period")
                selected_settings = place["settings"]
                profile = [
                    row
                    for row in place.get("daily_profile", [])
                    if row.get("entity") == selected_settings.get("source_registry_id")
                    and row.get("segment") == selected_settings.get("segment")
                ]
                if selected_settings.get("source_mode", "manual") == "manual":
                    from .core.statistics import manual_profile

                    profile = await hass.async_add_executor_job(
                        manual_profile,
                        place["readings"],
                        place_id,
                        selected_settings.get("segment"),
                        hass.config.time_zone,
                    )
                result = await hass.async_add_executor_job(
                    seasonal_forecast,
                    profile,
                    payload["start"],
                    payload["end"],
                )
                if result["complete"]:
                    from .core.common import day

                    quote = await hass.async_add_executor_job(
                        lambda: calculate(
                            start=payload["start"],
                            end=payload["end"],
                            segments=result["daily"],
                            tariffs=place["tariffs"],
                            conversions=place["conversions"],
                            events=[],
                            opening_credit="0",
                            payments_complete=True,
                        )
                    )
                    result["remaining_cost_czk"] = (
                        quote["known_cost_czk"] if quote["complete"] else None
                    )
                    result["price_warnings"] = quote["warnings"]
                    plans = [
                        e
                        for e in active_versions(place["events"])
                        if e["role"] == "prescribed"
                        and day(payload["start"]) <= day(e["from"])
                        and day(e["to"]) <= day(payload["end"])
                    ]
                    periods = [(e["from"], e["to"]) for e in plans]
                    planned = (
                        sum((Decimal(e["amount"]) for e in plans), Decimal(0))
                        if plans and len(periods) == len(set(periods))
                        else None
                    )
                    current = coordinator.data.get(place_id, {})
                    aligned = (
                        current.get("evaluated_to") == payload["start"]
                        and place["settings"].get("period_to") == payload["end"]
                    )
                    outcome = project_outcome(
                        current.get("balance_czk") if aligned else None,
                        result["remaining_cost_czk"],
                        planned,
                        len(plans),
                    )
                    result.update(outcome)
                    from homeassistant.util import dt as dt_util

                    snapshot = wire(
                        {
                            "id": fingerprint([payload, dt_util.utcnow().isoformat()]),
                            "from": payload["start"],
                            "to": payload["end"],
                            "built_at": dt_util.utcnow().isoformat(),
                            "result": result,
                            "inputs": profile,
                        }
                    )
                    await repo.transact(
                        lambda data: (
                            data["places"][place_id]
                            .setdefault("local_forecasts", [])
                            .append(snapshot)
                        )
                    )
            elif action == "compare_measurement":
                from homeassistant.util import dt as dt_util

                if payload.get("confirm_period") is not True:
                    raise DataError("comparison_basis_confirmation_required")
                place = repo.data["places"][place_id]
                snapshot = place["snapshots"][payload["snapshot"]]
                result = await hass.async_add_executor_job(
                    compare_measurement,
                    place_id,
                    place,
                    snapshot,
                    snapshot["periods"][payload["period"]],
                    hass.config.time_zone,
                    dt_util.utcnow(),
                )
            elif action == "compare_forecast":
                place = repo.data["places"][place_id]
                snapshot = place["snapshots"][payload["snapshot"]]
                prediction = snapshot["periods"][payload["period"]]
                invoice = next(
                    (
                        i
                        for i in active_versions(place["invoices"])
                        if i["id"] == payload["invoice"]
                    ),
                    None,
                )
                if (
                    not invoice
                    or invoice.get("confirmed") is not True
                    or invoice.get("energy_mwh") is None
                    or payload.get("confirm_period") is not True
                ):
                    raise DataError("comparable_invoice_required")
                from .core.common import day, instant, local_day

                if local_day(instant(snapshot["retrieved_at"]), hass.config.time_zone) >= day(
                    invoice["to"]
                ):
                    raise DataError("snapshot_not_before_actual_period_end")
                common = {
                    "place": place_id,
                    "unit": "MWh",
                    "conversion_id": "supplier_reported_energy",
                    "segments": ["supplier_period"],
                }
                result = compare_forecast(
                    {
                        **common,
                        "from": prediction["From"],
                        "to": prediction["To"],
                        "value": prediction["PortalTotalMwh"],
                        "retrieved_at": snapshot["retrieved_at"],
                    },
                    {
                        **common,
                        "from": invoice["from"],
                        "to": invoice["to"],
                        "value": invoice["energy_mwh"],
                        "complete": True,
                    },
                )
            elif action == "cloud_logout":
                await coordinator.history.cancel()
                await coordinator.portal.logout()
                coordinator.cloud_status = "reauth_required"
                if payload.get("forget") is True:
                    updated = dict(coordinator.entry.data)
                    updated.pop("password", None)
                    updated.pop("username", None)
                    hass.config_entries.async_update_entry(coordinator.entry, data=updated)
                result = {"logged_out": True}
            elif action in ("finance_export", "invoice_pdf"):
                place = repo.data["places"][place_id]
                kind = payload.get("kind", "invoices")
                if kind not in ("advances", "invoices"):
                    raise DataError("invalid_finance_kind")
                available = place.get("portal_evidence", {}).get(kind, {}).get("rows", [])
                if action == "invoice_pdf":
                    if kind != "invoices" or not any(
                        r["id"] == str(payload["document_id"]) for r in available
                    ):
                        raise DataError("portal_document_identity_required")
                    content, filename = await coordinator.portal.invoice_pdf(payload["document_id"])
                else:
                    content, filename = await coordinator.portal.finance_export(
                        kind, [int(r["id"]) if r["id"].isdigit() else r["id"] for r in available]
                    )
                sha = await hass.async_add_executor_job(
                    put_artifact, coordinator.artifact_root, content
                )

                def save(data):
                    rows = data["places"][place_id]["artifacts"]
                    if not any(r["id"] == sha for r in rows):
                        from homeassistant.util import dt as dt_util

                        rows.append(
                            {
                                "id": sha,
                                "filename": filename,
                                "source": "mnd",
                                "acquired_at": dt_util.utcnow().isoformat(),
                            }
                        )

                await repo.transact(save)
                result = {"artifact": sha, "filename": filename}
            elif action in ("portal_profile", "portal_payments", "portal_document"):
                place = repo.data["places"][place_id]
                source = place["settings"].get("portal")
                if not source:
                    raise DataError("cloud_place_not_connected")
                if action == "portal_profile":
                    result = await coordinator.portal.profile(source["partner_id"])
                elif action == "portal_payments":
                    result = await coordinator.portal.payments(
                        source["partner_id"],
                        source["customer_id"],
                        source["cp_id"],
                        offset=payload.get("offset", 0),
                    )
                else:
                    documents = await coordinator.portal.contract_documents(
                        source["cp_id"], source["contract_id"]
                    )
                    selected = (
                        [d for d in documents if str(d.get("DOCID")) == str(payload["document_id"])]
                        if isinstance(documents, list)
                        else []
                    )
                    if len(selected) != 1:
                        raise DataError("portal_document_identity_required")
                    content, filename = await coordinator.portal.download_contract(
                        source["cp_id"], source["contract_id"], selected[0]
                    )
                    if "/" in filename or "\\" in filename:
                        raise DataError("invalid_document_name")
                    sha = await hass.async_add_executor_job(
                        put_artifact, coordinator.artifact_root, content
                    )

                    def save_document(data):
                        artifacts = data["places"][place_id]["artifacts"]
                        if not any(a["id"] == sha for a in artifacts):
                            from homeassistant.util import dt as dt_util

                            artifacts.append(
                                {
                                    "id": sha,
                                    "filename": filename,
                                    "source": "mnd",
                                    "acquired_at": dt_util.utcnow().isoformat(),
                                }
                            )

                    await repo.transact(save_document)
                    result = {"saved": True, "artifact": sha}
            elif action == "export":
                if place_id not in repo.data["places"]:
                    raise DataError("place_not_found")
                result = backup_document(repo.account, place_id, repo.data["places"][place_id])
            elif action == "csv":
                place = repo.data["places"][place_id]
                rows = [{**r, "value": Decimal(r["value"])} for r in place["readings"]]
                content = await hass.async_add_executor_job(
                    export_csv,
                    rows,
                    ["date", "observed_at", "value", "meter", "source", "method", "status", "id"],
                )
                result = {"content": content.decode("utf-8")}
            elif action == "dashboard":
                prefix = f"{coordinator.entry.data['account_id']}:{place_id}:"
                registry = er.async_get(hass)
                entities = {
                    e.unique_id.removeprefix(prefix): e.entity_id
                    for e in er.async_entries_for_config_entry(registry, coordinator.entry.entry_id)
                    if e.platform == DOMAIN
                    and e.unique_id.startswith(prefix)
                    and e.disabled_by is None
                }
                result = await hass.async_add_executor_job(
                    build_views,
                    payload["title"],
                    payload["path"],
                    entities,
                    coordinator.entry.entry_id,
                    place_id,
                )
            else:
                raise DataError("unknown_action")
        if action in ("compare_measurement", "compare_forecast"):
            # Porovnání patří k původní prognóze a shodnému období. Opakování
            # nevytvoří duplicitu a nová prognóza nepřepíše starší výsledek.
            prediction = snapshot["periods"][payload["period"]]
            comparison = wire(
                {
                    **result,
                    "from": prediction["From"],
                    "to": prediction["To"],
                    "snapshot_at": snapshot["retrieved_at"],
                }
            )
            comparison["id"] = fingerprint(comparison)

            def remember(data):
                rows = data["places"][place_id].setdefault("comparisons", [])
                if not any(r["id"] == comparison["id"] for r in rows):
                    rows.append(comparison)

            await repo.transact(remember)
        connection.send_result(msg["id"], wire(result))
    except (
        DataError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        HomeAssistantError,
        OSError,
    ) as err:
        reason = str(err) if isinstance(err, DataError) else "invalid_request"
        connection.send_error(msg["id"], reason, reason)


def _authorize(request):
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        raise web.HTTPForbidden()


class ImportView(HomeAssistantView):
    url = "/api/" + DOMAIN + "/import/{entry_id}/{place}"
    name = "api:" + DOMAIN + ":import"
    requires_auth = True

    async def post(self, request, entry_id, place):
        _authorize(request)
        try:
            coordinator = _coordinator(request.app["hass"], entry_id)
            filename = request.query.get("filename", "")
            if not filename.lower().endswith((".json", ".xlsx", ".zip", ".pdf")):
                raise DataError("unsupported_import_type")
            chunks, size = [], 0
            async for chunk in request.content.iter_chunked(64 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise web.HTTPRequestEntityTooLarge(max_size=MAX_BYTES, actual_size=size)
                chunks.append(chunk)
            result = await coordinator.async_import(
                place, b"".join(chunks), filename, preview=request.query.get("preview") == "1"
            )
            return web.json_response(wire(result))
        except (DataError, HomeAssistantError, OSError) as err:
            reason = str(err) if isinstance(err, DataError) else "archive_write_failed"
            return web.json_response(
                {"error": reason}, status=400 if isinstance(err, DataError) else 500
            )


class ArtifactView(HomeAssistantView):
    url = "/api/" + DOMAIN + "/artifact/{entry_id}/{place}/{sha}"
    name = "api:" + DOMAIN + ":artifact"
    requires_auth = True

    async def get(self, request, entry_id, place, sha):
        _authorize(request)
        try:
            coordinator = _coordinator(request.app["hass"], entry_id)
            content = coordinator.repository.data["places"].get(place)
            if not content or not any(a["id"] == sha for a in content["artifacts"]):
                raise DataError("artifact_not_found")
            result = await coordinator.hass.async_add_executor_job(
                get_artifact, coordinator.artifact_root, sha
            )
            return web.Response(
                body=result,
                content_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{sha}"',
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "no-store",
                },
            )
        except (DataError, OSError):
            raise web.HTTPNotFound() from None


class BackupView(HomeAssistantView):
    """Záloha místa a výslovně vybraných originálů, nikdy přihlašovacích údajů."""

    url = "/api/" + DOMAIN + "/backup/{entry_id}/{place}"
    name = "api:" + DOMAIN + ":backup"
    requires_auth = True

    async def get(self, request, entry_id, place):
        _authorize(request)
        try:
            coordinator = _coordinator(request.app["hass"], entry_id)
            content = copy.deepcopy(coordinator.repository.data["places"][place])
            document = backup_document(coordinator.repository.account, place, content)
            documents = {}
            if request.query.get("documents") == "1":
                for artifact in content["artifacts"]:
                    documents[artifact["id"]] = await coordinator.hass.async_add_executor_job(
                        get_artifact, coordinator.artifact_root, artifact["id"]
                    )
            result = await coordinator.hass.async_add_executor_job(make_zip, document, documents)
            return web.Response(
                body=result,
                content_type="application/zip",
                headers={
                    "Content-Disposition": 'attachment; filename="mnd-private-backup.zip"',
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                },
            )
        except (DataError, OSError, KeyError):
            raise web.HTTPBadRequest() from None
