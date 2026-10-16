"""Přesné časové hranice, neúplné dny a přechody DST na UTC ose."""

import copy
import unittest
from decimal import Decimal as D

from test_domain import PLACE, reading, request

from custom_components.mnd_tariff_accounting.core.accounting import calculate
from custom_components.mnd_tariff_accounting.core.common import DataError
from custom_components.mnd_tariff_accounting.core.metering import current_state


def timed(first="2026-01-01T00:00:00Z", last="2026-01-01T12:00:00Z", **extra):
    return request(
        start=first,
        end=last,
        events=[],
        opening_credit="0",
        segments=[{"from": first, "to": last, "m3": "10", "complete": True}],
        **extra,
    )


class TemporalTests(unittest.TestCase):
    def test_same_day_real_delta_is_priced_without_inventing_a_whole_day(self):
        result = calculate(**timed())
        self.assertTrue(result["complete"])
        self.assertEqual(result["volume_m3"], 10)
        self.assertEqual(result["energy_mwh"], D("0.1"))
        self.assertEqual(result["balance_czk"], D("-100"))
        self.assertFalse(result["estimated"])

    def test_partial_daily_fixed_fee_requires_explicit_estimation(self):
        params = timed()
        params["tariffs"][0].update(fixed="310", prorate_fixed=True)
        result = calculate(**params)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["balance_czk"])
        self.assertEqual(result["known_cost_czk"], 100)
        self.assertIn("fixed_intraday_proration_unknown", result["warnings"])
        result = calculate(**{**params, "allow_linear": True})
        self.assertEqual(result["known_cost_czk"], 105)
        self.assertTrue(result["estimated"])

    def test_two_intraday_segments_are_not_overlapping_daily_consumption(self):
        params = timed()
        params["segments"] = [
            {
                "from": "2026-01-01T00:00:00Z",
                "to": "2026-01-01T06:00:00Z",
                "m3": "4",
                "complete": True,
            },
            {
                "from": "2026-01-01T06:00:00Z",
                "to": "2026-01-01T12:00:00Z",
                "m3": "6",
                "complete": True,
            },
        ]
        self.assertEqual(calculate(**params)["known_cost_czk"], 100)
        params["segments"][1]["from"] = "2026-01-01T05:00:00Z"
        with self.assertRaisesRegex(DataError, "overlapping_consumption"):
            calculate(**params)

    def test_intraday_tariff_change_needs_measurement_or_declared_estimate(self):
        params = timed()
        first = copy.deepcopy(params["tariffs"][0])
        second = copy.deepcopy(first)
        first["to"] = "2026-01-01T06:00:00Z"
        second.update({"from": first["to"], "commodity": "1500"})
        params["tariffs"] = [first, second]
        self.assertFalse(calculate(**params)["complete"])
        result = calculate(**{**params, "allow_linear": True})
        self.assertEqual(result["known_cost_czk"], 150)
        self.assertTrue(result["estimated"])

    def test_dst_23_hour_day_still_has_one_daily_fixed_fee(self):
        params = timed(
            "2026-03-29T00:00:00+01:00", "2026-03-30T00:00:00+02:00", zone="Europe/Prague"
        )
        params["segments"][0]["m3"] = "0"
        params["tariffs"][0].update(
            {"from": "2026-03-01", "to": "2026-04-01", "fixed": "310", "prorate_fixed": True}
        )
        params["conversions"][0].update({"from": "2026-03-01", "to": "2026-04-01"})
        result = calculate(**params)
        self.assertEqual(result["known_cost_czk"], 10)
        self.assertFalse(result["estimated"])

    def test_date_only_boundary_is_not_precise_intraday_measurement(self):
        params = timed()
        params["segments"][0].update({"from": "2026-01-01", "time_uncertain": True})
        result = calculate(**params)
        self.assertFalse(result["complete"])
        self.assertTrue(result["estimated"])
        self.assertIn("boundary_time_unknown", result["warnings"])

    def test_exact_midnights_agree_with_daily_accounting_including_half_cent(self):
        for fixed in ("0", "310", "0.005"):
            original = request()
            original["tariffs"][0]["fixed"] = fixed
            precise = copy.deepcopy(original)
            for row in precise["segments"]:
                row["from"] += "T00:00:00Z"
                row["to"] += "T00:00:00Z"
            left, right = calculate(**original), calculate(**precise)
            for key in (
                "volume_m3",
                "energy_mwh",
                "known_cost_czk",
                "balance_czk",
                "complete",
                "estimated",
            ):
                self.assertEqual(left[key], right[key], (fixed, key))

    def test_monthly_actual_payment_is_not_prorated_at_current_noon(self):
        params = timed(ledger_end="2026-02-01", as_of="2026-01-01")
        params["events"] = [
            {
                "id": "paid",
                "role": "payment",
                "date": "2026-01-01",
                "amount": "500",
                "from": "2026-01-01",
                "to": "2026-02-01",
            }
        ]
        result = calculate(**params)
        self.assertEqual(result["paid_czk"], 500)
        self.assertEqual(result["balance_czk"], 400)

    def test_new_calibration_after_reset_starts_a_new_valid_tail(self):
        anchor = reading(observed_at="2026-01-01T00:00:00Z")
        samples = [
            {
                "entity": "sensor-id",
                "segment": "0001",
                "unit": unit,
                "state_class": "total",
                "value": value,
                "at": at,
            }
            for at, unit, value in [
                ("2026-01-01T00:00:00Z", "m³", "200"),
                ("2026-01-01T06:00:00Z", "kWh", "0"),
                ("2026-01-01T10:00:00Z", "m³", "0"),
                ("2026-01-01T12:00:00Z", "m³", "2"),
            ]
        ]
        result = current_state(
            [anchor],
            samples,
            {
                "place": PLACE,
                "segment": "0001",
                "entity": "sensor-id",
                "at": "2026-01-01T10:00:00Z",
                "physical": "1005",
                "sensor": "0",
            },
            place=PLACE,
            segment="0001",
            zone="UTC",
            source_mode="sensor",
        )
        self.assertEqual(result["value"], 1007)
