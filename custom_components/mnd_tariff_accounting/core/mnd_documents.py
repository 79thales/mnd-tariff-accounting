"""Úzké ověření originálních PDF MND pro čtecí finanční přehled.

Nejde o obecný odhad částek z PDF. Přijímáme pouze jednoznačné názvy polí,
účetní součty a tabulku s párovými cenami s/bez DPH. Neznámý formát vrací
doménovou chybu, ne nulovou cenu. Texty a identity se nikdy nezapisují do logu.
"""

import io
import re
from datetime import timedelta
from decimal import Decimal
from html import unescape

from .common import DataError, day, decimal, fingerprint, money, wire

NUMBER = r"\d+(?:[ \u00a0\u202f]\d{3})*(?:[,.]\d+)?"
PAIR = re.compile(rf"({NUMBER})\s*\[\s*({NUMBER})\s*\]")
CZ_DATE = r"\d{1,2}\.\s*\d{1,2}\.\s*\d{4}"


def pdf_text(content):
    """Omezená textová extrakce v executoru; nikdy OCR, odkazy ani přílohy."""
    from pypdf import PdfReader
    from pypdf.errors import PyPdfError

    if len(content) > 8 * 1024 * 1024 or not content.startswith(b"%PDF-"):
        raise DataError("mnd_pdf_invalid")
    try:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) > 20:
            raise DataError("mnd_pdf_unsupported")
        texts = []
        for page in reader.pages:
            stream = page.get_contents()
            if stream and len(stream.get_data()) > 2 * 1024 * 1024:
                raise DataError("mnd_pdf_too_large")
            texts.append(page.extract_text() or "")
        text = "\n".join(texts)
        if len(text) > 500_000:
            raise DataError("mnd_pdf_too_large")
        return text
    except (PyPdfError, ValueError, KeyError, RecursionError) as error:
        if isinstance(error, DataError):
            raise
        raise DataError("mnd_pdf_unreadable") from error


def czech_day(text):
    """Datum z hlavičky je kalendářní hranice, nikoli vymyšlený čas odečtu."""
    parts = [int(x) for x in re.findall(r"\d+", text)]
    if len(parts) != 3:
        raise DataError("mnd_document_date_invalid")
    return day(f"{parts[2]:04d}-{parts[1]:02d}-{parts[0]:02d}")


def tariff_from_text(text, annual_mwh):
    """Vybere doložené odběrové pásmo z tabulky celkové ceny MND.

    Každý řádek musí mít šest dvojic: regulovaná variabilní/stálá,
    obchodní variabilní/stálá, jejich dva součty. Kontrolujeme aritmetiku
    a DPH 21 %. Kapacitní pásma nad posledním měsíčním pásmem se neodhadují.
    Výstup jsou Kč/MWh a Kč/měsíc včetně DPH, nezahrnuje individuální slevu.
    """
    if not all(label in text for label in ("MND", "ROČNÍ ODBĚR", "CELKOVÁ CENA")):
        raise DataError("mnd_tariff_format_unknown")
    header = re.search(rf"platn[ée].{{0,100}}?od\s+({CZ_DATE})", text, re.I)
    if not header:
        raise DataError("mnd_tariff_validity_missing")
    valid_from = czech_day(header[1])
    table = text.split("ROČNÍ ODBĚR", 1)[1].split("ROČNÍ ODBĚR", 1)[0]
    # PDF má na první řádce hranice pásma i první cenu. Oddělíme je před
    # čtením částky, jinak by např. „15 450,50“ mohlo znamenat 15 450,50 Kč.
    table = re.sub(
        r"(?m)^\s*(\d+(?:,\d+)?)\s+(\d+(?:,\d+)?)\s+(\d[^\n]*)$",
        r"BAND:\1:\2\n\3",
        table,
    )
    pairs = list(PAIR.finditer(table))
    if not pairs or len(pairs) % 6:
        raise DataError("mnd_tariff_table_ambiguous")
    annual = decimal(annual_mwh, nonnegative=True)
    rows, previous = [], 0
    for offset in range(0, len(pairs), 6):
        group = pairs[offset : offset + 6]
        markers = re.findall(r"BAND:([^:\n]+):([^\n]+)", table[previous : group[0].start()])
        previous = group[-1].end()
        if len(markers) != 1:
            raise DataError("mnd_tariff_band_ambiguous")
        low, high = map(decimal, markers[0])
        values = [(decimal(p[1]), decimal(p[2])) for p in group]
        if low >= high or any(g < 0 or n < 0 for g, n in values):
            raise DataError("mnd_tariff_values_invalid")
        if any(abs(g - money(n * Decimal("1.21"))) > Decimal("0.02") for g, n in values):
            raise DataError("mnd_tariff_vat_mismatch")
        if any(
            abs(values[a][col] + values[b][col] - values[c][col]) > Decimal("0.02")
            for a, b, c in ((0, 2, 4), (1, 3, 5))
            for col in (0, 1)
        ):
            raise DataError("mnd_tariff_sum_mismatch")
        rows.append((low, high, values))
    selected = [v for a, b, v in rows if a < annual <= b or a == annual == 0]
    if len(selected) != 1:
        raise DataError("mnd_tariff_band_unavailable")
    values = selected[0]
    return wire(
        {
            "from": valid_from,
            "regulatory_to": day(f"{valid_from.year + 1}-01-01"),
            "regulated_mwh": values[0][0],
            "regulated_month": values[1][0],
            "commodity_mwh": values[2][0],
            "commodity_month": values[3][0],
            "variable_mwh": values[4][0],
            "fixed_month": values[5][0],
            "vat_included": True,
            "method": "mnd_six_column_gross_net_table_v1",
        }
    )


