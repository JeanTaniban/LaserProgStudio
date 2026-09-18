# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable

from .base import MachineTransportError, PortInfo


def _import_serial():
    try:
        import serial  # type: ignore
        return serial
    except Exception as exc:  # pragma: no cover - depends on optional runtime package
        raise MachineTransportError("pyserial is required for USB machine control. Install pyserial to enable this panel.") from exc


def list_serial_ports() -> list[PortInfo]:
    try:
        from serial.tools import list_ports  # type: ignore
    except Exception:
        return []
    ports: list[PortInfo] = []
    for port in list_ports.comports():
        ports.append(PortInfo(str(port.device), str(getattr(port, "description", "") or ""), str(getattr(port, "hwid", "") or "")))
    return ports


class GrblSerialTransport:
    """Small GRBL line-streaming transport for USB.

    This class deliberately avoids hidden job start semantics.  The UI must ask
    for confirmation before streaming any line containing laser-on commands.
    """

    def __init__(self, port: str, *, baudrate: int = 115200, timeout_s: float = 2.0):
        self.port = str(port)
        self.baudrate = int(baudrate)
        self.timeout_s = float(timeout_s)
        self._serial = None
        self._write_lock = threading.RLock()

    @property
    def is_open(self) -> bool:
        ser = self._serial
        return bool(ser is not None and getattr(ser, "is_open", False))

    def connect(self) -> list[str]:
        serial = _import_serial()
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s, write_timeout=self.timeout_s)
            # GRBL commonly resets after opening USB serial. Give it time, then
            # consume the startup banner if present.
            time.sleep(2.0)
            return self.read_available(max_lines=20)
        except Exception as exc:
            self._serial = None
            raise MachineTransportError(f"Could not open {self.port}: {exc}") from exc

    def close(self) -> None:
        ser = self._serial
        self._serial = None
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass

    def write_line(self, line: str) -> None:
        ser = self._require_open()
        payload = (str(line).strip() + "\n").encode("ascii", errors="ignore")
        with self._write_lock:
            ser.write(payload)
            try:
                ser.flush()
            except Exception:
                pass

    def read_line(self) -> str:
        ser = self._require_open()
        raw = ser.readline()
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace").strip()
        return str(raw).strip()

    def read_available(self, *, max_lines: int = 50) -> list[str]:
        ser = self._require_open()
        lines: list[str] = []
        for _ in range(max(1, int(max_lines))):
            waiting = int(getattr(ser, "in_waiting", 0) or 0)
            if waiting <= 0:
                break
            line = self.read_line()
            if line:
                lines.append(line)
        return lines

    def command(self, line: str, *, wait_ok: bool = True, timeout_s: float | None = None) -> list[str]:
        self.write_line(line)
        if not wait_ok:
            return []
        return self._read_until_response(timeout_s=timeout_s or self.timeout_s)

    def stream_gcode(self, lines: Iterable[str], *, progress: Callable[[int, str], None] | None = None, should_cancel: Callable[[], bool] | None = None) -> int:
        count = 0
        for raw_line in lines:
            if should_cancel is not None and should_cancel():
                break
            line = _strip_gcode_comment(str(raw_line)).strip()
            if not line:
                continue
            count += 1
            if progress is not None:
                progress(count, line)
            self.write_line(line)
            responses = self._read_until_response(timeout_s=self.timeout_s)
            if any(resp.lower().startswith(("error", "alarm")) for resp in responses):
                raise MachineTransportError("Controller stopped on: " + " | ".join(responses))
        return count

    def feed_hold(self) -> None:
        self._write_realtime(b"!")

    def soft_reset(self) -> None:
        self._write_realtime(bytes((0x18,)))

    def emergency_stop(self, *, close_port: bool = True) -> None:
        """Issue GRBL real-time hold + soft reset without waiting for planner ACKs."""
        try:
            self._write_realtime(b"!")
            time.sleep(0.03)
            self._write_realtime(bytes((0x18,)))
        finally:
            if close_port:
                self.close()

    def _write_realtime(self, payload: bytes) -> None:
        ser = self._require_open()
        with self._write_lock:
            try:
                ser.write(bytes(payload))
                ser.flush()
            except Exception as exc:
                raise MachineTransportError(f"Could not send GRBL real-time stop command: {exc}") from exc

    def _read_until_response(self, *, timeout_s: float) -> list[str]:
        deadline = time.monotonic() + max(0.1, float(timeout_s))
        responses: list[str] = []
        while time.monotonic() <= deadline:
            line = self.read_line()
            if not line:
                continue
            responses.append(line)
            low = line.lower()
            if low == "ok" or low.startswith("error") or low.startswith("alarm"):
                return responses
        raise MachineTransportError("Timed out waiting for GRBL response.")

    def _require_open(self):
        ser = self._serial
        if ser is None or not getattr(ser, "is_open", False):
            raise MachineTransportError("Serial port is not connected.")
        return ser


def _strip_gcode_comment(line: str) -> str:
    # Remove semicolon comments. Parenthesized comments are intentionally left
    # untouched because GRBL variants differ; LaserProg emits semicolon comments.
    return str(line).split(";", 1)[0]
