"""Tests for panel-control (hands_off) switch semantics."""

import asyncio

from custom_components.pentair_rs485.hub import PentairHub, PumpConfig
from custom_components.pentair_rs485.rs485.packets import (
    CommandProfile,
    PumpType,
)


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


def test_panel_control_blocks_ha_commands():
    async def _run() -> None:
        bus = _RecordingBus()
        hub = PentairHub(
            bus=bus,  # type: ignore[arg-type]
            app_address=33,
            pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VS)],
        )
        await hub.async_set_panel_control(1, True)
        assert hub.is_hands_off(1) is True
        before = len(bus.sequences)
        await hub.async_run_rpm(1, 2000)
        assert len(bus.sequences) == before  # ignored

    asyncio.run(_run())


def test_panel_control_off_reapplies_desired_setpoint():
    async def _run() -> None:
        bus = _RecordingBus()
        hub = PentairHub(
            bus=bus,  # type: ignore[arg-type]
            app_address=33,
            pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VS)],
        )
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        await hub.async_set_panel_control(1, True)
        await hub.async_set_panel_control(1, False)
        assert hub.is_hands_off(1) is False
        flat = [b for seq in bus.sequences for b in seq]
        assert any(list(p)[7:13] == [1, 4, 2, 196, 7, 208] for p in flat)

    asyncio.run(_run())


def test_resume_skips_when_panel_control_persisted():
    async def _run() -> None:
        bus = _RecordingBus()
        hub = PentairHub(
            bus=bus,  # type: ignore[arg-type]
            app_address=33,
            pumps=[PumpConfig(index=1, name="Pool", pump_type=PumpType.VS)],
        )
        hub.set_should_run(1, True)
        hub.set_target_rpm(1, 2000)
        hub._command_profile[1] = CommandProfile.RPM
        hub.set_hands_off(1, True)
        before = len(bus.sequences)
        await hub.async_resume_desired_pumps()
        # Only local-control assert, no RPM resume
        flat = [b for seq in bus.sequences[before:] for b in seq]
        assert any(list(p)[7:10] == [4, 1, 0] for p in flat)
        assert not any(list(p)[7:11] == [1, 4, 2, 196] for p in flat)

    asyncio.run(_run())
