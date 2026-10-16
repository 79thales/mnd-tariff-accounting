"""Syntetické doklady: předpis, částečné platby, revize a průtok nejsou zaměnitelné."""

import copy
import unittest
from datetime import datetime, timezone

from custom_components.mnd_tariff_accounting.core.accounting import active_versions
from custom_components.mnd_tariff_accounting.core.archive import new_place
from custom_components.mnd_tariff_accounting.core.common import DataError
from custom_components.mnd_tariff_accounting.core.finance import (
    accept_advances,
    finance_rows,
    merge_finance,
)
from custom_components.mnd_tariff_accounting.core.live import anchor_comparisons, flow_value


class FinanceTests(unittest.TestCase):
    def row(self):
        return {
            "ADVI_ID": 1,
            "CP_ID": 7,
            "CUSTA_ID": 8,
            "ADVI_SUMTOTAL": "1000",
            "ADVI_BALANCE": "750",
            "ADVI_DATE": "2026-01-15",
            "CURRENCY": {"code": "CZK"},
            "PayInfo": [{"PAY_AMOUNT": "250", "PAY_DATE": "2026-01-14"}],
        }

    def normalized(self, row=None):
        return finance_rows("advances", [row or self.row()], {"cp_id": 7, "customer_id": 8})

    def test_prescription_and_real_partial_payment_are_separate(self):
        row = self.normalized()[0]
        self.assertEqual(row["prescribed"], "1000")
        self.assertEqual(row["paid"], "250")
        self.assertEqual(row["remaining"], "750")
        self.assertEqual(
            self.normalized({k: v for k, v in self.row().items() if k != "PayInfo"})[0]["paid"],
            None,
        )

    def test_another_account_or_currency_fails_without_silent_merge(self):
        for key, value in (("CP_ID", 9), ("CUSTA_ID", 9), ("CURRENCY", {"code": "EUR"})):
            with self.assertRaises(DataError):
                self.normalized({**self.row(), key: value})

    def test_repeated_import_and_correction_are_auditable(self):
        place = new_place()
        place["settings"].update(period_from="2026-01-01", period_to="2026-02-01")
        place["portal_evidence"] = {"advances": {"rows": self.normalized()}}
        self.assertEqual(accept_advances("synthetic", place, "2026-02-02"), 2)
        self.assertEqual(accept_advances("synthetic", place, "2026-02-02"), 0)
        revised = {**self.row(), "PayInfo": [{"PAY_AMOUNT": "300", "PAY_DATE": "2026-01-14"}]}
        place["portal_evidence"]["advances"]["rows"] = self.normalized(revised)
        self.assertEqual(accept_advances("synthetic", place, "2026-02-02"), 1)
        self.assertEqual(
            [r["amount"] for r in active_versions(place["events"]) if r["role"] == "payment"],
            ["300"],
        )
        self.assertEqual(len(place["events"]), 3)

    def test_shorter_prefix_preserves_older_document(self):
        old = self.normalized()
        new = self.normalized({**self.row(), "ADVI_ID": 2})
        before = copy.deepcopy(old)
        self.assertEqual(len(merge_finance(old, new)), 2)
        self.assertEqual(old, before)

    def test_equal_same_day_payments_are_not_deduplicated(self):
        row = self.row()
        row["PayInfo"] *= 2
        self.assertEqual(self.normalized(row)[0]["paid"], "500")

    def test_unconfigured_allocation_cannot_enter_accounting(self):
        with self.assertRaises(DataError):
            accept_advances("synthetic", new_place(), "2026-02-02")

    def test_withdrawn_source_payment_creates_zero_revision_not_duplicate_credit(self):
        place = new_place()
        place["settings"].update(period_from="2026-01-01", period_to="2026-02-01")
        place["portal_evidence"] = {"advances": {"rows": self.normalized()}}
        accept_advances("synthetic", place, "2026-02-02")
        place["portal_evidence"]["advances"]["rows"] = self.normalized(
            {**self.row(), "PayInfo": []}
        )
        accept_advances("synthetic", place, "2026-02-02")
        self.assertEqual(
            [r["amount"] for r in active_versions(place["events"]) if r["role"] == "payment"], ["0"]
        )
        self.assertEqual(accept_advances("synthetic", place, "2026-02-02"), 0)


class LiveFlowTests(unittest.TestCase):
    def test_new_mnd_anchor_reports_old_sensor_difference_without_mutation(self):
        place = new_place()
        place["settings"] = {
            "calibration": {
                "place": "p",
                "entity": "e",
                "segment": "meter",
                "at": "2026-01-01T00:00:00+00:00",
                "physical": "1000",
                "sensor": "20",
            }
        }
        place["readings"] = [
            {
                "id": "r",
                "place": "p",
                "meter": "meter",
                "date": "2026-01-02",
                "observed_at": "2026-01-02T00:00:00+00:00",
                "value": "1012",
                "source": "mnd",
            }
        ]
        place["samples"] = [
            {
                "entity": "e",
                "segment": "meter",
                "unit": "m³",
                "state_class": "total_increasing",
                "at": "2026-01-02T00:00:00+00:00",
                "value": "30",
                "continuity": True,
            }
        ]
        before = copy.deepcopy(place)
        comparison = anchor_comparisons("p", place, "UTC")[0]
        self.assertEqual(comparison["expected"], "1010")
        self.assertEqual(comparison["difference"], "2")
        self.assertEqual(place, before)

    def test_exact_units_and_stale_unknown_are_not_zero(self):
        now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        self.assertEqual(flow_value("10", "L/min", now, now)["current_flow_m3h"], "0.60")
        self.assertIsNone(
            flow_value("0", "m³/h", "2026-01-01T10:00:00+00:00", now)["current_flow_m3h"]
        )
        self.assertIsNone(flow_value("unavailable", "m³/h", now, now)["current_flow_m3h"])
        self.assertEqual(flow_value("2", "kWh", now, now)["flow_status"], "incompatible_unit")
        self.assertEqual(flow_value("0", "m³/h", now, now)["current_flow_m3h"], "0")
