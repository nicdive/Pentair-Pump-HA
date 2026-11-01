"""Constants for the Pentair RS485 pump integration."""

from __future__ import annotations

DOMAIN = "pentair_rs485"

CONF_APP_ADDRESS = "app_address"
CONF_PUMPS = "pumps"
CONF_PUMP_INDEX = "pump_index"
CONF_PUMP_TYPE = "pump_type"
CONF_PUMP_NAME = "pump_name"
CONF_KEEP_PUMPS = "keep_pumps"
CONF_ADD_ANOTHER = "add_another"
CONF_COVER_ENTITY = "cover_entity_id"
CONF_COVER_INVERT = "cover_invert"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SETUP_MODE = "setup_mode"
SETUP_MODE_PUMP = "pump"
SETUP_MODE_DISPLAY = "display"


def is_display_entry(data: dict | None) -> bool:
    """True for the Lovelace-only Home Assistant (no USB / no pumps)."""
    return bool(data) and data.get(CONF_SETUP_MODE) == SETUP_MODE_DISPLAY


def default_setup_mode(ports: list[str] | None) -> str:
    """Prefer display-only when no USB-serial adapter is visible."""
    found = ports or []
    if any(
        token in path
        for path in found
        for token in ("ttyUSB", "ttyACM", "serial/by-id")
    ):
        return SETUP_MODE_PUMP
    return SETUP_MODE_DISPLAY

DEFAULT_APP_ADDRESS = 33
DEFAULT_BAUD_RATE = 9600
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 120
DEFAULT_COVER_INVERT = False
DEFAULT_COVER_BOOST_RPM = 2000
DEFAULT_COVER_BOOST_GPM = 60

DEFAULT_WATCHDOG_ENABLED = True
DEFAULT_WATCHDOG_TOLERANCE = 100
DEFAULT_WATCHDOG_GPM_TOLERANCE = 5
DEFAULT_WATCHDOG_RECOVERY_DELAY = 15

# Missed polls before a pump is considered offline (status is kept, just marked stale).
STALE_POLL_MISSES = 3

PUMP_TYPES = ("VS", "VF", "VSF")

ATTR_PUMP_INDEX = "pump_index"
ATTR_PROGRAM = "program"
ATTR_DESIRED_RUN = "desired_run"
ATTR_ONLINE = "online"
ATTR_SPEED = "speed"
ATTR_RPM = "rpm"
ATTR_GPM = "gpm"
ATTR_POWER = "power"

SERVICE_RUN_PROGRAM = "run_program"
SERVICE_SAVE_PROGRAM = "save_program"
SERVICE_SET_SPEED = "set_speed"
SERVICE_SET_POWER = "set_power"

MIN_RPM = 450
MAX_RPM = 3450
MIN_GPM = 15
MAX_GPM = 130
