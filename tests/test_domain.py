"""Syntetické regresní případy MND; žádné osobní ani živé podklady.

Testy běží standardním unittest bez HA, prokazují finanční a měřicí
invarianty, ne pouze podobnost výstupu s implementací.
"""

import copy
import io
import unittest
import zipfile
from datetime import date, datetime, timedelta
from decimal import Decimal as D
from xml.sax.saxutils import escape

from custom_components.mnd_tariff_accounting.core.accounting import (
    calculate,
    invoice_settlement,
)
from custom_components.mnd_tariff_accounting.core.archive import Repository, apply_import
from custom_components.mnd_tariff_accounting.core.common import DataError, decimal, load_json, money
from custom_components.mnd_tariff_accounting.core.forecast import (
    add_snapshot,
    compare_forecast,
    seasonal_forecast,
)
from custom_components.mnd_tariff_accounting.core.metering import (
    Reading,
    consumption_intervals,
    current_state,
    meter_points,
)
from custom_components.mnd_tariff_accounting.core.xlsx import parse_workbook

PLACE = "27ZG000Z0000000X"
OTHER = "27ZG000Z0000000Y"


def reading(value="1000", at="2026-01-01", source="mnd", **extra):
    return Reading.parse(
        {
            "id": f"{at}-{value}-{source}",
            "place": PLACE,
            "meter": "0001",
            "date": at,
            "value": value,
            "source": source,
            **extra,
        }
    )


def workbook(*, place=PLACE, rows=None, date1904=False, formula=False, metadata=None):
    """Minimální skutečný OOXML ZIP, generovaný výhradně ze syntetických buněk."""
    rows = rows or [["1.1.2026", "1 000,5", "0001", "Samoodečtem", "Evidenční"]]
    table = [
        [f"Odečty EIC {place}"],
        [],
        ["Datum", "Stav (m³)", "Číslo plynoměru", "Způsob zjištění", "Stav"],
        *rows,
    ]
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    )
    for i, row in enumerate(table, 1):
        sheet += f'<row r="{i}">'
        for j, text in enumerate(row):
            ref = f"{chr(65 + j)}{i}"
            cell = f"<is><t>{escape(str(text))}</t></is>"
            if formula and i == 4 and j == 1:
                cell += "<f>1+1</f>"
            sheet += f'<c r="{ref}" t="inlineStr">{cell}</c>'
        sheet += "</row>"
    sheet += "</sheetData></worksheet>"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            f'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><workbookPr date1904="{int(date1904)}"/><sheets><sheet name="Odečty" r:id="s1"/>'
            + ('<sheet name="Parametry" r:id="s2"/>' if metadata else "")
            + "</sheets></workbook>",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships><Relationship Id="s1" Target="worksheets/sheet1.xml"/>'
            + ('<Relationship Id="s2" Target="worksheets/sheet2.xml"/>' if metadata else "")
            + "</Relationships>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
        if metadata:
            archive.writestr("xl/worksheets/sheet2.xml", sheet.replace(place, metadata))
    return output.getvalue()


def request(**extra):
    return {
        "start": "2026-01-01",
        "end": "2026-02-01",
        "segments": [{"from": "2026-01-01", "to": "2026-02-01", "m3": "100", "complete": True}],
        "tariffs": [
            {
                "from": "2026-01-01",
                "to": "2026-02-01",
                "commodity": "500",
                "other": "500",
                "fixed": "0",
                "includes_vat": True,
                "all_components_known": True,
                "prorate_fixed": False,
            }
        ],
        "conversions": [{"from": "2026-01-01", "to": "2026-02-01", "kwh_per_m3": "10"}],
        "events": [
            {
                "id": "p1",
                "role": "payment",
                "amount": "1200",
                "from": "2026-01-01",
                "to": "2026-02-01",
            }
        ],
        "opening_credit": "100",
        "payments_complete": True,
        **extra,
    }


