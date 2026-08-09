"""Inbound RS485 frame parsing for Pentair pumps."""

from __future__ import annotations

import logging

from .packets import PumpStatus, pump_address_to_index

_LOGGER = logging.getLogger(__name__)

# Field indices from nodejs-poolController src/etc/constants.js pumpPacketFields
_CMD = 6
_MODE = 7
_DRIVESTATE = 8
_WATTSH = 9
_WATTSL = 10
_RPMH = 11
_RPML = 12
_GPM = 13
_PPC = 14
_ERR = 15
_TIMER = 18
_HOUR = 19
_MIN = 20

_ACTION = 4
_FROM = 3


def verify_checksum(frame: list[int]) -> bool:
    """Validate checksum on a 165... frame (without leading 255)."""
    if len(frame) < 8 or frame[0] != 165:
        return False
    packet_checksum = (frame[-2] << 8) + frame[-1]
    data_sum = sum(frame[:-2])
    return packet_checksum == data_sum


def extract_frames(buffer: bytearray) -> tuple[list[list[int]], bytearray]:
    """Extract complete pump frames from a serial read buffer."""
    frames: list[list[int]] = []
    i = 0
    while i < len(buffer):
        if i + 1 < len(buffer) and buffer[i] == 255 and buffer[i + 1] == 165:
            if i + 7 > len(buffer):
                break
            # Matches nodejs-poolController receive-buffer.js:
            # chatterlen = buffer[6] + 6 + 2 (bytes starting at 165)
            payload_len = buffer[i + 6]
            frame_len = payload_len + 6 + 2
            if i + 1 + frame_len > len(buffer):
                break
            frame = list(buffer[i + 1 : i + 1 + frame_len])
            if verify_checksum(frame):
                frames.append(frame)
                _LOGGER.debug("Parsed frame action=%s from=%s", frame[4], frame[3])
            else:
                _LOGGER.warning(
                    "RS485 checksum mismatch, dropping frame: %s",
                    " ".join(f"{b:02x}" for b in frame),
                )
            i += 1 + frame_len
        else:
            i += 1
    remainder = buffer[i:]
    return frames, bytearray(remainder)


def parse_pump_status(frame: list[int]) -> PumpStatus | None:
    """Parse a pump status response (action 7, from pump address)."""
    if len(frame) < 21:
        return None
    if frame[_ACTION] != 7:
        _LOGGER.debug(
            "Ignoring pump frame action=%s from=%s", frame[_ACTION], frame[_FROM]
        )
        return None
    source = frame[_FROM]
    if not 96 <= source <= 111:
        return None

    index = pump_address_to_index(source)
    watts = frame[_WATTSH] * 256 + frame[_WATTSL]
    rpm = frame[_RPMH] * 256 + frame[_RPML]
    gpm = frame[_GPM]

    return PumpStatus(
        index=index,
        hour=frame[_HOUR],
        minute=frame[_MIN],
        run=frame[_CMD],
        mode=frame[_MODE],
        drivestate=frame[_DRIVESTATE],
        watts=watts,
        rpm=rpm,
        gpm=gpm,
        ppc=frame[_PPC],
        err=frame[_ERR],
        timer=frame[_TIMER],
    )
