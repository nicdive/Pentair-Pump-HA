"""Number platform for Pentair RS485 pump speed control."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DEFAULT_COVER_BOOST_GPM,
    DEFAULT_COVER_BOOST_RPM,
    DOMAIN,
    MAX_GPM,
    MAX_RPM,
    MIN_GPM,
    MIN_RPM,
)
from .coordinator import PentairPumpCoordinator
from .cover_boost import CoverBoostController
from .entity import PentairPumpEntity
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
    entities: list[NumberEntity] = []
    for pump in coordinator.hub.pumps:
        entities.append(
            PentairPumpRpmNumber(coordinator, pump.index, entry_id)
        )
        entities.append(
            PentairPumpGpmNumber(coordinator, pump.index, entry_id)
        )
        entities.append(
            PentairCoverBoostSpeedNumber(
                coordinator, cover_boost, pump.index, entry_id
            )
        )
        for program in range(1, 5):
            entities.append(
                PentairProgramSpeedNumber(
                    coordinator, pump.index, program, entry_id
                )
            )
    async_add_entities(entities)


class PentairPumpRpmNumber(PentairPumpEntity, NumberEntity, RestoreEntity):
    """Set RPM — restores target after HA restart without auto-sending unless desired_run."""

    _attr_translation_key = "rpm"
    _attr_native_min_value = MIN_RPM
    _attr_native_max_value = MAX_RPM
    _attr_native_step = 50
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = "rpm"
    _attr_icon = "mdi:speedometer"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
        self._attr_entity_registry_enabled_default = coordinator.hub.supports_rpm(
            pump_index
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None or last.state in (None, "unknown", "unavailable"):
            return
        try:
            self.coordinator.hub.set_target_rpm(
                self.pump_index, int(float(last.state))
            )
        except ValueError:
            return

    @property
    def native_value(self) -> float | None:
        target = self.coordinator.hub.get_target_rpm(self.pump_index)
        if target is not None:
            return float(target)
        rpm = self.pump_data.get("rpm", 0)
        return float(rpm) if rpm else None

    @property
    def available(self) -> bool:
        return super().available and bool(self.pump_data.get("supports_rpm", True))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.hub.async_run_rpm(self.pump_index, int(value))
        await self.coordinator.async_request_refresh()


class PentairPumpGpmNumber(PentairPumpEntity, NumberEntity, RestoreEntity):
    """Set GPM — restores target after HA restart without auto-sending unless desired_run."""

    _attr_translation_key = "gpm"
    _attr_native_min_value = MIN_GPM
    _attr_native_max_value = MAX_GPM
    _attr_native_step = 1
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = "gpm"
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
        self._attr_entity_registry_enabled_default = coordinator.hub.supports_gpm(
            pump_index
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None or last.state in (None, "unknown", "unavailable"):
            return
        try:
            self.coordinator.hub.set_target_gpm(
                self.pump_index, int(float(last.state))
            )
        except ValueError:
            return

    @property
    def native_value(self) -> float | None:
        target = self.coordinator.hub.get_target_gpm(self.pump_index)
        if target is not None:
            return float(target)
        gpm = self.pump_data.get("gpm", 0)
        return float(gpm) if gpm else None

    @property
    def available(self) -> bool:
        return super().available and bool(self.pump_data.get("supports_gpm", True))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.hub.async_run_gpm(self.pump_index, int(value))
        await self.coordinator.async_request_refresh()


class PentairCoverBoostSpeedNumber(
    PentairPumpEntity, NumberEntity, RestoreEntity
):
    """Target speed applied when cover opens and boost switch is on."""

    _attr_translation_key = "cover_boost_speed"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:speedometer-medium"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        cover_boost: CoverBoostController,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
        self._cover_boost = cover_boost

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            try:
                self._cover_boost.set_boost_speed(
                    self.pump_index, int(float(last.state))
                )
                return
            except ValueError:
                pass
        profile = self._cover_boost.get_boost_profile(self.pump_index)
        default = (
            DEFAULT_COVER_BOOST_GPM
            if profile == CommandProfile.GPM
            else DEFAULT_COVER_BOOST_RPM
        )
        if self._cover_boost.get_boost_speed(self.pump_index) is None:
            self._cover_boost.set_boost_speed(self.pump_index, default)

    @property
    def _uses_gpm(self) -> bool:
        return (
            self._cover_boost.get_boost_profile(self.pump_index) == CommandProfile.GPM
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
        speed = self._cover_boost.get_boost_speed(self.pump_index)
        return float(speed) if speed is not None else None

    @property
    def available(self) -> bool:
        return bool(self._cover_boost.cover_entity_id)

    async def async_set_native_value(self, value: float) -> None:
        self._cover_boost.set_boost_speed(self.pump_index, int(value))
        await self._cover_boost.async_reevaluate_pump(self.pump_index)
        self.async_write_ha_state()


class PentairProgramSpeedNumber(PentairPumpEntity, NumberEntity, RestoreEntity):
    """Save a RPM/GPM speed into pump program slot 1-4."""

    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:content-save"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        program: int,
        entry_id: str,
    ) -> None:
        self._program = program
        self._attr_translation_key = f"program_{program}_speed"
        super().__init__(coordinator, pump_index, entry_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None or last.state in (None, "unknown", "unavailable"):
            return
        try:
            self.coordinator.hub.set_saved_program_speed(
                self.pump_index, self._program, int(float(last.state))
            )
        except ValueError:
            return

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
