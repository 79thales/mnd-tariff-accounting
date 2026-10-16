"""Verzovaná soukromá záloha místa a volitelných originálů.

ZIP se nerozbaluje do uživatelské cesty. Hash ověřuje integritu, nikoli
pravost dodavatele. Přístupy a relace nejsou součástí zálohy.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile

from .archive import SECTIONS, empty_archive, merge_records, validate_archive
from .common import MAX_BYTES, DataError, canonical, fingerprint, load_json, wire
from .forecast import add_snapshot

FORMAT = "mnd-ha-place"


def backup_document(account: str, place_id: str, place: dict) -> dict:
    """JSON má metadata originálů; samotné soubory přidá explicitní ZIP export."""
    payload = {"account": account, "place_id": place_id, "place": wire(place)}
    return {
        "format": FORMAT,
        "schema_version": 1,
        "payload": payload,
        "sha256": fingerprint(payload),
    }


def parse_native(content: bytes, expected_place: str) -> dict:
    raw = load_json(content)
    if not isinstance(raw, dict) or raw.get("format") != FORMAT or raw.get("schema_version") != 1:
        raise DataError("unsupported_backup_version")
    payload = raw.get("payload")
    if not isinstance(payload, dict) or fingerprint(payload) != raw.get("sha256"):
        raise DataError("backup_checksum_mismatch")
    if payload.get("place_id") != expected_place or not isinstance(payload.get("account"), str):
        raise DataError("supply_point_mismatch")
    candidate = empty_archive(payload["account"])
    candidate["places"][expected_place] = payload["place"]
    validate_archive(candidate, payload["account"])
    return {
        "place": expected_place,
        "native": payload["place"],
        "id": raw["sha256"],
        "readings": [],
        "warnings": ["document_content_requires_zip_backup"],
        "documents": {},
    }


def make_zip(document: dict, documents: dict[str, bytes]) -> bytes:
    """Obsah jen z výslovného výběru; každý originál odpovídá metadatům místa."""
    allowed = {a["id"] for a in document["payload"]["place"]["artifacts"]}
    if set(documents) - allowed:
        raise DataError("backup_artifact_mismatch")
    if sum(len(c) for c in documents.values()) + len(canonical(document)) > MAX_BYTES:
        raise DataError("backup_too_large")
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("archive.json", canonical(document))
        for sha, content in sorted(documents.items()):
            if not re.fullmatch(r"[a-f0-9]{64}", sha) or hashlib.sha256(content).hexdigest() != sha:
                raise DataError("artifact_corrupt")
            archive.writestr("documents/" + sha, content)
    return output.getvalue()


def parse_zip(content: bytes, expected_place: str) -> dict:
    if len(content) > MAX_BYTES:
        raise DataError("backup_too_large")
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
                    or not (
                        i.filename == "archive.json"
                        or re.fullmatch(r"documents/[a-f0-9]{64}", i.filename)
                    )
                    for i in infos
                )
            ):
                raise DataError("unsafe_backup_zip")
            parsed = parse_native(archive.read("archive.json"), expected_place)
            allowed = {a["id"] for a in parsed["native"]["artifacts"]}
            for name in names:
                if name == "archive.json":
                    continue
                sha = name.removeprefix("documents/")
                value = archive.read(name)
                if sha not in allowed or hashlib.sha256(value).hexdigest() != sha:
                    raise DataError("backup_artifact_mismatch")
                parsed["documents"][sha] = value
            parsed["warnings"] = (
                [] if allowed == set(parsed["documents"]) else ["some_document_content_missing"]
            )
            return parsed
    except (zipfile.BadZipFile, KeyError, RuntimeError) as err:
        raise DataError("invalid_backup_zip") from err


def restore_place(data: dict, parsed: dict):
    """Slučuje neměnné revize; starší záloha nesmaže místní změny.

    Při odlišném nastavení je nutný nový profil. Různý obsah téhož ID
    odmítne celou transakci; opakovaná obnova je idempotentní.
    """
    target = data["places"][parsed["place"]]
    restored = parsed["native"]
    if target["settings"] and target["settings"] != restored["settings"]:
        raise DataError("restore_settings_conflict")
    for section in SECTIONS:
        if section == "snapshots":
            for snapshot in restored[section]:
                target[section] = add_snapshot(target[section], snapshot)
        elif section == "samples":
            target[section] = list(
                {fingerprint(s): s for s in target[section] + restored[section]}.values()
            )
        else:
            target[section], _ = merge_records(target[section], restored[section])
    target["settings"] = restored["settings"]
    target["coverage"] = restored.get("coverage")
    target["name"] = restored.get("name", target["name"])
    for section in (
        "daily_profile",
        "local_forecasts",
        "comparisons",
        "portal_evidence",
        "invoice_evidence",
        "price_evidence",
        "billing_documents_context",
        "last_successful_import",
    ):
        if section in restored:
            target[section] = restored[section]
    return {"restored": True}
