"""End-to-end robustness scenarios (restart, panel, outage, cover)."""

import asyncio

from unittest.mock import AsyncMock

from custom_components.pentair_rs485.cover_boost import CoverBoostController
from custom_components.pentair_rs485.hub import PentairHub, PumpConfig
from custom_components.pentair_rs485.rs485.packets import (
    CommandProfile,
    PumpStatus,
    PumpType,
)


class _RecordingBus:
    def __init__(self) -> None:
        self.sequences: list[list[bytes]] = []

    async def async_open(self) -> None:
        return None

    async def async_close(self) -> None:
        return None

    async def async_ensure_open(self) -> None:
        return None

    async def async_reconnect(self) -> None:
        return None

    async def async_send_sequence(self, packets):
        self.sequences.append(list(packets))
        return []


class _FakeHass:
    def __init__(self) -> None:
        self.states = type("S", (), {"get": lambda *_a, **_k: None})()

    def async_create_task(self, coro):
        return asyncio.get_event_loop().create_task(coro)


class _FakeCoordinator:
    def __init__(self) -> None:
        self.async_request_refresh = AsyncMock()


def _status(**kwargs) -> PumpStatus:
    base = dict(
        index=1,
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


def _hub() -> tuple[PentairHub, _RecordingBus]:
    bus = _RecordingBus()
    hub = PentairHub(
        bus=bus,  # type: ignore[arg-type]
        app_address=33,
        pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF)],
    )
    return hub, bus


def _rpm_packets(bus: _RecordingBus) -> bool:
    flat = [b for seq in bus.sequences for b in seq]
    return any(len(list(p)) >= 13 and list(p)[7:11] == [1, 4, 2, 196] for p in flat)


def test_voluntary_stop_then_reboot_does_not_start():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, False)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        await hub.async_resume_desired_pumps()
        assert bus.sequences == []

    asyncio.run(_run())


def test_desired_run_reboot_resumes_rpm():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        await hub.async_resume_desired_pumps()
        assert _rpm_packets(bus)

    asyncio.run(_run())


def test_panel_mode_reboot_keeps_local_no_rpm_resume():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        hub.set_hands_off(1, True)
        await hub.async_resume_desired_pumps()
        flat = [b for seq in bus.sequences for b in seq]
        assert any(list(p)[7:10] == [4, 1, 0] for p in flat)
        assert not _rpm_packets(bus)

    asyncio.run(_run())


def test_panel_blocks_side_effects_on_rpm():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_hands_off(1, True)
        hub.set_should_run(1, False)
        before = len(bus.sequences)
        await hub.async_run_rpm(1, 2500)
        assert len(bus.sequences) == before
        assert hub.should_run(1) is False
        assert hub.get_target_rpm(1) is None

    asyncio.run(_run())


def test_watchdog_outage_reapplies_when_not_panel():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_mode(1, 2)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        hub._status[1] = _status(mode=0, run=4, rpm=0)
        await hub.async_recover_mode(1, delay=0)
        assert _rpm_packets(bus)

    asyncio.run(_run())


def test_watchdog_skipped_in_panel_mode():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_mode(1, 2)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        hub.set_hands_off(1, True)
        hub._status[1] = _status(mode=0, run=4, rpm=0)
        before = len(bus.sequences)
        await hub.async_recover_mode(1, delay=0)
        assert len(bus.sequences) == before

    asyncio.run(_run())


def test_cover_boost_skipped_and_restore_deferred_in_panel_mode():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_hands_off(1, True)
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
        before = len(bus.sequences)
        await ctrl._async_apply_boost(1)
        assert len(bus.sequences) == before
        assert ctrl.is_boost_active(1) is False

        # Simulate active boost then panel mode, cover closes — keep snapshot
        hub.set_hands_off(1, False)
        await ctrl._async_apply_boost(1)
        assert ctrl.is_boost_active(1) is True
        hub.set_hands_off(1, True)
        n = len(bus.sequences)
        await ctrl._async_restore(1)
        assert len(bus.sequences) == n
        assert ctrl.is_boost_active(1) is True  # deferred, still marked active

    asyncio.run(_run())
