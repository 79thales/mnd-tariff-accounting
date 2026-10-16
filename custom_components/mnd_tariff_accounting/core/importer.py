"""Import společného C# kontraktu v1 bez ztráty volitelných polí a Decimal."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from .common import MAX_ROWS, DataError, decimal, fingerprint, identity, instant, load_json
from .metering import document_reading


def _validate(value, rule, schema, depth=0):
    """Validace použitého podmnožinového JSON Schema draft 2020-12.

    Přibalený kontrakt používá $ref, anyOf, typy, enum, const, minimum,
    required a additionalProperties. Neznámé verzování se odmítne dříve než
    import; tato funkce není deklarována jako obecný JSON Schema engine.
    """
    if depth > 32:
        raise DataError("archive_too_deep")
    if "$ref" in rule:
        return _validate(value, schema["$defs"][rule["$ref"].split("/")[-1]], schema, depth + 1)
    if "anyOf" in rule:
        for alternative in rule["anyOf"]:
            try:
                _validate(value, alternative, schema, depth + 1)
                return
            except DataError:
                pass
        raise DataError("archive_schema_mismatch")
    if "const" in rule and (value != rule["const"] or isinstance(value, bool)):
        raise DataError("unsupported_schema_version")
    if "enum" in rule and value not in rule["enum"]:
        raise DataError("archive_invalid_enum")
    checks = {
        "object": lambda x: isinstance(x, dict),
        "array": lambda x: isinstance(x, list),
        "string": lambda x: isinstance(x, str),
        "boolean": lambda x: isinstance(x, bool),
        "null": lambda x: x is None,
        "number": lambda x: isinstance(x, (int, Decimal)) and not isinstance(x, bool),
        "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
    }
    types = rule.get("type", [])
    types = [types] if isinstance(types, str) else types
    if types and not any(checks[t](value) for t in types):
        raise DataError("archive_wrong_type")
    if value is None:
        return
    if isinstance(value, dict):
        if any(k not in value for k in rule.get("required", [])):
            raise DataError("archive_missing_field")
        if rule.get("additionalProperties") is False and set(value) - set(
            rule.get("properties", {})
        ):
            raise DataError("archive_unknown_field")
        for key, item in value.items():
            if key in rule.get("properties", {}):
                _validate(item, rule["properties"][key], schema, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_ROWS:
            raise DataError("too_many_rows")
        for item in value:
            _validate(item, rule.get("items", {}), schema, depth + 1)
    elif isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        number = decimal(value)
        if "minimum" in rule and number < rule["minimum"]:
            raise DataError("archive_negative_number")
    elif isinstance(value, str):
        try:
            if rule.get("format") == "date":
                date.fromisoformat(value)
            if rule.get("format") == "date-time":
                instant(value)
        except ValueError as err:
            raise DataError("archive_invalid_date") from err


def parse_v1(content: bytes, expected_place: str, zone="UTC") -> dict:
    """Zachová celou původní verzi, zdrojové výsledky i cesty jako metadata.

    Dokumenty uvedené Windows cestou se neotvírají; originál se importuje
    zvlášť. Neznámé identity a cizí záznamy odmítnou celou transakci.
    """
    identity(expected_place)
    raw = load_json(content)
    if not isinstance(raw, dict) or raw.get("SchemaVersion") != 1:
        raise DataError("unsupported_schema_version")
    schema = json.loads(
        (Path(__file__).parents[1] / "schemas/mnd-data-v1.schema.json").read_text(encoding="utf-8")
    )
    # Volitelné rozšíření v1 mohlo ve starších exportech chybět. Jeho absence
    # zůstane v raw zachována; validátor ji neposune na potvrzený prázdný seznam.
    expanded = {
        key: None
        for key in (
            "Tariffs",
            "Payments",
            "Documents",
            "PricingEvidence",
            "PortalRetrievedAt",
            "Deposit",
            "ConsumptionPeriods",
            "ConsumptionSnapshots",
        )
    }
    expanded.update(raw)
    _validate(expanded, schema, schema)
    if raw["Place"]["Id"] != expected_place:
        raise DataError("supply_point_mismatch")
    for reading in raw["Readings"]:
        if reading["SupplyPointId"] != expected_place:
            raise DataError("supply_point_mismatch")
    for document in raw.get("Documents") or []:
        if document["SupplyPointId"] != expected_place:
            raise DataError("supply_point_mismatch")
    if raw.get("Actual") and raw["Actual"]["SupplyPointId"] != expected_place:
        raise DataError("supply_point_mismatch")
    sha = fingerprint(raw)
    readings = [document_reading(r, sha).dump() for r in raw["Readings"]]
    actual = raw.get("Actual")
    if actual and actual["Source"] == "Manual":
        from .common import local_day
        from .metering import Reading

        # Ruční fyzický stav přejde do časované místní vrstvy. Externě odvozený
        # stav HomeAssistant bez surové kalibrace zůstává pouze v raw v1;
        # neprohlásíme jej za nově ověřený fyzický stav nativního senzoru.
        readings.append(
            Reading.parse(
                {
                    "id": fingerprint(actual),
                    "place": expected_place,
                    "meter": actual["MeterNumber"],
                    "date": local_day(actual["MeasuredAt"], zone),
                    "observed_at": actual["MeasuredAt"],
                    "value": actual["MeterStateM3"],
                    "source": "manual",
                    "estimated": actual["Estimated"],
                    "note": actual.get("Note") or "",
                    "method": "Ruční odečet importovaný z C#",
                    "evidence": sha,
                }
            ).dump()
        )
    tariffs = []
    for tariff in raw.get("Tariffs") or []:
        tariffs.append(
            {
                "id": fingerprint(tariff),
                "name": tariff["Name"],
                "from": tariff["From"],
                "to": tariff["ToExclusive"],
                "commodity": tariff["CommodityCzkPerMwh"],
                "other": tariff["OtherCzkPerMwh"],
                "fixed": tariff["FixedCzkPerMonth"],
                "includes_vat": tariff["PricesIncludeVat"],
                "vat_percent": tariff["VatRatePercent"],
                "all_components_known": tariff["AllComponentsKnown"],
                "prorate_fixed": tariff["ProrateFixedByCalendarDays"],
                "role": tariff["Role"].lower(),
                "evidence": sha,
            }
        )
    events = []
    for payment in raw.get("Payments") or []:
        # Legacy v1 nemá transakční ID: zachováváme každou pozici. Automatické
        # sloučení s ruční/bankovní platbou bez potvrzení není bezpečné.
        events.append(
            {
                "id": fingerprint([sha, "payment", len(events)]),
                "place": expected_place,
                "amount": payment["AmountCzk"],
                "date": payment["PaidOn"],
                "from": payment["PeriodFrom"],
                "to": payment["PeriodToExclusive"],
                "role": "payment" if payment["IsPaid"] else "prescribed",
                "verification": "unmatched" if payment["IsPaid"] else "source_document",
                "source": payment["Source"],
                "evidence": sha,
            }
        )
    snapshots = [
        {"retrieved_at": s["RetrievedAt"], "periods": s["Periods"], "source": "mnd"}
        for s in raw.get("ConsumptionSnapshots") or []
    ]
    return {
        "place": expected_place,
        "id": sha,
        "raw": raw,
        "readings": readings,
        "tariffs": tariffs,
        "events": events,
        "snapshots": snapshots,
    }


def export_csv(rows: list[dict], columns: list[str]) -> bytes:
    """CSV cs-CZ, středník, UTF-8 BOM; text neotevře vzorec v Excelu.

    Čísla mají čárku; datum ISO. Ochrana se týká textů, ne znaménka
    legitimních desetinných čísel. Jednotky mají být součástí názvů sloupců.
    """
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(columns)
    for row in rows:
        values = []
        for key in columns:
            value = row.get(key)
            if isinstance(value, Decimal):
                text = str(value).replace(".", ",")
            else:
                text = "" if value is None else str(value)
                if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                    text = "'" + text
            values.append(text)
        writer.writerow(values)
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
