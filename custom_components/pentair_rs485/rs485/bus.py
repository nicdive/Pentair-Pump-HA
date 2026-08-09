"""Async RS485 serial bus for Pentair pump communication."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

import serial

from .parser import extract_frames, parse_pump_status
from .packets import PumpStatus

_LOGGER = logging.getLogger(__name__)

COMMAND_GAP = 0.15
RESPONSE_TIMEOUT = 3.0


class RS485Bus:
    """Thread-safe RS485 bus using pyserial in the executor."""

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

    def add_status_listener(self, callback: Callable[[PumpStatus], None]) -> None:
        self._status_callbacks.append(callback)

    async def async_open(self) -> None:
        await self._run(self._open)

    async def async_close(self) -> None:
        await self._run(self._close)

    async def async_send(self, packet: bytes) -> None:
        async with self._lock:
            await self._run(self._write, packet)
            await asyncio.sleep(COMMAND_GAP)

    async def async_send_sequence(self, packets: list[bytes]) -> list[PumpStatus]:
        """Send a command sequence and collect status responses."""
        async with self._lock:
            await self._run(self._reset_input_buffer)
            for packet in packets:
                await self._run(self._write, packet)
                await asyncio.sleep(COMMAND_GAP)
            return await self._collect_status(timeout=RESPONSE_TIMEOUT)

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
        _LOGGER.info("Opened RS485 port %s @ %s baud", self._port, self._baud_rate)

    def _close(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None

    def _reset_input_buffer(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.reset_input_buffer()
            self._read_buffer.clear()

    def _write(self, packet: bytes) -> None:
        if not self._serial or not self._serial.is_open:
            raise OSError("RS485 port is not open")
        self._serial.write(packet)
        self._serial.flush()
        _LOGGER.debug("TX %s", packet.hex(" "))

    def _read_available(self) -> None:
        if not self._serial or not self._serial.is_open:
            return
        data = self._serial.read(512)
        if data:
            self._read_buffer.extend(data)
            _LOGGER.debug("RX %s", data.hex(" "))

    async def _collect_status(self, timeout: float) -> list[PumpStatus]:
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
            if statuses:
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
        return statuses

    def _drain_status_frames(self) -> list[PumpStatus]:
        frames, self._read_buffer = extract_frames(self._read_buffer)
        statuses: list[PumpStatus] = []
        for frame in frames:
            status = parse_pump_status(frame)
            if status:
                _LOGGER.info(
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
        return await loop.run_in_executor(None, lambda: func(*args))
