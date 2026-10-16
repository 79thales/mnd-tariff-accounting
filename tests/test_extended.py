"""Regrese importu, záloh, DST a transakcí nad syntetickými podklady."""

import asyncio
import copy
import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.mnd_tariff_accounting.core.accounting import (
    invoice_settlement,
    ledger_totals,
)
from custom_components.mnd_tariff_accounting.core.archive import (
    Repository,
    empty_archive,
    new_place,
)
from custom_components.mnd_tariff_accounting.core.backup import (
    backup_document,
    make_zip,
    parse_zip,
    restore_place,
)
from custom_components.mnd_tariff_accounting.core.common import DataError, canonical, day
from custom_components.mnd_tariff_accounting.core.importer import export_csv, parse_v1
from custom_components.mnd_tariff_accounting.core.statistics import daily_profile
from custom_components.mnd_tariff_accounting.dashboard import build_views
from custom_components.mnd_tariff_accounting.editing import edit_place

PLACE = "27ZG000Z0000000X"
NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def archive():
    data = empty_archive("synthetic-account")
    data["places"][PLACE] = new_place("Synthetic place")
    return data


def source_v1():
    return {
        "SchemaVersion": 1,
        "Place": {"Id": PLACE, "Address": "Synthetic", "Commodity": "Plyn"},
        "ExportedAt": "2026-01-01T12:00:00Z",
        "Readings": [
            {
                "SupplyPointId": PLACE,
                "Date": "2026-01-01",
                "MeterStateM3": 1000,
                "MeterNumber": "00001",
                "Method": "Samoodečtem",
                "Status": "Neznámý status",
                "SourceFile": "synthetic.xlsx",
                "SourceRow": 1,
            }
        ],
        "Coverage": {"Status": "Unverified", "Evidence": "Synthetic", "Segments": []},
        "Actual": None,
        "Accounting": None,
    }


class ImportTests(unittest.TestCase):
    def test_manual_actual_v1_keeps_its_local_day_and_physical_source(self):
        source = source_v1()
        source["Actual"] = {
            "SupplyPointId": PLACE,
            "MeterNumber": "00001",
            "MeterStateM3": 1005,
            "MeasuredAt": "2026-01-02T00:30:00+01:00",
            "RetrievedAt": "2026-01-02T01:00:00+01:00",
            "Source": "Manual",
            "Estimated": False,
            "Note": "Synthetic manual reading",
        }
        result = parse_v1(canonical(source), PLACE, "Europe/Prague")
        self.assertEqual(result["readings"][-1]["source"], "manual")
        self.assertEqual(str(result["readings"][-1]["date"]), "2026-01-02")
        self.assertEqual(result["raw"]["Actual"], source["Actual"])

    def test_old_v1_optional_fields_not_synthesized_in_raw(self):
        parsed = parse_v1(canonical(source_v1()), PLACE)
        self.assertNotIn("Deposit", parsed["raw"])
        self.assertEqual(parsed["readings"][0]["status"], "Neznámý status")

    def test_decimal_json_preserved(self):
        raw = canonical(source_v1()).replace(
            b'"MeterStateM3":1000', b'"MeterStateM3":1000.1234567890123456789'
        )
        self.assertEqual(
            parse_v1(raw, PLACE)["readings"][0]["value"], Decimal("1000.1234567890123456789")
        )

    def test_future_v1_version_wrong_place_and_wrong_type(self):
        for field, value in (("SchemaVersion", 2), ("Readings", "not-an-array")):
            source = source_v1()
            source[field] = value
            with self.assertRaises(DataError):
                parse_v1(canonical(source), PLACE)
        with self.assertRaises(DataError):
            parse_v1(canonical(source_v1()), "27ZG000Z0000000Y")

    def test_csv_formula_protection_and_decimal(self):
        data = export_csv(
            [{"text": "=1+1", "number": Decimal("-1.25")}], ["text", "number"]
        ).decode("utf-8-sig")
        self.assertIn("'=1+1", data)
        self.assertIn("-1,25", data)


class BackupTests(unittest.TestCase):
    def test_zip_roundtrip_with_original(self):
        data = archive()
        original = b"synthetic original"
        sha = hashlib.sha256(original).hexdigest()
        data["places"][PLACE]["artifacts"].append({"id": sha, "filename": "synthetic.txt"})
        document = backup_document("synthetic-account", PLACE, data["places"][PLACE])
        content = make_zip(document, {sha: original})
        restored = parse_zip(content, PLACE)
        self.assertEqual(restored["documents"][sha], original)
        target = archive()
        restore_place(target, restored)
        self.assertEqual(target["places"][PLACE], data["places"][PLACE])

    def test_corrupt_original_or_wrong_place_rejected(self):
        data = archive()
        document = backup_document("synthetic-account", PLACE, data["places"][PLACE])
        content = make_zip(document, {})
        with self.assertRaises(DataError):
            parse_zip(content, "27ZG000Z0000000Y")
        with self.assertRaises(DataError):
            make_zip(document, {"bad": b"bad"})

    def test_restore_does_not_replace_local_settings(self):
        data = archive()
        document = backup_document("synthetic-account", PLACE, data["places"][PLACE])
        parsed = parse_zip(make_zip(document, {}), PLACE)
        data["places"][PLACE]["settings"] = {"opening_credit": "123"}
        with self.assertRaises(DataError):
            restore_place(data, parsed)