def invoice_from_text(text, expected_place, row):
    """Originální náklad převezme jen po identitě a kontrole částek s DPH.

    Výsledek faktury není cena plynu. Úhrady předpisů se neberou z tohoto
    dokladu podruhé; vracíme náklad, rozsah a samostatný výsledek vyúčtování.
    Fakturovaný konečný den převádíme na výlučný následující den jen zde,
    kde formát faktury výslovně obsahuje období od–do.
    """
    if expected_place not in text or str(row["number"]) not in text:
        raise DataError("mnd_invoice_identity_mismatch")
    amounts = re.findall(
        rf"^Fakturovaná částka za odběr plynu[ \t]+({NUMBER})[ \t]*Kč[ \t]*$", text, re.M
    )
    totals = re.findall(
        rf"Celková platba za dodávku plynu a souvisejících služeb s\s*DPH\s+({NUMBER})\s*Kč", text
    )
    if len(amounts) != 1 or len(totals) != 1 or decimal(amounts[0]) != decimal(totals[0]):
        raise DataError("mnd_invoice_cost_ambiguous")
    ranges = re.findall(rf"({CZ_DATE})\s*[-–]\s*({CZ_DATE})", text)
    start, end = day(row["from"]), day(row["to_inclusive"])
    if not any(czech_day(a) == start and czech_day(b) == end for a, b in ranges):
        raise DataError("mnd_invoice_period_mismatch")
    conversion = re.search(
        rf"([\d \u00a0]+)\s*m[³3]\s*x\s*objemový koeficient\s+({NUMBER})\s*x\s*spalné teplo\s+({NUMBER})",
        text,
    )
    result = {
        "id": row["id"],
        "from": start,
        "to": end + timedelta(days=1),
        "cost_czk": decimal(totals[0], nonnegative=True),
        "invoice_result_czk": None,
        "source": "original_mnd_invoice",
        "verified": True,
        "text_hash": fingerprint(text),
        "domestic_tdd": bool(re.search(r"TDD\).*?DOM\d", text)),
    }
    settlements = {
        (-1 if label.upper() == "NEDOPLATEK" else 1) * decimal(value)
        for label, value in re.findall(rf"(PŘEPLATEK|NEDOPLATEK)\s+({NUMBER})\s*Kč", text, re.I)
    }
    if len(settlements) == 1:
        result["invoice_result_czk"] = settlements.pop()
    if conversion:
        result["kwh_per_m3"] = decimal(conversion[2]) * decimal(conversion[3])
    energy = re.search(rf"Přepočet spotřeby z m[³3] na MWh:[^\n]+?=\s*({NUMBER})\s*MWh", text)
    if energy:
        result["energy_mwh"] = decimal(energy[1])
    return wire(result)


def current_price(details, document, parsed, invoice):
    """Složí skutečný smluvní produkt, regulované složky a doloženou slevu.

    PRNOW se nesmí zaměnit s PRFUT nebo alternativou. Měsíční distribuce
    i obchodní platba jsou včetně DPH. Individuální sleva se použije pouze
    při výslovném Kč/MWh vč. DPH a datu konce zvýhodnění. Částka z osobního
    smluvního sdělení má přednost před odvozováním slevy z obecného PDF;
    procentní marketingový text není přesnější než explicitní jednotková cena.
    Regulované sazby jsou známé jen pro rok účinnosti PDF; pozdější použití
    smí být výslovně označeným předpokladem prognózy, nikdy vzniklým nákladem.
    """
    if document.get("TYPE") != "PRNOW" or not invoice.get("domestic_tdd"):
        raise DataError("mnd_price_scope_unverified")
    algorithm = details.get("BusinessAlgorithm") or {}
    prices = algorithm.get("PriceListUnitPrices") or {}
    if prices.get("Spot") is not False:
        raise DataError("mnd_spot_price_unsupported")
    if not document.get("CONT_DATE_FROM"):
        raise DataError("mnd_tariff_validity_missing")
    first = max(day(str(document["CONT_DATE_FROM"])[:10]), day(parsed["from"]))
    last = day(str(prices["ValidTo"])[:10]) + timedelta(days=1) if prices.get("ValidTo") else None
    commodity = decimal(parsed["commodity_mwh"])
    caption = unescape(re.sub(r"<[^>]*>", " ", prices.get("DiscountsMessage") or ""))
    discounted_to = None
    if caption.strip():
        amount = re.search(rf"cena po slevě činí\s+({NUMBER})\s*Kč za MWh vč\.\s*DPH", caption)
        percent = re.search(r"o\s+(\d+(?:[,.]\d+)?)\s*%", caption)
        dates = re.findall(CZ_DATE, caption)
        if not amount or not percent or len(dates) != 1:
            raise DataError("mnd_discount_unverified")
        discounted = decimal(amount[1])
        if not 0 <= decimal(percent[1]) <= 100 or not 0 < discounted <= commodity:
            raise DataError("mnd_discount_mismatch")
        commodity, discounted_to = discounted, czech_day(dates[0]) + timedelta(days=1)
        last = min(last, discounted_to) if last else discounted_to
    return wire(
        {
            **parsed,
            "from": first,
            "to": last,
            "commodity_mwh": commodity,
            "variable_mwh": commodity + decimal(parsed["regulated_mwh"]),
            "fixed_month": decimal(parsed["commodity_month"]) + decimal(parsed["regulated_month"]),
            "source": "original_mnd_current_tariff",
            "verified": True,
            "discount_to": discounted_to,
        }
    )
