"""Přesná mapování polí doložených ve veřejném klientovi MND.

Původní odpovědi zůstávají v neveřejném archivu, ne v diagnostice. Chybějící
pole se nedoplňují heuristikou; neznámé schéma zabrání chybné identifikaci.
"""

from .common import DataError, day, decimal, identity
from .metering import document_reading


def supply_point(row: dict, partner_id) -> dict:
    """Veřejné UI používá CPE_EAN jako EIC/EAN, CP_ID a CONT_ID pro dotazy."""
    required = ("CPE_EAN", "CP_ID", "CONT_ID", "CP_NAME")
    if not isinstance(row, dict) or any(key not in row for key in required):
        raise DataError("portal_schema_changed")
    return {
        "id": identity(row["CPE_EAN"]),
        "name": str(row["CP_NAME"]),
        "cp_id": row["CP_ID"],
        "contract_id": row["CONT_ID"],
        "partner_id": partner_id,
        "customer_id": row.get("CUSTA_ID"),
    }


def technical_details(raw: dict) -> dict:
    """Whitelist veřejného getteru supplyPointsCardData, bez adresních heuristik.

    Vrací údaje pouze do chráněného panelu. Prázdný objekt není doplněn
    odhadovaným distributorem, měřidlem ani roční spotřebou.
    """
    if not isinstance(raw, dict):
        raise DataError("portal_schema_changed")

    def nested(key, field):
        item = raw.get(key)
        return item.get(field) if isinstance(item, dict) else None

    return {
        "name": raw.get("CP_NAME"),
        "identity": raw.get("CPE_EAN"),
        "customer_account": raw.get("CUSTA_ACCOUNTNO"),
        "contract": raw.get("CONT_CONTRACTNO"),
        "commodity": nested("CP_TYPE", "name"),
        "distributor": nested("Distributor", "PARTNER_FULLNAME"),
        "meter": nested("Device", "DEV_NUMBER"),
        "measurement": nested("METERING_TYPE", "name"),
        "annual_mwh": decimal(raw.get("CPE_CONS_AVE_YEAR"), optional=True, nonnegative=True),
    }


def portal_readings(rows, place, evidence):
    """DAT, M3G, DEV_NUM, CRMT_NAME a STATUS_NAME jsou pole veřejného UI."""
    if not isinstance(rows, list):
        raise DataError("portal_schema_changed")
    result = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or any(
            k not in row for k in ("DAT", "M3G", "DEV_NUM", "CRMT_NAME", "STATUS_NAME")
        ):
            raise DataError("portal_schema_changed")
        fields = {
            "SupplyPointId": place,
            "Date": str(row["DAT"])[:10],
            "MeterStateM3": row["M3G"],
            "MeterNumber": str(row["DEV_NUM"]),
            "Method": row["CRMT_NAME"],
            "Status": row["STATUS_NAME"].get("name", "")
            if isinstance(row["STATUS_NAME"], dict)
            else row["STATUS_NAME"],
            "SourceFile": evidence,
            "SourceRow": index,
        }
        result.append(document_reading(fields, evidence).dump())
    return result


def consumption_periods(rows: list[dict]) -> list[dict]:
    """TYPE R/U/E jsou odečty / minulý odhad / budoucí odhad.

    CONS_VT a CONS_NT jsou kWh podle převodu /1000 ve veřejném chartLabelData.
    Chybějící díl zůstává None; neznámé druhy nejsou automaticky skutečnost.
    Překrývající se období zůstávají samostatná a nepřičítají se k sobě.
    """
    if not isinstance(rows, list):
        raise DataError("portal_schema_changed")
    periods = {}
    fields = {"R": "ReadingsMwh", "U": "PastEstimateMwh", "E": "FutureEstimateMwh"}
    flags = {"R": "HasReadings", "U": "HasPastEstimate", "E": "HasFutureEstimate"}
    for row in rows:
        if not isinstance(row, dict) or any(k not in row for k in ("DATE_FROM", "DATE_TO", "TYPE")):
            raise DataError("portal_schema_changed")
        left, right = str(row["DATE_FROM"])[:10], str(row["DATE_TO"])[:10]
        day(left), day(right)
        key = (left, right)
        item = periods.setdefault(
            key,
            {
                "From": left,
                "To": right,
                "PortalTotalMwh": None,
                "ReadingsMwh": None,
                "PastEstimateMwh": None,
                "FutureEstimateMwh": None,
                "HasReadings": False,
                "HasPastEstimate": False,
                "HasFutureEstimate": False,
                "OriginalLabel": f"{left}–{right}",
                "Quality": "public_client_mapping_unverified_live",
            },
        )
        kind = row["TYPE"]
        if kind not in fields:
            raise DataError("portal_unknown_consumption_type")
        if item[flags[kind]]:
            raise DataError("portal_duplicate_consumption_type")
        item[flags[kind]] = True
        nt, vt = (
            decimal(row.get("CONS_NT"), optional=True, nonnegative=True),
            decimal(row.get("CONS_VT"), optional=True, nonnegative=True),
        )
        item[fields[kind]] = (nt + vt) / 1000 if nt is not None and vt is not None else None
    for item in periods.values():
        present = [item[fields[k]] for k in fields if item[flags[k]]]
        if present and all(v is not None for v in present):
            item["PortalTotalMwh"] = sum(present)
    return sorted(periods.values(), key=lambda item: item["From"])
