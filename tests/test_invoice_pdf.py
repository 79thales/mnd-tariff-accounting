"""Návrhy z PDF nejsou potvrzenou fakturou ani automatickým účetním zápisem."""

import io
import unittest
from decimal import Decimal

from custom_components.mnd_tariff_accounting.core.common import DataError
from custom_components.mnd_tariff_accounting.core.invoice_pdf import (
    parse_invoice_pdf,
    propose_from_text,
)

PLACE = "27ZG000Z0000000X"


class PdfProposalTests(unittest.TestCase):
    def test_real_synthetic_pdf_is_extracted_without_accounting_confirmation(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(
            f"BT /F1 12 Tf 20 150 Td (EIC {PLACE}) Tj 0 -20 Td (Synthetic total 1250.50 CZK) Tj ET".encode(
                "ascii"
            )
        )
        page[NameObject("/Contents")] = stream
        content = io.BytesIO()
        writer.write(content)
        proposal = parse_invoice_pdf(content.getvalue(), PLACE)
        self.assertTrue(proposal["identity_found"])
        self.assertEqual(proposal["candidates"][0]["value"], Decimal("1250.50"))
        self.assertFalse(proposal["candidates"][0]["confirmed"])

    def test_encrypted_or_oversized_pdf_refused(self):
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("synthetic")
        content = io.BytesIO()
        writer.write(content)
        with self.assertRaisesRegex(DataError, "encrypted"):
            parse_invoice_pdf(content.getvalue(), PLACE)
        with self.assertRaisesRegex(DataError, "too_large"):
            parse_invoice_pdf(b"%PDF-" + b" " * (8 * 1024 * 1024), PLACE)

    def test_surplus_is_not_cost_and_ambiguous_amounts_preserved(self):
        text = f"EIC {PLACE}\nCelkové náklady 12 000,50 Kč\nPřeplatek 300,25 Kč\nPřeplatek 100 Kč"
        proposal = propose_from_text(text, PLACE)
        self.assertEqual(
            [c["kind"] for c in proposal["candidates"]], ["cost", "surplus", "surplus"]
        )
        self.assertEqual(proposal["candidates"][0]["value"], Decimal("12000.50"))
        self.assertTrue(proposal["requires_confirmation"])
        self.assertTrue(all(not c["confirmed"] for c in proposal["candidates"]))

    def test_scan_needs_manual_entry_and_foreign_identity_rejected(self):
        self.assertIn("pdf_no_text_manual_entry_required", propose_from_text("", PLACE)["warnings"])
        with self.assertRaises(DataError):
            propose_from_text("EIC 27ZG000Z0000000Y", PLACE)