class NumbersTests(unittest.TestCase):
    def test_czech_number_and_zero(self):
        self.assertEqual(decimal("1\u00a0234,50"), D("1234.50"))
        self.assertEqual(decimal("0"), 0)
        self.assertIsNone(decimal(None, optional=True))

    def test_nonfinite_and_float_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity", True, 0.1):
            with self.subTest(value=value), self.assertRaises(DataError):
                decimal(value)

    def test_rounding_away_from_zero(self):
        self.assertEqual(money(D("1.005")), D("1.01"))
        self.assertEqual(money(D("-1.005")), D("-1.01"))

    def test_json_duplicate_and_nan_rejected(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(DataError):
                load_json(raw)
        self.assertEqual(
            load_json('{"x":0.123456789012345678901}')["x"], D("0.123456789012345678901")
        )


class WorkbookTests(unittest.TestCase):
    def test_real_zip_shifted_heading_and_czech_number(self):
        parsed = parse_workbook(workbook(), f"Odečty_{PLACE}(1).xlsx", PLACE)
        self.assertEqual(parsed["readings"][0]["reading"].value, D("1000.5"))
        self.assertEqual(parsed["readings"][0]["reading"].meter, "0001")
        self.assertTrue(parsed["complete"])

    def test_wrong_id_in_name_or_selection_or_metadata(self):
        for filename, selected, metadata in (
            (f"Odečty_{OTHER}.xlsx", PLACE, None),
            ("x.xlsx", OTHER, None),
            ("x.xlsx", PLACE, OTHER),
        ):
            with self.subTest(selected=selected), self.assertRaises(DataError):
                parse_workbook(workbook(metadata=metadata), filename, selected)

    def test_renamed_file_warning(self):
        self.assertIn(
            "filename_identity_missing",
            parse_workbook(workbook(), "export.xlsx", PLACE)["warnings"],
        )

    def test_formula_html_and_path_rejected(self):
        for data, filename in (
            (workbook(formula=True), "x.xlsx"),
            (b"<html>Login</html>", "x.xlsx"),
            (workbook(), "../x.xlsx"),
        ):
            with self.assertRaises(DataError):
                parse_workbook(data, filename, PLACE)

    def test_date_systems(self):
        for serial, is1904, expected in (
            ("1", False, date(1900, 1, 1)),
            ("61", False, date(1900, 3, 1)),
            ("0", True, date(1904, 1, 1)),
        ):
            output = parse_workbook(
                workbook(rows=[[serial, "0", "0001", "Odečtem", "Nový status"]], date1904=is1904),
                "x.xlsx",
                PLACE,
            )
            self.assertEqual(output["readings"][0]["reading"].date, expected)

    def test_invalid_rows_not_zero(self):
        parsed = parse_workbook(workbook(rows=[["60", "0", "0001", "", ""]]), "x.xlsx", PLACE)
        self.assertFalse(parsed["complete"])
        self.assertEqual(len(parsed["rejected"]), 1)
        self.assertEqual(parsed["readings"], [])


class MeterTests(unittest.TestCase):
    def test_statuses_preserved_one_point(self):
        a = reading(status="Evidenční")
        b = reading(status="Vyfakturovaný", id="b")
        points = meter_points([a, b], PLACE)
        self.assertEqual(len(points), 1)
        self.assertEqual(len(points[0]["sources"]), 2)

    def test_priority_same_boundary(self):
        points = meter_points([reading(), reading("1004", source="manual")], PLACE)
        self.assertEqual(points[0]["value"], 1000)

    def test_conflict_and_decrease_break_intervals(self):
        rows = [
            reading(),
            reading("1010", "2026-01-02"),
            reading("1011", "2026-01-02"),
            reading("1020", "2026-01-03"),
            reading("0", "2026-01-04"),
        ]
        intervals = consumption_intervals(rows, PLACE)
        self.assertTrue(all(i["consumption_m3"] is None for i in intervals))

    def test_sensor_mnd_rebase_and_correction(self):
        at = "2026-01-01T12:00:00+00:00"
        anchor = reading(observed_at=at)
        samples = [
            {
                "entity": "registry1",
                "segment": "0001",
                "unit": "m³",
                "state_class": "total",
                "at": stamp,
                "value": value,
            }
            for stamp, value in ((at, "200"), ("2026-01-02T12:00:00+00:00", "230"))
        ]
        result = current_state(
            [anchor], samples, None, place=PLACE, segment="0001", zone="Europe/Prague"
        )
        self.assertEqual(result["value"], 1030)
        correction = reading(
            "1002", observed_at=at, supersedes=anchor.id, evidence="document-revision"
        )
        self.assertEqual(
            current_state(
                [anchor, correction],
                samples,
                None,
                place=PLACE,
                segment="0001",
                zone="Europe/Prague",
            )["value"],
            1032,
        )

    def test_unpaired_daily_anchor_not_midnight(self):
        result = current_state(
            [reading()], [], None, place=PLACE, segment="0001", zone="Europe/Prague"
        )
        self.assertEqual(result["reason"], "anchor_time_unpaired")
        self.assertIsInstance(result["at"], date)
        self.assertNotIsInstance(result["at"], datetime)

    def test_intermediate_reset_detected(self):
        at = "2026-01-01T00:00:00Z"
        samples = [
            {
                "entity": "s",
                "segment": "0001",
                "unit": "m³",
                "state_class": "total",
                "at": f"2026-01-0{i}T00:00:00Z",
                "value": v,
            }
            for i, v in enumerate(("200", "0", "230"), 1)
        ]
        calibration = {
            "place": PLACE,
            "segment": "0001",
            "entity": "s",
            "at": at,
            "physical": "1000",
            "sensor": "200",
        }
        self.assertIsNone(
            current_state(
                [], samples, calibration, place=PLACE, segment="0001", zone="Europe/Prague"
            )["value"]
        )


class AccountingTests(unittest.TestCase):
    def test_100_plus_1200_minus_1000(self):
        output = calculate(**request())
        self.assertEqual(output["balance_czk"], 300)
        self.assertEqual(output["energy_mwh"], 1)
        self.assertTrue(output["complete"])

    def test_unpaid_prescription_does_not_increase_balance(self):
        req = request()
        req["events"].append(
            {**req["events"][0], "id": "plan", "role": "prescribed", "amount": "500"}
        )
        self.assertEqual(calculate(**req)["balance_czk"], 300)

    def test_refund_changes_balance_not_invoice_result(self):
        req = request()
        req["events"].append(
            {**req["events"][0], "id": "refund", "role": "refund", "amount": "300", "invoice": "i1"}
        )
        self.assertEqual(calculate(**req)["balance_czk"], 0)
        settlement = invoice_settlement({"id": "i1", "result": "300"}, req["events"])
        self.assertEqual(
            settlement,
            {
                "result": D(300),
                "remaining": D(0),
                "over_settled": D(0),
                "kind": "surplus",
                "remaining_signed": D(0),
                "remaining_kind": "balanced",
                "settlement_complete": True,
            },
        )

    def test_unknown_inputs_not_zero(self):
        for changes in (
            {"opening_credit": None},
            {"payments_complete": False},
            {"conversions": []},
            {"tariffs": []},
            {"segments": []},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(calculate(**request(**changes))["balance_czk"])

    def test_true_zero_valid(self):
        req = request()
        req["segments"][0]["m3"] = "0"
        self.assertEqual(calculate(**req)["balance_czk"], 1300)

    def test_tariff_boundary_requires_measurement(self):
        req = request()
        tariff = req["tariffs"][0]
        req["tariffs"] = [
            {**tariff, "to": "2026-01-15", "prorate_fixed": True},
            {**tariff, "from": "2026-01-15", "commodity": "1000", "prorate_fixed": True},
        ]
        self.assertIsNone(calculate(**req)["balance_czk"])
        self.assertTrue(calculate(**{**req, "allow_linear": True})["estimated"])

    def test_alternative_not_charged(self):
        req = request()
        req["tariffs"].append({**req["tariffs"][0], "role": "alternative", "commodity": "999999"})
        self.assertEqual(calculate(**req)["balance_czk"], 300)

    def test_vat_once_and_month_fixed(self):
        req = request()
        req["tariffs"][0].update(includes_vat=False, vat_percent="21", fixed="100")
        self.assertEqual(calculate(**req)["known_cost_czk"], D("1331.00"))

    def test_monthly_proration_preserves_exact_half_cent(self):
        req = request()
        req["segments"][0]["m3"] = "0"
        req["tariffs"][0]["fixed"] = "1.005"
        self.assertEqual(calculate(**req)["known_cost_czk"], D("1.01"))

    def test_invoice_replaces_cost(self):
        req = request(
            invoices=[
                {
                    "id": "i1",
                    "from": "2026-01-01",
                    "to": "2026-02-01",
                    "cost": "800",
                    "confirmed": True,
                }
            ]
        )
        self.assertEqual(calculate(**req)["known_cost_czk"], 800)
        self.assertEqual(calculate(**req)["balance_czk"], 500)

    def test_assumed_paid_not_actual(self):
        req = request()
        req["events"][0]["role"] = "assumed_paid"
        self.assertEqual(calculate(**req)["paid_czk"], 0)

    def test_unmatched_payment_incomplete(self):
        req = request()
        req["events"][0]["verification"] = "unmatched"
        self.assertIsNone(calculate(**req)["balance_czk"])

    def test_overlapping_intervals_rejected(self):
        req = request()
        req["segments"].append(copy.deepcopy(req["segments"][0]))
        with self.assertRaises(DataError):
            calculate(**req)


class ForecastTests(unittest.TestCase):
    def test_zero_actual_percentage_undefined(self):
        common = {
            "place": PLACE,
            "segments": ["0001"],
            "from": "2026-01-01",
            "to": "2026-02-01",
            "unit": "MWh",
            "conversion_id": "c1",
        }
        output = compare_forecast(
            {**common, "value": "1"}, {**common, "value": "0", "complete": True}
        )
        self.assertIsNone(output["percentage"])
        with self.assertRaises(DataError):
            compare_forecast(
                {**common, "value": "1"},
                {**common, "to": "2026-01-15", "value": "0", "complete": True},
            )

    def test_old_forecast_is_preserved(self):
        snapshots = add_snapshot(
            [], {"retrieved_at": "2026-01-01T00:00:00Z", "periods": [{"future": "3"}]}
        )
        snapshots = add_snapshot(
            snapshots, {"retrieved_at": "2026-02-01T00:00:00Z", "periods": [{"future": "2"}]}
        )
        self.assertEqual(snapshots[0]["periods"][0]["future"], "3")

    def test_summer_only_cannot_predict_winter(self):
        self.assertFalse(seasonal_forecast([], "2026-10-01", "2026-11-01")["complete"])
        history = [
            {"date": date(2026, 10, 1) - timedelta(days=i), "m3": "1", "complete": True}
            for i in range(1, 366)
        ]
        self.assertEqual(seasonal_forecast(history, "2026-10-01", "2026-11-01")["value"], 31)


class ArchiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_idempotent_import_and_restore(self):
        saved = []

        async def save(data):
            saved.append(copy.deepcopy(data))

        repository = Repository("account-1", None, save)
        parsed = parse_workbook(workbook(), "x.xlsx", PLACE)
        await repository.transact(lambda data: apply_import(data, parsed))
        await repository.transact(lambda data: apply_import(data, parsed))
        self.assertEqual(len(saved), 1)
        restored = Repository("account-1", saved[-1], save)
        self.assertEqual(len(restored.data["places"][PLACE]["readings"]), 1)

    async def test_failed_commit_does_not_publish(self):
        async def save(data):
            raise OSError("synthetic disk full")

        repository = Repository("a", None, save)
        with self.assertRaises(OSError):
            await repository.transact(lambda data: data.update(marker=True))
        self.assertNotIn("marker", repository.data)

    async def test_future_schema_and_revision_rejected(self):
        async def save(data):
            pass

        with self.assertRaises(DataError):
            Repository("a", {"schema_version": 999}, save)
        repository = Repository("a", None, save)
        with self.assertRaises(DataError):
            await repository.transact(lambda data: None, expected_revision=9)


if __name__ == "__main__":
    unittest.main()
