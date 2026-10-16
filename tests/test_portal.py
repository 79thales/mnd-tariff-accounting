"""Řízený transport MND bez sítě a bez skutečných přístupů."""

import json
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from custom_components.mnd_tariff_accounting.core.portal_mapping import consumption_periods
from custom_components.mnd_tariff_accounting.portal import (
    AuthenticationRequired,
    PortalClient,
    PortalError,
    RateLimited,
    retry_seconds,
)


class Content:
    def __init__(self, raw):
        self.raw = raw

    async def iter_chunked(self, size):
        yield self.raw


class Response:
    def __init__(self, data=None, status=200, headers=None, raw=None):
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self.content_length = None
        self.content = Content(raw if raw is not None else json.dumps(data).encode())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **options):
        self.calls.append((method, url, options))
        return self.responses.pop(0)


class PortalTests(unittest.IsolatedAsyncioTestCase):
    async def test_payment_request_includes_public_period_and_omits_missing_parameters(self):
        session = Session([Response([])])
        portal = PortalClient(session)
        portal._token = "synthetic"
        await portal.payments(1, None, 7)
        params = session.calls[0][2]["params"]
        self.assertEqual(params["payPeriod"], 365)
        self.assertNotIn("custaId", params)
        self.assertEqual(params["cpId"], 7)

    async def test_finance_grows_prefix_and_reports_limit_instead_of_false_complete(self):
        session = Session(
            [
                Response([{"ADVI_ID": n} for n in range(100)]),
                Response([{"ADVI_ID": n} for n in range(101)]),
            ]
        )
        portal = PortalClient(session)
        portal._token = "synthetic"
        result = await portal.finance_list("advances", 1, 2, 7)
        self.assertTrue(result["complete"])
        self.assertEqual([c[2]["params"]["maxRowCount"] for c in session.calls], [100, 200])

    async def test_export_uses_selected_document_ids_and_validated_generated_file(self):
        session = Session(
            [
                Response({"DocumentGuid": "synthetic-guid", "FileName": "zaloha.xlsx"}),
                Response(raw=b"PK\x03\x04synthetic"),
            ]
        )
        portal = PortalClient(session)
        portal._token = "synthetic"
        content, name = await portal.finance_export("advances", [1, 2])
        self.assertTrue(content.startswith(b"PK"))
        self.assertEqual(name, "zaloha.xlsx")
        self.assertEqual(session.calls[0][2]["json"], [1, 2])
        self.assertTrue(session.calls[0][1].endswith("/Documents/AdvanceExport"))
        self.assertNotIn("Inatoken", session.calls[1][2]["headers"])

    async def test_http_date_and_long_retry_after_are_respected(self):
        now = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(retry_seconds("Fri, 16 Oct 2026 12:02:00 GMT", now), 120)
        self.assertEqual(retry_seconds("172800", now), 172800)
        self.assertEqual(retry_seconds("invalid", now), 60)

    async def test_login_verifies_authorized_partners_and_no_token_in_url(self):
        session = Session(
            [Response({"InaToken": "synthetic-token"}), Response([{"PARTNER_ID": 7}])]
        )
        portal = PortalClient(session)
        await portal.login("synthetic@example.invalid", "synthetic-password")
        self.assertEqual(len(session.calls), 2)
        self.assertTrue(all(call[2]["allow_redirects"] is False for call in session.calls))
        self.assertEqual(session.calls[1][2]["headers"]["Inatoken"], "synthetic-token")
        self.assertNotIn("synthetic-token", session.calls[1][1])
        await portal.logout()
        with self.assertRaises(AuthenticationRequired):
            await portal.supply_points(7)

    async def test_rejected_password_is_not_retried(self):
        session = Session([Response(status=401)])
        with self.assertRaises(AuthenticationRequired):
            await PortalClient(session).login("synthetic", "synthetic")
        self.assertEqual(len(session.calls), 1)

    async def test_http_200_html_is_not_authentication(self):
        with self.assertRaises(PortalError):
            await PortalClient(
                Session(
                    [Response(headers={"Content-Type": "text/html"}, raw=b"<html>Login</html>")]
                )
            ).login("synthetic", "synthetic")

    async def test_redirect_requires_interaction(self):
        with self.assertRaises(AuthenticationRequired):
            await PortalClient(Session([Response(status=302)])).login("synthetic", "synthetic")

    async def test_rate_limit_retains_retry_after(self):
        with self.assertRaises(RateLimited) as error:
            await PortalClient(
                Session([Response(status=429, headers={"Retry-After": "120"})])
            ).login("synthetic", "synthetic")
        self.assertEqual(error.exception.seconds, 120)

    async def test_export_payload_and_document_validation(self):
        from datetime import date

        session = Session(
            [
                Response({"DocumentGuid": "synthetic-guid", "FileName": "synthetic.xlsx"}),
                Response(raw=b"PK\x03\x04synthetic"),
            ]
        )
        portal = PortalClient(session)
        portal._token = "synthetic"
        content, name = await portal.export_readings(1, 2, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual(name, "synthetic.xlsx")
        self.assertTrue(content.startswith(b"PK"))
        self.assertEqual(session.calls[0][2]["json"]["DO"], "2026-01-31 23:59:00")
        self.assertNotIn("Inatoken", session.calls[1][2]["headers"])

    def test_three_graph_parts_are_numeric_not_css(self):
        rows = [
            {
                "DATE_FROM": "2026-01-01",
                "DATE_TO": "2027-01-01",
                "TYPE": typ,
                "CONS_NT": 0,
                "CONS_VT": value,
            }
            for typ, value in (("R", 1000), ("U", 200), ("E", 8000))
        ]
        graph = consumption_periods(rows)[0]
        self.assertEqual(graph["ReadingsMwh"], Decimal(1))
        self.assertEqual(graph["PortalTotalMwh"], Decimal("9.2"))

    def test_missing_graph_part_is_unknown(self):
        graph = consumption_periods(
            [
                {
                    "DATE_FROM": "2026-01-01",
                    "DATE_TO": "2027-01-01",
                    "TYPE": "R",
                    "CONS_NT": None,
                    "CONS_VT": 5,
                }
            ]
        )[0]
        self.assertIsNone(graph["ReadingsMwh"])
        self.assertIsNone(graph["PortalTotalMwh"])
