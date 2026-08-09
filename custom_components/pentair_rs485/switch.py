"""Switch platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities(
        [
            PentairPumpPowerSwitch(coordinator, pump.index)
            for pump in coordinator.hub.pumps
        ]
        + [
            PentairDisplayActiveSwitch(coordinator, pump.index)
            for pump in coordinator.hub.pumps
        ]
    )


class PentairPumpPowerSwitch(PentairPumpEntity, SwitchEntity):
    """Switch to turn a pump on or off."""

    _attr_translation_key = "power"

    @property
    def is_on(self) -> bool:
        return bool(self.pump_data.get("power"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.hub.async_set_power(self.pump_index, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.hub.async_set_power(self.pump_index, False)
        await self.coordinator.async_request_refresh()


class PentairDisplayActiveSwitch(PentairPumpEntity, SwitchEntity):
    """Keep the pump LCD active while HA can still send remote commands."""

    _attr_translation_key = "display_active"
    _attr_icon = "mdi:monitor"

    @property
    def is_on(self) -> bool:
        return bool(self.pump_data.get("display_active"))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.hub.async_set_display_active(self.pump_index, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.hub.async_set_display_active(self.pump_index, False)
        await self.coordinator.async_request_refresh()
