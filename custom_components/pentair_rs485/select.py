"""Select platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .coordinator import PentairPumpCoordinator
from .cover_boost import CoverBoostController
from .entity import PentairPumpEntity
from .rs485.modes import PUMP_MODE_BY_NAME, PUMP_MODE_LABELS
from .rs485.packets import CommandProfile


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    stored = hass.data[DOMAIN][entry.entry_id]
    coordinator: PentairPumpCoordinator = stored["coordinator"]
    cover_boost: CoverBoostController = stored["cover_boost"]
    entry_id = entry.entry_id
    entities: list[SelectEntity] = []
    for pump in coordinator.hub.pumps:
        idx = pump.index
        entities.append(PentairCommandProfileSelect(coordinator, idx, entry_id))
        entities.append(PentairPumpModeSelect(coordinator, idx, entry_id))
        entities.append(
            PentairCoverBoostProfileSelect(
                coordinator, cover_boost, idx, entry_id
            )
        )
    async_add_entities(entities)


class PentairCommandProfileSelect(PentairPumpEntity, SelectEntity):
    _attr_translation_key = "command_profile"
    _attr_icon = "mdi:swap-horizontal"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
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
    _attr_translation_key = "pump_mode"
    _attr_icon = "mdi:state-machine"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
        self._attr_options = [
            key for key in PUMP_MODE_LABELS if not key.startswith("unknown_")
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


class PentairCoverBoostProfileSelect(
    PentairPumpEntity, SelectEntity, RestoreEntity
):
    _attr_translation_key = "cover_boost_profile"
    _attr_icon = "mdi:swap-vertical"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        cover_boost: CoverBoostController,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
        self._cover_boost = cover_boost
        self._attr_options = ["rpm", "gpm"]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("rpm", "gpm"):
            self._cover_boost.set_boost_profile(
                self.pump_index, CommandProfile(last.state)
            )

    @property
    def current_option(self) -> str | None:
        return self._cover_boost.get_boost_profile(self.pump_index).value

    @property
    def available(self) -> bool:
        return bool(self._cover_boost.cover_entity_id)

    async def async_select_option(self, option: str) -> None:
        self._cover_boost.set_boost_profile(self.pump_index, CommandProfile(option))
        await self._cover_boost.async_reevaluate_pump(self.pump_index)
        self.async_write_ha_state()
