"""Čtecí asynchronní klient podle veřejného JS Moje MND z 16. 10. 2026.

Prozkoumané JS potvrzuje /api/SignInToInternetAccount s UserName/Password,
odpověď InaToken/Partners a hlavičku Inatoken u čtení. Tyto znalosti nejsou
důkazem živého testu nové integrace. Token zůstává pouze v paměti. Klient
neposílá samoodečty, platby ani změny smluv; dovolené POST jsou jen login
a žádost o soubor exportu. TLS se ověřuje a redirect se nepovoluje.
"""

from __future__ import annotations

import asyncio
import random
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from math import ceil

from aiohttp import ClientError

from .core.common import MAX_BYTES, DataError, load_json

ORIGIN = "https://moje.mnd.cz"
PUBLIC_SOURCE = "/_next/static/chunks/pages/_app-d4693e13afff6e1f.js"


class PortalError(DataError):
    """Bez URL, syrové odpovědi, tokenu nebo zákaznické identity v hlášení."""


class AuthenticationRequired(PortalError):
    pass


class RateLimited(PortalError):
    def __init__(self, seconds=60):
        super().__init__("portal_rate_limited")
        self.seconds = max(1, int(seconds))


def retry_seconds(value, now=None):
    """Retry-After může být počet sekund i HTTP datum; chybný údaj má 60 s.

    Dlouhý platný odstup se nezkrátí na polling interval. Ukládá se jen
    monotónní konec blokace v paměti, nikoli zákaznická síťová odpověď.
    """
    if len(value) > 128:
        return 60
    if value.isdigit():
        return max(1, int(value))
    try:
        target = parsedate_to_datetime(value)
        if target.tzinfo is None:
            return 60
        return max(1, ceil((target - (now or datetime.now(timezone.utc))).total_seconds()))
    except (ValueError, TypeError, OverflowError):
        return 60


