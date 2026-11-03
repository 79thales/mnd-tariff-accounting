"""Asynchronní načtení konfigurovaného pásma pro volání v event loopu."""

from zoneinfo import ZoneInfoNotFoundError

from homeassistant.util import dt as dt_util


async def async_configured_time_zone(hass):
    """Vrátí pásmo HA; chybějící data vyvolají původní chybu před výpočtem.

    Načtení i cache zajišťuje Home Assistant. None nesmí způsobit přechod
    na pásmo hostitele nebo vytvoření časových hranic bez pásma.
    """
    zone = await dt_util.async_get_time_zone(hass.config.time_zone)
    if zone is None:
        raise ZoneInfoNotFoundError(hass.config.time_zone)
    return zone
