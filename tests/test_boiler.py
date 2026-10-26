"""Syntetické důkazy jednotek, mezer, resetů, DST a izolace elektřiny kotle."""

import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from custom_components.mnd_tariff_accounting.core.archive import new_place
from custom_components.mnd_tariff_accounting.core.boiler import (
    consumption_summary,
    demand_value,
    electrical_value,
    energy_period,
)
from custom_components.mnd_tariff_accounting.core.common import DataError
from custom_components.mnd_tariff_accounting.core.statistics import daily_profile
from custom_components.mnd_tariff_accounting.editing import edit_place


class BoilerTests(unittest.TestCase):
    now = datetime(2026, 10, 26, 10, tzinfo=timezone.utc)

    def test_exact_unit_conversion_and_real_zero(self):
        self.assertEqual(electrical_value("0.094", "kW", self.now, self.now)["value"], "94.000")
        self.assertEqual(
            electrical_value("20", "Wh", self.now, self.now, energy=True)["value"], "0.020"
        )
        self.assertEqual(electrical_value("0", "W", self.now, self.now)["value"], "0")

    def test_bad_or_unknown_reading_is_never_zero(self):
        for value, unit in (
            ("unavailable", "W"),
            ("unknown", "W"),
            ("NaN", "W"),
            ("-1", "W"),
            ("1", "m³"),
        ):
            self.assertIsNone(electrical_value(value, unit, self.now, self.now)["value"])

    def test_stale_and_future_report(self):
        for at in (self.now - timedelta(seconds=901), self.now + timedelta(seconds=1)):
            r = electrical_value("94", "W", at, self.now)
            self.assertEqual(r["quality"], "stale")
            self.assertIsNone(r["value"])

    def test_demand_is_not_an_inferred_flame(self):
        self.assertTrue(demand_value("heat", {"hvac_action": "heating"}))
        self.assertFalse(demand_value("heat", {"hvac_action": "idle"}))
        self.assertIsNone(demand_value("heat"))
        self.assertIsNone(demand_value("unavailable"))

    def statistics(self, start, hours):
        first = int(start.timestamp()) - 3600
        return [
            {"start": first + i * 3600, "state": 10 + i, "sum": 100 + i, "change": 1}
            for i in range(hours + 1)
        ]

    def test_energy_uses_delta_not_first_counter_and_wh_converts(self):
        start = self.now.replace(hour=0)
        rows = self.statistics(start, 2)
        r = energy_period(rows, start, start + timedelta(hours=2), self.now, Decimal("0.001"))
        self.assertEqual(r["value_kwh"], "0.002")
        self.assertTrue(r["complete"])

    def test_energy_reset_and_gap_preserve_known_part(self):
        start = self.now.replace(hour=0)
        rows = self.statistics(start, 4)
        rows[2]["state"] = 0
        rows.pop(3)
        r = energy_period(rows, start, start + timedelta(hours=4), self.now, Decimal(1))
        self.assertEqual(r["value_kwh"], "1")
        self.assertFalse(r["complete"])
        self.assertEqual(r["known_hours"], 1)

    def test_energy_state_change_must_match_sum_change(self):
        start = self.now.replace(hour=0)
        rows = self.statistics(start, 1)
        rows[1]["state"] = 99
        result = energy_period(rows, start, self.now, self.now, Decimal(1))
        self.assertIsNone(result["value_kwh"])
        self.assertEqual(result["known_hours"], 0)

    def test_negative_physical_energy_counter_is_not_consumption(self):
        start = self.now.replace(hour=0)
        rows = self.statistics(start, 1)
        rows[0]["state"], rows[1]["state"] = -2, -1
        result = energy_period(rows, start, self.now, self.now, Decimal(1))
        self.assertIsNone(result["value_kwh"])

    def test_energy_fractional_timezone_does_not_include_boundary_hour(self):
        start = self.now.replace(hour=0, minute=30)
        rows = self.statistics(self.now.replace(hour=0), 3)
        end = start + timedelta(hours=2)
        result = energy_period(rows, start, end, self.now, Decimal(1))
        self.assertEqual(result["value_kwh"], "1")
        self.assertEqual(result["expected_closed_hours"], 1)
        self.assertFalse(result["complete"])

    def test_invalid_last_gas_hour_does_not_extend_known_coverage(self):
        start = self.now.replace(hour=0)
        rows = self.statistics(start, 2)
        rows[-1]["change"] = 999
        profile = daily_profile(rows, "UTC")
        row = next(item for item in profile if item["date"] == start.date().isoformat())
        self.assertEqual(row["observed_to"], (start + timedelta(hours=1)).isoformat())
        self.assertEqual(row["known_m3"], Decimal(1))

    def test_energy_does_not_fill_missing_or_open_hour(self):
        start = self.now.replace(hour=0)
        r = energy_period([], start, self.now, self.now, Decimal(1))
        self.assertIsNone(r["value_kwh"])
        rows = self.statistics(start, 1)
        r = energy_period(
            rows, start, start + timedelta(hours=1), start + timedelta(minutes=30), Decimal(1)
        )
        self.assertIsNone(r["value_kwh"])

    def test_energy_rejects_conflicting_hour(self):
        start = self.now.replace(hour=0)
        rows = self.statistics(start, 1)
        rows.append({**rows[-1], "change": 2})
        with self.assertRaises(DataError):
            energy_period(rows, start, self.now, self.now, Decimal(1))

    def test_dst_day_contains_23_or_25_real_hours(self):
        zone = ZoneInfo("Europe/Prague")
        for date, hours in (("2026-03-29", 23), ("2026-10-25", 25)):
            start = datetime.fromisoformat(date).replace(tzinfo=zone)
            end = start + timedelta(days=1)
            r = energy_period(self.statistics(start, hours), start, end, end, Decimal(1))
            self.assertEqual(r["expected_closed_hours"], hours)
            self.assertEqual(r["value_kwh"], str(hours))
            self.assertTrue(r["complete"])

    def place(self):
        p = new_place("Synthetic")
        p["settings"].update({"source_registry_id": "chosen", "segment": "meter"})
        p["daily_profile"] = [
            {
                "date": "2026-10-25",
                "entity": "chosen",
                "segment": "meter",
                "m3": "2",
                "complete": True,
            },
            {
                "date": "2026-10-26",
                "entity": "chosen",
                "segment": "meter",
                "m3": None,
                "known_m3": "0.16",
                "complete": False,
                "observed_to": "2026-10-26T09:00:00+00:00",
            },
            {
                "date": "2026-10-26",
                "entity": "other",
                "segment": "meter",
                "m3": "999",
                "complete": True,
            },
        ]
        return p

    def test_gas_periods_select_only_configured_source_and_keep_missing_days(self):
        p = self.place()
        r = consumption_summary(p, self.now, "Europe/Prague")
        self.assertEqual(r["today"]["value_m3"], "0.16")
        self.assertEqual(r["month"]["value_m3"], "2.16")
        self.assertEqual(r["today"]["observed_to"], "2026-10-26T09:00:00+00:00")
        self.assertFalse(r["month"]["complete"])
        self.assertIsNone(r["days"][0]["value_m3"])

    def test_old_profile_has_no_invented_observation_time(self):
        p = self.place()
        p["daily_profile"][1].pop("observed_to")
        self.assertIsNone(consumption_summary(p, self.now, "Europe/Prague")["today"]["observed_to"])

    def edit(self, p, record):
        return edit_place(
            {"places": {"synthetic": p}},
            place_id="synthetic",
            section="boiler",
            record=record,
            now=self.now,
            zone="Europe/Prague",
        )

    def test_disabled_by_default_and_turning_off_preserves_selection(self):
        p = self.place()
        self.assertFalse(p["settings"].get("boiler_enabled", False))
        self.edit(p, {"boiler_enabled": True, "boiler_power_entity": "sensor.synthetic_power"})
        self.edit(p, {"boiler_enabled": False})
        self.assertEqual(p["settings"]["boiler_power_entity"], "sensor.synthetic_power")

    def test_no_power_or_invalid_boolean_is_rejected(self):
        for record in (
            {"boiler_enabled": True},
            {"boiler_enabled": "true"},
            {"boiler_max_age": 5},
            {"boiler_max_age": "900.5"},
            {"boiler_max_age": 900.5},
            {"boiler_max_age": True},
            {"boiler_max_age": None},
        ):
            with self.assertRaises((DataError, ValueError)):
                self.edit(self.place(), record)

    def test_boiler_edit_does_not_modify_accounting_records(self):
        p = self.place()
        baseline = copy.deepcopy({k: v for k, v in p.items() if k not in ("settings", "audit")})
        self.edit(p, {"boiler_enabled": True, "boiler_power_entity": "sensor.synthetic_power"})
        self.assertEqual({k: v for k, v in p.items() if k not in ("settings", "audit")}, baseline)


if __name__ == "__main__":
    unittest.main()
