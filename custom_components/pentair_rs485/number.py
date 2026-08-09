"""Number platform for Pentair RS485 pump speed control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_GPM, MAX_RPM, MIN_GPM, MIN_RPM
from .coordinator import PentairPumpCoordinator
from .entity import PentairPumpEntity
from .rs485.packets import CommandProfile


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PentairPumpCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    entities: list[NumberEntity] = []
    for pump in coordinator.hub.pumps:
        entities.append(PentairPumpRpmNumber(coordinator, pump.index))
        entities.append(PentairPumpGpmNumber(coordinator, pump.index))
        for program in range(1, 5):
            entities.append(
                PentairProgramSpeedNumber(coordinator, pump.index, program)
            )
    async_add_entities(entities)


class PentairPumpRpmNumber(PentairPumpEntity, NumberEntity):
    """Set RPM — sends Manuel RPM mode then VS RPM packet."""

    _attr_translation_key = "rpm"
    _attr_native_min_value = MIN_RPM
    _attr_native_max_value = MAX_RPM
    _attr_native_step = 50
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = "rpm"
    _attr_icon = "mdi:speedometer"

    @property
    def native_value(self) -> float | None:
        target = self.coordinator.hub.get_target_rpm(self.pump_index)
        if target is not None:
            return float(target)
        rpm = self.pump_data.get("rpm", 0)
        return float(rpm) if rpm else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.hub.async_run_rpm(self.pump_index, int(value))
        await self.coordinator.async_request_refresh()


class PentairPumpGpmNumber(PentairPumpEntity, NumberEntity):
    """Set GPM — sends Manuel débit mode then VF GPM packet."""

    _attr_translation_key = "gpm"
    _attr_native_min_value = MIN_GPM
    _attr_native_max_value = MAX_GPM
    _attr_native_step = 1
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = "gpm"
    _attr_icon = "mdi:water-pump"

    @property
    def native_value(self) -> float | None:
        target = self.coordinator.hub.get_target_gpm(self.pump_index)
        if target is not None:
            return float(target)
        gpm = self.pump_data.get("gpm", 0)
        return float(gpm) if gpm else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.hub.async_run_gpm(self.pump_index, int(value))
        await self.coordinator.async_request_refresh()


class PentairProgramSpeedNumber(PentairPumpEntity, NumberEntity):
    """Save a RPM/GPM speed into pump program slot 1-4 (wiki action save program)."""

    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:content-save"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        program: int,
    ) -> None:
        self._program = program
        self._attr_translation_key = f"program_{program}_speed"
        super().__init__(coordinator, pump_index)

    @property
    def _uses_gpm(self) -> bool:
        return (
            self.coordinator.hub.get_command_profile(self.pump_index)
            == CommandProfile.GPM
        )

    @property
    def native_min_value(self) -> float:
        return float(MIN_GPM if self._uses_gpm else MIN_RPM)

    @property
    def native_max_value(self) -> float:
        return float(MAX_GPM if self._uses_gpm else MAX_RPM)

    @property
    def native_step(self) -> float:
        return 1.0 if self._uses_gpm else 50.0

    @property
    def native_unit_of_measurement(self) -> str:
        return "gpm" if self._uses_gpm else "rpm"

    @property
    def native_value(self) -> float | None:
        speed = self.pump_data.get(f"program_{self._program}_speed")
        return float(speed) if speed is not None else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.hub.async_save_program(
            self.pump_index, self._program, int(value)
        )
        await self.coordinator.async_request_refresh()
