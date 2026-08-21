"""High-level pump control (standalone mode command sequences)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from .const import DEFAULT_WATCHDOG_RECOVERY_DELAY, STALE_POLL_MISSES
from .rs485.bus import RS485Bus
from .rs485.modes import decode_drivestate, decode_error, decode_mode
from .rs485.packets import (
    CommandProfile,
    PumpStatus,
    PumpType,
    pump_index_to_address,
    request_status,
    run_gpm,
    run_program,
    run_rpm,
    save_program,
    set_local_control,
    set_manual_mode,
    set_power,
    set_pump_mode,
    set_remote_control,
    set_speed1_mode,
    validate_gpm,
    validate_rpm,
)

_LOGGER = logging.getLogger(__name__)


def _default_profile(pump_type: PumpType) -> CommandProfile:
    """Default RS485 command set from configured pump type."""
    if pump_type == PumpType.VF:
        return CommandProfile.GPM
    # VS and VSF default to RPM; VSF can switch to GPM via the select entity.
    return CommandProfile.RPM


@dataclass(slots=True)
class PumpConfig:
    index: int
    name: str
    pump_type: PumpType


@dataclass(slots=True)
class PentairHub:
    bus: RS485Bus
    app_address: int
    pumps: list[PumpConfig] = field(default_factory=list)
    _status: dict[int, PumpStatus] = field(default_factory=dict)
    _target_rpm: dict[int, int] = field(default_factory=dict)
    _target_gpm: dict[int, int] = field(default_factory=dict)
    _target_mode: dict[int, int] = field(default_factory=dict)
    _command_profile: dict[int, CommandProfile] = field(default_factory=dict)
    _should_run: dict[int, bool] = field(default_factory=dict)
    _display_active: dict[int, bool] = field(default_factory=dict)
    _hands_off: set[int] = field(default_factory=set)
    _saved_program: dict[tuple[int, int], int] = field(default_factory=dict)
    _recovery_in_progress: set[int] = field(default_factory=set)
    _poll_misses: dict[int, int] = field(default_factory=dict)
    _online: dict[int, bool] = field(default_factory=dict)

    async def async_setup(self) -> None:
        try:
            await self.bus.async_open()
        except OSError as err:
            _LOGGER.error("RS485 port %s could not be opened: %s", self.bus.port, err)
        for pump in self.pumps:
            if pump.index not in self._command_profile:
                self._command_profile[pump.index] = _default_profile(pump.pump_type)

    async def async_shutdown(self) -> None:
        self._recovery_in_progress.clear()
        await self.bus.async_close()

    def get_pump(self, index: int) -> PumpConfig | None:
        return next((p for p in self.pumps if p.index == index), None)

    def supports_rpm(self, index: int) -> bool:
        pump = self.get_pump(index)
        if pump is None:
            return True
        return pump.pump_type in (PumpType.VS, PumpType.VSF)

    def supports_gpm(self, index: int) -> bool:
        pump = self.get_pump(index)
        if pump is None:
            return True
        return pump.pump_type in (PumpType.VF, PumpType.VSF)

    def is_pump_online(self, index: int) -> bool:
        return self._online.get(index, False)

    def get_status(self, index: int) -> PumpStatus | None:
        return self._status.get(index)

    def get_target_rpm(self, index: int) -> int | None:
        return self._target_rpm.get(index)

    def get_target_gpm(self, index: int) -> int | None:
        return self._target_gpm.get(index)

    def get_command_profile(self, index: int) -> CommandProfile:
        """Active RS485 command set (RPM vs GPM), with mode-based fallback."""
        if index in self._command_profile:
            return self._command_profile[index]
        mode = self.get_target_mode(index)
        if mode == 1:
            return CommandProfile.GPM
        pump = next((p for p in self.pumps if p.index == index), None)
        if pump:
            return _default_profile(pump.pump_type)
        return CommandProfile.RPM

    def set_command_profile(self, index: int, profile: CommandProfile) -> None:
        self._command_profile[index] = profile
        if profile == CommandProfile.GPM:
            self.set_target_mode(index, 1)
        else:
            self.set_target_mode(index, 2)
        _LOGGER.info("Pump %s command profile set to %s", index, profile.value)

    def get_live_speed_for_save(self, index: int) -> int | None:
        status = self.get_status(index)
        if not status:
            return None
        profile = self.get_command_profile(index)
        if profile == CommandProfile.GPM and status.gpm:
            return status.gpm
        if profile == CommandProfile.RPM and status.rpm:
            return status.rpm
        return status.rpm or status.gpm or None

    def set_target_rpm(self, index: int, rpm: int) -> None:
        self._target_rpm[index] = rpm

    def set_target_gpm(self, index: int, gpm: int) -> None:
        self._target_gpm[index] = gpm

    def get_target_mode(self, index: int) -> int | None:
        return self._target_mode.get(index)

    def set_target_mode(self, index: int, mode: int) -> None:
        self._target_mode[index] = mode
        _LOGGER.info("Pump %s target mode set to %s (%s)", index, mode, decode_mode(mode))

    def get_saved_program_speed(self, index: int, program: int) -> int | None:
        return self._saved_program.get((index, program))

    def set_saved_program_speed(self, index: int, program: int, speed: int) -> None:
        self._saved_program[(index, program)] = speed

    def set_should_run(self, index: int, should_run: bool) -> None:
        self._should_run[index] = should_run

    def should_run(self, index: int) -> bool:
        return self._should_run.get(index, False)

    def is_display_active(self, index: int) -> bool:
        return self._display_active.get(index, False)

    def is_hands_off(self, index: int) -> bool:
        return index in self._hands_off

    def set_hands_off(self, index: int, enabled: bool) -> None:
        """Memory-only panel-control flag (used on HA state restore)."""
        if enabled:
            self._hands_off.add(index)
            self.set_display_active(index, True)
        else:
            self._hands_off.discard(index)
        _LOGGER.info("Pump %s hands_off=%s", index, enabled)

    def set_display_active(self, index: int, active: bool) -> None:
        self._display_active[index] = active
        _LOGGER.info("Pump %s display active set to %s", index, active)

    def is_recovery_in_progress(self, index: int) -> bool:
        return index in self._recovery_in_progress

    def status_dict(self, index: int, pump: PumpConfig) -> dict:
        status = self.get_status(index)
        online = self.is_pump_online(index)
        base = {
            "name": pump.name,
            "type": pump.pump_type.value,
            "display_active": self.is_display_active(index),
            "hands_off": self.is_hands_off(index),
            "desired_run": self.should_run(index),
            "online": online,
            "supports_rpm": self.supports_rpm(index),
            "supports_gpm": self.supports_gpm(index),
            "command_profile": self.get_command_profile(index).value,
            "program_1_speed": self.get_saved_program_speed(index, 1),
            "program_2_speed": self.get_saved_program_speed(index, 2),
            "program_3_speed": self.get_saved_program_speed(index, 3),
            "program_4_speed": self.get_saved_program_speed(index, 4),
            "target_mode": self.get_target_mode(index),
            "target_mode_label": (
                decode_mode(self.get_target_mode(index))
                if self.get_target_mode(index) is not None
                else None
            ),
            "target_rpm": self.get_target_rpm(index),
            "target_gpm": self.get_target_gpm(index),
        }
        if not status:
            base.update(
                {
                    "power": False,
                    "rpm": 0,
                    "gpm": 0,
                    "watts": 0,
                    "err": 0,
                    "err_label": "ok",
                    "mode": 0,
                    "mode_label": "filter",
                    "drivestate": 0,
                    "drivestate_label": "fault",
                    "ppc": 0,
                    "timer": 0,
                    "hour": 0,
                    "minute": 0,
                }
            )
            return base
        base.update(
            {
                "power": status.is_on,
                "rpm": status.rpm,
                "gpm": status.gpm,
                "watts": status.watts,
                "err": status.err,
                "err_label": decode_error(status.err),
                "mode": status.mode,
                "mode_label": decode_mode(status.mode),
                "drivestate": status.drivestate,
                "drivestate_label": decode_drivestate(status.drivestate),
                "ppc": status.ppc,
                "timer": status.timer,
                "hour": status.hour,
                "minute": status.minute,
            }
        )
        return base

    def _address(self, index: int) -> int:
        return pump_index_to_address(index)

    def _wrap_remote_sequence(self, index: int, middle: list[bytes]) -> list[bytes]:
        """Remote prefix; release to local panel when display-active mode is on."""
        address = self._address(index)
        packets = [set_remote_control(self.app_address, address)]
        packets.extend(middle)
        if self.is_display_active(index):
            packets.append(set_local_control(self.app_address, address))
        return packets

    def _resume_remote_control(self, index: int) -> None:
        self._hands_off.discard(index)

    def _panel_blocks(self, index: int, action: str) -> bool:
        if not self.is_hands_off(index):
            return False
        _LOGGER.warning(
            "Pump %s: panel control active — %s ignored "
            "(turn off « panel control » switch first)",
            index,
            action,
        )
        return True

    async def _run_command(self, index: int, middle: list[bytes]) -> PumpStatus | None:
        if self._panel_blocks(index, "HA command"):
            return self.get_status(index)
        return await self._run_sequence(
            index, self._wrap_remote_sequence(index, middle)
        )

    async def _run_sequence(self, index: int, packets: list[bytes]) -> PumpStatus | None:
        expects_status = any(_packet_is_status_request(packet) for packet in packets)
        responses = await self.bus.async_send_sequence(
            packets,
            expect_index=index if expects_status else None,
            wait_status=expects_status,
        )
        return self._store_responses(
            responses, index, count_miss=expects_status
        )

    async def async_set_pump_mode(self, index: int, mode: int) -> PumpStatus | None:
        if self._panel_blocks(index, "set mode"):
            return self.get_status(index)
        self.set_target_mode(index, mode)
        if mode == 1:
            self._command_profile[index] = CommandProfile.GPM
        elif mode == 2:
            self._command_profile[index] = CommandProfile.RPM
        address = self._address(index)
        _LOGGER.info("Set pump %s mode %s (address %s)", index, mode, address)
        return await self._run_command(
            index,
            [
                set_pump_mode(self.app_address, address, mode),
                request_status(self.app_address, address),
            ],
        )

    async def async_send_manual_mode(self, index: int) -> PumpStatus | None:
        """Wiki action 5 mode 1 = Manual flow (GPM)."""
        if self._panel_blocks(index, "manual flow"):
            return self.get_status(index)
        self.set_command_profile(index, CommandProfile.GPM)
        self.set_should_run(index, True)
        address = self._address(index)
        return await self._run_command(
            index,
            [
                set_manual_mode(self.app_address, address),
                request_status(self.app_address, address),
            ],
        )

    async def async_send_speed1_mode(self, index: int) -> PumpStatus | None:
        """Wiki action 5 mode 2 = Manual RPM (packet [5,1,2])."""
        if self._panel_blocks(index, "manual RPM"):
            return self.get_status(index)
        self.set_command_profile(index, CommandProfile.RPM)
        self.set_should_run(index, True)
        address = self._address(index)
        return await self._run_command(
            index,
            [
                set_speed1_mode(self.app_address, address),
                request_status(self.app_address, address),
            ],
        )

    async def async_set_display_active(self, index: int, active: bool) -> PumpStatus | None:
        """Toggle IntelliComm-style display mode (panel stays active between commands)."""
        self.set_display_active(index, active)
        address = self._address(index)
        if self.is_hands_off(index):
            # Panel-control mode owns local/remote; only remember the preference.
            return self.get_status(index)
        if active:
            return await self._run_sequence(
                index, [set_local_control(self.app_address, address)]
            )
        return await self._run_sequence(
            index,
            [
                set_remote_control(self.app_address, address),
                request_status(self.app_address, address),
            ],
        )

    async def async_set_panel_control(
        self, index: int, enabled: bool
    ) -> PumpStatus | None:
        """ON = physical panel owns the pump; OFF = return control to HA."""
        address = self._address(index)
        if enabled:
            self._hands_off.add(index)
            self.set_display_active(index, True)
            _LOGGER.info("Pump %s panel control ON (hands off HA)", index)
            return await self._run_sequence(
                index, [set_local_control(self.app_address, address)]
            )

        self._hands_off.discard(index)
        _LOGGER.info("Pump %s panel control OFF (HA remote)", index)
        status = await self._run_sequence(
            index,
            [
                set_remote_control(self.app_address, address),
                request_status(self.app_address, address),
            ],
        )
        if self.should_run(index):
            try:
                await self._async_reapply_setpoint(index)
            except (OSError, ValueError) as err:
                _LOGGER.error(
                    "Pump %s: failed to re-apply HA setpoint after panel control: %s",
                    index,
                    err,
                )
        elif self.is_display_active(index):
            await self._run_sequence(
                index, [set_local_control(self.app_address, address)]
            )
        return status

    async def async_release_to_pump(self, index: int) -> PumpStatus | None:
        """Compatibility alias — prefer async_set_panel_control(True)."""
        return await self.async_set_panel_control(index, True)

    async def async_send_local_control(self, index: int) -> PumpStatus | None:
        return await self.async_set_panel_control(index, True)

    async def async_recover_mode(
        self, index: int, delay: float = DEFAULT_WATCHDOG_RECOVERY_DELAY
    ) -> None:
        if self.is_hands_off(index):
            return
        if index in self._recovery_in_progress:
            return
        target_mode = self.get_target_mode(index)
        if target_mode is None:
            return
        status = self.get_status(index)
        if status and status.mode == target_mode:
            # Mode OK — still re-apply setpoint if pump stopped after power loss.
            if status.is_on:
                return
        self._recovery_in_progress.add(index)
        try:
            _LOGGER.warning(
                "Watchdog pump %s: restoring mode %s (was %s)",
                index,
                decode_mode(target_mode),
                decode_mode(status.mode) if status else "?",
            )
            await self.async_set_pump_mode(index, target_mode)
            await self._async_reapply_setpoint(index)
            await asyncio.sleep(delay)
        finally:
            self._recovery_in_progress.discard(index)

    async def _async_reapply_setpoint(self, index: int) -> PumpStatus | None:
        """Re-send last RPM/GPM after power loss (mode alone is not enough)."""
        profile = self.get_command_profile(index)
        if profile == CommandProfile.GPM:
            gpm = self.get_target_gpm(index)
            if gpm is not None:
                return await self.async_run_gpm(index, gpm)
        rpm = self.get_target_rpm(index)
        if rpm is not None:
            return await self.async_run_rpm(index, rpm)
        gpm = self.get_target_gpm(index)
        if gpm is not None:
            return await self.async_run_gpm(index, gpm)
        return None

    def seed_runtime_from_status(self, index: int) -> None:
        """If desired_run is set, adopt live mode/speed for watchdog continuity.

        Never flips should_run to True from live status alone — a voluntary stop
        before HA restart must not cause an auto-start.
        """
        if not self.should_run(index):
            return
        status = self.get_status(index)
        if not status:
            return
        if self.get_target_mode(index) is None:
            self.set_target_mode(index, status.mode)
        if status.mode == 1 and status.gpm and self.get_target_gpm(index) is None:
            self.set_target_gpm(index, status.gpm)
            self._command_profile[index] = CommandProfile.GPM
        elif status.rpm and self.get_target_rpm(index) is None:
            self.set_target_rpm(index, status.rpm)
            if status.mode == 2:
                self._command_profile[index] = CommandProfile.RPM

    async def async_resume_desired_pumps(self) -> None:
        """After HA start: re-apply setpoints only when desired_run was True.

        If the pump was stopped on purpose (desired_run False), do nothing.
        If panel control is active, leave the physical panel alone.
        """
        for pump in self.pumps:
            index = pump.index
            if self.is_hands_off(index):
                _LOGGER.info(
                    "Pump %s panel control active — skip HA auto-resume",
                    index,
                )
                # Re-assert local control after reboot.
                address = self._address(index)
                try:
                    await self._run_sequence(
                        index, [set_local_control(self.app_address, address)]
                    )
                except OSError as err:
                    _LOGGER.error("Pump %s local control after reboot failed: %s", index, err)
                continue
            if not self.should_run(index):
                _LOGGER.info(
                    "Pump %s desired_run=False — skip auto-resume after HA start",
                    index,
                )
                continue
            _LOGGER.info("Pump %s desired_run=True — resume setpoint after HA start", index)
            try:
                await self._async_reapply_setpoint(index)
            except (OSError, ValueError) as err:
                _LOGGER.error("Resume failed pump %s: %s", index, err)

    async def async_request_status(self, index: int) -> PumpStatus | None:
        if self.is_hands_off(index):
            return self.get_status(index)
        address = self._address(index)
        status = await self._run_sequence(
            index,
            self._wrap_remote_sequence(
                index, [request_status(self.app_address, address)]
            ),
        )
        if status is None:
            _LOGGER.warning("No status for pump %s", index)
        return status

    async def async_set_power(self, index: int, power: bool) -> PumpStatus | None:
        if self._panel_blocks(index, "power"):
            return self.get_status(index)
        self.set_should_run(index, power)
        if power and (
            self.get_target_rpm(index) is not None
            or self.get_target_gpm(index) is not None
        ):
            try:
                return await self._async_reapply_setpoint(index)
            except ValueError:
                pass
        address = self._address(index)
        return await self._run_command(
            index,
            [
                set_power(self.app_address, address, power),
                request_status(self.app_address, address),
            ],
        )

    async def async_run_rpm(
        self,
        index: int,
        rpm: int,
        *,
        update_target: bool = True,
        update_should_run: bool = True,
    ) -> PumpStatus | None:
        """Manual RPM mode first, then VS-style RPM packet (VS / VSF / VF)."""
        if not validate_rpm(rpm):
            raise ValueError(f"RPM {rpm} out of range")
        if self._panel_blocks(index, "set RPM"):
            return self.get_status(index)
        if update_target:
            self.set_command_profile(index, CommandProfile.RPM)
            self.set_target_rpm(index, rpm)
        if update_should_run:
            self.set_should_run(index, True)
        address = self._address(index)
        return await self._run_command(
            index,
            [
                set_speed1_mode(self.app_address, address),
                set_power(self.app_address, address, True),
                run_rpm(self.app_address, address, rpm),
                request_status(self.app_address, address),
            ],
        )

    async def async_run_gpm(
        self,
        index: int,
        gpm: int,
        *,
        update_target: bool = True,
        update_should_run: bool = True,
    ) -> PumpStatus | None:
        """Manual flow mode first, then VF-style GPM packet (VF / VSF)."""
        if not validate_gpm(gpm):
            raise ValueError(f"GPM {gpm} out of range")
        if self._panel_blocks(index, "set GPM"):
            return self.get_status(index)
        if update_target:
            self.set_command_profile(index, CommandProfile.GPM)
            self.set_target_gpm(index, gpm)
        if update_should_run:
            self.set_should_run(index, True)
        address = self._address(index)
        return await self._run_command(
            index,
            [
                set_manual_mode(self.app_address, address),
                set_power(self.app_address, address, True),
                run_gpm(self.app_address, address, gpm),
                request_status(self.app_address, address),
            ],
        )

    async def async_run_program(self, index: int, program: int) -> PumpStatus | None:
        if self._panel_blocks(index, "run program"):
            return self.get_status(index)
        address = self._address(index)
        middle: list[bytes] = [run_program(self.app_address, address, program)]
        if program != 0:
            self.set_should_run(index, True)
            status = self.get_status(index)
            if not status or not status.is_on:
                middle.insert(0, set_power(self.app_address, address, True))
        else:
            # Stop program is documented as a way to stop the pump: clear the
            # persisted intent so a HA restart does not auto-resume.
            self.set_should_run(index, False)
            middle.append(set_power(self.app_address, address, False))
        middle.append(request_status(self.app_address, address))
        return await self._run_command(index, middle)

    async def async_save_program(
        self, index: int, program: int, speed: int
    ) -> PumpStatus | None:
        if not 1 <= program <= 4:
            raise ValueError(f"Invalid program {program}")
        if self._panel_blocks(index, "save program"):
            return self.get_status(index)
        profile = self.get_command_profile(index)
        if profile == CommandProfile.GPM and not validate_gpm(speed):
            raise ValueError(f"GPM {speed} out of range")
        if profile == CommandProfile.RPM and not validate_rpm(speed):
            raise ValueError(f"RPM {speed} out of range")
        address = self._address(index)
        result = await self._run_command(
            index,
            [
                save_program(self.app_address, address, program, speed),
                request_status(self.app_address, address),
            ],
        )
        self.set_saved_program_speed(index, program, speed)
        return result

    async def async_poll_all(self) -> None:
        for pump in self.pumps:
            if not self.is_hands_off(pump.index):
                await self.async_request_status(pump.index)

    def _note_hit(self, index: int) -> None:
        self._poll_misses[index] = 0
        self._online[index] = True

    def _note_miss(self, index: int) -> None:
        misses = self._poll_misses.get(index, 0) + 1
        self._poll_misses[index] = misses
        if misses >= STALE_POLL_MISSES:
            if self._online.get(index):
                _LOGGER.warning(
                    "Pump %s: no RS485 status for %s polls — marking offline",
                    index,
                    misses,
                )
            self._online[index] = False

    def _store_responses(
        self,
        responses: list[PumpStatus],
        index: int,
        *,
        count_miss: bool = False,
    ) -> PumpStatus | None:
        found: PumpStatus | None = None
        for status in responses:
            self._status[status.index] = status
            self._note_hit(status.index)
            if status.index == index:
                found = status
        if found is None and count_miss:
            self._note_miss(index)
        return found


def _packet_is_status_request(packet: bytes) -> bool:
    """True if this outbound frame is an action-7 status poll."""
    return len(packet) >= 9 and list(packet)[7:9] == [7, 0]
