"""Nativní integrace MND: setup, unload a zachování účetního archivu.

Doménové jádro lze importovat bez HA. HA závislosti se načtou až při setupu.
Odebrání konfigurace neodstraní finanční Store ani soukromé doklady.
"""

from .const import PLATFORMS


async def async_setup_entry(hass, entry):
    """Načte archiv a zdroje; zápisy a posluchače ukončíme před unloadem.

    Inicializace nepřidává nic do Energy a nemění existující Overview.
    Poškozený archiv zastaví setup, nepublikuje prázdné potvrzené hodnoty.
    """
    from .api import async_setup_api
    from .coordinator import MndCoordinator
    from .services import async_setup_services

    coordinator = MndCoordinator(hass, entry)
    try:
        await coordinator.async_initialize()
        entry.runtime_data = coordinator
        await async_setup_api(hass)
        await async_setup_services(hass)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.async_close()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass, entry):
    """Reload zachová archiv; žádné smazání odečtů při změně zdroje či jména."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Zastaví práci před odpojením entit; rozpracovaný zápis se dokončí atomicky."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_close()
    return unloaded


async def async_remove_entry(hass, entry):
    """Historie zůstává v neveřejném úložišti pro explicitní export/obnovu."""


async def async_migrate_entry(hass, entry):
    """První schéma konfigurace; budoucí neznámou verzi nelze tiše degradovat."""
    return entry.version == 1
