"""Ověření orientační návaznosti MND/HA na syntetických datech."""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from custom_components.mnd_tariff_accounting.core.archive import new_place
from custom_components.mnd_tariff_accounting.core.orientational import orientational_view
from custom_components.mnd_tariff_accounting.core.projection import evaluate_place

PLACE = "27ZG000Z0000000X"
NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def scenario():
    place = new_place("synthetic")
    place["settings"].update(segment="meter", source_registry_id="volume",
                             history_registry_id="pulse", history_unit_m3="0.01")
    readings = [("2025-10-15", "10"), ("2025-11-15", "41"), ("2025-12-15", "71"),
                ("2026-01-14", "101"), ("2026-03-30", "200"), ("2026-10-15", "300")]
    place["readings"] = [
        {"id": f"r{i}", "place": PLACE, "meter": "meter", "segment": "meter",
         "date": date, "value": value, "source": "mnd", "method": "Samoodečtem"}
        for i, (date, value) in enumerate(readings)
    ]
    place["daily_profile"] = [
        {"date": (NOW.date() - timedelta(days=i)).isoformat(), "m3": "1", "complete": True,
         "entity": "pulse", "segment": "meter", "original_unit": "pulse",
         "volume_per_unit_m3": "0.01"}
        for i in range(1, 288)
    ]
    place["daily_profile"].append({"date": NOW.date().isoformat(), "known_m3": "0.5",
        "complete": False, "known_hours": 11, "reasons": [], "observed_to": "2026-10-16T11:00:00Z",
        "entity": "pulse", "segment": "meter", "original_unit": "pulse", "volume_per_unit_m3": "0.01"})
    place["samples"] = [
        {"entity": "volume", "segment": "meter", "unit": "m3", "state_class": "total_increasing",
         "at": "2026-10-16T10:59:00Z", "value": "100"},
        {"entity": "volume", "segment": "meter", "unit": "m3", "state_class": "total_increasing",
         "at": NOW.isoformat(), "value": "100.1"},
    ]
    place["invoice_evidence"] = [{"verified": True, "from": "2025-01-01", "to": "2026-03-31",
                                  "cost_czk": "100", "kwh_per_m3": "10"}]
    place["price_evidence"] = {"verified": True, "from": "2026-01-01", "to": "2028-01-01",
        "regulatory_to": "2027-01-01", "variable_mwh": "1000", "fixed_month": "100"}
    place["portal_evidence"] = {"advances": {"list_complete": True, "rows": [
        {"due": "2026-04-15", "prescribed": "2000", "payments_known": True,
         "payments": [{"date": "2026-04-14", "amount": "2000"}]},
        {"due": "2027-01-15", "prescribed": "3000", "payments_known": True, "payments": []},
    ]}}
    return place, {"from": "2026-03-31", "to": "2027-04-08"}


