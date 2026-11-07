"""The Pentair RS485 Pump integration v0.8.2."""

DOMAIN = "pentair_rs485"
PLATFORMS = ["switch", "number", "sensor", "button", "select", "binary_sensor"]


async def async_setup(hass, config):
    """Set up the Pentair RS485 integration."""
    from .frontend import async_register_frontend

    await async_register_frontend(hass)
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
        CONF_SCAN_INTERVAL,
        DEFAULT_APP_ADDRESS,
        DEFAULT_SCAN_INTERVAL,
        MAX_SCAN_INTERVAL,
        MIN_SCAN_INTERVAL,
        SERVICE_RUN_PROGRAM,
        SERVICE_SAVE_PROGRAM,
        SERVICE_SET_POWER,
        SERVICE_SET_SPEED,
        is_display_entry,
    )
    from .coordinator import PentairPumpCoordinator
    from .cover_boost import CoverBoostController, cover_options_from_entry
    from .hub import PentairHub, PumpConfig
    from .rs485.bus import RS485Bus
    from .rs485.packets import PumpType

    data = entry.data
    if is_display_entry(data):
        from .frontend import async_register_frontend

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"mode": "display"}
        await async_register_frontend(hass)
        return True

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
        app_address=data.get(CONF_APP_ADDRESS, DEFAULT_APP_ADDRESS),
        pumps=pumps,
    )
    await hub.async_setup()

    options = entry.options or {}
    try:
        scan_interval = int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    except (TypeError, ValueError):
        scan_interval = DEFAULT_SCAN_INTERVAL
    scan_interval = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, scan_interval))

    coordinator = PentairPumpCoordinator(hass, hub, scan_interval=scan_interval)

    cover_entity, cover_invert = cover_options_from_entry(entry)
    cover_boost = CoverBoostController(
        hass,
        hub,
        coordinator,
        cover_entity_id=cover_entity,
        cover_invert=cover_invert,
    )
    coordinator.cover_boost = cover_boost

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "coordinator": coordinator,
        "cover_boost": cover_boost,
        "entry_id": entry.entry_id,
    }

    # RestoreEntity runs during platform setup — must happen BEFORE first RS485
    # poll so panel-control / desired_run are known and we don't steal the panel.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    from .device_cleanup import async_remove_orphan_pumps

    async_remove_orphan_pumps(hass, entry, {p.index for p in pumps})

    await cover_boost.async_setup()
    await coordinator.async_refresh()

    async def _startup_sync(_event=None):
        await cover_boost.async_startup_sync()
        await hub.async_resume_desired_pumps()
        await coordinator.async_request_refresh()

    if hass.is_running:
        hass.async_create_task(_startup_sync())
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _startup_sync)
        )

    from .service import async_setup_services

    if not hass.services.has_service(DOMAIN, SERVICE_RUN_PROGRAM):
        async_setup_services(hass)

    from .frontend import async_register_frontend

    await async_register_frontend(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass, entry):
    """Reload when options or reconfigure data change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    from .const import (
        SERVICE_RUN_PROGRAM,
        SERVICE_SAVE_PROGRAM,
        SERVICE_SET_POWER,
        SERVICE_SET_SPEED,
    )

    stored = hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}
    if stored.get("mode") == "display":
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        stored = hass.data[DOMAIN].pop(entry.entry_id)
        cover_boost = stored.get("cover_boost")
        if cover_boost is not None:
            await cover_boost.async_shutdown()
        coordinator = stored.get("coordinator")
        if coordinator is not None and hasattr(coordinator, "async_shutdown"):
            await coordinator.async_shutdown()
        await stored["hub"].async_shutdown()
        if not hass.data.get(DOMAIN):
            for service in (
                SERVICE_RUN_PROGRAM,
                SERVICE_SAVE_PROGRAM,
                SERVICE_SET_SPEED,
                SERVICE_SET_POWER,
            ):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
    return unload_ok
