"""Čtecí finanční evidence portálu, oddělená od potvrzené účetní knihy.

Pole jsou doložena veřejnou stránkou payments a jejími detailními dialogy.
Neznámé období či alokace nevytváří účetní událost. Přehled tak může ukázat
pravdivý předpis a jeho úhrady i bez nastaveného místního účetního období.
"""

from .accounting import active_versions
from .common import DataError, day, decimal, fingerprint, period, wire


def _date(value):
    return day(str(value)[:10]).isoformat() if value else None


def _name(value):
    return value.get("name") if isinstance(value, dict) else None


def finance_rows(kind, rows, source):
    """Vrací stabilní čtecí řádky a odmítne smíchaný účet/místo/měnu.

    Dokladové ID je identita, hash obsahu dokládá revizi. SumTotal je
    předpis, Balance zbývající úhrada; skutečné platby jsou pouze PayInfo.
    Neuvedená vazba na místo zůstává doložena filtrovaným požadavkem.
    """
    if kind not in ("advances", "invoices") or not isinstance(rows, list):
        raise DataError("portal_finance_schema_changed")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise DataError("portal_finance_schema_changed")
        for field, target in (("CP_ID", "cp_id"), ("CUSTA_ID", "customer_id")):
            if row.get(field) is not None and source.get(target) is not None:
                if str(row[field]) != str(source[target]):
                    raise DataError("portal_finance_identity_mismatch")
        currency = row.get("CURRENCY")
        if not isinstance(currency, dict) or currency.get("code") != "CZK":
            raise DataError("portal_finance_currency_unsupported")
        advance = kind == "advances"
        key = "ADVI_ID" if advance else "IVA_ID"
        if row.get(key) is None or str(row[key]) in seen:
            raise DataError("portal_finance_duplicate_or_missing_id")
        seen.add(str(row[key]))
        payments = []
        if row.get("PayInfo") is not None and not isinstance(row["PayInfo"], list):
            raise DataError("portal_finance_schema_changed")
        for index, payment in enumerate(row.get("PayInfo") or []):
            # Každá položka představuje skutečně zaúčtovanou částku na
            # tomto dokladu. Identické položky zachováváme, nesléváme platby.
            amount = decimal(payment.get("PAY_AMOUNT"), nonnegative=True)
            at = _date(payment.get("PAY_DATE"))
            if at is None:
                raise DataError("portal_finance_payment_date_missing")
            payments.append({"date": at, "amount": amount, "index": index})
        result.append(
            wire(
                {
                    "id": str(row[key]),
                    "revision": fingerprint(row),
                    "kind": kind,
                    "number": str(row.get("INVOICENO") or row[key]),
                    "date": _date(row.get("ADVI_DATE") if advance else row.get("DATE_ISSUE")),
                    "due": _date(row.get("ADVI_DATE") if advance else row.get("DATE_DUE_DELAY")),
                    "from": _date(row.get("ADVI_DATE_FROM") if advance else row.get("DATEFROM")),
                    "to_inclusive": _date(
                        row.get("ADVI_DATE_TO") if advance else row.get("DATETO")
                    ),
                    "prescribed": decimal(row.get("ADVI_SUMTOTAL"), optional=True)
                    if advance
                    else None,
                    "remaining": decimal(
                        row.get("ADVI_BALANCE" if advance else "BALANCE"), optional=True
                    ),
                    "invoice_result": decimal(row.get("BALANCE_SAVED"), optional=True)
                    if not advance
                    else None,
                    "state": _name(row.get("ADVI_STATE" if advance else "STATE")),
                    "state_code": (row.get("ADVI_STATE" if advance else "STATE") or {}).get("code"),
                    "payments": payments,
                    "paid": sum((decimal(p["amount"]) for p in payments), decimal(0))
                    if isinstance(row.get("PayInfo"), list)
                    else None,
                    "payments_known": isinstance(row.get("PayInfo"), list),
                }
            )
        )
    return sorted(result, key=lambda r: (r["date"] or "", r["id"]), reverse=True)


def merge_finance(previous, current):
    """Aktualizuje doklady bez smazání starších mimo aktuální prefix.

    Revize s časem získání zůstávají v neveřejném auditu. Ruční účetní
    záznamy nejsou součást tohoto čtecího seznamu a nemohou se přepsat.
    """
    records = {r["id"]: r for r in previous}
    records.update({r["id"]: r for r in current})
    return sorted(records.values(), key=lambda r: (r.get("date") or "", r["id"]), reverse=True)


def accept_advances(place_id, place, now):
    """Po potvrzení správce přiřadí doklady splatné ve zvoleném období.

    Alokace je výslovné uživatelské rozhodnutí, ne odhad období z částky.
    Každý předpis a PayInfo položka má vlastní stabilní zdrojový klíč.
    Změna částky vytvoří revizi; opakované potvrzení nic nezdvojí. Ruční
    záznam stejné částky se automaticky nemaže ani nepáruje heuristikou.
    """
    left, right = period(place["settings"].get("period_from"), place["settings"].get("period_to"))
    records = place.get("portal_evidence", {}).get("advances", {}).get("rows", [])
    existing = active_versions(place["events"])
    added = 0
    expected = set()
    detailed = {r["id"] for r in records if r.get("payments_known")}
    for row in records:
        if not row.get("due") or not left <= day(row["due"]) < right:
            continue
        parts = [("prescribed", row["due"], row.get("prescribed"), "prescribed")]
        parts += [
            ("payment", p["date"], p["amount"], f"payment:{p['index']}") for p in row["payments"]
        ]
        for role, date, amount, part in parts:
            if amount is None or (role == "payment" and day(date) > day(now)):
                continue
            key = fingerprint([place_id, row["id"], part, str(left), str(right)])
            expected.add(key)
            old = next((e for e in existing if e.get("source_id") == key), None)
            record = wire(
                {
                    "place": place_id,
                    "role": role,
                    "amount": amount,
                    "date": date,
                    "from": left,
                    "to": right,
                    "source": "mnd_advances",
                    "source_id": key,
                    "source_document": row["id"],
                    "verification": "user_confirmed_allocation",
                }
            )
            if old and all(old.get(k) == v for k, v in record.items()):
                continue
            record["id"] = fingerprint(record)
            # Návrat původního obsahu po opravě je další revize, nikoli cyklus.
            if any(e["id"] == record["id"] for e in place["events"]):
                record["id"] = fingerprint([record, old["id"] if old else None])
            if old:
                record["supersedes"] = old["id"]
            place["events"].append(record)
            added += 1
    # Zmizelá úhrada v nově doloženém detailu je oprava, nikoli historická
    # platba navíc. Vytvoříme nulovou opravnou verzi jen ve stejné alokaci;
    # chybějící detail ani zmizelá stránka seznamu k rušení nestačí.
    for old in existing:
        if (
            old.get("source") == "mnd_advances"
            and old.get("role") == "payment"
            and old.get("source_document") in detailed
            and old.get("source_id") not in expected
            and old.get("from") == str(left)
            and old.get("to") == str(right)
            and decimal(old["amount"]) != 0
        ):
            replacement = {**old, "amount": "0", "supersedes": old["id"]}
            replacement["id"] = fingerprint([old["id"], "withdrawn_by_source"])
            place["events"].append(replacement)
            added += 1
    return added
