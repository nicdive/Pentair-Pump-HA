"""Tests for watchdog seeding / setpoint re-apply after outages."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

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

    async def async_send_sequence(self, packets, **_kwargs):
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


def test_seed_runtime_from_status_after_ha_restart():
    hub = PentairHub(
        bus=_FakeBus(),  # type: ignore[arg-type]
        app_address=33,
        pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VSF)],
    )
    hub.set_should_run(1, True)  # restored desired_run
    hub._status[1] = _status()
    assert hub.get_target_mode(1) is None
    hub.seed_runtime_from_status(1)
    assert hub.should_run(1) is True
    assert hub.get_target_mode(1) == 2
    assert hub.get_target_rpm(1) == 1800


def test_recover_reapplies_rpm_setpoint():
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
        hub._status[1] = _status(mode=0, run=4, rpm=0)
        await hub.async_recover_mode(1, delay=0)
        # Mode restore sequence then RPM re-apply sequence must both have been sent.
        assert len(bus.sequences) >= 2
        flat = [b for seq in bus.sequences for b in seq]
        # RPM setpoint 2000 = 0x07D0
        assert any(list(p)[7:13] == [1, 4, 2, 196, 7, 208] for p in flat)
        # Mode 2 packet present
        assert any(list(p)[7:10] == [5, 1, 2] for p in flat)

    asyncio.run(_run())


class _RecordingBus(_FakeBus):
    def __init__(self) -> None:
        self.sequences: list[list[bytes]] = []

    async def async_send_sequence(self, packets, **_kwargs):
        self.sequences.append(list(packets))
        return []
