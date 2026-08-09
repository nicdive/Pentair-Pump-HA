"""Data update coordinator for Pentair RS485 pumps."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WATCHDOG_ENABLED,
    DEFAULT_WATCHDOG_RECOVERY_DELAY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class PentairPumpCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Poll pump status over RS485."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub,
        *,
        watchdog_enabled: bool = DEFAULT_WATCHDOG_ENABLED,
        watchdog_delay: int = DEFAULT_WATCHDOG_RECOVERY_DELAY,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.hub = hub
        self._watchdog_enabled = watchdog_enabled
        self._watchdog_delay = watchdog_delay
        self._recovery_pending: set[int] = set()

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            await self.hub.async_poll_all()
        except OSError as err:
            raise UpdateFailed(f"RS485 communication failed: {err}") from err

        data: dict[int, dict] = {}
        for pump in self.hub.pumps:
            data[pump.index] = self.hub.status_dict(pump.index, pump)
            if self._watchdog_enabled and self.hub.get_status(pump.index):
                self._maybe_schedule_recovery(pump.index, data[pump.index])
        return data

    def _maybe_schedule_recovery(self, index: int, pump_data: dict) -> None:
        if not self.hub.should_run(index):
            return
        if self.hub.is_hands_off(index):
            return
        if self.hub.is_recovery_in_progress(index) or index in self._recovery_pending:
            return

        target_mode = self.hub.get_target_mode(index)
        measured_mode = pump_data.get("mode")
        if target_mode is None or measured_mode == target_mode:
            return

        _LOGGER.warning(
            "Watchdog pump %s mode target=%s measured=%s",
            index,
            pump_data.get("target_mode_label"),
            pump_data.get("mode_label"),
        )
        self._recovery_pending.add(index)
        self.hass.async_create_task(self._run_recovery(index))

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
