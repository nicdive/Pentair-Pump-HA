"""Binary sensors for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PentairPumpCoordinator
from .cover_boost import CoverBoostController
from .entity import PentairPumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    stored = hass.data[DOMAIN][entry.entry_id]
    coordinator: PentairPumpCoordinator = stored["coordinator"]
    cover_boost: CoverBoostController = stored["cover_boost"]
    entry_id = entry.entry_id
    entities: list[BinarySensorEntity] = [
        PentairBusOnlineBinarySensor(coordinator, entry_id),
    ]
    for pump in coordinator.hub.pumps:
        entities.append(
            PentairCoverBoostActiveBinarySensor(
                coordinator, cover_boost, pump.index, entry_id
            )
        )
    async_add_entities(entities)


class PentairBusOnlineBinarySensor(BinarySensorEntity):
    """True when the RS485 adapter is open and last I/O succeeded."""

    _attr_has_entity_name = True
    _attr_translation_key = "bus_online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: PentairPumpCoordinator, entry_id: str
    ) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_bus_online"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_bus")},
            name="Pentair RS485",
            manufacturer="Pentair",
        )

    @property
    def is_on(self) -> bool:
        bus = self.coordinator.hub.bus
        return bus.is_open and bus.last_error is None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )


class PentairCoverBoostActiveBinarySensor(PentairPumpEntity, BinarySensorEntity):
    """True while cover-open boost is actively applied."""

    _attr_translation_key = "cover_boost_active"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        cover_boost: CoverBoostController,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator, pump_index, entry_id)
        self._cover_boost = cover_boost

    @property
    def is_on(self) -> bool:
        return self._cover_boost.is_boost_active(self.pump_index)

    @property
    def available(self) -> bool:
        return bool(self._cover_boost.cover_entity_id)
