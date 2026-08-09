"""Tests for RS485 packet building (validated against nodejs-poolController v5.3.0 specs)."""

from custom_components.pentair_rs485.protocol.packets import (
    PumpType,
    build_packet,
    pump_index_to_address,
    request_status,
    run_rpm,
    set_power,
    set_remote_control,
)


def test_pump_index_to_address():
    assert pump_index_to_address(1) == 96
    assert pump_index_to_address(2) == 97


def test_remote_control_pump1():
    # specs/helpers/pumpCommands.js pump1RemotePacket
    packet = set_remote_control(33, 96)
    assert list(packet) == [255, 0, 255, 165, 0, 96, 33, 4, 1, 255, 2, 42]


def test_request_status_pump1():
    packet = request_status(33, 96)
    assert list(packet) == [255, 0, 255, 165, 0, 96, 33, 7, 0, 1, 45]


def test_power_on_pump1():
    packet = set_power(33, 96, True)
    assert list(packet) == [255, 0, 255, 165, 0, 96, 33, 6, 1, 10, 1, 55]


def test_power_off_pump1():
    packet = set_power(33, 96, False)
    assert list(packet) == [255, 0, 255, 165, 0, 96, 33, 6, 1, 4, 1, 49]


def test_run_rpm_1000_vs():
    packet = run_rpm(33, 96, PumpType.VS, 1000)
    # pump1SetRPM1000Packet payload: [165, 0, 96, 33, 1, 4, 2, 196, 3, 232]
    assert list(packet)[3:13] == [165, 0, 96, 33, 1, 4, 2, 196, 3, 232]


def test_build_packet_checksum():
    core = build_packet(33, 96, [4, 1, 255])
    assert core[:3] == b"\xff\x00\xff"
    assert core[3] == 165
