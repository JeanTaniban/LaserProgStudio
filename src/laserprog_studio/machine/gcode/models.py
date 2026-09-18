# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Point2D = tuple[float, float]
PathRole = Literal["cut", "engrave"]


@dataclass(frozen=True, slots=True)
class Toolpath:
    role: PathRole
    points: tuple[Point2D, ...]
    closed: bool = True
    note: str = ""

    @property
    def is_valid(self) -> bool:
        return len(self.points) >= (3 if self.closed else 2)


@dataclass(slots=True)
class ManualFocusSettings:
    """Known-height focus model for safe Z planning.

    The UI labels mirror the user-facing mental model:
    - support_height_mm: top of the honeycomb/sommier above the machine base;
    - material_thickness_mm: stock thickness;
    - focus_distance_mm: head-to-surface focus distance;
    - max_focus_depth_mm: deepest allowed focus point inside the material.

    G-code is emitted as relative Z offsets by default because absolute Z zero
    differs between GRBL integrations.  The absolute heights are still used for
    validation and job comments.
    """

    support_height_mm: float = 0.0
    material_thickness_mm: float = 3.0
    focus_distance_mm: float = 7.0
    safety_margin_mm: float = 0.5
    max_focus_depth_mm: float = 1.0
    enable_z_steps: bool = False
    z_step_per_pass_mm: float = 0.0
    # Conventional GRBL cutting motion is usually negative Z into the work.
    # Keep this visible in the UI and in comments; do not hide this assumption.
    z_down_sign: int = -1

    @property
    def material_surface_height_mm(self) -> float:
        return float(self.support_height_mm) + float(self.material_thickness_mm)

    @property
    def focused_head_height_surface_mm(self) -> float:
        return self.material_surface_height_mm + float(self.focus_distance_mm)

    @property
    def min_safe_focused_head_height_mm(self) -> float:
        return float(self.support_height_mm) + float(self.focus_distance_mm) + float(self.safety_margin_mm)

    def focus_depth_for_pass(self, pass_index: int) -> float:
        if not self.enable_z_steps:
            return 0.0
        return max(0.0, float(pass_index) * abs(float(self.z_step_per_pass_mm)))

    def validate_for_passes(self, passes: int) -> list[str]:
        warnings: list[str] = []
        material = max(0.0, float(self.material_thickness_mm))
        if material <= 0.0:
            warnings.append("Material thickness must be greater than 0 mm.")
        if float(self.focus_distance_mm) <= 0.0:
            warnings.append("Focus distance must be greater than 0 mm.")
        if float(self.max_focus_depth_mm) < 0.0:
            warnings.append("Maximum focus depth cannot be negative.")
        deepest_requested = self.focus_depth_for_pass(max(0, int(passes) - 1))
        allowed_by_material = max(0.0, material - max(0.0, float(self.safety_margin_mm)))
        allowed = min(max(0.0, float(self.max_focus_depth_mm)), allowed_by_material)
        if deepest_requested > allowed + 1.0e-9:
            warnings.append(
                "Z-step focus depth would exceed the safe limit "
                f"({deepest_requested:.3f} mm requested, {allowed:.3f} mm allowed)."
            )
        if self.enable_z_steps and abs(float(self.z_step_per_pass_mm)) <= 1.0e-9 and int(passes) > 1:
            warnings.append("Z steps are enabled but the Z step per pass is 0 mm.")
        if self.z_down_sign not in (-1, 1):
            warnings.append("Z down direction must be either -1 or +1.")
        return warnings


@dataclass(slots=True)
class GCodeJobSettings:
    """Laser G-code generation settings kept independent from Qt."""

    job_name: str = "LaserProg job"
    cut_power_percent: float = 80.0
    cut_feed_mm_min: float = 180.0
    cut_passes: int = 1
    engrave_power_percent: float = 18.0
    engrave_feed_mm_min: float = 1200.0
    hatch_spacing_mm: float = 0.25
    travel_feed_mm_min: float = 3000.0
    use_dynamic_power_m4: bool = True
    include_fill_engraving: bool = True
    include_outline_cut: bool = True
    dwell_after_laser_off_s: float = 0.02
    focus: ManualFocusSettings = field(default_factory=ManualFocusSettings)

    def validate(self) -> list[str]:
        warnings = self.focus.validate_for_passes(int(self.cut_passes))
        if int(self.cut_passes) < 1:
            warnings.append("Cut passes must be at least 1.")
        if float(self.cut_feed_mm_min) <= 0.0:
            warnings.append("Cut feed must be greater than 0 mm/min.")
        if float(self.engrave_feed_mm_min) <= 0.0:
            warnings.append("Engrave feed must be greater than 0 mm/min.")
        if float(self.travel_feed_mm_min) <= 0.0:
            warnings.append("Travel feed must be greater than 0 mm/min.")
        if float(self.hatch_spacing_mm) <= 0.0:
            warnings.append("Hatch spacing must be greater than 0 mm.")
        return warnings
