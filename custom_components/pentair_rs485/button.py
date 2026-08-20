"""Button platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PentairPumpCoordinator
from .entity import PentairPumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PentairPumpCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    entry_id = entry.entry_id
    entities: list[ButtonEntity] = []
    for pump in coordinator.hub.pumps:
        idx = pump.index
        entities.extend(
            [
                PentairManualFlowButton(coordinator, idx, entry_id),
                PentairManualRpmButton(coordinator, idx, entry_id),
                PentairFilterModeButton(coordinator, idx, entry_id),
                PentairRunProgramButton(coordinator, idx, 1, entry_id),
                PentairRunProgramButton(coordinator, idx, 2, entry_id),
                PentairRunProgramButton(coordinator, idx, 3, entry_id),
                PentairRunProgramButton(coordinator, idx, 4, entry_id),
                PentairStopProgramButton(coordinator, idx, entry_id),
                PentairSaveProgramButton(coordinator, idx, 1, entry_id),
                PentairSaveProgramButton(coordinator, idx, 2, entry_id),
                PentairSaveProgramButton(coordinator, idx, 3, entry_id),
                PentairSaveProgramButton(coordinator, idx, 4, entry_id),
            ]
        )
    async_add_entities(entities)


class PentairManualFlowButton(PentairPumpEntity, ButtonEntity):
    _attr_translation_key = "manual_flow"
    _attr_icon = "mdi:water-pump"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_send_manual_mode(self.pump_index)
        await self.coordinator.async_request_refresh()


class PentairManualRpmButton(PentairPumpEntity, ButtonEntity):
    _attr_translation_key = "manual_rpm"
    _attr_icon = "mdi:speedometer"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_send_speed1_mode(self.pump_index)
        await self.coordinator.async_request_refresh()


class PentairFilterModeButton(PentairPumpEntity, ButtonEntity):
    _attr_translation_key = "filter_mode"
    _attr_icon = "mdi:filter"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        await self.coordinator.hub.async_set_pump_mode(self.pump_index, 0)
        await self.coordinator.async_request_refresh()


class PentairRunProgramButton(PentairPumpEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        program: int,
        entry_id: str,
    ) -> None:
        self._program = program
        self._attr_translation_key = f"run_program_{program}"
        super().__init__(coordinator, pump_index, entry_id)

    async def async_press(self) -> None:
        await self.coordinator.hub.async_run_program(self.pump_index, self._program)
        await self.coordinator.async_request_refresh()


class PentairStopProgramButton(PentairPumpEntity, ButtonEntity):
    _attr_translation_key = "stop_program"
    _attr_icon = "mdi:stop"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_run_program(self.pump_index, 0)
        await self.coordinator.async_request_refresh()


class PentairSaveProgramButton(PentairPumpEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:content-save"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        program: int,
        entry_id: str,
    ) -> None:
        self._program = program
        self._attr_translation_key = f"save_program_{program}"
        super().__init__(coordinator, pump_index, entry_id)

    async def async_press(self) -> None:
        speed = self.coordinator.hub.get_live_speed_for_save(self.pump_index)
        if speed is None:
            return
        await self.coordinator.hub.async_save_program(
            self.pump_index, self._program, speed
        )
        await self.coordinator.async_request_refresh()
