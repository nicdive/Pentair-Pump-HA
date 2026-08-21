"""Diagnostics dump for Pentair RS485 config entries."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not stored:
        return {"error": "not_loaded"}

    hub = stored["hub"]
    cover_boost = stored.get("cover_boost")
    pumps: list[dict[str, Any]] = []
    for pump in hub.pumps:
        data = hub.status_dict(pump.index, pump)
        pumps.append(
            {
                "index": pump.index,
                "name": pump.name,
                "type": pump.pump_type.value,
                "online": hub.is_pump_online(pump.index),
                "desired_run": hub.should_run(pump.index),
                "hands_off": hub.is_hands_off(pump.index),
                "display_active": hub.is_display_active(pump.index),
                "command_profile": hub.get_command_profile(pump.index).value,
                "target_rpm": hub.get_target_rpm(pump.index),
                "target_gpm": hub.get_target_gpm(pump.index),
                "target_mode": hub.get_target_mode(pump.index),
                "boost_enabled": (
                    cover_boost.is_enabled(pump.index) if cover_boost else None
                ),
                "boost_active": (
                    cover_boost.is_boost_active(pump.index) if cover_boost else None
                ),
                "live": {
                    "power": data.get("power"),
                    "rpm": data.get("rpm"),
                    "gpm": data.get("gpm"),
                    "watts": data.get("watts"),
                    "mode": data.get("mode_label"),
                    "err": data.get("err_label"),
                },
            }
        )

    return {
        "entry": {
            "port": entry.data.get("port"),
            "app_address": entry.data.get("app_address"),
            "options": dict(entry.options or {}),
        },
        "bus": {
            "open": hub.bus.is_open,
            "last_error": hub.bus.last_error,
        },
        "pumps": pumps,
    }
