"""Tests for cover-open boost helper logic."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.pentair_rs485.cover_boost import CoverBoostController
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
        self._status = SimpleNamespace(is_on=True)

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


def test_raw_is_open_and_invert():
    ctrl = CoverBoostController(
        _FakeHass(),  # type: ignore[arg-type]
        _FakeHub(),  # type: ignore[arg-type]
        _FakeCoordinator(),  # type: ignore[arg-type]
        cover_entity_id="binary_sensor.volet",
        cover_invert=False,
    )
    assert ctrl._raw_is_open("on") is True
    assert ctrl._raw_is_open("off") is False
    assert ctrl._raw_is_open("open") is True
    ctrl.cover_invert = True
    assert ctrl._raw_is_open("on") is False
    assert ctrl._raw_is_open("off") is True


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
        ctrl.set_enabled(1, True)
        ctrl.set_boost_profile(1, CommandProfile.RPM)
        ctrl.set_boost_speed(1, 2500)
        ctrl._cover_open = True
        await ctrl._async_apply_boost(1)
        hub.async_run_rpm.assert_awaited_with(1, 2500)
        assert ctrl.is_boost_active(1) is True
        await ctrl._async_restore(1)
        hub.async_run_rpm.assert_awaited_with(1, 1200)
        assert ctrl.is_boost_active(1) is False

    asyncio.run(_run())
