"""Návrh hodnot z textové faktury PDF; žádné automatické zaúčtování.

PDF nemá jednotnou účetní sémantiku. Nalezené částky jsou kandidáti, více
výskytů zůstává více výskyty a uživatel údaje potvrzuje ve formuláři faktury.
Neskenuje obrázky ani neprovádí JavaScript, přílohy nebo odkazy dokumentu.
"""

from __future__ import annotations

import io
import re

from .common import DataError, decimal
from .xlsx import IDENTIFIER

LABELS = {
    "přeplatek": "surplus",
    "nedoplatek": "deficit",
    "celkové náklady": "cost",
    "náklady na dodávku": "cost",
    "přijaté zálohy": "included_advances",
}
AMOUNT = re.compile(
    r"(?P<number>[+-]?\d(?:[\d \u00a0\u202f]*\d)?(?:[,.]\d{1,3})?)\s*(?P<unit>Kč|CZK|MWh|kWh|m[³3])",
    re.I,
)


def propose_from_text(text: str, expected_place: str) -> dict:
    """Ponechá kontext každého kandidáta; finanční výsledek není celkový náklad."""
    found = {m.group().upper() for m in IDENTIFIER.finditer(text)}
    if found and found != {expected_place}:
        raise DataError("pdf_supply_point_mismatch")
    candidates = []
    for line in text.splitlines():
        for match in AMOUNT.finditer(line):
            label = next(
                (kind for phrase, kind in LABELS.items() if phrase in line.lower()), "unclassified"
            )
            candidates.append(
                {
                    "kind": label,
                    "value": decimal(match["number"]),
                    "unit": match["unit"],
                    "context": line[:300],
                    "confirmed": False,
                }
            )
            if len(candidates) > 500:
                raise DataError("pdf_too_many_candidates")
    return {
        "candidates": candidates,
        "identity_found": bool(found),
        "requires_confirmation": True,
        "warnings": ([] if found else ["pdf_identity_confirmation_required"])
        + ([] if text.strip() else ["pdf_no_text_manual_entry_required"]),
    }


def parse_invoice_pdf(content: bytes, expected_place: str) -> dict:
    """Vstup nejvýše 8 MiB / 20 stran / 2 MiB obsahu strany, bez OCR.

    Čtení běží v adaptéru mimo event loop. Limit rozbaleného obsahu se kontroluje
    před extrakcí podle doporučení pypdf; nejde o izolovaný procesový sandbox.
    Zašifrovaný/poškozený doklad má samostatnou chybu a účetnictví nemění.
    """
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    if len(content) > 8 * 1024 * 1024 or not content.startswith(b"%PDF-"):
        raise DataError("pdf_invalid_or_too_large")
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise DataError("pdf_encrypted")
        if len(reader.pages) > 20:
            raise DataError("pdf_too_many_pages")
        texts = []
        for page in reader.pages:
            stream = page.get_contents()
            if stream and len(stream.get_data()) > 2 * 1024 * 1024:
                raise DataError("pdf_content_too_large")
            texts.append(page.extract_text() or "")
            if sum(map(len, texts)) > 500_000:
                raise DataError("pdf_text_too_large")
        return propose_from_text("\n".join(texts), expected_place)
    except (PyPdfError, ValueError, RecursionError, KeyError) as err:
        if isinstance(err, DataError):
            raise
        raise DataError("pdf_parse_failed") from err
