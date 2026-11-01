"""Remove leftover pump devices/entities after a reconfigure.

0.5.2 identified devices as (domain, \"1\"). 0.6.2+ uses
(domain, \"{entry_id}_1\"). A rename/reconfigure then leaves the old
Pool Pump device on the config entry forever unless we drop anything
that is not a current-format keep identifier.
"""

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


def current_keep_device_identifiers(
    entry_id: str, keep_indexes: set[int]
) -> set[tuple[str, str]]:
    """Identifiers for the hub and pumps that must stay."""
    keep = {(DOMAIN, f"{entry_id}_bus")}
    keep |= {(DOMAIN, f"{entry_id}_{index}") for index in keep_indexes}
    return keep


def unique_id_pump_index(entry_id: str, unique_id: str) -> int | None:
    """Return the pump index encoded in a current-format unique_id."""
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
    """Return the pump index for a current-format pump device."""
    prefix = f"{entry_id}_"
    for domain, ident in identifiers:
        if domain != DOMAIN or not ident.startswith(prefix):
            continue
        rest = ident[len(prefix) :]
        if rest.isdigit():
            return int(rest)
    return None


def is_kept_entity(entry_id: str, unique_id: str, keep_indexes: set[int]) -> bool:
    if unique_id == f"{entry_id}_bus_online":
        return True
    index = unique_id_pump_index(entry_id, unique_id)
    return index is not None and index in keep_indexes


def should_remove_entity(
    entry_id: str, unique_id: str, keep_indexes: set[int]
) -> bool:
    """Drop leftover entities, including 0.5.2 unique_ids (domain_index_key)."""
    if not unique_id:
        return True
    return not is_kept_entity(entry_id, unique_id, keep_indexes)


def should_remove_device(
    entry_id: str,
    identifiers: set[tuple[str, str]],
    keep_indexes: set[int],
) -> bool:
    """Drop any device on this entry that is not the current hub/pump."""
    keep = current_keep_device_identifiers(entry_id, keep_indexes)
    relevant = {item for item in identifiers if item[0] == DOMAIN}
    if not relevant:
        return True
    return relevant.isdisjoint(keep)


def async_remove_orphan_pumps(
    hass: Any, entry: Any, keep_indexes: set[int]
) -> int:
    """Drop registry rows for pumps no longer in the config entry."""
    from homeassistant.helpers import device_registry as dr
    from homeassistant.helpers import entity_registry as er

    removed = 0
    dev_reg = dr.async_get(hass)
    remove_device_ids: set[str] = set()
    for device in list(dr.async_entries_for_config_entry(dev_reg, entry.entry_id)):
        if should_remove_device(
            entry.entry_id, set(device.identifiers), keep_indexes
        ):
            remove_device_ids.add(device.id)

    ent_reg = er.async_get(hass)
    for entity in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        if entity.device_id in remove_device_ids or should_remove_entity(
            entry.entry_id, entity.unique_id or "", keep_indexes
        ):
            ent_reg.async_remove(entity.entity_id)
            removed += 1

    for device_id in remove_device_ids:
        dev_reg.async_remove_device(device_id)
        removed += 1
    return removed
