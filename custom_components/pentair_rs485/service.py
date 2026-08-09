"""Home Assistant services for Pentair RS485 pumps."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_PROGRAM,
    ATTR_PUMP_INDEX,
    DOMAIN,
    SERVICE_RUN_PROGRAM,
    SERVICE_SAVE_PROGRAM,
)

SERVICE_RUN_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PUMP_INDEX): vol.All(cv.positive_int, vol.Range(min=1, max=16)),
        vol.Required(ATTR_PROGRAM): vol.All(vol.Coerce(int), vol.Range(min=0, max=4)),
    }
)

SERVICE_SAVE_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PUMP_INDEX): vol.All(cv.positive_int, vol.Range(min=1, max=16)),
        vol.Required(ATTR_PROGRAM): vol.All(cv.positive_int, vol.Range(min=1, max=4)),
        vol.Required("speed"): cv.positive_int,
    }
)


def _get_coordinator(hass: HomeAssistant, pump_index: int):
    for data in hass.data.get(DOMAIN, {}).values():
        hub = data["hub"]
        if any(pump.index == pump_index for pump in hub.pumps):
            return data["coordinator"], hub
    raise ServiceValidationError(f"Pump index {pump_index} not found")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Pentair RS485 services once."""

    async def run_program(call: ServiceCall) -> None:
        pump_index = call.data[ATTR_PUMP_INDEX]
        program = call.data[ATTR_PROGRAM]
        coordinator, hub = _get_coordinator(hass, pump_index)
        await hub.async_run_program(pump_index, program)
        await coordinator.async_request_refresh()

    async def save_program(call: ServiceCall) -> None:
        pump_index = call.data[ATTR_PUMP_INDEX]
        program = call.data[ATTR_PROGRAM]
        speed = call.data["speed"]
        coordinator, hub = _get_coordinator(hass, pump_index)
        await hub.async_save_program(pump_index, program, speed)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_PROGRAM,
        run_program,
        schema=SERVICE_RUN_PROGRAM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_PROGRAM,
        save_program,
        schema=SERVICE_SAVE_PROGRAM_SCHEMA,
    )
