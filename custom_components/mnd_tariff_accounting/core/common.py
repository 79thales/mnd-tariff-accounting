"""Společná validace hranic, desetinných hodnot a bezpečné serializace."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 200_000


class DataError(ValueError):
    """Stabilní důvod chyby pro UI; neobsahuje syrový zákaznický vstup."""


def decimal(value: Any, *, optional: bool = False, nonnegative: bool = False) -> Decimal | None:
    """Přijme českou či invariantní desetinnou hodnotu, odmítne NaN a bool.

    None/prázdný řetězec je dovolen jen pro výslovně volitelné pole. Neprovádí
    převod jednotek ani zaokrouhlení. Limity počtu číslic chrání výpočty i UI.
    """
    if value is None or value == "":
        if optional:
            return None
        raise DataError("missing_number")
    if isinstance(value, (bool, float)):
        # Peněžní import se parsuje přímo do Decimal; float už mohl ztratit přesnost.
        raise DataError("inexact_number")
    try:
        text = re.sub(r"[\s\u00a0\u202f]", "", str(value)).replace(",", ".")
        if len(text) > 80:
            raise DataError("number_too_large")
        result = Decimal(text)
    except InvalidOperation as err:
        raise DataError("invalid_number") from err
    if not result.is_finite() or result.as_tuple().exponent < -24 or abs(result) > Decimal("1e20"):
        raise DataError("invalid_number")
    if nonnegative and result < 0:
        raise DataError("negative_number")
    return result


def money(value: Decimal) -> Decimal:
    """Konečná částka Kč: dvě desetinná místa, přesná polovina od nuly."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def day(value: Any) -> date:
    """Kalendářní datum bez vymyšleného času; datetime není datumový bod."""
    if isinstance(value, datetime):
        raise DataError("date_requires_day")
    try:
        return value if isinstance(value, date) else date.fromisoformat(value)
    except (ValueError, TypeError) as err:
        raise DataError("invalid_date") from err


def instant(value: Any) -> datetime:
    """Skutečný okamžik vyžaduje offset; ukládá se v UTC i přes opakovanou hodinu."""
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
        if result.tzinfo is None or result.utcoffset() is None:
            raise DataError("timezone_required")
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError) as err:
        raise DataError("invalid_instant") from err


def local_day(value: datetime, zone: str) -> date:
    """Datum podle konfigurace HA, nikoli časového pásma vývojového počítače."""
    return instant(value).astimezone(ZoneInfo(zone)).date()


def period(left: Any, right: Any) -> tuple[date, date]:
    """Účetní [od, do); nejvýše 100 let pro omezení kalendářního průchodu."""
    start, end = day(left), day(right)
    if not 0 < (end - start).days <= 36600:
        raise DataError("invalid_period")
    return start, end


def wire(value: Any) -> Any:
    """Bezeztrátový interní JSON: Decimal je řetězec, časy ISO, nula zůstává nula."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(v) for v in value]
    return value


def canonical(value: Any) -> bytes:
    """Deterministická reprezentace pro audit a porovnání revizí bez ztráty přesnosti."""
    return json.dumps(
        wire(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_json(content: bytes | str) -> Any:
    """Omezený JSON bez duplicitních klíčů a nekonečen; čísla přímo jako Decimal."""
    if len(content) > MAX_BYTES:
        raise DataError("file_too_large")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DataError("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise DataError("invalid_number")

    try:
        return json.loads(
            content, parse_float=Decimal, object_pairs_hook=pairs, parse_constant=invalid_constant
        )
    except (ValueError, UnicodeError, RecursionError) as err:
        raise DataError("invalid_json") from err


def identity(value: Any) -> str:
    """EIC/EAN je řetězec, nikdy číslo. Povoluje syntetické i skutečné identity."""
    if not isinstance(value, str) or not re.fullmatch(r"(?:\d{2}[A-Z][A-Z0-9]{13}|\d{18})", value):
        raise DataError("invalid_supply_point")
    return value
