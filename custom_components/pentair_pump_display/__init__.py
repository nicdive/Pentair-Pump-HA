"""Lovelace LCD card only — no RS485, no pump hardware."""

from .const import DOMAIN
from .frontend import async_register_frontend


async def async_setup(hass, config):
    return True


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = True
    await async_register_frontend(hass)
    return True


async def async_unload_entry(hass, entry):
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True
