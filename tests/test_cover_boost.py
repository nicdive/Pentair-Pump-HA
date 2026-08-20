"""Tests for cover-open boost helper logic."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.pentair_rs485.cover_boost import (
    BoostSnapshot,
    CoverBoostController,
)
from custom_components.pentair_rs485.rs485.packets import CommandProfile


class _FakeHass:
    def __init__(self) -> None:
        self.states = SimpleNamespace(get=lambda _eid: None)

    def async_create_task(self, coro):
        return asyncio.get_event_loop().create_task(coro)


class _FakeHub:
    def __init__(self) -> None:
        self.pumps = [SimpleNamespace(index=1)]
        self.async_run_rpm = AsyncMock()
        self.async_run_gpm = AsyncMock()
        self.async_set_power = AsyncMock()
        self._profile = CommandProfile.RPM
        self._rpm = 1200
        self._gpm = None
        self._status = SimpleNamespace(is_on=True, rpm=1200, gpm=0)

    def get_command_profile(self, index: int) -> CommandProfile:
        return self._profile

    def get_target_rpm(self, index: int):
        return self._rpm

    def get_target_gpm(self, index: int):
        return self._gpm

    def get_status(self, index: int):
        return self._status


class _FakeCoordinator:
    def __init__(self) -> None:
        self.async_request_refresh = AsyncMock()


def _ctrl(**kwargs) -> CoverBoostController:
    return CoverBoostController(
        _FakeHass(),  # type: ignore[arg-type]
        _FakeHub(),  # type: ignore[arg-type]
        _FakeCoordinator(),  # type: ignore[arg-type]
        cover_entity_id="binary_sensor.volet",
        **kwargs,
    )


def test_raw_is_open_and_invert():
    ctrl = _ctrl(cover_invert=False)
    assert ctrl._raw_is_open("on") is True
    assert ctrl._raw_is_open("off") is False
    assert ctrl._raw_is_open("open") is True
    assert ctrl._raw_is_open("unavailable") is None
    assert ctrl._raw_is_open("unknown") is None
    ctrl.cover_invert = True
    assert ctrl._raw_is_open("on") is False
    assert ctrl._raw_is_open("off") is True


def test_ignore_unavailable_does_not_flip_cover():
    async def _run() -> None:
        ctrl = _ctrl()
        ctrl.mark_entities_ready()
        ctrl.set_enabled(1, True)
        ctrl.set_boost_speed(1, 2500)
        await ctrl._async_handle_cover_state("on")
        assert ctrl.is_cover_open() is True
        await ctrl._async_handle_cover_state("unavailable")
        assert ctrl.is_cover_open() is True

    asyncio.run(_run())


def test_apply_and_restore_rpm():
    async def _run() -> None:
        hub = _FakeHub()
        coord = _FakeCoordinator()
        ctrl = CoverBoostController(
            _FakeHass(),  # type: ignore[arg-type]
            hub,  # type: ignore[arg-type]
            coord,  # type: ignore[arg-type]
            cover_entity_id="binary_sensor.volet",
        )
        ctrl.mark_entities_ready()
        ctrl.set_enabled(1, True)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        ctrl.set_boost_speed(1, 2500)
        ctrl._cover_open = True
        await ctrl._async_apply_boost(1)
        hub.async_run_rpm.assert_awaited_with(1, 2500)
        assert ctrl.is_boost_active(1) is True
        snap = ctrl.get_snapshot(1)
        assert snap is not None
        assert snap.speed == 1200
        await ctrl._async_restore(1)
        hub.async_run_rpm.assert_awaited_with(1, 1200)
        assert ctrl.is_boost_active(1) is False

    asyncio.run(_run())


def test_restore_snapshot_survives_restart_semantics():
    snap = BoostSnapshot.from_dict(
        {"profile": "rpm", "speed": 1500, "was_on": True}
    )
    assert snap is not None
    ctrl = _ctrl()
    ctrl.restore_active_snapshot(1, snap)
    assert ctrl.is_boost_active(1) is True
    assert ctrl.get_snapshot(1).speed == 1500