class EditorTests(unittest.TestCase):
    def test_corrected_invoice_inherits_refund_and_exposes_excess(self):
        old = {
            "id": "old",
            "from": "2026-01-01",
            "to": "2026-02-01",
            "cost": "1000",
            "result": "200",
            "confirmed": True,
        }
        corrected = {**old, "id": "new", "supersedes": "old", "cost": "1100", "result": "100"}
        refund = {"id": "refund", "invoice": "old", "role": "refund", "amount": "200"}
        result = invoice_settlement(corrected, [refund], [old, corrected])
        self.assertEqual(result["result"], 100)
        self.assertEqual(result["remaining"], 0)
        self.assertEqual(result["over_settled"], 100)
        self.assertEqual(result["remaining_signed"], -100)

    def test_refunded_surplus_corrected_to_deficit_increases_actual_debt(self):
        invoice = {"id": "corrected", "supersedes": "old", "result": "-100"}
        result = invoice_settlement(
            invoice, [{"id": "refund", "invoice": "old", "role": "refund", "amount": "200"}]
        )
        self.assertEqual(result["remaining"], 300)
        self.assertEqual(result["remaining_kind"], "deficit")

    def test_unmatched_bank_payment_cannot_close_confirmed_invoice(self):
        result = invoice_settlement(
            {"id": "bill", "result": "-100"},
            [
                {
                    "id": "pay",
                    "invoice": "bill",
                    "role": "payment",
                    "amount": "100",
                    "verification": "unmatched",
                }
            ],
        )
        self.assertFalse(result["settlement_complete"])
        self.assertIsNone(result["remaining"])

    def test_transfer_with_two_identical_directions_cannot_settle_invoice(self):
        result = invoice_settlement(
            {"id": "bill", "result": "100"},
            [
                {
                    "id": "a",
                    "invoice": "bill",
                    "role": "transfer_out",
                    "amount": "100",
                    "counterpart": "b",
                },
                {"id": "b", "role": "transfer_out", "amount": "100", "counterpart": "a"},
            ],
        )
        self.assertFalse(result["settlement_complete"])
        self.assertIsNone(result["remaining"])

    def test_transfer_records_both_sides_and_unmatched_credit_is_incomplete(self):
        data = archive()
        self.edit(
            data,
            "transfer",
            {
                "id": "transfer-op",
                "amount": "250",
                "date": "2026-03-01",
                "from": "2026-01-01",
                "to": "2026-03-01",
                "target_from": "2026-03-01",
                "target_to": "2026-05-01",
            },
        )
        events = data["places"][PLACE]["events"]
        first = ledger_totals(events, day("2026-01-01"), day("2026-03-01"))
        next_period = ledger_totals(events, day("2026-03-01"), day("2026-05-01"))
        self.assertEqual(first["transfer_out"], 250)
        self.assertEqual(next_period["transfer_in"], 250)
        self.assertEqual(first["payment"], 0)
        self.assertEqual(next_period["warnings"], [])
        broken = ledger_totals(events[1:], day("2026-03-01"), day("2026-05-01"))
        self.assertIn("transfer_matching_required", broken["warnings"])

    def test_future_actual_payment_rejected_but_plan_allowed(self):
        record = {"id": "future", "role": "payment", "date": "2099-01-01", "amount": "500"}
        with self.assertRaisesRegex(DataError, "future_payment"):
            self.edit(archive(), "events", record)
        self.edit(archive(), "events", {**record, "role": "prescribed"})

    def test_same_payment_amount_with_corrected_date_creates_revision(self):
        data = archive()
        self.edit(data, "settings", {"period_from": "2026-01-01", "period_to": "2026-03-01"})
        for operation, date in [("one", "2026-01-05"), ("two", "2026-01-06")]:
            self.edit(
                data,
                "advance_grid",
                {"id": operation, "rows": [{"month": "2026-01", "paid": "500", "paid_on": date}]},
            )
        events = data["places"][PLACE]["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1]["supersedes"], events[0]["id"])
        self.assertEqual(events[1]["date"], "2026-01-06")

    def edit(self, data, section, record):
        return edit_place(
            data, place_id=PLACE, section=section, record=record, now=NOW, zone="Europe/Prague"
        )

    def test_future_reading_and_mnd_forgery_rejected(self):
        for record in (
            {"id": "x", "meter": "0001", "value": "2", "observed_at": "2099-01-01T00:00:00Z"},
            {
                "id": "x",
                "meter": "0001",
                "value": "2",
                "observed_at": "2026-01-01T00:00:00Z",
                "source": "mnd",
            },
        ):
            with self.assertRaises(DataError):
                self.edit(archive(), "readings", record)

    def test_monthly_plan_does_not_create_payment(self):
        data = archive()
        self.edit(data, "settings", {"period_from": "2026-01-01", "period_to": "2026-03-01"})
        self.edit(
            data,
            "advance_grid",
            {"id": "operation-1", "rows": [{"month": "2026-01", "prescribed": "500"}]},
        )
        self.assertEqual([e["role"] for e in data["places"][PLACE]["events"]], ["prescribed"])

    def test_monthly_overpayment_allowed_and_correction_audited(self):
        data = archive()
        self.edit(data, "settings", {"period_from": "2026-01-01", "period_to": "2026-03-01"})
        self.edit(
            data,
            "advance_grid",
            {
                "id": "op1",
                "rows": [
                    {
                        "month": "2026-01",
                        "prescribed": "500",
                        "paid": "700",
                        "paid_on": "2026-01-05",
                    }
                ],
            },
        )
        self.edit(
            data,
            "advance_grid",
            {"id": "op2", "rows": [{"month": "2026-01", "paid": "750", "paid_on": "2026-01-05"}]},
        )
        events = data["places"][PLACE]["events"]
        self.assertEqual(len(events), 3)
        self.assertEqual(events[-1]["supersedes"], events[1]["id"])

    def test_grid_invalid_row_rolls_back_whole_transaction(self):
        data = archive()
        self.edit(data, "settings", {"period_from": "2026-01-01", "period_to": "2026-03-01"})
        before = copy.deepcopy(data)

        async def attempt():
            async def save(_data):
                raise AssertionError("Neplatná transakce nesmí dosáhnout zapisovače.")

            repo = Repository("synthetic-account", data, save)
            with self.assertRaises(DataError):
                await repo.transact(
                    lambda candidate: self.edit(
                        candidate,
                        "advance_grid",
                        {
                            "id": "op1",
                            "rows": [
                                {"month": "2026-01", "prescribed": "500"},
                                {"month": "2026-02", "prescribed": "-1"},
                            ],
                        },
                    )
                )
            self.assertEqual(repo.data, before)

        asyncio.run(attempt())
        self.assertEqual(data, before)


class StatisticsTests(unittest.TestCase):
    def rows(self, local_date):
        zone = ZoneInfo("Europe/Prague")
        start = datetime.fromisoformat(local_date).replace(tzinfo=zone)
        end = start + timedelta(days=1)
        first, last = int(start.timestamp()), int(end.timestamp())
        return [
            {"start": stamp, "state": i, "sum": i, "change": 1}
            for i, stamp in enumerate(range(first - 3600, last, 3600))
        ]

    def test_spring_and_autumn_have_23_and_25_hours(self):
        for value, hours in (("2026-03-29", 23), ("2026-10-25", 25)):
            profile = daily_profile(self.rows(value), "Europe/Prague")[-1]
            self.assertTrue(profile["complete"])
            self.assertEqual(profile["expected_hours"], hours)
            self.assertEqual(profile["m3"], hours)

    def test_missing_or_frozen_unknown_data_not_zero(self):
        rows = self.rows("2026-10-01")
        rows.pop(10)
        self.assertIsNone(daily_profile(rows, "Europe/Prague")[-1]["m3"])


class DashboardTests(unittest.TestCase):
    def test_template_entities_and_navigation(self):
        keys = (
            "current_flow_m3h",
            "current_deposit_czk",
            "latest_mnd",
            "latest_mnd_date",
            "current_meter",
            "status",
            "volume_m3",
            "known_cost_czk",
            "paid_czk",
            "balance_czk",
            "billing_paid_czk",
            "billing_plan_czk",
            "billing_cost_czk",
            "billing_forecast_cost_czk",
            "billing_forecast_balance_czk",
            "billing_actual_mwh",
            "billing_forecast_mwh",
            "billing_volume_m3",
        )
        result = build_views(
            "Synthetic MND",
            "synthetic-gas",
            {key: "sensor.renamed_" + key for key in keys},
            "synthetic-entry",
            PLACE,
        )
        self.assertEqual(result["missing_entities"], [])
        views = result["config"]["views"]
        self.assertEqual(len(views), 6)
        self.assertTrue(all(v["cards"][0]["layout_version"] == 3 for v in views))
        self.assertTrue(
            all(v["subview"] and v["back_path"] == "/lovelace/synthetic-gas" for v in views[1:])
        )
        self.assertNotIn("{{", canonical(result).decode())


class ConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_serial_transactions_do_not_lose_newer_data(self):
        saved = []

        async def save(data):
            await asyncio.sleep(0)
            saved.append(copy.deepcopy(data))

        repo = Repository("synthetic-account", None, save)
        await asyncio.gather(
            repo.transact(lambda data: data.update(a=1)),
            repo.transact(lambda data: data.update(b=2)),
        )
        self.assertEqual(repo.data["revision"], 2)
        self.assertEqual(repo.data["a"], 1)
        self.assertEqual(repo.data["b"], 2)

    async def test_cancellation_finishes_started_commit(self):
        started, finish = asyncio.Event(), asyncio.Event()

        async def save(data):
            started.set()
            await finish.wait()

        repo = Repository("synthetic-account", None, save)
        task = asyncio.create_task(repo.transact(lambda data: data.update(committed=True)))
        await started.wait()
        task.cancel()
        finish.set()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(repo.data["committed"])
