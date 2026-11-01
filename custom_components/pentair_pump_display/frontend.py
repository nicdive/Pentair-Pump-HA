"""Serve the IntelliFlo Lovelace card (no serial / pump code)."""

from __future__ import annotations

import logging
from pathlib import Path

from .const import CARD_FILE, DOMAIN

_LOGGER = logging.getLogger(__name__)

_URL = f"/{DOMAIN}/{CARD_FILE}"
_REGISTERED = False


async def async_register_frontend(hass) -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    www = Path(__file__).parent / "www"
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/{DOMAIN}", str(www), False)]
        )
    except (AttributeError, ImportError, ValueError) as err:
        _LOGGER.debug("Static path register fallback: %s", err)
        if hasattr(hass.http, "register_static_path"):
            hass.http.register_static_path(f"/{DOMAIN}", str(www), False)

    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, _URL)
    except (ImportError, AttributeError) as err:
        _LOGGER.debug("add_extra_js_url unavailable: %s", err)
        await _async_add_lovelace_resource(hass, _URL)

    _REGISTERED = True
    _LOGGER.info("Pentair Lovelace card available at %s", _URL)


async def _async_add_lovelace_resource(hass, url: str) -> None:
    lovelace = hass.data.get("lovelace")
    resources = getattr(lovelace, "resources", None) if lovelace else None
    if resources is None:
        return
    try:
        if hasattr(resources, "async_load"):
            await resources.async_load()
        for item in resources.async_items():
            if item.get("url", "").startswith(f"/{DOMAIN}/"):
                return
        if getattr(resources, "mode", "storage") == "yaml":
            _LOGGER.info("Lovelace YAML: add %s as a module resource", url)
            return
        await resources.async_create_item({"res_type": "module", "url": url})
    except Exception as err:  # noqa: BLE001 — resource API varies by HA version
        _LOGGER.debug("Could not auto-add Lovelace resource: %s", err)
