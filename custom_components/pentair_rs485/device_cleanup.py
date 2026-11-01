"""Remove leftover pump devices/entities after a reconfigure."""

from __future__ import annotations

from typing import Any

from .const import CONF_PUMP_INDEX, DOMAIN


def filter_kept_pumps(pumps: list[dict], keep: Any) -> list[dict]:
    """Keep only pumps whose index is in the reconfigure multi-select."""
    if keep is None:
        return list(pumps)
    if isinstance(keep, (str, int)):
        keep = [keep]
    keep_ids = {int(x) for x in keep}
    return [p for p in pumps if int(p[CONF_PUMP_INDEX]) in keep_ids]


def unique_id_pump_index(entry_id: str, unique_id: str) -> int | None:
    """Return the pump index encoded in an entity unique_id, or None."""
    prefix = f"{entry_id}_"
    if not unique_id.startswith(prefix):
        return None
    head = unique_id[len(prefix) :].split("_", 1)[0]
    if head.isdigit():
        return int(head)
    return None


def device_pump_index(
    entry_id: str, identifiers: set[tuple[str, str]]
) -> int | None:
    """Return the pump index for a pump device, or None for the hub."""
    prefix = f"{entry_id}_"
    for domain, ident in identifiers:
        if domain != DOMAIN or not ident.startswith(prefix):
            continue
        rest = ident[len(prefix) :]
        if rest.isdigit():
            return int(rest)
    return None


def should_remove_entity(
    entry_id: str, unique_id: str, keep_indexes: set[int]
) -> bool:
    index = unique_id_pump_index(entry_id, unique_id)
    return index is not None and index not in keep_indexes


def should_remove_device(
    entry_id: str,
    identifiers: set[tuple[str, str]],
    keep_indexes: set[int],
) -> bool:
    index = device_pump_index(entry_id, identifiers)
    return index is not None and index not in keep_indexes


def async_remove_orphan_pumps(
    hass: Any, entry: Any, keep_indexes: set[int]
) -> int:
    """Drop registry rows for pumps no longer in the config entry."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    removed = 0
    ent_reg = er.async_get(hass)
    for entity in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        if should_remove_entity(
            entry.entry_id, entity.unique_id or "", keep_indexes
        ):
            ent_reg.async_remove(entity.entity_id)
            removed += 1

    dev_reg = dr.async_get(hass)
    for device in list(dr.async_entries_for_config_entry(dev_reg, entry.entry_id)):
        if should_remove_device(
            entry.entry_id, set(device.identifiers), keep_indexes
        ):
            dev_reg.async_remove_device(device.id)
            removed += 1
    return removed
