"""Lovelace-only setup mode (house HA / Remote HA)."""

from custom_components.pentair_rs485.const import (
    CONF_SETUP_MODE,
    SETUP_MODE_DISPLAY,
    SETUP_MODE_PUMP,
    is_display_entry,
)


def test_display_entry_detection() -> None:
    assert is_display_entry({CONF_SETUP_MODE: SETUP_MODE_DISPLAY}) is True
    assert is_display_entry({CONF_SETUP_MODE: SETUP_MODE_PUMP}) is False
    assert is_display_entry({"port": "/dev/ttyUSB0"}) is False
    assert is_display_entry({}) is False
    assert is_display_entry(None) is False
