"""Tests for RS485 packet building (validated against nodejs-poolController specs)."""

from custom_components.pentair_rs485.rs485.packets import (
    build_packet,
    pump_index_to_address,
    request_status,
    run_gpm,
    run_program,
    run_rpm,
    save_program,
    set_power,
    set_pump_mode,
    set_remote_control,
)


def test_pump_index_to_address():
    assert pump_index_to_address(1) == 96
    assert pump_index_to_address(2) == 97


def test_remote_control_pump1():
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


def test_run_rpm_1000():
    packet = run_rpm(33, 96, 1000)
    assert list(packet)[3:13] == [165, 0, 96, 33, 1, 4, 2, 196, 3, 232]


def test_run_gpm_30():
    packet = run_gpm(33, 96, 30)
    assert list(packet)[3:13] == [165, 0, 96, 33, 1, 4, 2, 228, 0, 30]


def test_run_program_1():
    packet = run_program(33, 96, 1)
    assert list(packet)[3:13] == [165, 0, 96, 33, 1, 4, 3, 33, 0, 8]


def test_save_program_2_rpm():
    packet = save_program(33, 96, 2, 1500)
    assert list(packet)[7:13] == [1, 4, 3, 40, 5, 220]


def test_set_pump_mode_ext_program():
    packet = set_pump_mode(33, 96, 9)
    assert list(packet)[7:10] == [5, 1, 9]


def test_build_packet_checksum():
    core = build_packet(33, 96, [4, 1, 255])
    assert core[:3] == b"\xff\x00\xff"
    assert core[3] == 165
