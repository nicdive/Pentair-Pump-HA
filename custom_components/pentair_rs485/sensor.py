"""Sensor platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PentairPumpCoordinator
from .entity import PentairPumpEntity
from .rs485.modes import (
    DRIVE_STATE_LABELS,
    PUMP_ERROR_LABELS,
    PUMP_MODE_LABELS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PentairPumpCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    entry_id = entry.entry_id
    entities: list[SensorEntity] = []
    for pump in coordinator.hub.pumps:
        idx = pump.index
        entities.extend(
            [
                PentairPumpWattsSensor(coordinator, idx, entry_id),
                PentairPumpRpmSensor(coordinator, idx, entry_id),
                PentairPumpGpmSensor(coordinator, idx, entry_id),
                PentairPumpModeSensor(coordinator, idx, entry_id),
                PentairPumpDriveStateSensor(coordinator, idx, entry_id),
                PentairPumpPpcSensor(coordinator, idx, entry_id),
                PentairPumpTimerSensor(coordinator, idx, entry_id),
                PentairPumpClockSensor(coordinator, idx, entry_id),
                PentairPumpErrorSensor(coordinator, idx, entry_id),
            ]
        )
    async_add_entities(entities)


class PentairPumpWattsSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "watts"
    _attr_native_unit_of_measurement = "W"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _require_online = True

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("watts")


class PentairPumpRpmSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "rpm_reading"
    _attr_native_unit_of_measurement = "rpm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _require_online = True

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("rpm")

    @property
    def available(self) -> bool:
        return super().available and bool(self.pump_data.get("supports_rpm", True))

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("rpm")


class PentairPumpGpmSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "gpm_reading"
    _attr_native_unit_of_measurement = "gpm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _require_online = True

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("gpm")

    @property
    def available(self) -> bool:
        return super().available and bool(self.pump_data.get("supports_gpm", True))

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("gpm")


class PentairPumpModeSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(PUMP_MODE_LABELS.keys())
    _require_online = True

    @property
    def native_value(self) -> str | None:
        return self.pump_data.get("mode_label")


class PentairPumpDriveStateSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "drive_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(DRIVE_STATE_LABELS.keys()) + ["unknown_3", "unknown_5"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _require_online = True

    @property
    def native_value(self) -> str | None:
        return self.pump_data.get("drivestate_label")


class PentairPumpPpcSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "ppc"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _require_online = True

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("ppc")


class PentairPumpTimerSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "timer"
    _attr_native_unit_of_measurement = "min"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _require_online = True

    @property
    def native_value(self) -> int | None:
        return self.pump_data.get("timer")


class PentairPumpClockSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "clock"
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _require_online = True

    @property
    def native_value(self) -> str | None:
        hour = self.pump_data.get("hour", 0)
        minute = self.pump_data.get("minute", 0)
        return f"{hour:02d}:{minute:02d}"


class PentairPumpErrorSensor(PentairPumpEntity, SensorEntity):
    _attr_translation_key = "error"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(PUMP_ERROR_LABELS.keys())
    _require_online = True

    @property
    def native_value(self) -> str | None:
        return self.pump_data.get("err_label")