class OrientationalTests(unittest.TestCase):
    def test_projection_reacts_without_manual_billing_period(self):
        p, billing = scenario()
        p["settings"]["source_mode"] = "sensor"
        p["snapshots"] = [{"retrieved_at": "2026-10-16T10:00:00Z", "periods": [
            {"From": billing["from"], "To": billing["to"], "ReadingsMwh": "1",
             "PortalTotalMwh": "5"}]}]
        result = evaluate_place(PLACE, p, "UTC", NOW)
        self.assertEqual(result["status"], "needs_configuration")
        self.assertEqual(result["own_billing"]["status"], "estimated")
        self.assertEqual(result["billing"]["forecast_mwh"], "5")
        before = Decimal(result["own_billing"]["balance_czk"])
        p["samples"][-1]["value"] = "100.2"
        updated = evaluate_place(PLACE, p, "UTC", NOW)
        self.assertEqual(Decimal(updated["own_billing"]["balance_czk"]), before - Decimal("1.00"))
        self.assertEqual(updated["billing"]["forecast_mwh"], "5")

    def test_daily_mnd_and_ha_update_without_double_counting(self):
        p, billing = scenario()
        before = copy.deepcopy(p)
        one = orientational_view(PLACE, p, billing, NOW, "UTC", False)
        self.assertEqual(one["status"], "estimated")
        self.assertEqual(one["actual_m3"], Decimal("100.6"))
        self.assertEqual(one["measured_at"], NOW)
        self.assertTrue(one["boundary_estimated"])
        self.assertTrue(one["conversion_estimated"])
        self.assertTrue(one["history_source_assumed"])
        self.assertGreater(one["interpolated_days"], 0)
        self.assertEqual(p, before)
        p["samples"][-1]["value"] = "100.2"
        two = orientational_view(PLACE, p, billing, NOW, "UTC", False)
        self.assertEqual(two["actual_m3"], Decimal("100.7"))
        self.assertEqual(two["balance_czk"], one["balance_czk"] - Decimal("1.00"))

    def test_gap_after_closed_hour_keeps_last_known_value(self):
        p, billing = scenario()
        p["samples"].append({**p["samples"][-1], "at": "2026-10-16T11:30:00Z", "value": None})
        result = orientational_view(PLACE, p, billing, NOW, "UTC", True)
        self.assertEqual(result["actual_m3"], Decimal("100.5"))
        self.assertEqual(result["live_status"], "sensor_gap")
        self.assertEqual(result["measured_at"], datetime(2026, 10, 16, 11, tzinfo=timezone.utc))

    def test_old_live_baseline_and_overlapping_conversions_are_not_assumed_safe(self):
        p, billing = scenario()
        p["samples"][0]["at"] = "2026-10-16T09:59:00Z"
        result = orientational_view(PLACE, p, billing, NOW, "UTC", False)
        self.assertEqual(result["actual_m3"], Decimal("100.5"))
        self.assertEqual(result["live_status"], "baseline_missing")
        p["conversions"] = [{"from": "2026-03-01", "to": "2027-05-01", "kwh_per_m3": "10"},
                            {"from": "2026-10-01", "to": "2027-01-01", "kwh_per_m3": "11"}]
        self.assertIsNone(orientational_view(PLACE, p, billing, NOW, "UTC", False))

    def test_missing_winter_or_conflicting_mnd_does_not_invent_forecast(self):
        p, billing = scenario()
        p["readings"] = [r for r in p["readings"] if r["date"] >= "2026-01-01"]
        self.assertIsNone(orientational_view(PLACE, p, billing, NOW, "UTC", False))
        p, billing = scenario()
        p["readings"].append({**p["readings"][-1], "id": "conflict", "value": "301"})
        self.assertIsNone(orientational_view(PLACE, p, billing, NOW, "UTC", False))

    def test_missing_hour_is_not_assumed_zero(self):
        p, billing = scenario()
        p["daily_profile"][-1]["known_hours"] = 10
        self.assertIsNone(orientational_view(PLACE, p, billing, NOW, "UTC", False))

    def test_dst_fall_day_uses_real_25_hour_fraction(self):
        p, billing = scenario()
        now = datetime(2026, 10, 25, 11, tzinfo=timezone.utc)
        p["daily_profile"] = [row for row in p["daily_profile"] if row["date"] != "2026-10-16"]
        for i in range(16, 25):
            p["daily_profile"].append({"date": f"2026-10-{i:02d}", "m3": "1", "complete": True,
                "entity": "pulse", "segment": "meter", "original_unit": "pulse", "volume_per_unit_m3": "0.01"})
        p["daily_profile"].append({"date": "2026-10-25", "known_m3": "0.5", "complete": False,
            "known_hours": 12, "reasons": [], "observed_to": "2026-10-25T10:00:00Z",
            "entity": "pulse", "segment": "meter", "original_unit": "pulse", "volume_per_unit_m3": "0.01"})
        p["samples"][0]["at"] = "2026-10-25T09:59:00Z"
        p["samples"][1]["at"] = now.isoformat()
        result = orientational_view(PLACE, p, billing, now, "Europe/Prague", True)
        self.assertEqual(result["actual_m3"], Decimal("109.6"))
        days = (datetime(2027, 4, 8).date() - now.date()).days
        self.assertEqual(result["future_m3"], Decimal(days - 1) + Decimal(12) / Decimal(25))

    def test_missing_closed_day_after_last_mnd_is_not_zero(self):
        p, billing = scenario()
        now = NOW + timedelta(days=1)
        self.assertIsNone(orientational_view(PLACE, p, billing, now, "UTC", False))


if __name__ == "__main__":
    unittest.main()
