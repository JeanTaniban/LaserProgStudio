# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from laserprog_studio.engraving.laser_3mf_core import CanvasTransform, RenderConfig, global_bounds, safe_buffer, union_by_operation
from laserprog_studio.machine.profiles import FALCON_A1_PRO_PROFILE, MachineProfile

from .models import GCodeJobSettings, Toolpath
from .planner import GCodeGeometryTransform, hatch_toolpaths, outline_toolpaths


@dataclass(frozen=True, slots=True)
class GCodeJob:
    lines: tuple[str, ...]
    warnings: tuple[str, ...]
    cut_paths: int
    engrave_paths: int
    width_mm: float
    height_mm: float
    frame_paths: tuple[Toolpath, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    def write(self, path: Path | str) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.text, encoding="utf-8")
        return out


def generate_gcode(instances, cfg: RenderConfig, settings: GCodeJobSettings, profile: MachineProfile = FALCON_A1_PRO_PROFILE) -> GCodeJob:
    warnings = list(settings.validate())
    bounds = global_bounds(instances)
    canvas = CanvasTransform(bounds, cfg)
    transform = GCodeGeometryTransform.from_bounds(
        (canvas.minx, canvas.miny, canvas.maxx, canvas.maxy),
        page_margin_ratio=0.0,
        flip_y=True,
    )
    outline_geom = union_by_operation(instances, "outline") if bool(settings.include_outline_cut) else None
    if outline_geom is not None and not getattr(outline_geom, "is_empty", True):
        outline_geom = safe_buffer(outline_geom, float(cfg.contour_margin_mm))
    fill_geom = union_by_operation(instances, "fill") if bool(settings.include_fill_engraving) else None
    if fill_geom is not None and not getattr(fill_geom, "is_empty", True):
        fill_geom = safe_buffer(fill_geom, float(cfg.fill_margin_mm))

    cuts = outline_toolpaths(outline_geom, transform) if outline_geom is not None else []
    engraves = hatch_toolpaths(fill_geom, transform, float(settings.hatch_spacing_mm)) if fill_geom is not None else []
    if settings.include_outline_cut and not cuts:
        warnings.append("No outline/cut paths were generated from green geometry.")
    if settings.include_fill_engraving and not engraves:
        warnings.append("No hatch engraving paths were generated from red fill geometry.")

    if transform.width_mm > float(profile.work_area_x_mm) + 1.0e-9 or transform.height_mm > float(profile.work_area_y_mm) + 1.0e-9:
        warnings.append(
            "Job exceeds machine work area "
            f"({transform.width_mm:.3f} x {transform.height_mm:.3f} mm job, "
            f"{profile.work_area_x_mm:.3f} x {profile.work_area_y_mm:.3f} mm allowed)."
        )

    frame_paths = tuple(path for path in cuts if path.note == "outer" and path.is_valid)
    if not frame_paths:
        frame_paths = (_bounding_frame_path(transform),)

    lines = _header_lines(settings, profile, transform, warnings)
    lines.extend(_emit_setup(settings))
    if engraves:
        lines.append("")
        lines.append("; --- Fill engraving hatches ---")
        lines.extend(_emit_paths(engraves, power_s=profile.power_s_value(settings.engrave_power_percent), feed=float(settings.engrave_feed_mm_min), settings=settings))
    if cuts:
        lines.append("")
        lines.append("; --- Outline cutting paths ---")
        current_depth = 0.0
        for pass_index in range(max(1, int(settings.cut_passes))):
            depth = settings.focus.focus_depth_for_pass(pass_index)
            lines.append(f"; Pass {pass_index + 1}/{max(1, int(settings.cut_passes))} focus_depth={depth:.3f}mm")
            if bool(settings.focus.enable_z_steps):
                delta_depth = depth - current_depth
                if abs(delta_depth) > 1.0e-9:
                    lines.extend(_emit_relative_z(float(settings.focus.z_down_sign) * delta_depth, settings))
                current_depth = depth
            lines.extend(_emit_paths(cuts, power_s=profile.power_s_value(settings.cut_power_percent), feed=float(settings.cut_feed_mm_min), settings=settings))
        if bool(settings.focus.enable_z_steps) and current_depth > 1.0e-9:
            lines.append("; Retract Z to the recorded starting height")
            lines.extend(_emit_relative_z(-float(settings.focus.z_down_sign) * current_depth, settings))
    lines.extend(_footer_lines())
    return GCodeJob(tuple(lines), tuple(warnings), len(cuts), len(engraves), transform.width_mm, transform.height_mm, frame_paths)



