"""Button platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    entities: list[ButtonEntity] = []
    for pump in coordinator.hub.pumps:
        entities.extend(
            [
                PentairManualFlowButton(coordinator, pump.index),
                PentairManualRpmButton(coordinator, pump.index),
                PentairFilterModeButton(coordinator, pump.index),
                PentairReleaseRemoteButton(coordinator, pump.index),
                PentairRunProgramButton(coordinator, pump.index, 1),
                PentairRunProgramButton(coordinator, pump.index, 2),
                PentairRunProgramButton(coordinator, pump.index, 3),
                PentairRunProgramButton(coordinator, pump.index, 4),
                PentairStopProgramButton(coordinator, pump.index),
                PentairSaveProgramButton(coordinator, pump.index, 1),
                PentairSaveProgramButton(coordinator, pump.index, 2),
                PentairSaveProgramButton(coordinator, pump.index, 3),
                PentairSaveProgramButton(coordinator, pump.index, 4),
            ]
        )
    async_add_entities(entities)


class PentairManualFlowButton(PentairPumpEntity, ButtonEntity):
    """Action 5 mode 1 — manual flow (GPM) on VF WhisperFlo."""

    _attr_translation_key = "manual_flow"
    _attr_icon = "mdi:water-pump"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_send_manual_mode(self.pump_index)
        await self.coordinator.async_request_refresh()


class PentairManualRpmButton(PentairPumpEntity, ButtonEntity):
    """Action 5 mode 2 — manual RPM (packet [5,1,2])."""

    _attr_translation_key = "manual_rpm"
    _attr_icon = "mdi:speedometer"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_send_speed1_mode(self.pump_index)
        await self.coordinator.async_request_refresh()


class PentairFilterModeButton(PentairPumpEntity, ButtonEntity):
    _attr_translation_key = "filter_mode"
    _attr_icon = "mdi:filter"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_set_pump_mode(self.pump_index, 0)
        await self.coordinator.async_request_refresh()


class PentairReleaseRemoteButton(PentairPumpEntity, ButtonEntity):
    _attr_translation_key = "release_remote"
    _attr_icon = "mdi:gesture-tap-button"

    async def async_press(self) -> None:
        await self.coordinator.hub.async_release_to_pump(self.pump_index)
        await self.coordinator.async_request_refresh()


class PentairRunProgramButton(PentairPumpEntity, ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        program: int,
    ) -> None:
        self._program = program
        self._attr_translation_key = f"run_program_{program}"
        super().__init__(coordinator, pump_index)

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
    """Save current pump RPM/GPM reading into a program slot."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:content-save"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        program: int,
    ) -> None:
        self._program = program
        self._attr_translation_key = f"save_program_{program}"
        super().__init__(coordinator, pump_index)

    async def async_press(self) -> None:
        speed = self.coordinator.hub.get_live_speed_for_save(self.pump_index)
        if speed is None:
            return
        await self.coordinator.hub.async_save_program(
            self.pump_index, self._program, speed
        )
        await self.coordinator.async_request_refresh()
