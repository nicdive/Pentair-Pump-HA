"""Switch platform for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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
    entities: list[SwitchEntity] = []
    for pump in coordinator.hub.pumps:
        entities.append(PentairPumpPowerSwitch(coordinator, pump.index))
        entities.append(PentairDisplayActiveSwitch(coordinator, pump.index))
        entities.append(
            PentairCoverBoostSwitch(coordinator, cover_boost, pump.index)
        )
    async_add_entities(entities)


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


class PentairCoverBoostSwitch(PentairPumpEntity, SwitchEntity, RestoreEntity):
    """Enable automatic speed boost when the pool cover opens."""

    _attr_translation_key = "cover_boost"
    _attr_icon = "mdi:arrow-up-bold-hexagon-outline"

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        cover_boost: CoverBoostController,
        pump_index: int,
    ) -> None:
        super().__init__(coordinator, pump_index)
        self._cover_boost = cover_boost

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            self._cover_boost.set_enabled(self.pump_index, True)

    @property
    def is_on(self) -> bool:
        return self._cover_boost.is_enabled(self.pump_index)

    @property
    def available(self) -> bool:
        return bool(self._cover_boost.cover_entity_id)

    async def async_turn_on(self, **kwargs) -> None:
        self._cover_boost.set_enabled(self.pump_index, True)
        await self._cover_boost.async_reevaluate_pump(self.pump_index)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._cover_boost.set_enabled(self.pump_index, False)
        await self._cover_boost.async_reevaluate_pump(self.pump_index)
        self.async_write_ha_state()
