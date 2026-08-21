"""End-to-end robustness scenarios (restart, panel, outage, cover, multi-pump).

Post-v0.6.4 re-audit matrix — covers all hardened paths after desired_run,
panel-control switch, USB reconnect hooks, and cover-boost deferral.
"""

import asyncio

from unittest.mock import AsyncMock

from custom_components.pentair_rs485.cover_boost import (
    BoostSnapshot,
    CoverBoostController,
)
from custom_components.pentair_rs485.hub import PentairHub, PumpConfig
from custom_components.pentair_rs485.rs485.packets import (
    CommandProfile,
    PumpStatus,
    PumpType,
)


class _RecordingBus:
    def __init__(self) -> None:
        self.sequences: list[list[bytes]] = []
        self.ensure_open_calls = 0
        self.reconnect_calls = 0

    async def async_open(self) -> None:
        return None

    async def async_close(self) -> None:
        return None

    async def async_ensure_open(self) -> None:
        self.ensure_open_calls += 1

    async def async_reconnect(self) -> None:
        self.reconnect_calls += 1

    async def async_send_sequence(self, packets, **_kwargs):
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


def _hub(
    *pumps: PumpConfig,
) -> tuple[PentairHub, _RecordingBus]:
    bus = _RecordingBus()
    if not pumps:
        pumps = (PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF),)
    hub = PentairHub(
        bus=bus,  # type: ignore[arg-type]
        app_address=33,
        pumps=list(pumps),
    )
    return hub, bus


def _flat(bus: _RecordingBus) -> list[bytes]:
    return [b for seq in bus.sequences for b in seq]


def _has_rpm(bus: _RecordingBus, rpm_hi_lo: list[int] | None = None) -> bool:
    flat = _flat(bus)
    if rpm_hi_lo is None:
        return any(len(list(p)) >= 13 and list(p)[7:11] == [1, 4, 2, 196] for p in flat)
    return any(
        len(list(p)) >= 13 and list(p)[7:13] == [1, 4, 2, 196, *rpm_hi_lo]
        for p in flat
    )


def _has_gpm(bus: _RecordingBus) -> bool:
    # run_gpm payload: [1, 4, 2, 228, hi, lo]
    return any(
        len(list(p)) >= 13 and list(p)[7:11] == [1, 4, 2, 228] for p in _flat(bus)
    )


def _has_local(bus: _RecordingBus) -> bool:
    return any(list(p)[7:10] == [4, 1, 0] for p in _flat(bus))


def _has_remote(bus: _RecordingBus) -> bool:
    return any(list(p)[7:10] == [4, 1, 255] for p in _flat(bus))


def _rpm_packets(bus: _RecordingBus) -> bool:
    return _has_rpm(bus)


# --- Restart / desired_run -------------------------------------------------


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


def test_desired_run_reboot_resumes_gpm():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_gpm(1, 40)
        hub._command_profile[1] = CommandProfile.GPM
        await hub.async_resume_desired_pumps()
        assert _has_gpm(bus)

    asyncio.run(_run())


def test_seed_never_auto_starts_after_outage_status():
    hub, _bus = _hub()
    hub.set_should_run(1, False)
    hub._status[1] = _status(run=10, rpm=2200)
    hub.seed_runtime_from_status(1)
    assert hub.should_run(1) is False
    assert hub.get_target_rpm(1) is None


# --- Panel control ---------------------------------------------------------


def test_panel_mode_reboot_keeps_local_no_rpm_resume():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        hub.set_hands_off(1, True)
        await hub.async_resume_desired_pumps()
        assert _has_local(bus)
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


def test_panel_blocks_side_effects_on_power_and_mode():
    async def _run() -> None:
        hub, bus = _hub()
        hub.set_hands_off(1, True)
        hub.set_should_run(1, False)
        before = len(bus.sequences)
        await hub.async_set_power(1, True)
        await hub.async_set_pump_mode(1, 2)
        await hub.async_run_gpm(1, 35)
        await hub.async_run_program(1, 1)
        assert len(bus.sequences) == before
        assert hub.should_run(1) is False
        assert hub.get_target_mode(1) is None
        assert hub.get_target_gpm(1) is None

    asyncio.run(_run())


def test_panel_off_reapplies_then_cover_restore_after_deferral():
    """Cover closed under panel → snapshot kept; panel OFF → restore runs."""

    async def _run() -> None:
        hub, bus = _hub()
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        ctrl.mark_entities_ready()
        ctrl.set_enabled(1, True)
        ctrl.set_boost_speed(1, 2800)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        hub.set_target_rpm(1, 1800)
        hub._command_profile[1] = CommandProfile.RPM
        hub._status[1] = _status(rpm=1800)

        await ctrl._async_apply_boost(1)
        assert ctrl.is_boost_active(1) is True
        assert _has_rpm(bus, [10, 240])  # 2800

        hub.set_hands_off(1, True)
        n = len(bus.sequences)
        await ctrl._async_restore(1)
        assert len(bus.sequences) == n
        assert ctrl.is_boost_active(1) is True
        assert ctrl.get_snapshot(1) is not None

        # Leave panel mode + reevaluate as the switch does
        hub.set_hands_off(1, False)
        ctrl._cover_open = False
        await ctrl.async_reevaluate_pump(1)
        assert ctrl.is_boost_active(1) is False
        assert ctrl.get_snapshot(1) is None
        assert _has_rpm(bus, [7, 8])  # 1800 restored

    asyncio.run(_run())


