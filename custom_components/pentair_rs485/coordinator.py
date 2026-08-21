"""Data update coordinator for Pentair RS485 pumps."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WATCHDOG_ENABLED,
    DEFAULT_WATCHDOG_GPM_TOLERANCE,
    DEFAULT_WATCHDOG_RECOVERY_DELAY,
    DEFAULT_WATCHDOG_TOLERANCE,
    DOMAIN,
)
from .rs485.packets import CommandProfile

_LOGGER = logging.getLogger(__name__)


class PentairPumpCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Poll pump status over RS485."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub,
        *,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        watchdog_enabled: bool = DEFAULT_WATCHDOG_ENABLED,
        watchdog_delay: int = DEFAULT_WATCHDOG_RECOVERY_DELAY,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.data = {}
        self.hub = hub
        self.cover_boost = None
        self._watchdog_enabled = watchdog_enabled
        self._watchdog_delay = watchdog_delay
        self._recovery_pending: set[int] = set()
        self._recovery_tasks: set = set()

    def _status_payload(self) -> dict[int, dict]:
        data: dict[int, dict] = {}
        for pump in self.hub.pumps:
            if self.hub.is_pump_online(pump.index):
                self.hub.seed_runtime_from_status(pump.index)
            data[pump.index] = self.hub.status_dict(pump.index, pump)
            if self._watchdog_enabled and self.hub.get_status(pump.index):
                self._maybe_schedule_recovery(pump.index, data[pump.index])
        return data

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            await self.hub.bus.async_ensure_open()
            await self.hub.async_poll_all()
        except OSError as err:
            _LOGGER.warning("RS485 poll failed, attempting reconnect: %s", err)
            try:
                await self.hub.bus.async_reconnect()
                await self.hub.async_poll_all()
            except OSError as err2:
                _LOGGER.error("RS485 communication failed: %s", err2)
                # Keep last known values so entities stay usable (panel switch, etc.).
                return self._status_payload()

        return self._status_payload()

    def _maybe_schedule_recovery(self, index: int, pump_data: dict) -> None:
        if not self.hub.should_run(index):
            return
        if self.hub.is_hands_off(index):
            return
        if self.cover_boost is not None and self.cover_boost.is_boost_active(index):
            return
        if self.hub.is_recovery_in_progress(index) or index in self._recovery_pending:
            return

        status = self.hub.get_status(index)
        if status is None:
            return
        if status.is_priming:
            return

        target_mode = self.hub.get_target_mode(index)
        measured_mode = pump_data.get("mode")
        mode_ok = target_mode is None or measured_mode == target_mode
        needs_speed = False
        if self.hub.should_run(index) and not status.is_on:
            needs_speed = (
                self.hub.get_target_rpm(index) is not None
                or self.hub.get_target_gpm(index) is not None
            )
        elif mode_ok and status.is_on:
            # Power-loss can leave the pump "on" in the right mode at the wrong speed.
            profile = self.hub.get_command_profile(index)
            if profile == CommandProfile.GPM:
                target = self.hub.get_target_gpm(index)
                if target is not None and abs(status.gpm - target) > DEFAULT_WATCHDOG_GPM_TOLERANCE:
                    needs_speed = True
            else:
                target = self.hub.get_target_rpm(index)
                if target is not None and abs(status.rpm - target) > DEFAULT_WATCHDOG_TOLERANCE:
                    needs_speed = True

        if mode_ok and not needs_speed:
            return

        _LOGGER.warning(
            "Watchdog pump %s mode target=%s measured=%s on=%s rpm=%s gpm=%s",
            index,
            pump_data.get("target_mode_label"),
            pump_data.get("mode_label"),
            status.is_on,
            status.rpm,
            status.gpm,
        )
        self._recovery_pending.add(index)
        task = self.hass.async_create_task(self._run_recovery(index))
        self._recovery_tasks.add(task)
        task.add_done_callback(self._recovery_tasks.discard)

    async def async_shutdown(self) -> None:
        for task in list(self._recovery_tasks):
            task.cancel()
        self._recovery_tasks.clear()
        self._recovery_pending.clear()

    async def _run_recovery(self, index: int) -> None:
        try:
            await self.hub.async_recover_mode(
                index, delay=float(self._watchdog_delay)
            )
            await self.async_request_refresh()
        except OSError as err:
            _LOGGER.error("Watchdog recovery failed pump %s: %s", index, err)
        finally:
            self._recovery_pending.discard(index)
