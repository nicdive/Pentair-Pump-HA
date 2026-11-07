"""Serve the Lovelace pump-display card.

HA 2026.8+ no longer reliably injects ``add_extra_js_url`` into dashboards
already loaded (Custom element not found). Register a persistent Lovelace
resource and copy the JS to ``www/community/`` so ``/local/community/`` works
the same way as Marketplace dashboard cards.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_CARD = "pentair-pump-display-card.js"
_CARD_VERSION = "0.8.2"
_STATIC_URL = f"/{DOMAIN}/{_CARD}?v={_CARD_VERSION}"
_LOCAL_URL = f"/local/community/{DOMAIN}/{_CARD}?v={_CARD_VERSION}"
_PATHS_REGISTERED = False


def resource_bases() -> tuple[str, str]:
    return f"/{DOMAIN}/{_CARD}", f"/local/community/{DOMAIN}/{_CARD}"


def pick_resource_update(
    items: list[dict[str, Any]], new_url: str
) -> tuple[Any, bool]:
    """Return (item_id to update or None to create, already_current)."""
    bases = resource_bases()
    for item in items:
        url = str(item.get("url", ""))
        base = url.split("?", 1)[0]
        if base in bases:
            return item.get("id"), url == new_url
    return None, False


async def async_register_frontend(hass) -> None:
    """Serve the card JS and register it as a Lovelace module resource."""
    www = Path(__file__).parent / "www"
    await _async_register_static_path(hass, www)
    try:
        await hass.async_add_executor_job(_copy_card_to_www, hass, www / _CARD)
    except OSError as err:
        _LOGGER.warning("Could not copy Lovelace card to www/community: %s", err)
    await _async_ensure_lovelace_resource(hass, _LOCAL_URL)
    _try_extra_js_url(hass, _LOCAL_URL)
    _try_extra_js_url(hass, _STATIC_URL)
    _LOGGER.info("Pentair Lovelace card available at %s", _LOCAL_URL)


async def _async_register_static_path(hass, www: Path) -> None:
    global _PATHS_REGISTERED
    if _PATHS_REGISTERED or not www.is_dir():
        return
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(f"/{DOMAIN}", str(www), False)]
        )
    except (AttributeError, ImportError, ValueError) as err:
        _LOGGER.debug("Static path register fallback: %s", err)
        if hasattr(hass.http, "register_static_path"):
            try:
                hass.http.register_static_path(f"/{DOMAIN}", str(www), False)
            except ValueError:
                pass
    _PATHS_REGISTERED = True


def _copy_card_to_www(hass, src: Path) -> None:
    if not src.is_file():
        _LOGGER.warning("Lovelace card missing: %s", src)
        return
    dest = Path(hass.config.path("www", "community", DOMAIN, _CARD))
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.read_bytes() == src.read_bytes():
        return
    shutil.copy2(src, dest)
    _LOGGER.info("Copied Lovelace card to %s", dest)


def _try_extra_js_url(hass, url: str) -> None:
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, url)
    except (ImportError, AttributeError, ValueError) as err:
        _LOGGER.debug("add_extra_js_url skipped for %s: %s", url, err)


def _lovelace_resources(hass):
    data = hass.data.get("lovelace")
    if data is None:
        return None
    resources = getattr(data, "resources", None)
    if resources is not None:
        return resources
    if isinstance(data, dict):
        return data.get("resources")
    return None


def _is_yaml_resources(resources) -> bool:
    mode = getattr(resources, "mode", None)
    if mode is None:
        mode = getattr(resources, "_mode", "storage")
    value = getattr(mode, "value", mode)
    return str(value).lower() == "yaml"


async def _async_ensure_lovelace_resource(hass, url: str) -> None:
    resources = _lovelace_resources(hass)
    if resources is None:
        _LOGGER.debug("Lovelace resources not ready yet")
        return
    try:
        if hasattr(resources, "async_load"):
            await resources.async_load()
        items = list(resources.async_items()) if hasattr(resources, "async_items") else []
        item_id, current = pick_resource_update(items, url)
        if current:
            return
        if _is_yaml_resources(resources):
            _LOGGER.warning(
                "Lovelace YAML: ajoutez la ressource module %s "
                "(Paramètres → Tableaux de bord → Ressources)",
                url,
            )
            return
        payload = {"res_type": "module", "url": url}
        if item_id is not None and hasattr(resources, "async_update_item"):
            await resources.async_update_item(item_id, payload)
            _LOGGER.info("Updated Lovelace resource %s", url)
            return
        if hasattr(resources, "async_create_item"):
            await resources.async_create_item(payload)
            _LOGGER.info("Added Lovelace resource %s", url)
    except Exception as err:  # noqa: BLE001 — resource API varies by HA version
        _LOGGER.debug("Could not auto-add Lovelace resource: %s", err)
