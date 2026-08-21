"""Home Assistant services for Pentair RS485 pumps."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_GPM,
    ATTR_POWER,
    ATTR_PROGRAM,
    ATTR_PUMP_INDEX,
    ATTR_RPM,
    DOMAIN,
    SERVICE_RUN_PROGRAM,
    SERVICE_SAVE_PROGRAM,
    SERVICE_SET_POWER,
    SERVICE_SET_SPEED,
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

SERVICE_SET_SPEED_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PUMP_INDEX): vol.All(cv.positive_int, vol.Range(min=1, max=16)),
        vol.Optional(ATTR_RPM): cv.positive_int,
        vol.Optional(ATTR_GPM): cv.positive_int,
    }
)

SERVICE_SET_POWER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PUMP_INDEX): vol.All(cv.positive_int, vol.Range(min=1, max=16)),
        vol.Required(ATTR_POWER): cv.boolean,
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

    async def set_speed(call: ServiceCall) -> None:
        pump_index = call.data[ATTR_PUMP_INDEX]
        rpm = call.data.get(ATTR_RPM)
        gpm = call.data.get(ATTR_GPM)
        if rpm is None and gpm is None:
            raise ServiceValidationError("Provide rpm or gpm")
        coordinator, hub = _get_coordinator(hass, pump_index)
        if gpm is not None:
            await hub.async_run_gpm(pump_index, int(gpm))
        if rpm is not None:
            await hub.async_run_rpm(pump_index, int(rpm))
        await coordinator.async_request_refresh()

    async def set_power(call: ServiceCall) -> None:
        pump_index = call.data[ATTR_PUMP_INDEX]
        power = call.data[ATTR_POWER]
        coordinator, hub = _get_coordinator(hass, pump_index)
        await hub.async_set_power(pump_index, bool(power))
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SPEED,
        set_speed,
        schema=SERVICE_SET_SPEED_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_POWER,
        set_power,
        schema=SERVICE_SET_POWER_SCHEMA,
    )
