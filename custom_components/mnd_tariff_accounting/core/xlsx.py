"""Omezený čtecí OOXML parser podle chování referenčního Mnd.Core.

Originál je neměnný; neextrahuje se na disk, neprovádějí se vzorce, externí
vazby ani XML entity. Velikost ZIP, rozbalení a počet řádků mají pevné meze.
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import re
import unicodedata
import zipfile
from datetime import date, timedelta
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from .common import MAX_BYTES, MAX_ROWS, DataError, decimal, identity
from .metering import document_reading

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
IDENTIFIER = re.compile(r"(?<![A-Z0-9])(?:\d{2}[A-Z][A-Z0-9]{13}|\d{18})(?![A-Z0-9])", re.I)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.replace("³", "3"))
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Mn").lower().split())


def _identities(text: str) -> set[str]:
    return {m.group().upper() for m in IDENTIFIER.finditer(text)}


def _date(text: str, date1904: bool) -> date:
    """Oba Excel kalendáře; fiktivní 29. 2. 1900 a zlomky dnů se odmítají."""
    try:
        number = decimal(text)
    except DataError:
        number = None
    if number is not None:
        if (
            number != number.to_integral_value()
            or number < (0 if date1904 else 1)
            or (not date1904 and number == 60)
        ):
            raise DataError("invalid_excel_date")
        offset = int(number)
        return (
            date(1904, 1, 1) + timedelta(days=offset)
            if date1904
            else date(1899, 12, 31) + timedelta(days=offset - (offset > 60))
        )
    for separator, order in (("-", "ymd"), (".", "dmy"), ("/", "dmy")):
        parts = text.strip().split(separator)
        if len(parts) == 3:
            try:
                a, b, c = map(int, parts)
                return date(a, b, c) if order == "ymd" else date(c, b, a)
            except ValueError:
                pass
    raise DataError("invalid_date")


def parse_workbook(content: bytes, filename: str, expected_place: str) -> dict:
    """Vrátí odečty a počty odmítnutých řádků; nesoulad místa odmítne celý import.

    Výstup obsahuje hash originálu a metadata, nikoli nově vypočtené spotřeby.
    Přejmenovaný soubor je přijat jen s jednoznačnou vnitřní identitou.
    """
    identity(expected_place)
    if (
        len(content) > MAX_BYTES
        or len(filename) > 240
        or "/" in filename
        or "\\" in filename
        or filename in (".", "..")
    ):
        raise DataError("invalid_upload")
    sha = hashlib.sha256(content).hexdigest()
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if (
                len(infos) > 2000
                or len(set(names)) != len(names)
                or sum(i.file_size for i in infos) > MAX_BYTES
                or any(
                    i.flag_bits & 1
                    or "\\" in i.filename
                    or i.filename.startswith("/")
                    or ".." in PurePosixPath(i.filename).parts
                    for i in infos
                )
            ):
                raise DataError("unsafe_xlsx")

            def xml(name):
                raw = archive.read(name)
                if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper() or b"\x00" in raw:
                    raise DataError("unsafe_xml")
                return ET.fromstring(raw)

            workbook = xml("xl/workbook.xml")
            relations = {r.attrib["Id"]: r.attrib for r in xml("xl/_rels/workbook.xml.rels")}
            if any(r.get("TargetMode") == "External" for r in relations.values()):
                raise DataError("external_xlsx_relationship")
            strings = []
            if "xl/sharedStrings.xml" in names:
                strings = [
                    "".join(t.text or "" for t in item.iter(NS + "t"))
                    for item in xml("xl/sharedStrings.xml")
                ]

            def cells(sheet):
                rel = relations[sheet.attrib[REL + "id"]]
                target = rel["Target"]
                if ":" in target or "\\" in target or ".." in PurePosixPath(target).parts:
                    raise DataError("unsafe_xlsx_path")
                path = posixpath.normpath(
                    target.lstrip("/") if target.startswith("/") else "xl/" + target
                )
                root = xml(path)
                rows = root.findall(".//" + NS + "sheetData/" + NS + "row")
                if len(rows) > MAX_ROWS:
                    raise DataError("too_many_rows")
                output = []
                for row in rows:
                    values = {}
                    for cell in row.findall(NS + "c"):
                        if cell.find(NS + "f") is not None:
                            raise DataError("xlsx_formula")
                        ref = re.fullmatch(r"([A-Z]+)\d+", cell.attrib.get("r", ""))
                        if not ref:
                            raise DataError("invalid_cell_reference")
                        col = ref.group(1)
                        if col in values:
                            raise DataError("duplicate_cell")
                        raw = cell.findtext(NS + "v", "")
                        typ = cell.attrib.get("t")
                        if typ == "s":
                            index = int(raw)
                            if index < 0:
                                raise DataError("invalid_shared_string")
                            raw = strings[index]
                        elif typ == "inlineStr":
                            raw = "".join(t.text or "" for t in cell.iter(NS + "t"))
                        values[col] = raw.strip()
                    output.append((int(row.attrib["r"]), values))
                return output

            sheets = workbook.findall(".//" + NS + "sheet")
            selected = [s for s in sheets if normalize(s.attrib["name"]) == "odecty"]
            if len(selected) != 1:
                raise DataError("reading_sheet_missing")
            rows = cells(selected[0])
            headings, header_index = None, None
            for i, (_, row) in enumerate(rows[:100]):
                names = [normalize(x) for x in row.values()]
                if all(x in names for x in ("datum", "stav (m3)", "stav")):
                    if len(set(names)) != len(names):
                        raise DataError("duplicate_heading")
                    headings = {normalize(value): col for col, value in row.items()}
                    header_index = i
                    break
            if headings is None:
                raise DataError("reading_header_missing")
            for heading in ("datum", "stav (m3)", "cislo plynomeru", "zpusob zjisteni", "stav"):
                if heading not in headings:
                    raise DataError("reading_column_missing")
            title_ids = _identities(
                " ".join(v for _, row in rows[:header_index] for v in row.values())
            )
            if title_ids != {expected_place}:
                raise DataError("supply_point_mismatch")
            file_ids = _identities(filename)
            if file_ids and file_ids != title_ids:
                raise DataError("supply_point_mismatch")
            for sheet in sheets:
                if normalize(sheet.attrib["name"]) == "parametry":
                    meta = _identities(" ".join(v for _, row in cells(sheet) for v in row.values()))
                    if meta and meta != title_ids:
                        raise DataError("supply_point_mismatch")
            props = workbook.find(NS + "workbookPr")
            date1904 = props is not None and props.attrib.get("date1904") in ("1", "true")
            readings, rejected = [], []
            for row_num, row in rows[header_index + 1 :]:
                if not any(row.values()):
                    continue
                try:

                    def value(name):
                        return row.get(headings[name], "")

                    fields = {
                        "SupplyPointId": expected_place,
                        "Date": _date(value("datum"), date1904).isoformat(),
                        "MeterStateM3": decimal(value("stav (m3)"), nonnegative=True),
                        "MeterNumber": value("cislo plynomeru"),
                        "Method": value("zpusob zjisteni"),
                        "Status": value("stav"),
                        "SourceFile": filename,
                        "SourceRow": row_num,
                    }
                    reading = document_reading(fields, sha)
                    readings.append({"reading": reading, "row": row_num, "original": fields})
                except (DataError, ValueError, OverflowError):
                    rejected.append({"row": row_num, "reason": "invalid_reading_row"})
            return {
                "place": expected_place,
                "sha256": sha,
                "filename": filename,
                "readings": readings,
                "rejected": rejected,
                "warnings": [] if file_ids else ["filename_identity_missing"],
                "complete": not rejected,
            }
    except (
        zipfile.BadZipFile,
        KeyError,
        ET.ParseError,
        IndexError,
        ValueError,
        RuntimeError,
    ) as err:
        if isinstance(err, DataError):
            raise
        raise DataError("invalid_xlsx") from err
