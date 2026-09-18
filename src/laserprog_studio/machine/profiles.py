# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MachineProfile:
    """Static capabilities for a laser machine profile.

    Coordinates remain intentionally conservative: the current first driver uses
    GRBL-style streaming over USB and does not assume Creality's private Wi-Fi
    protocol or private autofocus commands.
    """

    id: str
    label: str
    work_area_x_mm: float
    work_area_y_mm: float
    default_focus_distance_mm: float
    default_power_max_s: int = 1000
    max_feed_mm_min: float = 30_000.0
    max_frame_feed_mm_min: float = 6_000.0
    supports_usb_grbl: bool = True
    supports_wifi_direct: bool = False
    autofocus_command: str | None = None
    notes: str = ""

    def power_s_value(self, percent: float) -> int:
        clamped = max(0.0, min(100.0, float(percent)))
        return int(round((clamped / 100.0) * int(self.default_power_max_s)))


FALCON_A1_PRO_PROFILE = MachineProfile(
    id="creality_falcon_a1_pro",
    label="Creality Falcon A1 Pro",
    work_area_x_mm=381.0,
    work_area_y_mm=305.0,
    default_focus_distance_mm=7.0,
    default_power_max_s=1000,
    max_feed_mm_min=30_000.0,
    max_frame_feed_mm_min=6_000.0,
    supports_usb_grbl=True,
    supports_wifi_direct=False,
    autofocus_command=None,
    notes=(
        "USB GRBL-style streaming is exposed as an experimental path. "
        "Autofocus is intentionally not emitted until the real Creality command "
        "is identified from official config or a capture."
    ),
)