def generate_frame_gcode(job: GCodeJob, *, feed_mm_min: float = 3000.0) -> tuple[str, ...]:
    """Build a laser-off program that follows each exterior contour once."""

    feed = max(1.0, float(feed_mm_min))
    paths = tuple(path for path in job.frame_paths if path.is_valid)
    if not paths:
        paths = (
            Toolpath(
                "cut",
                ((0.0, 0.0), (job.width_mm, 0.0), (job.width_mm, job.height_mm), (0.0, job.height_mm)),
                closed=True,
                note="frame-bounds",
            ),
        )
    lines = [
        "; LaserProg frame mode — laser must remain off",
        "G21 ; millimetres",
        "G90 ; absolute XY coordinates",
        "G94 ; feed per minute",
        "M5 ; laser off",
    ]
    for index, path in enumerate(paths, start=1):
        first = path.points[0]
        lines.append(f"; Exterior frame contour {index}")
        lines.append("M5")
        lines.append(f"G0 X{_num(first[0])} Y{_num(first[1])} F{_num(feed)}")
        for x, y in path.points[1:]:
            lines.append(f"G1 X{_num(x)} Y{_num(y)} F{_num(feed)}")
        if path.closed:
            lines.append(f"G1 X{_num(first[0])} Y{_num(first[1])} F{_num(feed)}")
    lines.append("M5")
    return tuple(lines)


def _emit_relative_z(delta_z_mm: float, settings: GCodeJobSettings) -> list[str]:
    return [
        "M5 ; laser off before Z movement",
        "G91 ; relative coordinates for bounded Z step",
        f"G0 Z{_num(delta_z_mm)} F{_num(settings.travel_feed_mm_min)}",
        "G90 ; restore absolute XY coordinates",
    ]


def _bounding_frame_path(transform: GCodeGeometryTransform) -> Toolpath:
    return Toolpath(
        "cut",
        (
            (0.0, 0.0),
            (transform.width_mm, 0.0),
            (transform.width_mm, transform.height_mm),
            (0.0, transform.height_mm),
        ),
        closed=True,
        note="frame-bounds",
    )


def generate_gcode_text(instances, cfg: RenderConfig, settings: GCodeJobSettings, profile: MachineProfile = FALCON_A1_PRO_PROFILE) -> str:
    return generate_gcode(instances, cfg, settings, profile).text


def _header_lines(settings: GCodeJobSettings, profile: MachineProfile, transform: GCodeGeometryTransform, warnings: Sequence[str]) -> list[str]:
    focus = settings.focus
    lines = [
        "; LaserProg Studio G-code export",
        f"; Job: {settings.job_name}",
        f"; Machine profile: {profile.label}",
        "; Coordinate units: millimetres",
        f"; Job size: {transform.width_mm:.3f} x {transform.height_mm:.3f} mm",
        "; Manual known-height focus model:",
        f";   support/honeycomb height: {focus.support_height_mm:.3f} mm",
        f";   material thickness: {focus.material_thickness_mm:.3f} mm",
        f";   focus distance: {focus.focus_distance_mm:.3f} mm",
        f";   focused head height at surface: {focus.focused_head_height_surface_mm:.3f} mm above base model",
        f";   minimum safe focused head height: {focus.min_safe_focused_head_height_mm:.3f} mm above base model",
        f";   max focus depth in material: {focus.max_focus_depth_mm:.3f} mm",
        f";   Z steps enabled: {bool(focus.enable_z_steps)} ; Z down sign: {int(focus.z_down_sign)}",
        "; SAFETY: verify focus, origin, frame, air assist and enclosure before firing the laser.",
    ]
    for warning in warnings:
        lines.append(f"; WARNING: {warning}")
    return lines


def _emit_setup(settings: GCodeJobSettings) -> list[str]:
    return [
        "G21 ; millimetres",
        "G90 ; absolute XY coordinates",
        "G94 ; feed per minute",
        "M5 ; laser off",
        f"G0 F{_num(settings.travel_feed_mm_min)}",
    ]


def _emit_paths(paths: Sequence[Toolpath], *, power_s: int, feed: float, settings: GCodeJobSettings) -> list[str]:
    lines: list[str] = []
    laser_cmd = "M4" if bool(settings.use_dynamic_power_m4) else "M3"
    for index, path in enumerate(paths, start=1):
        if not path.is_valid:
            continue
        first = path.points[0]
        lines.append(f"; {path.role} path {index} {path.note}".rstrip())
        lines.append("M5")
        if float(settings.dwell_after_laser_off_s) > 0.0:
            lines.append(f"G4 P{_num(settings.dwell_after_laser_off_s)}")
        lines.append(f"G0 X{_num(first[0])} Y{_num(first[1])} F{_num(settings.travel_feed_mm_min)}")
        lines.append(f"{laser_cmd} S{int(power_s)}")
        for x, y in path.points[1:]:
            lines.append(f"G1 X{_num(x)} Y{_num(y)} F{_num(feed)}")
        if path.closed:
            lines.append(f"G1 X{_num(first[0])} Y{_num(first[1])} F{_num(feed)}")
        lines.append("M5")
    return lines


def _footer_lines() -> list[str]:
    return [
        "",
        "; --- End job ---",
        "M5",
        "; Machine remains at the final safe position; no automatic return-to-origin move.",
        "; End of LaserProg G-code",
    ]


def _num(value: float) -> str:
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"
