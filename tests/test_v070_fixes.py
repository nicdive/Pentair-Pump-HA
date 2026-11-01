"""Regression tests for v0.7.0 reliability fixes."""

from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock

from custom_components.pentair_rs485.const import STALE_POLL_MISSES
from custom_components.pentair_rs485.cover_boost import CoverBoostController
from custom_components.pentair_rs485.hub import PentairHub, PumpConfig
from custom_components.pentair_rs485.rs485.bus import _have_expected_status
from custom_components.pentair_rs485.rs485.packets import (
    CommandProfile,
    PumpStatus,
    PumpType,
    build_packet,
)
from custom_components.pentair_rs485.rs485.parser import extract_frames, parse_pump_status


class _RecordingBus:
    def __init__(self) -> None:
        self.sequences: list[list[bytes]] = []

    async def async_open(self) -> None:
        return None

    async def async_close(self) -> None:
        return None

    async def async_send_sequence(self, packets, **_kwargs):
        self.sequences.append(list(packets))
        return []


class _FakeHass:
    def async_create_task(self, coro):
        return asyncio.get_event_loop().create_task(coro)

    def __init__(self) -> None:
        self.states = type("S", (), {"get": lambda *_a, **_k: None})()


class _FakeCoordinator:
    def __init__(self) -> None:
        self.async_request_refresh = AsyncMock()


def _status(index: int = 1, **kwargs) -> PumpStatus:
    base = dict(
        index=index,
        hour=12,
        minute=0,
        run=10,
        mode=2,
        drivestate=2,
        watts=400,
        rpm=1800,
        gpm=0,
        ppc=12,
        err=0,
        timer=0,
    )
    base.update(kwargs)
    return PumpStatus(**base)


def _hub(*pumps: PumpConfig) -> tuple[PentairHub, _RecordingBus]:
    bus = _RecordingBus()
    if not pumps:
        pumps = (PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF),)
    hub = PentairHub(bus=bus, app_address=33, pumps=list(pumps))  # type: ignore[arg-type]
    return hub, bus


def _flat(bus: _RecordingBus) -> list[bytes]:
    return [b for seq in bus.sequences for b in seq]


def _has_power_off(bus: _RecordingBus) -> bool:
    return any(list(p)[7:10] == [6, 1, 4] for p in _flat(bus))


def _make_status_frame(
    *,
    pump_index: int = 1,
    rpm: int = 1800,
    gpm: int = 0,
    watts: int = 400,
    run: int = 10,
    mode: int = 2,
) -> bytes:
    source = pump_index + 95
    rpm_h, rpm_l = divmod(rpm, 256)
    w_h, w_l = divmod(watts, 256)
    data = [
        run,
        mode,
        2,
        w_h,
        w_l,
        rpm_h,
        rpm_l,
        gpm,
        12,
        0,
        0,
        0,
        0,
        12,
        30,
    ]
    assert len(data) == 15
    return build_packet(source, 33, [7, 15, *data])


def test_parse_status_frame_roundtrip():
    packet = _make_status_frame(rpm=2000, watts=150)
    frames, remainder = extract_frames(bytearray(packet))
    assert remainder == b""
    assert len(frames) == 1
    status = parse_pump_status(frames[0])
    assert status is not None
    assert status.index == 1
    assert status.rpm == 2000
    assert status.watts == 150
    assert status.hour == 12
    assert status.minute == 30


def test_extract_frames_rejects_huge_payload_length():
    # FF A5 then a 255 length byte would previously skip 263 bytes of traffic.
    garbage = bytearray([255, 165, 0, 33, 96, 7, 255]) + bytearray(20)
    frames, remainder = extract_frames(garbage)
    assert frames == []
    # Should keep scanning rather than consume the whole buffer as one frame.
    assert len(remainder) < len(garbage)


def test_have_expected_status_waits_for_requested_pump():
    s1 = _status(index=1)
    s2 = _status(index=2)
    assert _have_expected_status([], 1) is False
    assert _have_expected_status([s1], 2) is False
    assert _have_expected_status([s1], 1) is True
    assert _have_expected_status([s1, s2], 2) is True
    assert _have_expected_status([s1], None) is True


def test_stop_program_clears_desired_run_and_powers_off():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 1800)
        await hub.async_run_program(1, 0)
        assert hub.should_run(1) is False
        assert _has_power_off(bus)

    asyncio.run(_run())


def test_power_on_reapplies_rpm_setpoint():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        await hub.async_set_power(1, True)
        assert hub.should_run(1) is True
        assert any(list(p)[7:13] == [1, 4, 2, 196, 7, 208] for p in _flat(bus))

    asyncio.run(_run())


