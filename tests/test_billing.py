"""Syntetické účetní období přes Nový rok, původní doklad a chybějící podklady."""

import copy
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from custom_components.mnd_tariff_accounting.core.archive import empty_archive, new_place
from custom_components.mnd_tariff_accounting.core.backup import (
    backup_document,
    parse_native,
    restore_place,
)
from custom_components.mnd_tariff_accounting.core.billing import (
    billing_view,
    fixed_cost,
    forecast_payments,
    own_outcome_from_energy,
)
from custom_components.mnd_tariff_accounting.core.common import DataError, canonical, day
from custom_components.mnd_tariff_accounting.core.metering import validate_samples
from custom_components.mnd_tariff_accounting.core.mnd_documents import (
    current_price,
    invoice_from_text,
    tariff_from_text,
)

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
PLACE = "27ZG000Z0000000X"


def place():
    p = new_place("Synthetic")
    p["settings"].update(source_registry_id="derived", history_registry_id="raw", segment="meter")
    p["snapshots"] = [
        {
            "retrieved_at": "2026-10-16T10:00:00Z",
            "periods": [
                {
                    "From": "2026-03-31",
                    "To": "2027-04-08",
                    "ReadingsMwh": "1",
                    "PortalTotalMwh": "5",
                }
            ],
        }
    ]
    p["readings"] = [{"source": "mnd", "date": "2026-10-11"}]
    p["portal_evidence"] = {
        "advances": {
            "list_complete": True,
            "rows": [
                {
                    "id": "a",
                    "due": "2026-04-15",
                    "prescribed": "1000",
                    "payments_known": True,
                    "payments": [{"date": "2026-04-14", "amount": "1000"}],
                },
                {
                    "id": "b",
                    "due": "2027-01-15",
                    "prescribed": "1000",
                    "payments_known": True,
                    "payments": [],
                },
                {
                    "id": "outside",
                    "due": "2027-04-15",
                    "prescribed": "9000",
                    "payments_known": True,
                    "payments": [],
                },
            ],
        }
    }
    p["price_evidence"] = {
        "verified": True,
        "from": "2026-01-01",
        "to": "2028-01-01",
        "regulatory_to": "2027-01-01",
        "variable_mwh": "363",
        "fixed_month": "36.30",
    }
    return p


