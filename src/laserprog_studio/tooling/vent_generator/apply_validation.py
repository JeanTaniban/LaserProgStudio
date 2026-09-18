# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_vent_path_mesh


@dataclass(frozen=True, slots=True)
class VentApplyCheck:
    """User-facing readiness result for the Vent Generator Apply action."""

    ok: bool
    message: str
    mesh_kind: str = ""
    field_errors: dict[str, str] = field(default_factory=dict)
    mesh_vertices: int = 0
    mesh_triangles: int = 0

    @property
    def summary(self) -> str:
        if self.ok:
            details = []
            if self.mesh_kind:
                details.append(self.mesh_kind)
            if self.mesh_vertices and self.mesh_triangles:
                details.append(f"{self.mesh_vertices} vertices / {self.mesh_triangles} triangles")
            suffix = " · ".join(details)
            return f"Ready to apply{': ' + suffix if suffix else '.'}"
        return self.message or "Vent route is not ready."


def _kind_value(value: Any) -> str:
    return str(getattr(value, "value", value or "")).strip().lower()


def vent_mesh_kind(payload: VentPathDraft | None) -> str:
    if not isinstance(payload, VentPathDraft):
        return ""
    kind = _kind_value(getattr(getattr(payload, "section", None), "kind", ""))
    if kind == VentSectionKind.ROUND.value:
        return "round pipe"
    if bool(getattr(payload, "fill_area", False)):
        return "rectangular fill block"
    return "rectangular wall-only duct"


def _base_field_errors(payload: VentPathDraft) -> dict[str, str]:
    errors: dict[str, str] = {}
    section = payload.section
    kind = _kind_value(getattr(section, "kind", ""))
    try:
        wall = float(payload.wall_thickness)
    except Exception:
        wall = 0.0
    if wall <= 0.0:
        errors["wall_thickness"] = "Wall thickness must be greater than 0 mm."
    if kind == VentSectionKind.ROUND.value:
        try:
            area = float(getattr(section, "area", 0.0) or 0.0)
        except Exception:
            area = 0.0
        if area <= 0.0:
            errors["section_area"] = "Round pipe flow area must be greater than 0 mm²."
    else:
        try:
            width = float(getattr(section, "width", 0.0) or 0.0)
        except Exception:
            width = 0.0
        try:
            height = float(getattr(section, "height", 0.0) or 0.0)
        except Exception:
            height = 0.0
        if width <= 0.0:
            errors["rect_width"] = "Inner width must be greater than 0 mm."
        if height <= 0.0:
            errors["rect_height"] = "Inner height must be greater than 0 mm."
    try:
        flare_side = getattr(payload, "flare_side", VentFlareSide.NONE)
        if not isinstance(flare_side, VentFlareSide):
            flare_side = VentFlareSide(str(flare_side))
    except Exception:
        flare_side = VentFlareSide.NONE
    try:
        flare_factor = float(getattr(payload, "flare_factor", 1.0) or 1.0)
    except Exception:
        flare_factor = 1.0
    if flare_side is not VentFlareSide.NONE and flare_factor <= 1.0:
        errors["flare_factor"] = "Use a flare scale above 1.0×, or choose No flare."
    return errors


def validate_vent_apply_payload(payload: VentPathDraft | None) -> VentApplyCheck:
    """Validate Apply without building the final mesh."""

    if not isinstance(payload, VentPathDraft):
        return VentApplyCheck(False, "Pick a plane before applying the vent mesh.", field_errors={"vent_report": "No active vent route."})
    field_errors = _base_field_errors(payload)
    try:
        validation = payload.validation_result()
    except Exception as exc:
        return VentApplyCheck(False, f"Could not validate the vent route: {exc}", mesh_kind=vent_mesh_kind(payload), field_errors={"vent_report": str(exc), **field_errors})
    if not validation.ok:
        message = validation.message() or "Vent route is not ready."
        if "add at least 2 waypoints" in message:
            field_errors.setdefault("route_summary", "Add an inlet and an outlet waypoint before Apply.")
        field_errors.setdefault("vent_report", message)
        return VentApplyCheck(False, message, mesh_kind=vent_mesh_kind(payload), field_errors=field_errors)
    if field_errors:
        first = next(iter(field_errors.values()))
        return VentApplyCheck(False, first, mesh_kind=vent_mesh_kind(payload), field_errors=field_errors)
    return VentApplyCheck(True, "Ready to apply.", mesh_kind=vent_mesh_kind(payload))


def preflight_vent_apply_mesh(payload: VentPathDraft | None) -> VentApplyCheck:
    """Validate and build the final mesh once so Apply can fail before touching app state."""

    check = validate_vent_apply_payload(payload)
    if not check.ok:
        return check
    assert isinstance(payload, VentPathDraft)
    try:
        mesh = make_vent_path_mesh(payload)
    except Exception as exc:
        return VentApplyCheck(
            False,
            f"Mesh generation failed: {exc}",
            mesh_kind=vent_mesh_kind(payload),
            field_errors={"vent_report": str(exc), "apply_check": str(exc)},
        )
    vertices = len(getattr(mesh, "vertices", ()) or ())
    triangles = len(getattr(mesh, "triangles", ()) or ())
    if vertices <= 0 or triangles <= 0:
        return VentApplyCheck(
            False,
            "Mesh generation produced an empty mesh.",
            mesh_kind=vent_mesh_kind(payload),
            field_errors={"vent_report": "Generated mesh is empty.", "apply_check": "Generated mesh is empty."},
        )
    return VentApplyCheck(True, "Ready to apply.", mesh_kind=vent_mesh_kind(payload), mesh_vertices=vertices, mesh_triangles=triangles)


__all__ = ["VentApplyCheck", "preflight_vent_apply_mesh", "validate_vent_apply_payload", "vent_mesh_kind"]