def test_cover_boost_does_not_overwrite_user_setpoint():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_target_rpm(1, 1600)
        hub.set_should_run(1, True)
        hub._command_profile[1] = CommandProfile.RPM
        hub._status[1] = _status(rpm=1600)
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        ctrl.mark_entities_ready()
        ctrl.set_enabled(1, True)
        ctrl.set_boost_speed(1, 2500)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        await ctrl._async_apply_boost(1)
        assert hub.get_target_rpm(1) == 1600
        assert hub.should_run(1) is True
        assert any(list(p)[7:13] == [1, 4, 2, 196, 9, 196] for p in _flat(bus))  # 2500

    asyncio.run(_run())


def test_cover_boost_restore_stops_pump_that_was_off():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_target_rpm(1, 1600)
        hub._command_profile[1] = CommandProfile.RPM
        hub._status[1] = _status(run=4, rpm=0)
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        ctrl.mark_entities_ready()
        ctrl.set_enabled(1, True)
        ctrl.set_boost_speed(1, 2500)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        await ctrl._async_apply_boost(1)
        bus.sequences.clear()
        await ctrl._async_restore(1)
        assert hub.should_run(1) is False
        assert _has_power_off(bus)
        assert not any(list(p)[7:11] == [1, 4, 2, 196] for p in _flat(bus))
        assert hub.get_target_rpm(1) == 1600

    asyncio.run(_run())


def test_closing_cover_keeps_boost_until_closed():
    async def _run() -> None:
        hub, _bus = _hub()
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="cover.volet",
        )
        ctrl.mark_entities_ready()
        await ctrl._async_handle_cover_state("open")
        assert ctrl.is_cover_open() is True
        await ctrl._async_handle_cover_state("closing")
        assert ctrl.is_cover_open() is True
        await ctrl._async_handle_cover_state("closed")
        assert ctrl.is_cover_open() is False

    asyncio.run(_run())


def test_pump_offline_after_consecutive_misses():
    hub, _bus = _hub()
    hub._store_responses([_status(index=1)], 1, count_miss=True)
    assert hub.is_pump_online(1) is True
    for _ in range(STALE_POLL_MISSES):
        hub._store_responses([], 1, count_miss=True)
    assert hub.is_pump_online(1) is False
    # Last live status is kept for diagnostics
    assert hub.get_status(1) is not None
    assert hub.get_status(1).rpm == 1800


def test_vs_vf_capability_flags():
    hub, _bus = _hub(
        PumpConfig(index=1, name="VS", pump_type=PumpType.VS),
        PumpConfig(index=2, name="VF", pump_type=PumpType.VF),
        PumpConfig(index=3, name="VSF", pump_type=PumpType.VSF),
    )
    assert hub.supports_rpm(1) is True and hub.supports_gpm(1) is False
    assert hub.supports_rpm(2) is True and hub.supports_gpm(2) is True
    assert hub.supports_rpm(3) is True and hub.supports_gpm(3) is True


def test_set_pump_mode_does_not_mark_desired_run():
    async def _run() -> None:
        hub, _bus = _hub()
        hub.set_should_run(1, False)
        await hub.async_set_pump_mode(1, 2)
        assert hub.should_run(1) is False

    asyncio.run(_run())


def test_local_control_does_not_count_as_poll_miss():
    async def _run() -> None:
        hub, _bus = _hub()
        hub._store_responses([_status(index=1)], 1, count_miss=True)
        assert hub.is_pump_online(1) is True
        await hub.async_set_panel_control(1, True)
        assert hub.is_pump_online(1) is True
        assert hub._poll_misses.get(1, 0) == 0

    asyncio.run(_run())


def test_cover_restore_keeps_desired_run_after_outage():
    """Pump was wanted on but currently off (outage): closing cover must resume."""

    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 1600)
        hub._command_profile[1] = CommandProfile.RPM
        hub._status[1] = _status(run=4, rpm=0)
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        ctrl.mark_entities_ready()
        ctrl.set_enabled(1, True)
        ctrl.set_boost_speed(1, 2500)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        await ctrl._async_apply_boost(1)
        bus.sequences.clear()
        await ctrl._async_restore(1)
        assert hub.should_run(1) is True
        assert any(list(p)[7:13] == [1, 4, 2, 196, 6, 64] for p in _flat(bus))  # 1600

    asyncio.run(_run())


def test_status_is_priming():
    assert _status(drivestate=1).is_priming is True
    assert _status(drivestate=4).is_priming is True
    assert _status(drivestate=2).is_priming is False
