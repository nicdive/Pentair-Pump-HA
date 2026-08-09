#!/usr/bin/env python3
"""Standalone RS485 debug script — run on Home Assistant SSH.

Usage:
  python3 /config/custom_components/pentair_rs485/debug_rs485.py /dev/ttyUSB0 1 VS
"""
from __future__ import annotations

import sys
import time

import serial

# Allow running from HA config path
sys.path.insert(0, "/config")

from custom_components.pentair_rs485.rs485.packets import (  # noqa: E402
    PumpType,
    request_status,
    set_remote_control,
)
from custom_components.pentair_rs485.rs485.parser import extract_frames, parse_pump_status  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: debug_rs485.py <port> <pump_index> [VS|VF|VSF]")
        return 1

    port = sys.argv[1]
    pump_index = int(sys.argv[2])
    address = pump_index + 95
    app_address = 33

    packets = [
        set_remote_control(app_address, address),
        request_status(app_address, address),
    ]

    print(f"Port: {port}")
    print(f"Pump index: {pump_index} -> RS485 address {address}")
    print(f"App address: {app_address}")
    print()

    with serial.Serial(port, 9600, timeout=0.5) as ser:
        ser.reset_input_buffer()
        for i, packet in enumerate(packets, 1):
            print(f"TX{i}: {packet.hex(' ')}")
            ser.write(packet)
            ser.flush()
            time.sleep(0.2)

        print("Listening 3s for responses...")
        buf = bytearray()
        deadline = time.time() + 3
        while time.time() < deadline:
            data = ser.read(256)
            if data:
                print(f"RX raw: {data.hex(' ')}")
                buf.extend(data)
            time.sleep(0.05)

        frames, remainder = extract_frames(buf)
        print(f"\nParsed {len(frames)} frame(s), {len(remainder)} byte(s) left in buffer")
        for n, frame in enumerate(frames, 1):
            print(f"Frame {n}: {' '.join(f'{b:02x}' for b in frame)}")
            status = parse_pump_status(frame)
            if status:
                print(
                    f"  -> Pump {status.index}: rpm={status.rpm} gpm={status.gpm} "
                    f"watts={status.watts} err={status.err}"
                )
            else:
                print(f"  -> Not a pump status (action={frame[4]}, from={frame[3]})")

        if not frames:
            print("\nNo frames parsed. Check:")
            print("- A/B wiring on RS485 adapter")
            print("- Pump powered on")
            print("- Correct pump index (try 1 or 2)")
            print("- No other software using the same serial port")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
