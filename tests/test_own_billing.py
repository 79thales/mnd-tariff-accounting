"""Syntetické odhady s přesnou kotvou, bezpečné chyby a zimní historie."""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from custom_components.mnd_tariff_accounting.core.archive import new_place
from custom_components.mnd_tariff_accounting.core.own_billing import (
    history_binding_matches,
    own_billing_view,
)
from custom_components.mnd_tariff_accounting.core.projection import evaluate_place

PLACE = "27ZG000Z0000000X"
NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def input_data():
    """Připraví úplný umělý profil; nepoužívá zákaznické hodnoty ani HA."""
    p = new_place("synthetic")
    p["settings"].update(segment="meter", source_registry_id="sensor", source_mode="sensor")
    p["readings"] = [{"id": "start", "place": PLACE, "segment": "meter", "meter": "meter",
        "date": "2026-01-01", "observed_at": "2026-01-01T00:00:00Z", "value": "100",
        "source": "mnd"}]
    p["samples"] = [
        {"entity": "sensor", "segment": "meter", "unit": "m3", "state_class": "total_increasing",
         "at": "2026-01-01T00:00:00Z", "value": "0"},
        {"entity": "sensor", "segment": "meter", "unit": "m3", "state_class": "total_increasing",
         "at": NOW.isoformat(), "value": "100"},
    ]
    p["daily_profile"] = [
        {"date": (NOW.date() - timedelta(days=i)).isoformat(), "m3": "1", "complete": True,
         "entity": "sensor", "segment": "meter", "original_unit": "m3"}
        for i in range(1, 366)
    ]
    p["conversions"] = [{"from": "2026-01-01", "to": "2027-01-01", "kwh_per_m3": "10"}]
    p["price_evidence"] = {"verified": True, "from": "2026-01-01", "to": "2027-01-01",
        "regulatory_to": "2027-01-01", "variable_mwh": "1000", "fixed_month": "100"}
    p["portal_evidence"] = {"advances": {"list_complete": True, "rows": [
        {"due": "2026-04-15", "prescribed": "2000", "payments_known": True,
         "payments": [{"date": "2026-04-14", "amount": "2000"}]},
        {"due": "2026-12-15", "prescribed": "3000", "payments_known": True, "payments": []},
    ]}}
    billing = {"from": "2026-01-01", "to": "2027-01-01"}
    measurement = {"reason": "derived_state", "value": "200", "at": NOW.isoformat()}
    return p, billing, measurement


