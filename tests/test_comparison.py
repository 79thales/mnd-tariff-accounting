"""Pozdější skutečnost nelze nahradit odhadem nebo převodem bez dokladu."""

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from test_domain import PLACE, reading

from custom_components.mnd_tariff_accounting.core.archive import new_place
from custom_components.mnd_tariff_accounting.core.common import DataError, wire
from custom_components.mnd_tariff_accounting.core.comparison import compare_measurement
from custom_components.mnd_tariff_accounting.core.forecast import seasonal_forecast
from custom_components.mnd_tariff_accounting.core.statistics import manual_profile


class MeasurementComparisonTests(unittest.TestCase):
    def fixture(self):
        place = new_place()
        place["settings"] = {"source_mode": "manual", "segment": "0001"}
        place["readings"] = wire(
            [
                reading("1000", "2026-01-01", "manual", observed_at="2026-01-01T00:00:00Z").dump(),
                reading("1100", "2026-02-01", "manual", observed_at="2026-02-01T00:00:00Z").dump(),
            ]
        )
        place["conversions"] = [
            {
                "id": "invoice-factor",
                "from": "2026-01-01",
                "to": "2026-02-01",
                "kwh_per_m3": "10",
                "evidence": "Synthetic invoice",
            }
        ]
        return place

    def compare(self, place):
        return compare_measurement(
            PLACE,
            place,
            {"retrieved_at": "2026-01-10T00:00:00Z"},
            {"From": "2026-01-01", "To": "2026-02-01", "PortalTotalMwh": "1.2"},
            "UTC",
            datetime(2026, 2, 2, tzinfo=timezone.utc),
        )

    def test_documented_completed_measurement_compares_in_mwh(self):
        result = self.compare(self.fixture())
        self.assertEqual(result["actual_mwh"], 1)
        self.assertEqual(result["difference"], Decimal("0.2"))
        self.assertEqual(result["percentage"], 20)

    def test_missing_or_estimated_conversion_refuses_physical_accuracy(self):
        for factors in (
            [],
            [
                {
                    "id": "x",
                    "from": "2026-01-01",
                    "to": "2026-02-01",
                    "kwh_per_m3": "10",
                    "evidence": "",
                }
            ],
        ):
            place = self.fixture()
            place["conversions"] = factors
            with self.assertRaisesRegex(DataError, "conversion_evidence"):
                self.compare(place)

    def test_incomplete_measurement_is_not_a_valid_actual(self):
        place = self.fixture()
        place["readings"].pop()
        with self.assertRaisesRegex(DataError, "actual_incomplete"):
            self.compare(place)

    def test_corrected_conversion_replaces_old_estimated_evidence(self):
        place = self.fixture()
        old = {**place["conversions"][0], "id": "old", "estimated": True, "evidence": ""}
        place["conversions"][0]["supersedes"] = "old"
        place["conversions"].insert(0, old)
        self.assertEqual(self.compare(place)["actual_mwh"], 1)

    def test_unknown_mnd_method_does_not_prove_daily_physical_measurement(self):
        first = "2026-01-01T00:00:00Z"
        last = "2026-01-02T00:00:00Z"
        rows = [
            reading("1000", "2026-01-01", "mnd", observed_at=first).dump(),
            reading("1001", "2026-01-02", "mnd", observed_at=last).dump(),
        ]
        self.assertEqual(manual_profile(wire(rows), PLACE, "0001", "UTC"), [])

    def test_manual_daily_year_supports_seasonal_forecast_without_recorder(self):
        first = datetime(2025, 1, 1, tzinfo=timezone.utc)
        readings = wire(
            [
                reading(
                    str(i),
                    (first + timedelta(days=i)).date().isoformat(),
                    "manual",
                    observed_at=(first + timedelta(days=i)).isoformat(),
                ).dump()
                for i in range(366)
            ]
        )
        profile = manual_profile(readings, PLACE, "0001", "UTC")
        self.assertEqual(len(profile), 365)
        result = seasonal_forecast(profile, "2026-01-01", "2026-02-01")
        self.assertTrue(result["complete"])
        self.assertEqual(result["value"], 31)

    def test_sparse_manual_difference_is_not_fabricated_daily_profile(self):
        self.assertEqual(manual_profile(self.fixture()["readings"], PLACE, "0001", "UTC"), [])
