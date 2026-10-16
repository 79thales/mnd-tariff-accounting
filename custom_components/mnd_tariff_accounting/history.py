"""Obnovitelný backfill MND po exportech; žádný běh neprohlašuje úplnost bez důkazu."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.util import dt as dt_util

from .core.archive import apply_import
from .core.common import DataError, day, fingerprint
from .core.xlsx import parse_workbook
from .portal import plan_history
from .storage import put_artifact


class HistoryRunner:
    """Jediná úloha entry, limit 15 minut / nejvýše 100 segmentů za jeden běh.

    Kurzor a přijaté řádky se zapisují společně. Po cancellation nebo unloadu
    zůstane stav paused/cancelled; restart úlohu nespustí sám. Dokončené
    originály se nemažou. Nový pokus obnoví právě nehotový úsek.
    """

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.task = None
        self._active = None

    def start(self, place_id, *, max_segments=10, resume=True):
        if self.task and not self.task.done():
            if self._active != ("cloud", place_id):
                raise DataError("history_other_task_running")
            return {"status": "running", "joined": True}
        if not 1 <= max_segments <= 100:
            raise DataError("invalid_history_limit")
        place = self.coordinator.repository.data["places"].get(place_id)
        if place is None or not place["settings"].get("portal"):
            raise DataError("cloud_place_not_connected")
        self._active = ("cloud", place_id)
        self.task = self.coordinator.hass.async_create_task(
            self._run(place_id, max_segments, resume)
        )
        return {"status": "running", "joined": False}

    async def cancel(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def start_local(self, place_id, start, end):
        """Nativní Recorder sdílí jediný běh entry s cloudovým backfillem."""
        if self.task and not self.task.done():
            if self._active != ("recorder", place_id):
                raise DataError("history_other_task_running")
            return {"status": "running", "joined": True}
        left, right = day(start), day(end)
        if not 0 < (right - left).days <= 1095:
            raise DataError("invalid_history_range")
        self._active = ("recorder", place_id)
        self.task = self.coordinator.hass.async_create_task(self._run_local(place_id, left, right))
        return {"status": "running", "joined": False}

    async def _run_local(self, place_id, start, end):
        from .recorder import async_read_history

        repo = self.coordinator.repository
        previous = repo.data["job"]

        def source_context():
            settings = repo.data["places"][place_id]["settings"]
            return fingerprint(
                [
                    settings.get("history_registry_id") or settings.get("source_registry_id"),
                    settings.get("history_unit_m3"),
                    settings.get("segment"),
                ]
            )

        # Kurzor lze převzít jen pro stejný fyzický zdroj a objem pulsu.
        # Po změně konfigurace se stejný interval načte znovu od začátku.
        source_revision = source_context()
        cursor = (
            day(previous["cursor"])
            if previous.get("kind") == "recorder"
            and previous.get("place") == place_id
            and previous.get("start") == start.isoformat()
            and previous.get("end") == end.isoformat()
            and previous.get("source_revision") == source_revision
            else start
        )
        await repo.transact(
            lambda data: data.update(
                job={
                    "kind": "recorder",
                    "status": "running",
                    "place": place_id,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "cursor": cursor.isoformat(),
                    "completed_blocks": 0,
                    "source_revision": source_revision,
                }
            )
        )
        try:
            async with asyncio.timeout(15 * 60):
                while cursor < end:
                    if source_context() != source_revision:
                        raise DataError("history_source_changed")
                    right = min(cursor + timedelta(days=7), end)
                    await async_read_history(
                        self.coordinator, place_id, cursor, right, right.isoformat()
                    )
                    cursor = right
                await repo.transact(lambda data: data["job"].update(status="completed"))
        except asyncio.CancelledError:
            await repo.transact(
                lambda data: data["job"].update(status="paused", reason="cancelled_or_unloaded")
            )
            raise
        except (DataError, TimeoutError) as err:
            reason = str(err) if isinstance(err, DataError) else "history_timeout"
            await repo.transact(
                lambda data: data["job"].update(
                    status="paused",
                    reason=reason,
                )
            )

    async def _run(self, place_id, max_segments, resume):
        coordinator = self.coordinator
        repo = coordinator.repository
        source = repo.data["places"][place_id]["settings"]["portal"]
        previous = repo.data["job"]
        today = dt_util.as_local(dt_util.utcnow()).date()
        resume_same = (
            resume
            and previous.get("kind") == "cloud"
            and previous.get("place") == place_id
            and previous.get("cursor")
        )
        end = day(previous["cursor"]) if resume_same else today

        def begin(data):
            data["job"] = {
                "kind": "cloud",
                "status": "running",
                "place": place_id,
                "cursor": end.isoformat(),
                "started_at": dt_util.utcnow().isoformat(),
                "segments": previous.get("segments", []) if resume_same else [],
            }

        await repo.transact(begin)
        try:
            async with asyncio.timeout(15 * 60):
                for start, stop in plan_history(end, max_segments=max_segments):
                    content, filename = await coordinator.portal.export_readings(
                        source["cp_id"], source["contract_id"], start, stop
                    )
                    parsed = await coordinator.hass.async_add_executor_job(
                        parse_workbook, content, filename, place_id
                    )
                    sha = await coordinator.hass.async_add_executor_job(
                        put_artifact, coordinator.artifact_root, content
                    )

                    def commit(data):
                        apply_import(data, parsed)
                        place = data["places"][place_id]
                        if not any(a["id"] == sha for a in place["artifacts"]):
                            place["artifacts"].append(
                                {
                                    "id": sha,
                                    "filename": filename,
                                    "acquired_at": dt_util.utcnow().isoformat(),
                                    "origin": "mnd",
                                    "requested_from": start.isoformat(),
                                    "requested_to": stop.isoformat(),
                                    "range_inclusive": True,
                                }
                            )
                        data["job"]["segments"].append(
                            {
                                "from": start.isoformat(),
                                "to": stop.isoformat(),
                                "rows": len(parsed["readings"]),
                                "sha256": sha,
                                "valid": parsed["complete"],
                            }
                        )
                        # Neplatný neprázdný řádek nesmí posunout kurzor jako
                        # úspěšně ověřené pokrytí. Úsek lze po opravě opakovat.
                        if parsed["complete"]:
                            data["job"]["cursor"] = (start - timedelta(days=1)).isoformat()
                        place["coverage"] = {
                            "Status": "Unverified" if parsed["complete"] else "Partial",
                            "Evidence": "Nejstarší hranice není doložena.",
                        }
                        if parsed["complete"]:
                            place["last_successful_import"] = dt_util.utcnow().isoformat()

                    await repo.transact(commit)
                    if not parsed["complete"]:
                        raise DataError("history_invalid_rows")
                await repo.transact(
                    lambda data: data["job"].update(
                        status="limited", reason="earliest_boundary_unverified"
                    )
                )
        except asyncio.CancelledError:
            await repo.transact(
                lambda data: data["job"].update(status="paused", reason="cancelled_or_unloaded")
            )
            raise
        except (DataError, TimeoutError) as err:
            reason = str(err) if isinstance(err, DataError) else "history_timeout"
            await repo.transact(lambda data: data["job"].update(status="paused", reason=reason))
        finally:
            await coordinator.async_recompute()