class OwnBillingTests(unittest.TestCase):
    def test_projection_updates_without_manual_ledger_period(self):
        p, _, _ = input_data()
        p["snapshots"] = [{"retrieved_at": "2026-10-16T10:00:00Z", "periods": [
            {"From": "2026-01-01", "To": "2027-01-01", "ReadingsMwh": "1",
             "PortalTotalMwh": "5"}]}]
        p["samples"] = [
            {"entity": "sensor", "segment": "meter", "unit": "m3",
             "state_class": "total_increasing", "at": "2026-01-01T00:00:00Z", "value": "0"},
            {"entity": "sensor", "segment": "meter", "unit": "m3",
             "state_class": "total_increasing", "at": NOW.isoformat(), "value": "100"},
        ]
        first = evaluate_place(PLACE, p, "UTC", NOW)
        self.assertEqual(first["status"], "needs_configuration")
        self.assertEqual(first["own_billing"]["status"], "estimated")
        self.assertEqual(first["billing"]["forecast_mwh"], "5")
        p["samples"][1]["value"] = "110"
        second = evaluate_place(PLACE, p, "UTC", NOW)
        self.assertEqual(second["billing"]["forecast_mwh"], "5")
        self.assertEqual(Decimal(second["own_billing"]["balance_czk"]),
                         Decimal(first["own_billing"]["balance_czk"]) - Decimal("100"))

    def test_exact_manual_physical_start_can_anchor_without_exact_mnd(self):
        p, billing, measurement = input_data()
        p["readings"][0]["source"] = "manual"
        result = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        self.assertEqual(result["status"], "estimated")
        p["readings"].append({**p["readings"][0], "id": "mnd-uncertain", "source": "mnd",
                              "observed_at": None, "value": "101"})
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "reading_time_ambiguous")

    def test_current_consumption_changes_own_balance_without_mutation(self):
        p, billing, measurement = input_data()
        before = copy.deepcopy(p)
        one = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        two = own_billing_view(PLACE, p, billing, {**measurement, "value": "210"}, NOW, "UTC")
        self.assertEqual(one["status"], "estimated")
        self.assertEqual(one["actual_mwh"], Decimal("1"))
        self.assertEqual(one["future_m3"], Decimal("76.5"))
        self.assertEqual(two["balance_czk"], one["balance_czk"] - Decimal("100"))
        self.assertEqual(p, before)

    def test_unpaired_day_or_missing_winter_never_creates_balance(self):
        p, billing, measurement = input_data()
        del p["readings"][0]["observed_at"]
        result = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        self.assertEqual(result["reason"], "period_start_reading_unverified")
        self.assertEqual(result["profile_complete_days"], 365)
        self.assertIsNone(result["balance_czk"])
        p, billing, measurement = input_data()
        p["daily_profile"] = p["daily_profile"][:280]
        result = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        self.assertEqual(result["reason"], "representative_year_missing")
        self.assertEqual(result["profile_complete_days"], 280)
        self.assertEqual(result["profile_required_days"], 365)
        self.assertTrue(result["profile_missing_months"])
        self.assertEqual(result["actual_m3"], Decimal("100"))
        self.assertIsNone(result["balance_czk"])

    def test_historical_unit_change_is_not_silently_merged(self):
        p, billing, measurement = input_data()
        p["daily_profile"][0]["original_unit"] = "pulse"
        p["daily_profile"][0]["volume_per_unit_m3"] = None
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "history_unit_changed")

    def test_mismatched_sources_and_missing_conversion_do_not_create_balance(self):
        p, billing, measurement = input_data()
        p["settings"]["history_registry_id"] = "other"
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "history_source_unverified")
        p["settings"].pop("history_registry_id")
        p["conversions"] = []
        result = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        self.assertEqual(result["reason"], "conversion_period_missing_or_ambiguous")
        self.assertIsNone(result["balance_czk"])

    def test_confirmed_pulse_and_volume_source_binding_is_invalidated_on_change(self):
        p, billing, measurement = input_data()
        p["settings"].update(history_registry_id="pulses", history_unit_m3="0.01")
        for row in p["daily_profile"]:
            row.update(entity="pulses", original_unit="pulse", volume_per_unit_m3="0.01")
        binding = {"source": "sensor", "history": "pulses", "segment": "meter", "factor": "0.01"}
        self.assertFalse(history_binding_matches(p["settings"]))
        p["settings"]["history_binding"] = binding
        self.assertTrue(history_binding_matches(p["settings"]))
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["status"],
                         "estimated")
        for field, changed in (("source_registry_id", "different"), ("history_registry_id", "other"),
                               ("history_unit_m3", "0.02"), ("segment", "other-meter")):
            modified = {**p["settings"], field: changed}
            self.assertFalse(history_binding_matches(modified), field)

    def test_reset_or_changed_meter_invalidates_period_even_with_newer_sensor_value(self):
        p, billing, measurement = input_data()
        p["readings"].append({**p["readings"][0], "id": "later", "date": "2026-05-01",
            "observed_at": "2026-05-01T10:00:00Z", "value": "90"})
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "meter_decrease")
        p["readings"][1].update(value="110", meter="different")
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "meter_changed")

    def test_source_history_must_cover_start_and_cannot_hide_recorded_gap_or_reset(self):
        p, billing, measurement = input_data()
        first = p["samples"].pop(0)
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "sample_history_start_missing")
        p["samples"].insert(0, first)
        p["samples"].insert(1, {**first, "at": "2026-05-01T00:00:00Z", "value": None})
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "sensor_gap")
        p["samples"][1]["value"] = "50"
        p["samples"].insert(2, {**first, "at": "2026-06-01T00:00:00Z", "value": "2"})
        self.assertEqual(own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")["reason"],
                         "sensor_reset")

    def test_bad_invoice_boundary_and_missing_price_do_not_hide_measured_volume(self):
        p, billing, measurement = input_data()
        p["invoice_evidence"] = [{"verified": True, "from": "2025-12-01", "to": "2026-02-01",
                                  "cost_czk": "10"}]
        result = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        self.assertIsNone(result["balance_czk"])
        self.assertIn("invoice_boundary_mismatch", result["warnings"])
        self.assertEqual(result["actual_m3"], Decimal("100"))
        p["invoice_evidence"] = []
        del p["price_evidence"]
        result = own_billing_view(PLACE, p, billing, measurement, NOW, "UTC")
        self.assertIsNone(result["balance_czk"])
        self.assertIn("verified_price_missing", result["warnings"])
        self.assertEqual(result["actual_mwh"], Decimal("1"))

    def test_midday_dst_uses_actual_hours_without_double_counting(self):
        p, billing, measurement = input_data()
        now = datetime(2026, 10, 25, 11, tzinfo=timezone.utc)
        p["readings"][0]["observed_at"] = "2025-12-31T23:00:00Z"
        p["samples"][0]["at"] = "2025-12-31T23:00:00Z"
        p["samples"][1]["at"] = now.isoformat()
        p["daily_profile"] = [
            {"date": (now.date() - timedelta(days=i)).isoformat(), "m3": "25", "complete": True,
             "entity": "sensor", "segment": "meter", "original_unit": "m3"}
            for i in range(1, 366)
        ]
        result = own_billing_view(PLACE, p, billing, {**measurement, "at": now.isoformat()},
                                  now, "Europe/Prague")
        # 25. 10. 2026 má 25 hodin; od 12:00 místního času zbývá 12 hodin.
        self.assertEqual(result["future_m3"], Decimal("1687"))


if __name__ == "__main__":
    unittest.main()
