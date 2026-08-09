"""The Pentair RS485 Pump integration v0.5.2."""

DOMAIN = "pentair_rs485"
PLATFORMS = ["switch", "number", "sensor", "button"]


async def async_setup(hass, config):
    """Set up the Pentair RS485 integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Pentair RS485 from a config entry."""
    from homeassistant.const import CONF_PORT

    from .const import (
        CONF_APP_ADDRESS,
        CONF_PUMP_INDEX,
        CONF_PUMP_NAME,
        CONF_PUMP_TYPE,
        CONF_PUMPS,
    )
    from .coordinator import PentairPumpCoordinator
    from .hub import PentairHub, PumpConfig
    from .rs485.bus import RS485Bus
    from .rs485.packets import PumpType

    data = entry.data
    bus = RS485Bus(data[CONF_PORT])
    pumps = [
        PumpConfig(
            index=p[CONF_PUMP_INDEX],
            name=p[CONF_PUMP_NAME],
            pump_type=PumpType(p[CONF_PUMP_TYPE]),
        )
        for p in data[CONF_PUMPS]
    ]
    hub = PentairHub(
        bus=bus,
        app_address=data.get(CONF_APP_ADDRESS, 33),
        pumps=pumps,
    )
    await hub.async_setup()

    coordinator = PentairPumpCoordinator(hass, hub)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    from .service import async_setup_services

    if not hass.services.has_service(DOMAIN, "run_program"):
        async_setup_services(hass)

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hub = hass.data[DOMAIN][entry.entry_id]["hub"]
        await hub.async_shutdown()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
