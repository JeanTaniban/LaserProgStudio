# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind

from .acoustics import estimate_vent_acoustics


MODE_CHOICES: tuple[tuple[str, str], ...] = (
    ("ADD", "Add waypoint"),
    ("MOD", "Modify route"),
    ("SUPP", "Delete point"),
    ("RST", "Reset route now"),
)
SECTION_CHOICES: tuple[tuple[str, str], ...] = (
    (VentSectionKind.RECTANGLE.value, "Rectangular duct"),
    (VentSectionKind.ROUND.value, "Round pipe"),
)
FLARE_CHOICES: tuple[tuple[str, str], ...] = (
    (VentFlareSide.NONE.value, "No flare"),
    (VentFlareSide.START.value, "Inlet"),
    (VentFlareSide.END.value, "Outlet"),
    (VentFlareSide.BOTH.value, "Both ends"),
)


def _float_value(values: dict[str, Any], key: str, default: float, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        value = float(values.get(key, default))
    except Exception:
        value = float(default)
    if minimum is not None:
        value = max(float(minimum), value)
    if maximum is not None:
        value = min(float(maximum), value)
    return value


def _bool_value(values: dict[str, Any], key: str, default: bool = False) -> bool:
    try:
        value = values.get(key, default)
    except Exception:
        return bool(default)
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off", ""}:
            return False
    return bool(value)


@dataclass(frozen=True, slots=True)
class VentGeneratorSettings:
    """Validated user settings for the Vent Generator Creator panel."""

    section_kind: VentSectionKind = VentSectionKind.RECTANGLE
    section_area: float = 100.0
    rect_width: float = 10.0
    rect_height: float = 10.0
    wall_thickness: float = 3.0
    target_length: float = 0.0
    curve_radius: float = 0.0
    curve_strength: float = 0.0
    fill_area: bool = False
    flare_side: VentFlareSide = VentFlareSide.NONE
    flare_factor: float = 1.0
    smart_snap: bool = True
    grid_snap: bool = False
    grid_step: float = 5.0
    snap_tolerance: float = 5.0
    enclosure_volume_l: float = 20.0

    @classmethod
    def from_values(cls, values: dict[str, Any] | None) -> "VentGeneratorSettings":
        values = dict(values or {})
        try:
            section_kind = VentSectionKind(str(values.get("section_kind", VentSectionKind.RECTANGLE.value)))
        except Exception:
            section_kind = VentSectionKind.RECTANGLE
        try:
            flare_side = VentFlareSide(str(values.get("flare_side", VentFlareSide.NONE.value)))
        except Exception:
            flare_side = VentFlareSide.NONE
        rect_width = _float_value(values, "rect_width", 10.0, minimum=0.001)
        rect_height = _float_value(values, "rect_height", 10.0, minimum=0.001)
        section_area = _float_value(values, "section_area", rect_width * rect_height, minimum=0.001)
        if section_kind is VentSectionKind.RECTANGLE:
            section_area = rect_width * rect_height
        return cls(
            section_kind=section_kind,
            section_area=section_area,
            rect_width=rect_width,
            rect_height=rect_height,
            wall_thickness=_float_value(values, "wall_thickness", 3.0, minimum=0.001),
            target_length=_float_value(values, "target_length", 0.0, minimum=0.0),
            curve_radius=_float_value(values, "curve_radius", 0.0, minimum=0.0),
            curve_strength=_float_value(values, "curve_strength", 0.0, minimum=-1.0, maximum=1.0),
            fill_area=_bool_value(values, "fill_area", False),
            flare_side=flare_side,
            flare_factor=_float_value(values, "flare_factor", 1.0, minimum=1.0, maximum=10.0),
            smart_snap=_bool_value(values, "smart_snap", True),
            grid_snap=_bool_value(values, "grid_snap", False),
            grid_step=_float_value(values, "grid_step", 5.0, minimum=0.001, maximum=100_000.0),
            snap_tolerance=_float_value(values, "snap_tolerance", 5.0, minimum=0.01, maximum=10_000.0),
            enclosure_volume_l=_float_value(values, "enclosure_volume_l", 20.0, minimum=0.0, maximum=1_000_000.0),
        )

    def as_values(self) -> dict[str, Any]:
        return {
            "section_kind": self.section_kind.value,
            "section_area": self.section_area,
            "rect_width": self.rect_width,
            "rect_height": self.rect_height,
            "wall_thickness": self.wall_thickness,
            "target_length": self.target_length,
            "curve_radius": self.curve_radius,
            "curve_strength": self.curve_strength,
            "fill_area": self.fill_area,
            "flare_side": self.flare_side.value,
            "flare_factor": self.flare_factor,
            "smart_snap": self.smart_snap,
            "grid_snap": self.grid_snap,
            "grid_step": self.grid_step,
            "snap_tolerance": self.snap_tolerance,
            "enclosure_volume_l": self.enclosure_volume_l,
        }

    @property
    def is_rectangle(self) -> bool:
        return self.section_kind is VentSectionKind.RECTANGLE

    @property
    def flare_enabled(self) -> bool:
        return self.flare_side is not VentFlareSide.NONE


def apply_settings_to_payload(payload: VentPathDraft, settings: VentGeneratorSettings) -> None:
    """Apply validated Creator panel settings to a vent draft payload."""

    payload.section.kind = settings.section_kind
    payload.wall_thickness = settings.wall_thickness
    payload.target_length = settings.target_length if settings.target_length > 0.0 else None
    payload.curve_radius = settings.curve_radius
    payload.curve_strength = settings.curve_strength
    payload.fill_area = bool(settings.fill_area and settings.is_rectangle)
    payload.flare_side = settings.flare_side
    payload.flare_factor = settings.flare_factor
    if settings.is_rectangle:
        payload.section.width = settings.rect_width
        payload.section.height = settings.rect_height
        payload.section.area = settings.rect_width * settings.rect_height
        payload.compact_wall_fusion = True
        payload.only_walls = False
    else:
        payload.section.width = None
        payload.section.height = None
        payload.section.area = settings.section_area
        payload.compact_wall_fusion = False
        payload.only_walls = False
    try:
        mode = getattr(payload, "mode", None)
        if str(getattr(mode, "value", mode or "")).upper() == "MOD" and getattr(payload, "selected_index", None) is not None:
            payload.set_selected_segment_curve(radius=settings.curve_radius, strength=settings.curve_strength)
    except Exception:
        pass


def settings_from_payload(payload: VentPathDraft | None) -> VentGeneratorSettings:
    if payload is None:
        return VentGeneratorSettings()
    section = getattr(payload, "section", None)
    try:
        section_kind = VentSectionKind(str(getattr(section, "kind", VentSectionKind.RECTANGLE.value)))
    except Exception:
        section_kind = VentSectionKind.RECTANGLE
    try:
        flare_side = VentFlareSide(str(getattr(payload, "flare_side", VentFlareSide.NONE.value)))
    except Exception:
        flare_side = VentFlareSide.NONE
    width = getattr(section, "width", None)
    height = getattr(section, "height", None)
    area = float(getattr(section, "area", 100.0) or 100.0)
    if width is None or height is None:
        width = height = max(area, 0.001) ** 0.5
    return VentGeneratorSettings(
        section_kind=section_kind,
        section_area=max(area, 0.001),
        rect_width=max(float(width), 0.001),
        rect_height=max(float(height), 0.001),
        wall_thickness=max(float(getattr(payload, "wall_thickness", 3.0)), 0.001),
        target_length=max(float(getattr(payload, "target_length", 0.0) or 0.0), 0.0),
        curve_radius=max(float(getattr(payload, "curve_radius", 0.0)), 0.0),
        curve_strength=max(-1.0, min(1.0, float(getattr(payload, "curve_strength", 0.0)))),
        fill_area=bool(getattr(payload, "fill_area", False)),
        flare_side=flare_side,
        flare_factor=max(float(getattr(payload, "flare_factor", 1.0)), 1.0),
        smart_snap=True,
        grid_snap=False,
        grid_step=max(float(payload.snap_grid_step()), 0.001),
        snap_tolerance=max(float(payload.snap_grid_step()) * 0.45, 0.25),
        enclosure_volume_l=20.0,
    )


def vent_report_text(
    payload: VentPathDraft | None,
    *,
    fallback: str = "Pick a plane, then draw at least two route points.",
    enclosure_volume_l: float | None = None,
) -> str:
    if not isinstance(payload, VentPathDraft):
        return fallback
    dims = payload.section_dimensions()
    lines = [
        f"Waypoints: {len(payload.waypoints)}",
        f"Profile: {payload.section.kind.value if hasattr(payload.section.kind, 'value') else payload.section.kind} {dims[0]:.1f} × {dims[1]:.1f} mm",
        f"Wall: {payload.wall_thickness:.1f} mm",
    ]
    try:
        metrics = payload.metrics()
        lines.append(f"Length: {metrics.centerline_length:.1f} mm")
        lines.append(f"Event height: {metrics.inner_height:.1f} mm")
        if metrics.target_delta is not None:
            lines.append(f"Target delta: {metrics.target_delta:+.1f} mm")
    except Exception:
        try:
            metrics = payload.geometry_metrics()
            lines.append(f"Length: {metrics.centerline_length:.1f} mm")
        except Exception:
            pass
    if enclosure_volume_l is not None:
        estimate = estimate_vent_acoustics(payload, enclosure_volume_l=float(enclosure_volume_l))
        if estimate is not None:
            lines.append(f"Box volume: {estimate.enclosure_volume_l:.2f} L")
            if estimate.tuning_hz is not None:
                lines.append(f"Tuning: {estimate.tuning_hz:.1f} Hz")
            elif estimate.warnings:
                lines.append(f"Tuning: {estimate.warnings[0]}")
    try:
        validation = payload.validation_result()
        lines.append("Status: ready" if validation.ok else f"Status: {validation.message()}")
    except Exception:
        pass
    return "\n".join(lines)


__all__ = [
    "FLARE_CHOICES",
    "MODE_CHOICES",
    "SECTION_CHOICES",
    "VentGeneratorSettings",
    "apply_settings_to_payload",
    "settings_from_payload",
    "vent_report_text",
]
