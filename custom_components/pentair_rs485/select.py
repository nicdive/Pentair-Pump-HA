"""Select platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PentairPumpCoordinator
from .entity import PentairPumpEntity
from .rs485.modes import PUMP_MODE_BY_NAME, PUMP_MODE_LABELS
from .rs485.packets import CommandProfile


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PentairPumpCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    entities: list[SelectEntity] = []
    for pump in coordinator.hub.pumps:
        entities.append(PentairCommandProfileSelect(coordinator, pump.index))
        entities.append(PentairPumpModeSelect(coordinator, pump.index))
    async_add_entities(entities)


class PentairCommandProfileSelect(PentairPumpEntity, SelectEntity):
    """Switch RS485 command set between RPM and GPM (critical for VSF)."""

    _attr_translation_key = "command_profile"
    _attr_icon = "mdi:swap-horizontal"

    def __init__(self, coordinator: PentairPumpCoordinator, pump_index: int) -> None:
        super().__init__(coordinator, pump_index)
        self._attr_options = ["rpm", "gpm"]

    @property
    def current_option(self) -> str | None:
        return self.pump_data.get("command_profile")

    async def async_select_option(self, option: str) -> None:
        profile = CommandProfile(option)
        self.coordinator.hub.set_command_profile(self.pump_index, profile)
        if profile == CommandProfile.GPM:
            await self.coordinator.hub.async_send_manual_mode(self.pump_index)
        else:
            await self.coordinator.hub.async_send_speed1_mode(self.pump_index)
        await self.coordinator.async_request_refresh()


class PentairPumpModeSelect(PentairPumpEntity, SelectEntity):
    """Set pump operating mode (wiki action 5)."""

    _attr_translation_key = "pump_mode"
    _attr_icon = "mdi:state-machine"

    def __init__(self, coordinator: PentairPumpCoordinator, pump_index: int) -> None:
        super().__init__(coordinator, pump_index)
        # Exclude placeholder unknown_* modes from the user-facing selector.
        self._attr_options = [
            key
            for key in PUMP_MODE_LABELS
            if not key.startswith("unknown_")
        ]

    @property
    def current_option(self) -> str | None:
        target = self.pump_data.get("target_mode_label")
        if target in self._attr_options:
            return target
        label = self.pump_data.get("mode_label")
        if label in self._attr_options:
            return label
        return "filter"

    async def async_select_option(self, option: str) -> None:
        mode_id = PUMP_MODE_BY_NAME[option]
        await self.coordinator.hub.async_set_pump_mode(self.pump_index, mode_id)
        await self.coordinator.async_request_refresh()
