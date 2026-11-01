"""Registrace modulu karty v úložišti zdrojů Lovelace bez duplicit."""

from urllib.parse import urlsplit


async def ensure_resource(resources, module_url):
    """Vrátí stav registrace pro předanou HA ResourceStorageCollection.

    Volající drží společný setup lock účtů a předem ověří storage režim.
    Nejdříve načteme uložené zdroje veřejnou metodou async_get_info; prázdná
    dosud nenačtená kolekce není důkazem, že registrace chybí. Vlastní zdroj
    poznáme podle přesné lokální cesty, měníme pouze jeho URL a typ. Hash
    obsahu v URL obnoví cache po aktualizaci. Cizí zdroje ani dashboardy
    neměníme, duplicitní vlastní záznamy nemažeme. Chyba API se propaguje
    volajícímu, takže setup neoznačí tuto fázi za úspěšnou a může ji opakovat.
    """
    await resources.async_get_info()
    target = urlsplit(module_url)
    for item in resources.async_items():
        candidate = urlsplit(item.get("url", ""))
        if candidate.scheme or candidate.netloc or candidate.path != target.path:
            continue
        if item["url"] == module_url and item.get("type") == "module":
            return "unchanged"
        await resources.async_update_item(
            item["id"], {"url": module_url, "res_type": "module"}
        )
        return "updated"
    await resources.async_create_item({"url": module_url, "res_type": "module"})
    return "created"
