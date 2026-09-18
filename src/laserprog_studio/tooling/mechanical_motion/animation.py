# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from typing import Callable, Mapping


class MechanicalAnimationController:
    """Optional Qt timer advancing the assembly's single rotary driver."""

    def __init__(self, on_angles: Callable[[dict[str, float]], None]) -> None:
        self._on_angles = on_angles
        self._timer = None
        self._angles: dict[str, float] = {}
        self._speeds_rpm: dict[str, float] = {}
        self._last_tick = 0.0

    @property
    def running(self) -> bool:
        timer = self._timer
        return bool(timer is not None and getattr(timer, "isActive", lambda: False)())

    def start(self, *, angles_deg: Mapping[str, float], speeds_rpm: Mapping[str, float]) -> bool:
        self._angles = {str(key): float(value) for key, value in angles_deg.items()}
        self._speeds_rpm = {str(key): float(value) for key, value in speeds_rpm.items()}
        self._last_tick = time.perf_counter()
        try:
            from PySide6.QtCore import QTimer

            if self._timer is None:
                self._timer = QTimer()
                self._timer.setInterval(33)
                self._timer.timeout.connect(self._tick)
            self._timer.start()
            return True
        except Exception:
            self._timer = None
            return False

    def stop(self) -> None:
        timer = self._timer
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass

    def set_speed(self, driver_id: str, speed_rpm: float) -> None:
        self._speeds_rpm[str(driver_id)] = float(speed_rpm)

    def set_speeds(self, values: Mapping[str, float]) -> None:
        self._speeds_rpm = {str(key): float(value) for key, value in values.items()}

    def set_angles(self, values: Mapping[str, float]) -> None:
        self._angles = {str(key): float(value) for key, value in values.items()}
        self._last_tick = time.perf_counter()

    def _tick(self) -> None:
        now = time.perf_counter()
        elapsed = max(0.0, min(0.25, now - self._last_tick))
        self._last_tick = now
        for driver_id, speed_rpm in self._speeds_rpm.items():
            # Keep an unbounded physical angle.  Wrapping the driver to 0..360
            # made every reduced output shaft jump back at each input revolution,
            # so later stages only rocked over a small arc instead of rotating.
            self._angles[driver_id] = (
                self._angles.get(driver_id, 0.0) + float(speed_rpm) * 6.0 * elapsed
            )
        try:
            self._on_angles(dict(self._angles))
        except Exception:
            self.stop()


__all__ = ["MechanicalAnimationController"]
