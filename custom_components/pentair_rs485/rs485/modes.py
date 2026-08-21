"""Pump mode and status decoding (nodejs-poolController wiki + VF WhisperFlo labels)."""

from __future__ import annotations

# RS485 mode byte → internal key (shown on sensor; translated in strings.json)
PUMP_MODES: dict[int, str] = {
    0: "filter",
    1: "manual_flow",  # VF: "Manuel débit" (wiki mode 1)
    2: "manual_rpm",  # VF: "Manuel RPM" (wiki mode 2 / speed 1 packet)
    3: "speed_2",
    4: "speed_3",
    5: "speed_4",
    6: "feature_1",
    7: "unknown_7",
    8: "unknown_8",
    9: "ext_program_1",
    10: "ext_program_2",
    11: "ext_program_3",
    12: "ext_program_4",
}

PUMP_MODE_LABELS: dict[str, str] = {
    "filter": "Filter",
    "manual_flow": "Manual flow",
    "manual_rpm": "Manual RPM",
    "speed_2": "Speed 2",
    "speed_3": "Speed 3",
    "speed_4": "Speed 4",
    "feature_1": "Feature 1",
    "unknown_7": "Unknown 7",
    "unknown_8": "Unknown 8",
    "ext_program_1": "External program 1",
    "ext_program_2": "External program 2",
    "ext_program_3": "External program 3",
    "ext_program_4": "External program 4",
}

PUMP_MODE_BY_NAME: dict[str, int] = {v: k for k, v in PUMP_MODES.items()}

DRIVE_STATES: dict[int, str] = {
    0: "fault",
    1: "priming",
    2: "running",
    4: "system_priming",
}

DRIVE_STATE_LABELS: dict[str, str] = {
    "fault": "Fault",
    "priming": "Priming",
    "running": "Running",
    "system_priming": "System priming",
}

PUMP_ERRORS: dict[int, str] = {
    0: "ok",
    1: "motor_overload",
    2: "filter_error",
    3: "prime_failed",
    4: "overheat",
    5: "power_outage",
    6: "drive_failure",
}

PUMP_ERROR_LABELS: dict[str, str] = {
    "ok": "OK",
    "motor_overload": "Motor overload",
    "filter_error": "Filter error",
    "prime_failed": "Prime failed",
    "overheat": "Overheat",
    "power_outage": "Power outage",
    "drive_failure": "Drive failure",
}


def decode_mode(value: int) -> str:
    return PUMP_MODES.get(value, f"unknown_{value}")


def decode_drivestate(value: int) -> str:
    return DRIVE_STATES.get(value, f"unknown_{value}")


def decode_error(value: int) -> str:
    return PUMP_ERRORS.get(value, f"code_{value}")
