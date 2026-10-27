"""Společný zdroj složení hlavního MND view a detailních subviews.

Šablona má pouze placeholdery a syntetické popisy. Entity se berou z registru
entry, nikdy podle osobního názvu vývojáře. Pouhý náhled nic nezapisuje.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlencode

from .core.common import DataError

TEMPLATE = Path(__file__).with_name("dashboard_template.json")


def build_views(title, path, entities, entry_id, place_id):
    """Vrátí účetní přehled MND a pět detailů z jediné přibalené šablony.

    Vzhled vlastní karty sdílí hlavní panel i náhled; entity jsou odkazy na
    skutečný registr, takže přejmenování senzoru nemění účetní identitu.
    JSON je současně platný YAML. Chybějící entity dovolují export, ne zápis.
    Prokliky do editoru nesou explicitní účet a místo v URL s bezpečně
    zakódovanými parametry; otevření odkazu nemění účetní data ani dashboard.
    """
    if (
        not isinstance(title, str)
        or not 1 <= len(title.strip()) <= 120
        or not re.fullmatch(r"[a-z][a-z0-9-]{0,59}", path)
    ):
        raise DataError("invalid_dashboard_path")
    config = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    missing = set()

    def expand(value):
        if isinstance(value, dict):
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v) for v in value]
        if not isinstance(value, str):
            return value
        replacements = {
            "TITLE": title.strip(),
            "PATH": path,
            "ENTRY": entry_id,
            "PLACE": place_id,
            "EDITOR_URL": "/mnd-tariff-accounting?"
            + urlencode({"entry_id": entry_id, "place": place_id, "tab": "editor"}),
        }
        for key, replacement in replacements.items():
            value = value.replace("{{" + key + "}}", replacement)

        def entity(match):
            key = match.group(1)
            if key not in entities:
                missing.add(key)
            return entities.get(key, "sensor.mnd_missing_" + key)

        return re.sub(r"\{\{entity:([a-z0-9_]+)\}\}", entity, value)

    return {
        "config": expand(config),
        "missing_entities": sorted(missing),
        "requirements": [],
        "comments": "Kompozice 7: vlastní odhad je oddělen od dodavatelského výhledu; jeho historii z Recorderu najdete v detailu účetnictví. Vlastní evidence je volitelná a její nápověda patří pouze do editoru; přehled používá podklady MND. Právě teď, spotřeba a stručné vyúčtování; nejvýše jeden sedmidenní graf. Volitelný příkon kotle podle administrace místa; elektřina není součást účtu MND. Spotřeba obsahuje provozní graf a měsíční historii, účetnictví finanční tabulky a graf záloh. Originální faktura má přednost. Nativní horní lišta HA a čtecí detaily; správa z konkrétního zařízení. Aktualizace mění jen vlastní kartu stejného účtu a místa; před zápisem exportovat zálohu Overview.",
    }
