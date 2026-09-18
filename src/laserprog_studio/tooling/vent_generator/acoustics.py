# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
import math

from laserprog_studio.planar_tools import VentPathDraft


@dataclass(frozen=True, slots=True)
class VentAcousticEstimate:
    physical_length_mm: float
    effective_length_mm: float
    inner_width_mm: float
    inner_height_mm: float
    section_area_mm2: float
    enclosure_volume_l: float
    tuning_hz: float | None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def tuning_text(self) -> str:
        if self.tuning_hz is None:
            if self.warnings:
                return self.warnings[0]
            return "Tuning unavailable."
        return f"{self.tuning_hz:.1f} Hz · L_eff {self.effective_length_mm:.1f} mm"


_SPEED_OF_SOUND_M_PER_S = 343.0


def estimate_vent_acoustics(payload: VentPathDraft | None, *, enclosure_volume_l: float) -> VentAcousticEstimate | None:
    if not isinstance(payload, VentPathDraft):
        return None
    try:
        width_mm, height_mm = payload.section_dimensions()
    except Exception:
        return None
    width_mm = max(float(width_mm), 0.0)
    height_mm = max(float(height_mm), 0.0)
    try:
        length_mm = max(float(payload.estimated_centerline_length()), 0.0)
    except Exception:
        length_mm = 0.0
    area_mm2 = max(width_mm * height_mm, 0.0)
    warnings: list[str] = []
    tuning_hz: float | None = None
    eff_length_mm = length_mm
    volume_l = max(float(enclosure_volume_l), 0.0)
    if len(getattr(payload, 'waypoints', ()) or ()) < 2:
        warnings.append("Add at least 2 waypoints for a tuning estimate.")
    if area_mm2 <= 0.0:
        warnings.append("Inner section must be positive.")
    if volume_l <= 0.0:
        warnings.append("Enter a box volume above 0 L.")
    if not warnings:
        equivalent_radius_mm = math.sqrt(area_mm2 / math.pi)
        # Simple slot-port style end correction, used as a first-pass estimate.
        eff_length_mm = max(length_mm + 1.7 * equivalent_radius_mm, 1.0e-6)
        area_m2 = area_mm2 * 1.0e-6
        volume_m3 = volume_l * 1.0e-3
        eff_length_m = eff_length_mm * 1.0e-3
        try:
            tuning_hz = (_SPEED_OF_SOUND_M_PER_S / (2.0 * math.pi)) * math.sqrt(area_m2 / (volume_m3 * eff_length_m))
        except Exception:
            tuning_hz = None
    return VentAcousticEstimate(
        physical_length_mm=length_mm,
        effective_length_mm=eff_length_mm,
        inner_width_mm=width_mm,
        inner_height_mm=height_mm,
        section_area_mm2=area_mm2,
        enclosure_volume_l=volume_l,
        tuning_hz=tuning_hz,
        warnings=tuple(warnings),
    )


__all__ = ["VentAcousticEstimate", "estimate_vent_acoustics"]