class PortalClient:
    """Jedna relace a zámek na účet; nezávislé instance nemíchají tokeny.

    GET má nejvýše tři pokusy při přechodné chybě, login jediný. 401/403
    ukončí automatické opakování a vyžaduje reauth. Unload zavolá logout,
    čímž odstraní lokální token; veřejný klient také odhlašuje jen lokálně.
    """

    def __init__(self, session):
        self.session = session
        self.lock = asyncio.Lock()
        self._token = None
        self.partners = []
        self._closed = False
        self._blocked_until = 0.0

    @property
    def authenticated(self):
        return self._token is not None and not self._closed

    async def _request(
        self, method, path, *, params=None, payload=None, authenticated=True, binary=False
    ):
        if self._closed:
            raise PortalError("portal_closed")
        remaining = self._blocked_until - asyncio.get_running_loop().time()
        if remaining > 0:
            raise RateLimited(max(1, int(remaining)))
        if authenticated and not self._token:
            raise AuthenticationRequired("portal_auth_required")
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Inatoken"] = self._token
        # URL a parametry mají interní whitelist v jednotlivých veřejných
        # metodách. Uživatelské URL ani serverové cesty se sem nepřebírají.
        for attempt in range(3 if method == "GET" else 1):
            try:
                async with asyncio.timeout(30):
                    async with self.session.request(
                        method,
                        ORIGIN + path,
                        params=params,
                        json=payload,
                        headers=headers,
                        allow_redirects=False,
                    ) as response:
                        if response.status in (401, 403):
                            self._token = None
                            raise AuthenticationRequired("portal_auth_required")
                        if response.status == 429:
                            retry = response.headers.get("Retry-After", "60")
                            error = RateLimited(retry_seconds(retry))
                            self._blocked_until = asyncio.get_running_loop().time() + error.seconds
                            raise error
                        if 300 <= response.status < 400:
                            raise AuthenticationRequired("portal_interaction_required")
                        if response.status >= 500:
                            raise OSError("portal_server_unavailable")
                        if response.status != 200:
                            raise PortalError("portal_request_failed")
                        if response.content_length and response.content_length > MAX_BYTES:
                            raise PortalError("portal_response_too_large")
                        parts, size = [], 0
                        async for part in response.content.iter_chunked(64 * 1024):
                            size += len(part)
                            if size > MAX_BYTES:
                                raise PortalError("portal_response_too_large")
                            parts.append(part)
                        raw = b"".join(parts)
                        if binary:
                            if not raw.startswith((b"PK\x03\x04", b"%PDF-")):
                                raise PortalError("portal_invalid_document")
                            return raw
                        if "json" not in response.headers.get("Content-Type", "").lower():
                            raise PortalError("portal_expected_json")
                        return load_json(raw)
            except (OSError, TimeoutError, ClientError) as err:
                if attempt == (2 if method == "GET" else 0):
                    raise PortalError("portal_unavailable") from err
                await asyncio.sleep(2**attempt + random.random())
        raise PortalError("portal_unavailable")

    async def login(self, username: str, password: str):
        """Úspěch vyžaduje token a autorizované čtení partnerů, nikoli jen HTTP 200."""
        async with self.lock:
            self._token = None
            result = await self._request(
                "POST",
                "/api/SignInToInternetAccount",
                authenticated=False,
                payload={"UserName": username, "Password": password},
            )
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("InaToken"), str)
                or not result["InaToken"]
            ):
                raise AuthenticationRequired("portal_interaction_or_credentials_required")
            self._token = result["InaToken"]
            try:
                partners = await self._request("GET", "/api/partners")
                if (
                    not isinstance(partners, list)
                    or not partners
                    or any(not isinstance(p, dict) or "PARTNER_ID" not in p for p in partners)
                ):
                    raise PortalError("portal_schema_changed")
                self.partners = partners
            except BaseException:
                self._token = None
                raise
            return partners

    async def supply_points(self, partner_id):
        async with self.lock:
            result = await self._request(
                "GET", "/api/consumptionPlaces", params={"partnerId": partner_id}
            )
            if not isinstance(result, list) or any(
                not isinstance(row, dict) or "CP_ID" not in row or "CONT_ID" not in row
                for row in result
            ):
                raise PortalError("portal_schema_changed")
            return result

    async def place_details(self, cp_id, contract_id):
        async with self.lock:
            return await self._request(
                "GET", "/api/consumptionPlace", params={"cpId": cp_id, "contractId": contract_id}
            )

    async def readings(self, cp_id, contract_id, years=3):
        async with self.lock:
            params = {"cpId": cp_id, "contractId": contract_id, "years": years}
            return await self._request("GET", "/api/readings", params=params)

    async def consumption(self, cp_id, contract_id, years=3):
        async with self.lock:
            params = {"cpId": cp_id, "contractId": contract_id, "years": years}
            return await self._request("GET", "/api/consumptions", params=params)

    async def contract_documents(self, cp_id, contract_id):
        async with self.lock:
            return await self._request(
                "GET", "/api/contractDocs", params={"cpId": cp_id, "contractId": contract_id}
            )

    async def deposit(self, cp_id, contract_id):
        async with self.lock:
            return await self._request(
                "GET",
                "/api/consumptionKoefBalance",
                params={"cpId": cp_id, "contractId": contract_id},
            )

    async def export_readings(self, cp_id, contract_id, start: date, end: date):
        """Doložený payload OD/DO má místní čas, oba dny včetně 00:00–23:59.

        GUID a název vrací exportní operace; klient z nich nesestavuje cestu
        disku. Soubor před importem znovu ověří svou vnitřní identitu.
        """
        if start > end or (end - start).days >= 366:
            raise PortalError("invalid_export_period")
        async with self.lock:
            result = await self._request(
                "POST",
                "/api/Documents/ReadingsExport",
                payload={
                    "CP_ID": cp_id,
                    "CONT_ID": contract_id,
                    "OD": start.isoformat() + " 00:00:00",
                    "DO": end.isoformat() + " 23:59:00",
                    "PERIOD": "R",
                },
            )
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("DocumentGuid"), str)
                or not isinstance(result.get("FileName"), str)
            ):
                raise PortalError("portal_schema_changed")
            content = await self._request(
                "GET",
                "/data/Documents/GetByGuid",
                params={"docGuid": result["DocumentGuid"]},
                authenticated=False,
                binary=True,
            )
            return content, result["FileName"]

    async def profile(self, partner_id):
        """Soukromé údaje jen na výslovné vyžádání, nikoli při běžném pollingu."""
        async with self.lock:
            return await self._request(
                "GET", "/api/inaOtherDetail", params={"partnerId": partner_id}
            )

    async def download_contract(self, cp_id, contract_id, document):
        """Doklad musí pocházet z čerstvého seznamu místa, ne z URL klienta panelu."""
        async with self.lock:
            guid, name = document.get("DOC_GUID"), document.get("DOC_NAME")
            if (
                not guid
                and document.get("ERR_TYPE") == 1
                and document.get("PRICE_ID")
                and (document.get("COE_ID") or document.get("CADCOE_ID"))
            ):
                params = {"cpId": cp_id, "contractId": contract_id, "priceId": document["PRICE_ID"]}
                for remote, field in (("coeId", "COE_ID"), ("cadcoeId", "CADCOE_ID")):
                    if document.get(field) is not None:
                        params[remote] = document[field]
                generated = await self._request(
                    "POST", "/api/Documents/ContractDocByPrice", params=params
                )
                if not isinstance(generated, dict):
                    raise PortalError("portal_schema_changed")
                guid, name = generated.get("DocumentGuid"), generated.get("FileName")
            if not isinstance(guid, str) or not isinstance(name, str) or not name:
                raise PortalError("portal_document_unavailable")
            content = await self._request(
                "GET",
                "/data/Documents/GetByGuid",
                params={"docGuid": guid},
                authenticated=False,
                binary=True,
            )
            return content, name

    async def payments(self, partner_id, customer_id, cp_id, *, offset=0, limit=100):
        if not 0 <= offset <= 100_000 or not 1 <= limit <= 500:
            raise PortalError("invalid_pagination")
        async with self.lock:
            return await self._request(
                "GET",
                "/api/payments",
                params={
                    "partnerId": partner_id,
                    "custaId": customer_id,
                    "caccId": 170,
                    "cpId": cp_id,
                    "maxRowCount": limit,
                    "skipRowCount": offset,
                },
            )

    async def logout(self):
        """Veřejný web odhlašuje vymazáním sessionStorage; serverový logout není doložen."""
        async with self.lock:
            self._token = None
            self.partners = []

    async def close(self):
        await self.logout()
        self._closed = True


def plan_history(end: date, *, max_segments=10, max_days=366, earliest=None):
    """Navazující exportní úseky oba dny včetně; limit není důkaz počátku historie."""
    from datetime import timedelta

    if not 1 <= max_segments <= 100 or not 1 <= max_days <= 366 or (earliest and earliest > end):
        raise DataError("invalid_history_range")
    result = []
    for _ in range(max_segments):
        start = end - timedelta(days=max_days - 1)
        if earliest:
            start = max(start, earliest)
        result.append((start, end))
        if earliest and start == earliest:
            break
        end = start - timedelta(days=1)
    return result
