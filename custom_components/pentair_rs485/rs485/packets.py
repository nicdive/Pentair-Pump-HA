"""RS485 packet builders for Pentair IntelliFlo pumps."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

PREAMBLE = bytes((255, 0, 255))
HEADER = 165


class PumpType(str, Enum):
    """Legacy config type — use CommandProfile for outbound commands."""

    VS = "VS"
    VF = "VF"
    VSF = "VSF"


class CommandProfile(str, Enum):
    """Which RS485 command set to use (field-tested on VF WhisperFlo)."""

    RPM = "rpm"  # VS packets: action 1, setpoint 196
    GPM = "gpm"  # VF packets: action 1, setpoint 228


def pump_index_to_address(index: int) -> int:
    if not 1 <= index <= 16:
        raise ValueError(f"Invalid pump index: {index}")
    return index + 95


def pump_address_to_index(address: int) -> int:
    if not 96 <= address <= 111:
        raise ValueError(f"Invalid pump address: {address}")
    return address - 95


def build_packet(app_address: int, dest: int, payload: list[int]) -> bytes:
    message = [HEADER, 0, dest, app_address, *payload]
    checksum = sum(message)
    message.extend((checksum >> 8, checksum & 0xFF))
    return PREAMBLE + bytes(message)


def _base(app_address: int, address: int, payload: list[int]) -> bytes:
    return build_packet(app_address, address, payload)


def set_remote_control(app_address: int, address: int) -> bytes:
    """Action 4 value 255 — remote lock, LCD shows 'Display not active'."""
    return _base(app_address, address, [4, 1, 255])


def set_local_control(app_address: int, address: int) -> bytes:
    """Action 4 value 0 — local panel active, physical buttons enabled."""
    return _base(app_address, address, [4, 1, 0])


def request_status(app_address: int, address: int) -> bytes:
    return _base(app_address, address, [7, 0])


def set_power(app_address: int, address: int, power: bool) -> bytes:
    return _base(app_address, address, [6, 1, 10 if power else 4])


def set_pump_mode(app_address: int, address: int, mode: int) -> bytes:
    """Action 5 — wiki: 0=filter, 1=manual, 2-5=speed 1-4, 6=feature 1."""
    if not 0 <= mode <= 12:
        raise ValueError(f"Invalid pump mode: {mode}")
    return _base(app_address, address, [5, 1, mode])


def set_manual_mode(app_address: int, address: int) -> bytes:
    return set_pump_mode(app_address, address, 1)


def set_speed1_mode(app_address: int, address: int) -> bytes:
    """Mode 2 — wiki speed 1 (used after power loss on some VF pumps)."""
    return set_pump_mode(app_address, address, 2)


def run_program(app_address: int, address: int, program: int) -> bytes:
    if not 0 <= program <= 4:
        raise ValueError(f"Invalid program: {program}")
    return _base(app_address, address, [1, 4, 3, 33, 0, 8 * program])


def run_rpm(app_address: int, address: int, rpm: int) -> bytes:
    """VS-style RPM command (works on VF WhisperFlo when profile is RPM)."""
    return _base(app_address, address, [1, 4, 2, 196, rpm >> 8, rpm & 0xFF])


def run_gpm(app_address: int, address: int, gpm: int) -> bytes:
    """VF-style GPM command."""
    return _base(app_address, address, [1, 4, 2, 228, gpm >> 8, gpm & 0xFF])


def save_program(
    app_address: int, address: int, program: int, speed: int
) -> bytes:
    if not 1 <= program <= 4:
        raise ValueError(f"Invalid program: {program}")
    payload = [1, 4, 3, 38 + program, speed >> 8, speed & 0xFF]
    return _base(app_address, address, payload)


def validate_rpm(value: int) -> bool:
    return 450 <= value <= 3450


def validate_gpm(value: int) -> bool:
    return 15 <= value <= 130


@dataclass(slots=True)
class PumpStatus:
    index: int
    hour: int
    minute: int
    run: int
    mode: int
    drivestate: int
    watts: int
    rpm: int
    gpm: int
    ppc: int
    err: int
    timer: int

    @property
    def is_on(self) -> bool:
        return self.run == 10 or self.rpm > 0 or self.gpm > 0
