"""Tests for desired_run resume semantics (no auto-start after voluntary stop)."""

import asyncio

from custom_components.pentair_rs485.hub import PentairHub, PumpConfig
from custom_components.pentair_rs485.rs485.packets import (
    CommandProfile,
    PumpStatus,
    PumpType,
)


class _FakeBus:
    async def async_open(self) -> None:
        return None

    async def async_close(self) -> None:
        return None

    async def async_send_sequence(self, packets):
        return []


class _RecordingBus(_FakeBus):
    def __init__(self) -> None:
        self.sequences: list[list[bytes]] = []

    async def async_send_sequence(self, packets):
        self.sequences.append(list(packets))
        return []


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


def test_seed_does_not_force_should_run_when_voluntarily_stopped():
    hub = PentairHub(
        bus=_FakeBus(),  # type: ignore[arg-type]
        app_address=33,
        pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF)],
    )
    hub.set_should_run(1, False)
    hub._status[1] = _status()
    hub.seed_runtime_from_status(1)
    assert hub.should_run(1) is False
    assert hub.get_target_rpm(1) is None


def test_seed_enriches_targets_only_when_desired_run():
    hub = PentairHub(
        bus=_FakeBus(),  # type: ignore[arg-type]
        app_address=33,
        pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF)],
    )
    hub.set_should_run(1, True)
    hub._status[1] = _status()
    hub.seed_runtime_from_status(1)
    assert hub.get_target_mode(1) == 2
    assert hub.get_target_rpm(1) == 1800


def test_resume_skips_when_desired_false():
    async def _run() -> None:
        bus = _RecordingBus()
        hub = PentairHub(
            bus=bus,  # type: ignore[arg-type]
            app_address=33,
            pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VS)],
        )
        hub.set_should_run(1, False)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        await hub.async_resume_desired_pumps()
        assert bus.sequences == []

    asyncio.run(_run())


def test_resume_runs_when_desired_true():
    async def _run() -> None:
        bus = _RecordingBus()
        hub = PentairHub(
            bus=bus,  # type: ignore[arg-type]
            app_address=33,
            pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VS)],
        )
        hub.set_should_run(1, True)
        hub.set_target_mode(1, 2)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        await hub.async_resume_desired_pumps()
        flat = [b for seq in bus.sequences for b in seq]
        assert any(list(p)[7:13] == [1, 4, 2, 196, 7, 208] for p in flat)

    asyncio.run(_run())
