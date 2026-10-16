"""Neveřejné originály a Store s propagací diskové chyby.

Doklady nikdy nejsou v /local ani ve statických cestách. Interní název je
hash, původní název zůstává metadatem. Soubory se neotvírají podle cesty
obsažené v importu; všechna I/O běží mimo event loop.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError
from homeassistant.util.json import SerializationError

from .core.common import MAX_BYTES, DataError


class ConfirmedStore(Store):
    """HA Store v privátním režimu; chyba zapisovače musí dojít až do formuláře."""

    async def async_save(self, data):
        """Potvrdí až skutečný zápis, také během zastavování Home Assistantu.

        Základní Store při stopping pouze naplánuje závěrečný zápis. Účetní
        transakce však musí znát výsledek už před zveřejněním nové revize.
        Stejný interní zapisovač zachová zámek, atomický soubor i úklid listeneru.
        """
        if self._read_only:
            raise HomeAssistantError("mnd_archive_read_only")
        await super().async_save(data)
        if self._data is not None:
            await self._async_handle_write_data()

    async def _async_write_data(self, data):
        # Standardní Store některé diskové chyby pouze zaloguje. Změna typu
        # zabrání tomu, aby UI potvrdilo commit, který zapisovač odmítl.
        try:
            await super()._async_write_data(data)
        except (WriteError, SerializationError) as err:
            raise HomeAssistantError("mnd_archive_write_failed") from err


def put_artifact(root: Path, content: bytes) -> str:
    """Atomický obsahový soubor; opakovaný upload ověří obsah místo přepsání.

    Pád mezi zápisem originálu a účetní transakcí může zanechat neodkazovaný
    soubor, ale nikoli odkaz na neexistující doklad či částečný originál.
    """
    if len(content) > MAX_BYTES:
        raise DataError("file_too_large")
    sha = hashlib.sha256(content).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    target = root / sha
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            raise DataError("artifact_corrupt")
        return sha
    descriptor, temporary = tempfile.mkstemp(prefix=".part-", dir=root)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return sha


def get_artifact(root: Path, sha: str) -> bytes:
    if not re.fullmatch(r"[a-f0-9]{64}", sha):
        raise DataError("invalid_artifact_id")
    path = root / sha
    if path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise DataError("invalid_artifact")
    result = path.read_bytes()
    if hashlib.sha256(result).hexdigest() != sha:
        raise DataError("artifact_corrupt")
    return result
