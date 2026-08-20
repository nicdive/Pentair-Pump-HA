"""Pool cover open → temporary pump speed boost."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from .const import CONF_COVER_ENTITY, CONF_COVER_INVERT, DEFAULT_COVER_INVERT
from .rs485.packets import CommandProfile

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

    from .coordinator import PentairPumpCoordinator
    from .hub import PentairHub

_LOGGER = logging.getLogger(__name__)

# Mirror homeassistant.const values (avoid hard HA import at module load for unit tests).
_STATE_ON = "on"
_STATE_OPEN = "open"
_STATE_OPENING = "opening"
_STATE_UNAVAILABLE = "unavailable"
_STATE_UNKNOWN = "unknown"
_OPEN_STATES = {_STATE_ON, _STATE_OPEN, _STATE_OPENING}
_IGNORE_STATES = {_STATE_UNAVAILABLE, _STATE_UNKNOWN, None, ""}


@dataclass
class BoostSnapshot:
    profile: str
    speed: int | None
    was_on: bool

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BoostSnapshot | None:
        if not data:
            return None
        try:
            profile = str(data["profile"])
            if profile not in ("rpm", "gpm"):
                return None
            speed = data.get("speed")
            return cls(
                profile=profile,
                speed=int(speed) if speed is not None else None,
                was_on=bool(data.get("was_on", False)),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def command_profile(self) -> CommandProfile:
        return CommandProfile(self.profile)


class CoverBoostController:
    """Listen to a cover/binary_sensor and raise pump speed while open."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: PentairHub,
        coordinator: PentairPumpCoordinator,
        *,
        cover_entity_id: str | None,
        cover_invert: bool = DEFAULT_COVER_INVERT,
    ) -> None:
        self.hass = hass
        self.hub = hub
        self.coordinator = coordinator
        self.cover_entity_id = cover_entity_id
        self.cover_invert = cover_invert
        self._unsub = None
        self._enabled: dict[int, bool] = {}
        self._boost_speed: dict[int, int] = {}
        self._boost_profile: dict[int, CommandProfile] = {}
        self._active: dict[int, bool] = {}
        self._snapshot: dict[int, BoostSnapshot] = {}
        self._cover_open: bool | None = None
        self._entities_ready = False

    def mark_entities_ready(self) -> None:
        """Entities have restored their last states; safe to act on cover."""
        self._entities_ready = True

    def is_enabled(self, index: int) -> bool:
        return self._enabled.get(index, False)

    def set_enabled(self, index: int, enabled: bool) -> None:
        self._enabled[index] = enabled
        _LOGGER.info("Cover boost pump %s enabled=%s", index, enabled)

    def get_boost_speed(self, index: int) -> int | None:
        return self._boost_speed.get(index)

    def set_boost_speed(self, index: int, speed: int) -> None:
        self._boost_speed[index] = speed

    def get_boost_profile(self, index: int) -> CommandProfile:
        if index in self._boost_profile:
            return self._boost_profile[index]
        return self.hub.get_command_profile(index)

    def set_boost_profile(self, index: int, profile: CommandProfile) -> None:
        self._boost_profile[index] = profile

    def is_boost_active(self, index: int) -> bool:
        return self._active.get(index, False)

    def get_snapshot(self, index: int) -> BoostSnapshot | None:
        return self._snapshot.get(index)

    def restore_active_snapshot(self, index: int, snap: BoostSnapshot) -> None:
        """After HA restart: remember pre-boost baseline while cover still open."""
        self._snapshot[index] = snap
        self._active[index] = True

    def is_cover_open(self) -> bool | None:
        return self._cover_open

    async def async_setup(self) -> None:
        """Subscribe to cover changes; do not apply boost until entities are ready."""
        if not self.cover_entity_id:
            _LOGGER.info("Cover boost: no cover entity configured")
            return
        from homeassistant.helpers.event import async_track_state_change_event

        self._unsub = async_track_state_change_event(
            self.hass, [self.cover_entity_id], self._async_cover_changed
        )

    async def async_startup_sync(self) -> None:
        """Call after platforms restored: sync cover state and apply if needed."""
        self.mark_entities_ready()
        if not self.cover_entity_id:
            return
        state = self.hass.states.get(self.cover_entity_id)
        if state is None or state.state in _IGNORE_STATES:
            _LOGGER.info(
                "Cover boost startup: cover %s not ready yet (state=%s)",
                self.cover_entity_id,
                None if state is None else state.state,
            )
            return
        await self._async_handle_cover_state(state.state, force=True)

    async def async_shutdown(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def _async_cover_changed(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        self.hass.async_create_task(self._async_handle_cover_state(new_state.state))

    def _raw_is_open(self, state: str) -> bool | None:
        if state in _IGNORE_STATES:
            return None
        open_ = state in _OPEN_STATES
        return (not open_) if self.cover_invert else open_

    async def _async_handle_cover_state(
        self, state: str, *, force: bool = False
    ) -> None:
        is_open = self._raw_is_open(state)
        if is_open is None:
            _LOGGER.debug("Cover boost ignoring transient state %s", state)
            return
        if not force and self._cover_open is is_open:
            return
        previous = self._cover_open
        self._cover_open = is_open
        _LOGGER.info(
            "Cover %s state=%s open=%s (was %s) entities_ready=%s",
            self.cover_entity_id,
            state,
            is_open,
            previous,
            self._entities_ready,
        )
        if not self._entities_ready:
            return
        if is_open:
            await self._async_apply_boost_all()
        elif previous is True or (force and not is_open):
            await self._async_restore_all()

    async def async_reevaluate_pump(self, index: int) -> None:
        """Called when enable switch or boost setpoint changes."""
        if self._cover_open is None and self.cover_entity_id:
            state = self.hass.states.get(self.cover_entity_id)
            if state is not None:
                parsed = self._raw_is_open(state.state)
                if parsed is not None:
                    self._cover_open = parsed
        if not self._entities_ready:
            return
        if self._cover_open and self.is_enabled(index):
            await self._async_apply_boost(index)
        elif self.is_boost_active(index) and (
            not self._cover_open or not self.is_enabled(index)
        ):
            await self._async_restore(index)

    async def _async_apply_boost_all(self) -> None:
        for pump in self.hub.pumps:
            if self.is_enabled(pump.index):
                await self._async_apply_boost(pump.index)

    async def _async_restore_all(self) -> None:
        for pump in self.hub.pumps:
            if self.is_boost_active(pump.index):
                await self._async_restore(pump.index)

    async def _async_apply_boost(self, index: int) -> None:
        if self.hub.is_hands_off(index):
            _LOGGER.info(
                "Cover boost skipped pump %s — panel control active", index
            )
            return
        speed = self.get_boost_speed(index)
        if speed is None:
            _LOGGER.warning("Cover boost pump %s: no boost speed set", index)
            return
        profile = self.get_boost_profile(index)
        if not self.is_boost_active(index):
            prev_profile = self.hub.get_command_profile(index)
            if prev_profile == CommandProfile.GPM:
                prev_speed = self.hub.get_target_gpm(index)
                if prev_speed is None:
                    status = self.hub.get_status(index)
                    prev_speed = status.gpm if status and status.gpm else None
            else:
                prev_speed = self.hub.get_target_rpm(index)
                if prev_speed is None:
                    status = self.hub.get_status(index)
                    prev_speed = status.rpm if status and status.rpm else None
            status = self.hub.get_status(index)
            self._snapshot[index] = BoostSnapshot(
                profile=prev_profile.value,
                speed=prev_speed,
                was_on=bool(status and status.is_on),
            )
        _LOGGER.info("Cover boost pump %s → %s %s", index, speed, profile.value)
        try:
            if profile == CommandProfile.GPM:
                await self.hub.async_run_gpm(index, speed)
            else:
                await self.hub.async_run_rpm(index, speed)
            self._active[index] = True
            await self.coordinator.async_request_refresh()
        except (OSError, ValueError) as err:
            _LOGGER.error("Cover boost failed pump %s: %s", index, err)

    async def _async_restore(self, index: int) -> None:
        if self.hub.is_hands_off(index):
            _LOGGER.info(
                "Cover boost restore deferred pump %s — panel control active",
                index,
            )
            return
        snap = self._snapshot.pop(index, None)
        self._active[index] = False
        if snap is None:
            return
        _LOGGER.info(
            "Cover boost restore pump %s profile=%s speed=%s was_on=%s",
            index,
            snap.profile,
            snap.speed,
            snap.was_on,
        )
        try:
            if snap.speed is not None:
                if snap.command_profile == CommandProfile.GPM:
                    await self.hub.async_run_gpm(index, snap.speed)
                else:
                    await self.hub.async_run_rpm(index, snap.speed)
            elif not snap.was_on:
                await self.hub.async_set_power(index, False)
            await self.coordinator.async_request_refresh()
        except (OSError, ValueError) as err:
            _LOGGER.error("Cover boost restore failed pump %s: %s", index, err)


def cover_options_from_entry(entry: Any) -> tuple[str | None, bool]:
    options = entry.options or {}
    entity = options.get(CONF_COVER_ENTITY) or None
    if isinstance(entity, str) and not entity.strip():
        entity = None
    invert = bool(options.get(CONF_COVER_INVERT, DEFAULT_COVER_INVERT))
    return entity, invert