class BillingTests(unittest.TestCase):
    def test_missing_month_is_assumed_once_and_disappears_after_mnd_supplies_it(self):
        p = place()
        p["portal_evidence"]["deposit"] = {"ADV_VALUE": "1234"}
        rows = p["portal_evidence"]["advances"]["rows"] = [
            {"due": "2026-01-12", "prescribed": "1234", "payments_known": True,
             "payments": [{"date": "2026-01-12", "amount": "1234"}]},
            {"due": "2026-03-12", "prescribed": "1234", "payments_known": True, "payments": []},
            {"due": "2026-04-12", "prescribed": "1234", "payments_known": True, "payments": []},
        ]
        start, end, today = day("2026-01-01"), day("2026-05-01"), day("2026-01-27")
        result = forecast_payments(p, start, end, today)
        self.assertEqual(result["paid_czk"], Decimal("1234.00"))
        self.assertEqual(result["remaining_czk"], Decimal("3702.00"))
        self.assertEqual(result["assumed_advances"], [{"date": "2026-02-12", "amount": Decimal("1234.00")}])
        rows.append({"due": "2026-02-12", "prescribed": "1234", "payments_known": True, "payments": []})
        result = forecast_payments(p, start, end, today)
        self.assertEqual(result["remaining_czk"], Decimal("3702.00"))
        self.assertEqual(result["assumed_advances"], [])

    def test_missing_months_are_assumptions_even_after_due_and_require_regular_plan(self):
        p = place()
        p["portal_evidence"]["deposit"] = {"ADV_VALUE": "1234"}
        rows = p["portal_evidence"]["advances"]["rows"] = [
            {"due": "2026-01-12", "prescribed": "1234", "payments_known": True,
             "payments": [{"date": "2026-01-12", "amount": "1234"}]},
            {"due": "2026-03-12", "prescribed": "1234", "payments_known": True, "payments": []},
            {"due": "2026-04-12", "prescribed": "1234", "payments_known": True, "payments": []},
        ]
        start, end = day("2026-01-01"), day("2026-07-01")
        result = forecast_payments(p, start, end, day("2026-02-16"))
        self.assertEqual([r["date"] for r in result["assumed_advances"]], ["2026-02-12", "2026-05-12", "2026-06-12"])
        self.assertEqual(result["paid_czk"], Decimal("1234.00"))
        rows[1]["prescribed"] = "1300"
        self.assertEqual(forecast_payments(p, start, end, day("2026-01-27"))["assumed_advances"], [])

    def test_own_outcome_updates_with_measured_energy_and_preserves_supplier_forecast(self):
        p = place()
        p["price_evidence"].update(variable_mwh="1000", fixed_month="100")
        p["portal_evidence"]["advances"]["rows"] = [
            {"due": "2026-04-15", "prescribed": "2000", "payments_known": True,
             "payments": [{"date": "2026-04-14", "amount": "2000"}]},
            {"due": "2026-12-15", "prescribed": "3000", "payments_known": True,
             "payments": []},
        ]
        start, end, through = day("2026-01-01"), day("2027-01-01"), day("2026-10-11")
        before = copy.deepcopy(p)
        first = own_outcome_from_energy(p, start, end, through, "1", "2", NOW.date())
        second = own_outcome_from_energy(p, start, end, through, "1.1", "2", NOW.date())
        self.assertEqual(first["forecast_cost_czk"], Decimal("4200.00"))
        self.assertEqual(first["balance_czk"], Decimal("800.00"))
        self.assertEqual(second["forecast_cost_czk"], Decimal("4300.00"))
        self.assertEqual(second["balance_czk"], Decimal("700.00"))
        self.assertEqual(p, before)

    def test_own_outcome_never_fills_missing_future_with_supplier_forecast(self):
        p = place()
        result = own_outcome_from_energy(
            p, day("2026-03-31"), day("2027-04-08"), day("2026-10-11"), "1", None,
            NOW.date(),
        )
        self.assertIsNone(result["total_mwh"])
        self.assertIsNone(result["forecast_cost_czk"])
        self.assertIsNone(result["balance_czk"])

    def test_forecast_payments_uses_actual_and_only_remaining_future_prescriptions(self):
        p = place()
        p["portal_evidence"]["advances"]["rows"][1]["payments"] = [
            {"date": "2026-10-01", "amount": "400"}
        ]
        before = copy.deepcopy(p)
        result = forecast_payments(p, day("2026-03-31"), day("2027-04-08"), NOW.date())
        self.assertEqual(result["paid_czk"], Decimal("1400.00"))
        self.assertEqual(result["remaining_czk"], Decimal("600.00"))
        self.assertEqual(result["expected_czk"], Decimal("2000.00"))
        self.assertTrue(result["complete"])
        self.assertEqual(p, before)

    def test_forecast_payments_does_not_assume_overdue_amount_or_double_overpayment(self):
        p = place()
        past, future = p["portal_evidence"]["advances"]["rows"][:2]
        past["payments"][0]["amount"] = "500"
        future["payments"] = [{"date": "2026-09-01", "amount": "1200"}]
        result = forecast_payments(p, day("2026-03-31"), day("2027-04-08"), NOW.date())
        self.assertEqual(result["paid_czk"], Decimal("1700.00"))
        self.assertEqual(result["remaining_czk"], Decimal("0.00"))
        self.assertIsNone(result["expected_czk"])
        self.assertEqual(result["reason"], "overdue_advance")

    def test_forecast_payments_refuses_partial_details_and_unresolved_refunds(self):
        p = place()
        p["portal_evidence"]["advances"]["rows"][0]["payments_stale"] = True
        self.assertEqual(
            forecast_payments(p, day("2026-03-31"), day("2027-04-08"), NOW.date())["reason"],
            "advance_details_incomplete",
        )
        p["portal_evidence"]["advances"]["rows"][0]["payments_stale"] = False
        p["events"] = [{"role": "refund"}]
        result = forecast_payments(p, day("2026-03-31"), day("2027-04-08"), NOW.date())
        self.assertIsNone(result["expected_czk"])
        self.assertEqual(result["reason"], "credit_or_refund_unresolved")

    def test_unavailable_sample_without_attributes_remains_a_gap(self):
        sample = {"entity": "raw", "segment": "meter", "at": "2026-01-01T00:00:00Z", "value": None}
        self.assertIsNone(validate_samples([sample], entity="raw", segment="meter")[0]["value"])
        with self.assertRaisesRegex(DataError, "incompatible_sensor"):
            validate_samples(
                [{**sample, "value": "1", "unit": "kWh", "state_class": "total"}],
                entity="raw",
                segment="meter",
            )

    def test_backup_restores_verified_document_context(self):
        p = place()
        p["readings"] = []
        p["invoice_evidence"] = []
        p["billing_documents_context"] = "synthetic-context"
        data = empty_archive("synthetic-account")
        data["places"][PLACE] = new_place("Synthetic")
        parsed = parse_native(canonical(backup_document("synthetic-account", PLACE, p)), PLACE)
        restore_place(data, parsed)
        self.assertEqual(data["places"][PLACE]["price_evidence"], p["price_evidence"])
        self.assertEqual(
            data["places"][PLACE]["billing_documents_context"], p["billing_documents_context"]
        )

    def test_supplier_billing_period_survives_new_year(self):
        result = billing_view(place(), NOW, "Europe/Prague")
        self.assertEqual(result["from"], "2026-03-31")
        self.assertEqual(result["to"], "2027-04-08")
        self.assertEqual(result["paid_czk"], "1000.00")
        self.assertEqual(result["planned_czk"], "2000.00")
        self.assertEqual(result["actual_mwh"], "1")
        self.assertIn("future_regulated_price_assumed", result["warnings"])

    def test_actual_payment_uses_payment_date_and_is_not_prescription(self):
        p = place()
        p["events"] = [{"amount": "1000", "role": "payment", "source": "mnd_advances"}]
        before = copy.deepcopy(p)
        result = billing_view(p, NOW, "UTC")
        self.assertEqual(result["series"]["paid"][1]["date"], "2026-04-14")
        self.assertEqual(result["series"]["planned"][1]["date"], "2026-04-15")
        self.assertEqual(result["paid_czk"], "1000.00")
        self.assertEqual(p, before)

    def test_no_evidence_is_unknown_but_verified_empty_list_is_zero(self):
        p = place()
        p["portal_evidence"] = {}
        self.assertIsNone(billing_view(p, NOW, "UTC")["paid_czk"])
        p["portal_evidence"] = {"advances": {"rows": [], "list_complete": True}}
        self.assertEqual(billing_view(p, NOW, "UTC")["paid_czk"], "0.00")

    def test_missing_price_does_not_hide_real_payments(self):
        p = place()
        p.pop("price_evidence")
        r = billing_view(p, NOW, "UTC")
        self.assertIsNone(r["known_cost_czk"])
        self.assertIsNone(r["forecast_balance_czk"])
        self.assertEqual(r["paid_czk"], "1000.00")

    def test_original_invoice_overrides_the_model_without_duplicate_cost(self):
        p = place()
        p["snapshots"] = []
        p["settings"].update(period_from="2026-03-31", period_to="2027-04-08")
        p["invoice_evidence"] = [
            {
                "verified": True,
                "from": "2026-03-31",
                "to": "2027-04-08",
                "cost_czk": "777.12",
                "invoice_result_czk": "222.88",
            }
        ]
        r = billing_view(p, datetime(2027, 4, 9, tzinfo=timezone.utc), "UTC")
        self.assertTrue(r["confirmed_invoice"])
        self.assertEqual(r["known_cost_czk"], "777.12")
        self.assertEqual(r["forecast_balance_czk"], "222.88")

    def test_monthly_sensor_series_does_not_replace_supplier_energy(self):
        p = place()
        p["daily_profile"] = [
            {
                "date": "2026-04-01",
                "m3": "3",
                "complete": True,
                "entity": "raw",
                "segment": "meter",
            },
            {
                "date": "2026-04-01",
                "m3": "300",
                "complete": True,
                "entity": "derived",
                "segment": "meter",
            },
            {
                "date": "2026-04-02",
                "m3": None,
                "known_m3": "1",
                "complete": False,
                "entity": "raw",
                "segment": "meter",
            },
        ]
        r = billing_view(p, NOW, "UTC")
        self.assertEqual(r["months"][1]["m3"], "4")
        self.assertFalse(r["months"][1]["complete"])
        self.assertIsNone(r["months"][2]["m3"])
        self.assertEqual(r["actual_mwh"], "1")

    def test_partial_original_replaces_its_energy_and_fixed_cost(self):
        p = place()
        p["invoice_evidence"] = [
            {
                "verified": True,
                "from": "2026-03-31",
                "to": "2026-05-01",
                "cost_czk": "123.45",
                "energy_mwh": "0.4",
            }
        ]
        r = billing_view(p, NOW, "UTC")
        expected = (
            Decimal("123.45")
            + Decimal("0.6") * 363
            + fixed_cost(p["price_evidence"], day("2026-05-01"), day("2026-10-11"))
        )
        self.assertEqual(Decimal(r["known_cost_czk"]), expected.quantize(Decimal(".01")))
        self.assertTrue(r["known_cost_complete"])
        self.assertFalse(r["confirmed_invoice"])

    def test_invoice_without_energy_preserves_only_its_documented_cost(self):
        p = place()
        p["invoice_evidence"] = [
            {"verified": True, "from": "2026-03-31", "to": "2026-05-01", "cost_czk": "123.45"}
        ]
        r = billing_view(p, NOW, "UTC")
        self.assertEqual(r["known_cost_czk"], "123.45")
        self.assertFalse(r["known_cost_complete"])
        self.assertIsNone(r["forecast_balance_czk"])
        self.assertIn("invoice_energy_boundary_missing", r["warnings"])

    def test_invoice_crossing_period_boundary_is_not_prorated(self):
        p = place()
        p["invoice_evidence"] = [
            {"verified": True, "from": "2026-03-01", "to": "2026-05-01", "cost_czk": "123.45"}
        ]
        r = billing_view(p, NOW, "UTC")
        self.assertIsNone(r["known_cost_czk"])
        self.assertIn("invoice_boundary_mismatch", r["warnings"])

    def test_overlapping_originals_require_documented_correction(self):
        p = place()
        p["invoice_evidence"] = [
            {"verified": True, "from": "2026-03-31", "to": "2026-05-01", "cost_czk": "123.45"},
            {"verified": True, "from": "2026-04-01", "to": "2026-05-02", "cost_czk": "123.45"},
        ]
        with self.assertRaisesRegex(DataError, "billing_invoice_overlap"):
            billing_view(p, NOW, "UTC")

    def test_payment_received_today_is_present_in_graph(self):
        p = place()
        p["portal_evidence"]["advances"]["rows"][0]["payments"][0]["date"] = "2026-10-16"
        r = billing_view(p, NOW, "UTC")
        self.assertEqual(r["series"]["paid"][-1]["value"], r["paid_czk"])


