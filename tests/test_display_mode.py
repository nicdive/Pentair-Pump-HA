"""Lovelace-only setup mode (house HA / Remote HA)."""

from custom_components.pentair_rs485.const import (
    default_setup_mode,
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


def test_default_setup_mode_follows_usb() -> None:
    assert default_setup_mode(["/dev/ttyUSB0"]) == SETUP_MODE_PUMP
    assert default_setup_mode([]) == SETUP_MODE_DISPLAY
    assert default_setup_mode(["/dev/ttyAMA0"]) == SETUP_MODE_DISPLAY
