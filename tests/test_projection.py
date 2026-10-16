"""Projekce stejných podkladů jako používají entity a panel, bez napodobení HA."""

import unittest
from datetime import datetime, timezone

from test_domain import PLACE, reading, request

from custom_components.mnd_tariff_accounting.core.archive import new_place
from custom_components.mnd_tariff_accounting.core.common import DataError, wire
from custom_components.mnd_tariff_accounting.core.forecast import add_snapshot
from custom_components.mnd_tariff_accounting.core.projection import evaluate_place

NOW = datetime(2026, 2, 2, tzinfo=timezone.utc)


def fixture():
    data = new_place("Synthetic")
    original = request()
    data["settings"] = {
        "period_from": "2026-01-01",
        "period_to": "2026-03-01",
        "opening_credit": "0",
        "payments_complete": True,
        "source_mode": "manual",
        "segment": "0001",
    }
    data["tariffs"] = original["tariffs"]
    data["conversions"] = original["conversions"]
    return data


class ProjectionTests(unittest.TestCase):
    def evaluate(self, place):
        return evaluate_place(PLACE, place, "UTC", NOW)

    def test_unknown_is_not_zero_and_empty_needs_configuration(self):
        result = self.evaluate(new_place())
        self.assertEqual(result["status"], "needs_configuration")
        self.assertIsNone(result["latest_mnd"])
        self.assertNotIn("balance_czk", result)

    def test_future_manual_does_not_become_current(self):
        place = fixture()
        place["readings"] = wire(
            [
                reading().dump(),
                reading("1100", "2026-02-01", "manual").dump(),
                reading("9999", "2026-03-01", "manual").dump(),
            ]
        )
        result = self.evaluate(place)
        self.assertEqual(result["current_meter"], "1100")
        self.assertEqual(result["evaluated_to"], "2026-02-01")
        self.assertIn("future_readings_excluded", result["warnings"])

    def test_mnd_conflict_is_not_arbitrary_maximum(self):
        place = fixture()
        place["readings"] = wire([reading().dump(), reading("1004").dump()])
        result = self.evaluate(place)
        self.assertIsNone(result["latest_mnd"])
        self.assertIsNone(result["current_meter"])

    def test_sensor_tail_follows_exact_mnd_anchor_without_persisting_fake_reading(self):
        place = fixture()
        place["settings"]["source_mode"] = "sensor"
        place["settings"]["source_registry_id"] = "registry-1"
        place["readings"] = wire([reading(observed_at="2026-01-01T00:00:00Z").dump()])
        place["samples"] = [
            {
                "entity": "registry-1",
                "segment": "0001",
                "unit": "m³",
                "state_class": "total_increasing",
                "value": value,
                "at": at,
            }
            for at, value in [("2026-01-01T00:00:00Z", "200"), ("2026-02-01T00:00:00Z", "230")]
        ]
        result = self.evaluate(place)
        self.assertEqual(result["current_meter"], "1030")
        self.assertEqual(result["volume_m3"], "30")
        self.assertEqual(result["measurement_source"], "mnd+sensor")
        self.assertEqual(len(place["readings"]), 1)

    def test_sensor_error_does_not_destroy_confirmed_invoice(self):
        place = fixture()
        place["settings"]["source_mode"] = "sensor"
        place["readings"] = wire([reading().dump()])
        place["invoices"] = [
            {
                "id": "invoice",
                "from": "2026-01-01",
                "to": "2026-02-01",
                "cost": "800",
                "result": "200",
                "confirmed": True,
            }
        ]
        place["samples"] = [
            {
                "entity": "registry-1",
                "segment": "0001",
                "unit": "kWh",
                "state_class": "total",
                "value": "1",
                "at": "2026-02-01T00:00:00Z",
            }
        ]
        result = self.evaluate(place)
        self.assertEqual(result["invoice_result_czk"], "200")
        self.assertEqual(result["measurement_reason"], "incompatible_sensor")

    def test_manual_same_day_after_exact_anchor_can_be_newer(self):
        place = fixture()
        place["readings"] = wire(
            [
                reading(observed_at="2026-01-01T00:00:00Z").dump(),
                reading("1002", "2026-01-01", "manual", observed_at="2026-01-01T12:00:00Z").dump(),
            ]
        )
        result = self.evaluate(place)
        self.assertEqual(result["current_meter"], "1002")
        # Dva m³ × 10 kWh/m³ × 1000 Kč/MWh = 20 Kč, nulový paušál.
        self.assertEqual(result["balance_czk"], "-20.00")
        self.assertTrue(result["complete"])

    def test_mismatched_local_date_is_rejected(self):
        place = fixture()
        place["readings"] = wire([reading(observed_at="2026-01-02T00:00:00Z").dump()])
        with self.assertRaisesRegex(DataError, "date_time_mismatch"):
            self.evaluate(place)

    def test_snapshot_import_order_does_not_replace_latest_forecast(self):
        later = {"retrieved_at": "2026-02-01T00:00:00Z", "periods": []}
        older = {"retrieved_at": "2026-01-01T00:00:00Z", "periods": []}
        result = add_snapshot(add_snapshot([], later), older)
        self.assertEqual(result[-1]["retrieved_at"], later["retrieved_at"])