def tariff_text():
    numbers = ["121 [100]", "12,10 [10]", "242 [200]", "24,20 [20]", "363 [300]", "36,30 [30]"]
    return "MND Ceny platné od 1. 1. 2026\nROČNÍ ODBĚR\nCELKOVÁ CENA\n0 20 " + "\n".join(numbers)


class DocumentTests(unittest.TestCase):
    def test_price_band_and_sums_are_verified_with_discount_scope(self):
        price = tariff_from_text(tariff_text(), "10")
        self.assertEqual(price["variable_mwh"], "363")
        details = {
            "BusinessAlgorithm": {
                "PriceListUnitPrices": {
                    "Spot": False,
                    "ValidTo": "2028-06-30",
                    "DiscountsMessage": "ceny o 10 %; Vaše cena po slevě činí 217,80 Kč za MWh vč. DPH. Končí 30. 06. 2028.",
                }
            }
        }
        selected = current_price(
            details,
            {"TYPE": "PRNOW", "CONT_DATE_FROM": "2026-01-16"},
            price,
            {"domestic_tdd": True},
        )
        self.assertEqual(selected["variable_mwh"], "338.80")
        self.assertEqual(selected["to"], "2028-07-01")
        with self.assertRaises(DataError):
            current_price(details, {"TYPE": "PRFUT"}, price, {"domestic_tdd": True})

    def test_bad_vat_or_arithmetic_never_creates_known_price(self):
        for text in (
            tariff_text().replace("121 [100]", "121 [99]"),
            tariff_text().replace("363 [300]", "364,21 [301]"),
        ):
            with self.assertRaises(DataError):
                tariff_from_text(text, "10")

    def test_invoice_cost_is_not_its_deficit_and_identity_is_required(self):
        text = (
            f"MND {PLACE} Synthetic-1\nFakturovaná částka za odběr plynu 1 210,00 Kč\n"
            "Celková platba za dodávku plynu a souvisejících služeb s DPH 1 210,00 Kč\n"
            "1. 1. 2026 - 31. 1. 2026\nNEDOPLATEK 210 Kč\n(TDD): DOM1"
        )
        row = {
            "id": "1",
            "number": "Synthetic-1",
            "from": "2026-01-01",
            "to_inclusive": "2026-01-31",
            "invoice_result": "210",
        }
        r = invoice_from_text(text, PLACE, row)
        self.assertEqual(r["cost_czk"], "1210.00")
        self.assertEqual(r["invoice_result_czk"], "-210")
        self.assertEqual(r["to"], "2026-02-01")
        self.assertTrue(r["domestic_tdd"])
        with self.assertRaises(DataError):
            invoice_from_text(text, "27ZG000Z0000001X", row)
