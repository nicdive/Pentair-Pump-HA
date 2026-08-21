"""Async RS485 serial bus for Pentair pump communication."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import serial

from .parser import extract_frames, parse_pump_status
from .packets import PumpStatus

_LOGGER = logging.getLogger(__name__)

COMMAND_GAP = 0.15
RESPONSE_TIMEOUT = 2.5

# pyserial SerialException is an OSError on 3.x; keep both for safety.
_SERIAL_ERRORS = (OSError, serial.SerialException)


class RS485Bus:
    """Thread-safe RS485 bus using pyserial on a dedicated worker thread."""

    def __init__(
        self,
        port: str,
        baud_rate: int = 9600,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._loop = loop
        self._serial: serial.Serial | None = None
        self._lock = asyncio.Lock()
        self._read_buffer = bytearray()
        self._status_callbacks: list[Callable[[PumpStatus], None]] = []
        self._last_error: str | None = None
        self._executor: ThreadPoolExecutor | None = None

    @property
    def port(self) -> str:
        return self._port

    @property
    def is_open(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def add_status_listener(self, callback: Callable[[PumpStatus], None]) -> None:
        self._status_callbacks.append(callback)

    def _ensure_executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="pentair-rs485"
            )
        return self._executor

    def _shutdown_executor(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def async_open(self) -> None:
        self._ensure_executor()
        await self._run(self._open)

    async def async_close(self) -> None:
        async with self._lock:
            try:
                if self._executor is not None:
                    await self._run(self._close)
            finally:
                self._shutdown_executor()

    async def async_reconnect(self) -> None:
        """Close and reopen the serial port (USB unplug/replug)."""
        _LOGGER.warning("Reconnecting RS485 port %s", self._port)
        async with self._lock:
            if self._executor is not None:
                await self._run(self._close)
            await asyncio.sleep(0.5)
            self._ensure_executor()
            await self._run(self._open)

    async def async_ensure_open(self) -> None:
        if self.is_open:
            return
        await self.async_open()

    async def async_send(self, packet: bytes) -> None:
        async with self._lock:
            await self._write_with_retry(packet)
            await asyncio.sleep(COMMAND_GAP)

    async def async_send_sequence(
        self,
        packets: list[bytes],
        *,
        expect_index: int | None = None,
        wait_status: bool = True,
    ) -> list[PumpStatus]:
        """Send a command sequence and collect status responses.

        When ``expect_index`` is set, wait until that pump replies (or timeout)
        instead of returning on the first status frame from any pump.
        """
        async with self._lock:
            try:
                await self._run(self._reset_input_buffer)
                for packet in packets:
                    await self._write_with_retry(packet)
                    await asyncio.sleep(COMMAND_GAP)
                if not wait_status:
                    return []
                return await self._collect_status(
                    timeout=RESPONSE_TIMEOUT, expect_index=expect_index
                )
            except _SERIAL_ERRORS as err:
                self._last_error = str(err)
                _LOGGER.error(
                    "RS485 sequence failed on %s: %s — retrying once", self._port, err
                )
                try:
                    await self._run(self._close)
                    await asyncio.sleep(0.5)
                    await self._run(self._open)
                    await self._run(self._reset_input_buffer)
                    for packet in packets:
                        await self._run(self._write, packet)
                        await asyncio.sleep(COMMAND_GAP)
                    if not wait_status:
                        self._last_error = None
                        return []
                    result = await self._collect_status(
                        timeout=RESPONSE_TIMEOUT, expect_index=expect_index
                    )
                    self._last_error = None
                    return result
                except _SERIAL_ERRORS as err2:
                    self._last_error = str(err2)
                    raise OSError(str(err2)) from err2

    async def _write_with_retry(self, packet: bytes) -> None:
        try:
            await self.async_ensure_open()
            await self._run(self._write, packet)
            self._last_error = None
        except _SERIAL_ERRORS:
            await self._run(self._close)
            await asyncio.sleep(0.3)
            await self._run(self._open)
            await self._run(self._write, packet)
            self._last_error = None

    async def async_poll_status(self) -> list[PumpStatus]:
        """Read any pending data from the bus."""
        async with self._lock:
            await self._run(self._read_available)
            return self._drain_status_frames()

    def _open(self) -> None:
        if self._serial and self._serial.is_open:
            return
        self._serial = serial.Serial(
            port=self._port,
            baudrate=self._baud_rate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2,
            write_timeout=2,
        )
        self._last_error = None
        _LOGGER.info("Opened RS485 port %s @ %s baud", self._port, self._baud_rate)

    def _close(self) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
            except _SERIAL_ERRORS as err:
                _LOGGER.debug("RS485 close on %s: %s", self._port, err)
        self._serial = None

    def _reset_input_buffer(self) -> None:
        if self._serial and self._serial.is_open:
            try:
                self._serial.reset_input_buffer()
            except _SERIAL_ERRORS:
                pass
            self._read_buffer.clear()

    def _write(self, packet: bytes) -> None:
        if not self._serial or not self._serial.is_open:
            raise OSError("RS485 port is not open")
        try:
            self._serial.write(packet)
            self._serial.flush()
        except _SERIAL_ERRORS as err:
            raise OSError(str(err)) from err
        _LOGGER.debug("TX %s", packet.hex(" "))

    def _read_available(self) -> None:
        if not self._serial or not self._serial.is_open:
            return
        try:
            data = self._serial.read(512)
        except _SERIAL_ERRORS as err:
            _LOGGER.warning("RS485 read error on %s: %s", self._port, err)
            self._last_error = str(err)
            return
        if data:
            self._read_buffer.extend(data)
            _LOGGER.debug("RX %s", data.hex(" "))

    async def _collect_status(
        self, timeout: float, expect_index: int | None = None
    ) -> list[PumpStatus]:
        deadline = time.monotonic() + timeout
        statuses: list[PumpStatus] = []
        seen: set[int] = set()
        raw_seen = False
        while time.monotonic() < deadline:
            await self._run(self._read_available)
            if self._read_buffer:
                raw_seen = True
            for status in self._drain_status_frames():
                if status.index not in seen:
                    seen.add(status.index)
                    statuses.append(status)
            if _have_expected_status(statuses, expect_index):
                break
            await asyncio.sleep(0.05)
        if not statuses:
            if raw_seen:
                _LOGGER.warning(
                    "RS485 data received on %s but no valid pump status frame parsed",
                    self._port,
                )
            else:
                _LOGGER.warning(
                    "No RS485 response on %s (check wiring, pump index, and port permissions)",
                    self._port,
                )
        elif expect_index is not None and expect_index not in seen:
            _LOGGER.warning(
                "RS485 status from pump(s) %s on %s, but pump %s did not reply",
                sorted(seen),
                self._port,
                expect_index,
            )
        return statuses

    def _drain_status_frames(self) -> list[PumpStatus]:
        frames, self._read_buffer = extract_frames(self._read_buffer)
        statuses: list[PumpStatus] = []
        for frame in frames:
            status = parse_pump_status(frame)
            if status:
                _LOGGER.debug(
                    "Pump %s status: rpm=%s gpm=%s watts=%s err=%s",
                    status.index,
                    status.rpm,
                    status.gpm,
                    status.watts,
                    status.err,
                )
                statuses.append(status)
                for callback in self._status_callbacks:
                    callback(status)
        return statuses

    async def _run(self, func: Callable, *args):
        loop = self._loop or asyncio.get_running_loop()
        return await loop.run_in_executor(self._ensure_executor(), lambda: func(*args))


def _have_expected_status(
    statuses: list[PumpStatus], expect_index: int | None
) -> bool:
    """True when we can stop waiting for more serial data."""
    if not statuses:
        return False
    if expect_index is None:
        return True
    return any(status.index == expect_index for status in statuses)