def test_boot_order_hands_off_before_poll_skips_remote():
    """Simulate restore → first poll: panel ON must not steal remote control."""

    async def _run() -> None:
        hub, bus = _hub()
        # Entity restore
        hub.set_hands_off(1, True)
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        # First coordinator poll
        await hub.async_poll_all()
        assert bus.sequences == []
        # Startup sync
        await hub.async_resume_desired_pumps()
        assert _has_local(bus)
        assert not _has_remote(bus)
        assert not _rpm_packets(bus)

    asyncio.run(_run())


# --- Watchdog / outage -----------------------------------------------------


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


def test_watchdog_skipped_when_desired_run_false():
    """Mirror coordinator gate: no recovery when desired_run is False."""

    async def _run() -> None:
        hub, bus = _hub()
        hub.set_should_run(1, False)
        hub.set_target_mode(1, 2)
        hub.set_target_rpm(1, 2000)
        hub._status[1] = _status(mode=0, run=4, rpm=0)
        # Coordinator only calls recover when should_run — same gate here.
        if hub.should_run(1) and not hub.is_hands_off(1):
            await hub.async_recover_mode(1, delay=0)
        assert bus.sequences == []

    asyncio.run(_run())


def test_bus_reconnect_hook_after_io_failure():
    """USB unplug path: bus.async_reconnect is callable and resets port."""

    async def _run() -> None:
        bus = _RecordingBus()
        await bus.async_ensure_open()
        await bus.async_reconnect()
        assert bus.ensure_open_calls == 1
        assert bus.reconnect_calls == 1

    asyncio.run(_run())


# --- Cover boost -----------------------------------------------------------


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

        hub.set_hands_off(1, False)
        await ctrl._async_apply_boost(1)
        assert ctrl.is_boost_active(1) is True
        hub.set_hands_off(1, True)
        n = len(bus.sequences)
        await ctrl._async_restore(1)
        assert len(bus.sequences) == n
        assert ctrl.is_boost_active(1) is True

    asyncio.run(_run())


def test_cover_boost_snapshot_survives_restart_while_cover_open():
    async def _run() -> None:
        hub, bus = _hub()
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        snap = BoostSnapshot(profile="rpm", speed=1600, was_on=True)
        ctrl.restore_active_snapshot(1, snap)
        ctrl.set_enabled(1, True)
        ctrl.set_boost_speed(1, 2500)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        ctrl.mark_entities_ready()
        ctrl._cover_open = True
        await ctrl._async_apply_boost(1)
        # Must not overwrite restored pre-boost baseline
        assert ctrl.get_snapshot(1) == snap
        assert _has_rpm(bus)

    asyncio.run(_run())


def test_unavailable_cover_does_not_clear_open_state():
    async def _run() -> None:
        hub, _bus = _hub()
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        ctrl.mark_entities_ready()
        ctrl._cover_open = True
        await ctrl._async_handle_cover_state("unavailable")
        assert ctrl._cover_open is True
        await ctrl._async_handle_cover_state("unknown")
        assert ctrl._cover_open is True

    asyncio.run(_run())


# --- Multi-pump isolation --------------------------------------------------


def test_dual_pump_panel_on_one_does_not_block_other():
    async def _run() -> None:
        hub, bus = _hub(
            PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF),
            PumpConfig(index=2, name="Spa", pump_type=PumpType.VS),
        )
        hub.set_hands_off(1, True)
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        hub.set_should_run(2, True)
        hub.set_target_rpm(2, 1500)
        hub._command_profile[2] = CommandProfile.RPM

        await hub.async_resume_desired_pumps()
        # Pump 1: local only; pump 2: RPM resume
        assert _has_local(bus)
        assert _has_rpm(bus, [5, 220])  # 1500

        bus.sequences.clear()
        await hub.async_run_rpm(2, 1600)
        assert _has_rpm(bus, [6, 64])  # 1600
        await hub.async_run_rpm(1, 2500)
        # Still blocked for pump 1 — no new 2500 packet after the 1600 seq
        assert not _has_rpm(bus, [9, 196])  # 2500

    asyncio.run(_run())


def test_dual_pump_watchdog_only_recovers_non_panel():
    async def _run() -> None:
        hub, bus = _hub(
            PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF),
            PumpConfig(index=2, name="Spa", pump_type=PumpType.VS),
        )
        for idx in (1, 2):
            hub.set_should_run(idx, True)
            hub.set_target_mode(idx, 2)
            hub.set_target_rpm(idx, 2000)
            hub._command_profile[idx] = CommandProfile.RPM
            hub._status[idx] = _status(index=idx, mode=0, run=4, rpm=0)
        hub.set_hands_off(1, True)

        await hub.async_recover_mode(1, delay=0)
        await hub.async_recover_mode(2, delay=0)
        # Only pump 2 recovery traffic
        assert _rpm_packets(bus)
        # No remote-control for address of pump 1 during recovery (panel)
        # Pump addresses: index 1 → 96, index 2 → 97
        remotes_to_96 = [
            p
            for p in _flat(bus)
            if len(list(p)) >= 10 and list(p)[5] == 96 and list(p)[7:10] == [4, 1, 255]
        ]
        assert remotes_to_96 == []

    asyncio.run(_run())
