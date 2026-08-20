"""The Pentair RS485 Pump integration v0.6.1."""

DOMAIN = "pentair_rs485"
PLATFORMS = ["switch", "number", "sensor", "button", "select"]


async def async_setup(hass, config):
    """Set up the Pentair RS485 integration."""
    return True


async def async_setup_entry(hass, entry):
    """Set up Pentair RS485 from a config entry."""
    from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STARTED

    from .const import (
        CONF_APP_ADDRESS,
        CONF_PUMP_INDEX,
        CONF_PUMP_NAME,
        CONF_PUMP_TYPE,
        CONF_PUMPS,
    )
    from .coordinator import PentairPumpCoordinator
    from .cover_boost import CoverBoostController, cover_options_from_entry
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

    cover_entity, cover_invert = cover_options_from_entry(entry)
    cover_boost = CoverBoostController(
        hass,
        hub,
        coordinator,
        cover_entity_id=cover_entity,
        cover_invert=cover_invert,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "coordinator": coordinator,
        "cover_boost": cover_boost,
    }

    # Platforms first so RestoreEntity can reload boost switch/speed/profile.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await cover_boost.async_setup()

    async def _startup_sync(_event=None):
        await cover_boost.async_startup_sync()

    if hass.is_running:
        hass.async_create_task(_startup_sync())
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _startup_sync)
        )

    from .service import async_setup_services

    if not hass.services.has_service(DOMAIN, "run_program"):
        async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass, entry):
    """Reload when options change (cover sensor)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        stored = hass.data[DOMAIN].pop(entry.entry_id)
        cover_boost = stored.get("cover_boost")
        if cover_boost is not None:
            await cover_boost.async_shutdown()
        await stored["hub"].async_shutdown()
    return unload_ok
