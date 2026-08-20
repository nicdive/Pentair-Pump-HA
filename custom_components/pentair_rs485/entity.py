"""Base entity for Pentair RS485 pumps."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PentairPumpCoordinator


class PentairPumpEntity(CoordinatorEntity[PentairPumpCoordinator]):
    """Representation of a Pentair pump entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PentairPumpCoordinator,
        pump_index: int,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.pump_index = pump_index
        self.entry_id = entry_id
        pump_data = coordinator.data.get(pump_index, {})
        name = pump_data.get("name", f"Pump {pump_index}")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{pump_index}")},
            name=name,
            manufacturer="Pentair",
            model=pump_data.get("type", "IntelliFlo"),
        )
        key = getattr(self, "_attr_translation_key", None)
        if key and not getattr(self, "_attr_unique_id", None):
            self._attr_unique_id = f"{entry_id}_{pump_index}_{key}"

    @property
    def pump_data(self) -> dict:
        return self.coordinator.data.get(self.pump_index, {})
