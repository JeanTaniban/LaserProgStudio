# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
from dataclasses import replace
from typing import Any

from laserprog_studio.modifiers.split_plane import split_selected_meshes_by_plane
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.inspector import (
    AutoPreview,
    BoolField,
    ButtonRow,
    ChoiceField,
    FloatField,
    HelpText,
    InspectorActionEvent,
    Panel,
    ReadonlyField,
    Section,
)

from .base import ToolSpec
from .ids import TOOL_MOD_SPLIT
from .preview_staleness import cancel_tool_preview_if_active
from .mesh_split import (
    CUSTOM_PRESET_ID,
    SPLIT_FEEDBACK_WINDOW_ID,
    bounds_size,
    build_split_feedback_window,
    center_of,
    scene_vertices,
    selected_indices_text,
    split_preset_choices,
    split_preset_note,
    split_preset_values,
    split_settings_from_values,
    triangle_count,
    validate_split_targets,
)


_SPLIT_PLANE_FACE_ID = "modifier_split:plane_face"
_SPLIT_PLANE_OUTLINE_ID = "modifier_split:plane_outline"
_SPLIT_PLANE_HANDLE_ID = "modifier_split:plane_handle"
_SPLIT_CUT_LINE_ID = "modifier_split:cut_line"
_SPLIT_PLANE_CENTER_ID = "modifier_split:plane_center"
_SPLIT_ROTATE_X_ID = "modifier_split:rotate_x"
_SPLIT_ROTATE_Y_ID = "modifier_split:rotate_y"
_SPLIT_ROTATE_HANDLE_IDS = (_SPLIT_ROTATE_X_ID, _SPLIT_ROTATE_Y_ID)
_SPLIT_ROTATION_FIELD_BY_HANDLE = {
    _SPLIT_ROTATE_X_ID: "rx_deg",
    _SPLIT_ROTATE_Y_ID: "ry_deg",
}
# Two useful relative tilts only.  The old Rz/twist control was removed because
# twisting a cutting plane around its own normal does not change the cut and made
# the gizmo noisy.
_SPLIT_ROTATION_SNAP_DEGREES = 5.0
_SPLIT_ROTATION_MAJOR_SNAP_DEGREES = 90.0
_SPLIT_ROTATION_LABEL_ID_BY_HANDLE = {
    _SPLIT_ROTATE_X_ID: "modifier_split:rotate_x_label",
    _SPLIT_ROTATE_Y_ID: "modifier_split:rotate_y_label",
}


def _add3(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _mul3(v: tuple[float, float, float], scale: float) -> tuple[float, float, float]:
    return (float(v[0]) * float(scale), float(v[1]) * float(scale), float(v[2]) * float(scale))


def _dot3(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross3(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _normalize3_local(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return (float(v[0]) / length, float(v[1]) / length, float(v[2]) / length)


def _rotate_vector_about_axis(
    vector: tuple[float, float, float],
    axis: tuple[float, float, float],
    degrees: float,
) -> tuple[float, float, float]:
    """Rotate ``vector`` around ``axis`` using Rodrigues' formula."""

    vx, vy, vz = _normalize3_local(vector)
    ax, ay, az = _normalize3_local(axis)
    radians = math.radians(float(degrees))
    c = math.cos(radians)
    s_ = math.sin(radians)
    dot = vx * ax + vy * ay + vz * az
    cross = (ay * vz - az * vy, az * vx - ax * vz, ax * vy - ay * vx)
    return _normalize3_local((
        vx * c + cross[0] * s_ + ax * dot * (1.0 - c),
        vy * c + cross[1] * s_ + ay * dot * (1.0 - c),
        vz * c + cross[2] * s_ + az * dot * (1.0 - c),
    ))


def _normal_to_two_tilt_degrees(normal: tuple[float, float, float]) -> tuple[float, float]:
    """Represent a normal with the two useful Split inspector angles.

    The Split UI intentionally has no twist/Rz angle: rotating a plane around
    its own normal does not alter the cut.  Any normal can still be represented
    by Rx/Ry with Rz fixed to zero.
    """

    nx, ny, nz = _normalize3_local(normal)
    rx = math.degrees(math.asin(max(-1.0, min(1.0, -ny))))
    cos_rx = math.cos(math.radians(rx))
    if abs(cos_rx) <= 1.0e-9:
        ry = 0.0
    else:
        ry = math.degrees(math.atan2(nx, nz))
    return (_bounded_angle_degrees(rx), _bounded_angle_degrees(ry))


def _plane_basis(normal: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    n = _normalize3_local(normal)
    helper = (0.0, 0.0, 1.0) if abs(float(n[2])) < 0.88 else (0.0, 1.0, 0.0)
    x_axis = _normalize3_local(_cross3(helper, n))
    y_axis = _normalize3_local(_cross3(n, x_axis))
    return x_axis, y_axis


def _plane_corners(origin: tuple[float, float, float], normal: tuple[float, float, float], size: float) -> tuple[tuple[float, float, float], ...]:
    x_axis, y_axis = _plane_basis(normal)
    half = max(float(size), 1.0e-6) * 0.5
    return (
        _add3(_add3(origin, _mul3(x_axis, -half)), _mul3(y_axis, -half)),
        _add3(_add3(origin, _mul3(x_axis, half)), _mul3(y_axis, -half)),
        _add3(_add3(origin, _mul3(x_axis, half)), _mul3(y_axis, half)),
        _add3(_add3(origin, _mul3(x_axis, -half)), _mul3(y_axis, half)),
    )


def _project_points_on_axis(
    points: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]],
    center: tuple[float, float, float],
    axis: tuple[float, float, float],
) -> tuple[float, float]:
    values = [_dot3((float(p[0]) - float(center[0]), float(p[1]) - float(center[1]), float(p[2]) - float(center[2])), axis) for p in points]
    if not values:
        return (0.0, 0.0)
    lo, hi = float(min(values)), float(max(values))
    if hi < lo:
        lo, hi = hi, lo
    return (lo, hi)


def _split_offset_limits_from_check(check: Any) -> tuple[float, float]:
    values = getattr(check, "offset_limits", None)
    if values is not None:
        try:
            lo, hi = tuple(float(v) for v in values[:2])
            if hi < lo:
                lo, hi = hi, lo
            return (lo, hi)
        except Exception:
            pass
    return (0.0, 0.0)


def _clamp_split_offset_value(ctx: Any, value: float, normal: tuple[float, float, float] | None = None) -> float:
    settings_values = dict(ctx.inspector.values())
    if normal is None:
        normal = split_settings_from_values(settings_values).normal
    try:
        meshes = list(ctx.document.meshes(include_preview=False))
        selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
        points = tuple(scene_vertices(meshes, selected))
        if not points:
            return float(value)
        center = tuple(float(v) for v in center_of(list(points)))
        lo, hi = _project_points_on_axis(points, center, _normalize3_local(normal))
        return float(min(max(float(value), float(lo)), float(hi)))
    except Exception:
        return float(value)


def _plane_display_extents_from_points(
    points: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]],
    normal: tuple[float, float, float],
) -> tuple[float, float, tuple[float, float, float], tuple[float, float, float]]:
    x_axis, y_axis = _plane_basis(normal)
    if not points:
        return (20.0, 20.0, x_axis, y_axis)
    center = center_of(list(points))
    u0, u1 = _project_points_on_axis(points, center, x_axis)
    v0, v1 = _project_points_on_axis(points, center, y_axis)
    width = max(float(u1 - u0), 1.0)
    height = max(float(v1 - v0), 1.0)
    # Small visible margin outside the model so the cutter stays readable without
    # looking like it can be dragged into empty space.
    width = max(width * 1.08, width + 4.0, 20.0)
    height = max(height * 1.08, height + 4.0, 20.0)
    return (float(width), float(height), x_axis, y_axis)


def _plane_corners_rect(
    origin: tuple[float, float, float],
    x_axis: tuple[float, float, float],
    y_axis: tuple[float, float, float],
    width: float,
    height: float,
) -> tuple[tuple[float, float, float], ...]:
    half_w = max(float(width), 1.0e-6) * 0.5
    half_h = max(float(height), 1.0e-6) * 0.5
    return (
        _add3(_add3(origin, _mul3(x_axis, -half_w)), _mul3(y_axis, -half_h)),
        _add3(_add3(origin, _mul3(x_axis, half_w)), _mul3(y_axis, -half_h)),
        _add3(_add3(origin, _mul3(x_axis, half_w)), _mul3(y_axis, half_h)),
        _add3(_add3(origin, _mul3(x_axis, -half_w)), _mul3(y_axis, half_h)),
    )


def _triangle_plane_segment(
    vertices: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
    *,
    eps: float = 1.0e-7,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    distances = [_dot3((p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]), normal) for p in vertices]
    points: list[tuple[float, float, float]] = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a = vertices[i]
        b = vertices[j]
        da = float(distances[i])
        db = float(distances[j])
        if abs(da) <= eps and abs(db) <= eps:
            points.extend((a, b))
            continue
        if abs(da) <= eps:
            points.append(a)
            continue
        if abs(db) <= eps:
            points.append(b)
            continue
        if (da < 0.0 < db) or (db < 0.0 < da):
            t = da / (da - db)
            points.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))
    unique: list[tuple[float, float, float]] = []
    for p in points:
        q = (float(p[0]), float(p[1]), float(p[2]))
        if not any(math.dist(q, existing) <= eps * 10.0 for existing in unique):
            unique.append(q)
    if len(unique) < 2:
        return None
    if len(unique) > 2:
        # Coplanar triangle: draw the longest edge on the cutter plane to make
        # the affected zone visible without flooding the overlay.
        best = (unique[0], unique[1])
        best_len = -1.0
        for i in range(len(unique)):
            for j in range(i + 1, len(unique)):
                length = math.dist(unique[i], unique[j])
                if length > best_len:
                    best_len = length
                    best = (unique[i], unique[j])
        return best
    if math.dist(unique[0], unique[1]) <= eps * 10.0:
        return None
    return (unique[0], unique[1])


def _cut_line_segments_for_selection(ctx: Any, origin: tuple[float, float, float], normal: tuple[float, float, float]) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...]:
    try:
        meshes = list(ctx.document.meshes(include_preview=False))
        selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    except Exception:
        return ()
    out: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    normal = _normalize3_local(normal)
    for index in selected:
        if not (0 <= int(index) < len(meshes)):
            continue
        mesh = meshes[int(index)]
        verts = list(getattr(mesh, "vertices", ()) or ())
        for tri in getattr(mesh, "triangles", ()) or ():
            try:
                ids = tuple(int(v) for v in tri[:3])
                pts = tuple((float(verts[i][0]), float(verts[i][1]), float(verts[i][2])) for i in ids)
            except Exception:
                continue
            segment = _triangle_plane_segment(pts, origin, normal)
            if segment is not None:
                out.append(segment)
    return tuple(out)


def _axis_screen_delta_world(ctx: Any, actor_point: tuple[float, float, float], axis: tuple[float, float, float]) -> float | None:
    state = getattr(getattr(ctx, "selection", None), "state", None)
    if state is None:
        return None
    previous = getattr(state, "last_screen_pos", None)
    current = getattr(state, "current_screen_pos", None)
    if previous is None or current is None:
        return None
    projector = getattr(getattr(ctx, "viewport", None), "world_to_screen", None)
    if not callable(projector):
        return None
    unit = _normalize3_local(axis)
    try:
        start = projector(actor_point)
        end = projector(_add3(actor_point, unit))
        sx = float(end[0]) - float(start[0])
        sy = float(end[1]) - float(start[1])
        pixels_per_world = math.hypot(sx, sy)
        if not math.isfinite(pixels_per_world) or pixels_per_world <= 1.0e-7:
            return None
        dx = float(current[0]) - float(previous[0])
        dy = float(current[1]) - float(previous[1])
        projected_pixels = (dx * sx + dy * sy) / pixels_per_world
        return float(projected_pixels) / pixels_per_world
    except Exception:
        return None


def _screen_delta_px(ctx: Any) -> tuple[float, float] | None:
    state = getattr(getattr(ctx, "selection", None), "state", None)
    if state is None:
        return None
    previous = getattr(state, "last_screen_pos", None)
    current = getattr(state, "current_screen_pos", None)
    if previous is None or current is None:
        return None
    try:
        return (float(current[0]) - float(previous[0]), float(current[1]) - float(previous[1]))
    except Exception:
        return None


def _tilt_delta_degrees_from_drag(
    ctx: Any,
    *,
    handle_position: tuple[float, float, float],
    drag_axis: tuple[float, float, float],
) -> float | None:
    """Convert a stable two-axis handle drag into snapped tilt degrees.

    Unlike the old ring handles, these handles do not represent objects to move
    around the plane.  Pointer movement along the projected local plane axis is
    interpreted as an angular nudge, then the handle is redrawn from the updated
    plane.
    """

    delta = _screen_delta_px(ctx)
    if delta is None:
        return None
    dx, dy = delta
    projector = getattr(getattr(ctx, "viewport", None), "world_to_screen", None)
    if callable(projector):
        try:
            unit = _normalize3_local(drag_axis)
            start = projector(handle_position)
            end = projector(_add3(handle_position, unit))
            sx = float(end[0]) - float(start[0])
            sy = float(end[1]) - float(start[1])
            length = math.hypot(sx, sy)
            if math.isfinite(length) and length > 1.0e-7:
                signed_pixels = (float(dx) * sx + float(dy) * sy) / length
                return float(signed_pixels) * 0.35
        except Exception:
            pass
    # Headless fallback: large enough to cross one snap step in tests and small
    # enough not to jump unexpectedly for normal mouse movement.
    dominant = float(dx) if abs(float(dx)) >= abs(float(dy)) else float(dy)
    return dominant * 0.35


def _bounded_angle_degrees(value: float) -> float:
    angle = float(value)
    while angle > 360.0:
        angle -= 720.0
    while angle < -360.0:
        angle += 720.0
    return max(-360.0, min(360.0, angle))


def _snap_angle_degrees(value: float, snap_degrees: float = _SPLIT_ROTATION_SNAP_DEGREES) -> float:
    snap = abs(float(snap_degrees))
    if snap <= 1.0e-9 or not math.isfinite(snap):
        return _bounded_angle_degrees(value)
    return _bounded_angle_degrees(round(float(value) / snap) * snap)


def _format_degrees(value: float) -> str:
    try:
        angle = float(value)
    except Exception:
        angle = 0.0
    text = f"{angle:.0f}" if abs(angle - round(angle)) <= 1.0e-6 else f"{angle:.1f}"
    return f"{text}°"


def _screen_angle_degrees(point: tuple[float, float], center: tuple[float, float]) -> float:
    return math.degrees(math.atan2(float(point[1]) - float(center[1]), float(point[0]) - float(center[0])))


def _normalize_delta_degrees(value: float) -> float:
    delta = float(value)
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return delta


def _split_rotation_snap_enabled(ctx: Any) -> bool:
    try:
        return bool(ctx.inspector.value("rotation_snap_enabled", True))
    except Exception:
        return True


def _format_split_report(*, selected_count: int, before: int, split_count: int | None = None, new_piece_count: int | None = None, ok: bool = True, message: str = "") -> str:
    if message:
        return str(message)
    if split_count is None or new_piece_count is None:
        return f"Selected: {int(selected_count)}\nTriangles before: {int(before)}"
    prefix = "Split preview ready." if ok else "Split failed."
    return f"{prefix}\nSelected: {int(selected_count)}\nMeshes split: {int(split_count)}\nNew pieces: {int(new_piece_count)}"


class SplitPlaneCreatorTool(CreatorTool):
    """Product-ready split-plane modifier built on the Creator API."""

    id = TOOL_MOD_SPLIT
    label = "Split"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select meshes", help="Select one or more parts to split."),
                ctx.workflow.step("tune", "Tune split plane", help="Choose a plane preset or adjust the plane manually."),
                ctx.workflow.step("preview", "Preview split", help="Stage the split result before applying it.", optional=True),
            ),
        )
        ctx.operations.register("split", self._operation_split, replace=True)
        ctx.operations.register("split_plane", self._operation_split, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._initialize_defaults(ctx)
        self._sync_selection_report(ctx, default="Choose a split preset, then Preview.")
        ctx.status.info("Split ready. Select parts, preview the plane split, then Apply.")
        self._sync_plane_projection(ctx, render=True)

    def on_close(self, ctx: Any) -> None:
        try:
            ctx.projected_drawing.clear_tool(self.id, render=False)
        except Exception:
            pass
        ctx.overlay.hide_window(SPLIT_FEEDBACK_WINDOW_ID)
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        message = "Split cancelled." if not changed else "Split preview cancelled."
        self._set_report(ctx, message, ok=True)
        self._sync_feedback(ctx, status=message)
        self._sync_plane_projection(ctx, render=False)
        self._close_after_cancel(ctx)
        return True

    def on_apply(self, ctx: Any) -> bool:
        if not bool(getattr(ctx.document, "has_preview", False)):
            if not self._preview_action(ctx, None):
                message = "Split failed: preview could not be generated."
                self._set_report(ctx, message, ok=False)
                self._sync_feedback(ctx, status=message)
                return False
        changed = bool(ctx.preview_session.apply(label="Split applied", operation_type="modifier_split"))
        message = "Split applied." if changed else "Preview first, then apply."
        self._set_report(ctx, message, ok=changed)
        self._sync_feedback(ctx, status=message)
        if changed:
            ctx.status.info("Split applied.")
        return changed

    def on_event(self, event: Any, ctx: Any) -> bool:
        action_id = str(getattr(event, "action_id", "") or getattr(event, "id", ""))
        return self._handle_action_id(action_id, ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        self._handle_action_id(str(button_id), ctx)

    def _handle_action_id(self, action_id: str, ctx: Any) -> bool:
        if action_id in {"split_overlay_reset", "reset_plane"}:
            return self._reset_action(ctx, None)
        if action_id in {"split_overlay_orient_xy", "orient_xy"}:
            return self._orientation_snap_action(ctx, "center_z")
        if action_id in {"split_overlay_orient_yz", "orient_yz"}:
            return self._orientation_snap_action(ctx, "center_x")
        if action_id in {"split_overlay_orient_xz", "orient_xz"}:
            return self._orientation_snap_action(ctx, "center_y")
        if action_id in {"split_overlay_preview", "preview"}:
            return self._preview_action(ctx, None)
        if action_id in {"split_overlay_apply", "apply_split"}:
            return self._apply_action(ctx, None)
        if action_id in {"split_overlay_cancel", "cancel_preview"}:
            return self.on_cancel(ctx)
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        if not bool(getattr(self, "_updating_preview_selection", False)):
            cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the selection changed.")
        self._initialize_defaults(ctx, preserve_rotation=True)
        self._sync_selection_report(ctx)
        if ctx.scene_selection.selected_indices():
            ctx.status.info("Split selection updated. Preview to stage the selected parts.")
        self._sync_plane_projection(ctx, render=True)
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        setting_change = lambda _field, _value: self._on_setting_changed(ctx)
        return Panel(
            "Split",
            id="modifier.split",
            owner_tool=self.id,
            description="Cut selected meshes with plane presets, preflight checks and a non-destructive preview.",
            auto_preview=AutoPreview(
                action_id="preview",
                debounce_ms=350,
                include_fields=("split_preset", "offset_mm", "rx_deg", "ry_deg", "plane_size_mm", "tolerance"),
            ),
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("split_help", "Select one or more real parts. Preview stages the split result; Apply commits it."),
                        ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                        ReadonlyField("preflight_check", "Check", default="No split target checked yet."),
                    ),
                ),
                Section(
                    "Quick split",
                    fields=(
                        ChoiceField("split_preset", "Preset", default="center_z", choices=split_preset_choices(), on_change=lambda _field, value: self._on_preset_change(ctx, value)),
                        ReadonlyField("preset_note", "Preset note", default=split_preset_note("center_z")),
                    ),
                ),
                Section(
                    "Orientation",
                    fields=(
                        HelpText("rotation_snap_help", "Two useful tilts only: no twist around the plane normal. Drag handles use a stable rotate-style gesture. Snap can be toggled."),
                        replace(BoolField("rotation_snap_enabled", "Snap rotation", default=True, tooltip="When enabled, Tilt U/V drags and buttons snap to 5° steps."), metadata={"persist": False}),
                        ButtonRow(
                            "split_orientation_actions",
                            "Quick planes",
                            buttons=(("orient_xy", "XY"), ("orient_yz", "YZ"), ("orient_xz", "XZ")),
                            callbacks={
                                "orient_xy": lambda _event: self._orientation_snap_action(ctx, "center_z"),
                                "orient_yz": lambda _event: self._orientation_snap_action(ctx, "center_x"),
                                "orient_xz": lambda _event: self._orientation_snap_action(ctx, "center_y"),
                            },
                        ),
                        ButtonRow(
                            "split_tilt_nudges",
                            "Tilt snaps",
                            buttons=(("tilt_u_minus", "U -5°"), ("tilt_u_plus", "U +5°"), ("tilt_v_minus", "V -5°"), ("tilt_v_plus", "V +5°"), ("tilt_reset", "Reset")),
                            callbacks={
                                "tilt_u_minus": lambda _event: self._tilt_nudge_action(ctx, "rx_deg", -_SPLIT_ROTATION_SNAP_DEGREES),
                                "tilt_u_plus": lambda _event: self._tilt_nudge_action(ctx, "rx_deg", _SPLIT_ROTATION_SNAP_DEGREES),
                                "tilt_v_minus": lambda _event: self._tilt_nudge_action(ctx, "ry_deg", -_SPLIT_ROTATION_SNAP_DEGREES),
                                "tilt_v_plus": lambda _event: self._tilt_nudge_action(ctx, "ry_deg", _SPLIT_ROTATION_SNAP_DEGREES),
                                "tilt_reset": lambda _event: self._tilt_reset_action(ctx),
                            },
                        ),
                    ),
                ),
                Section(
                    "Plane",
                    fields=(
                        FloatField("offset_mm", "Offset", default=0.0, min_value=-1_000_000.0, max_value=1_000_000.0, step=1.0, unit="mm", on_change=setting_change),
                        FloatField("rx_deg", "Tilt U", default=0.0, min_value=-360.0, max_value=360.0, step=5.0, unit="°", on_change=setting_change),
                        FloatField("ry_deg", "Tilt V", default=0.0, min_value=-360.0, max_value=360.0, step=5.0, unit="°", on_change=setting_change),
                        FloatField("plane_size_mm", "Plane size", default=120.0, min_value=1.0, max_value=1_000_000.0, step=5.0, unit="mm", on_change=setting_change),
                        FloatField("tolerance", "Tolerance", default=0.00001, min_value=0.00000001, max_value=10.0, step=0.00001, unit="mm", on_change=setting_change),
                    ),
                ),
                Section(
                    "Preview and apply",
                    fields=(
                        ButtonRow(
                            "split_actions",
                            "Actions",
                            buttons=(("reset_plane", "Recenter"), ("preview", "Preview"), ("apply_split", "Apply"), ("cancel_preview", "Cancel")),
                            callbacks={
                                "reset_plane": lambda event: self._reset_action(ctx, event),
                                "preview": lambda event: self._preview_action(ctx, event),
                                "apply_split": lambda event: self._apply_action(ctx, event),
                                "cancel_preview": lambda _event: self.on_cancel(ctx),
                            },
                        ),
                        ReadonlyField("split_report", "Report", default="Ready. Preview split to stage selected parts."),
                    ),
                ),
            ),
        )

    def _operation_split(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        settings = split_settings_from_values(params)
        clamped_offset = _clamp_split_offset_value(ctx, settings.offset_mm, settings.normal)
        if abs(float(clamped_offset) - float(settings.offset_mm)) > 1.0e-6:
            params = {**params, "offset_mm": clamped_offset}
            settings = split_settings_from_values(params)
        check = validate_split_targets(ctx, settings)
        if not check.ok:
            return OperationResult.failure(check.message, report=check.message)

        base_meshes = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        target = tuple(int(i) for i in check.target_indices)
        before = sum(triangle_count(base_meshes[i]) for i in target)
        try:
            meshes, new_selection, split_count, new_piece_count = split_selected_meshes_by_plane(
                [copy.deepcopy(mesh) for mesh in base_meshes],
                list(target),
                origin=check.origin,
                normal=check.normal,
                tolerance=settings.tolerance,
            )
        except Exception as exc:
            return OperationResult.failure(str(exc), report=str(exc))

        if int(split_count) <= 0:
            report = "No split: the plane does not cross the selected mesh volume. Adjust offset or rotation."
            return OperationResult.failure(
                report,
                report=report,
                metadata={"selected_indices": target, "origin": check.origin, "normal": check.normal, "settings_summary": settings.summary},
            )

        selected_out = tuple(int(i) for i in new_selection if 0 <= int(i) < len(meshes))
        report = _format_split_report(selected_count=len(target), before=before, split_count=int(split_count), new_piece_count=int(new_piece_count))
        return OperationResult.success(
            tuple(meshes),
            report=report,
            metadata={
                "changed_indices": selected_out,
                "selected_indices": selected_out,
                "source_indices": target,
                "split_count": int(split_count),
                "new_piece_count": int(new_piece_count),
                "before_triangles": before,
                "origin": check.origin,
                "normal": check.normal,
                "tolerance": settings.tolerance,
                "settings_summary": settings.summary,
                "preset_id": settings.preset_id,
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        self._normalize_plane_values(ctx, update_size=False)
        values = dict(event.values if event is not None else ctx.inspector.values())
        settings = split_settings_from_values(values)
        clamped_offset = _clamp_split_offset_value(ctx, settings.offset_mm, settings.normal)
        if abs(float(clamped_offset) - float(settings.offset_mm)) > 1.0e-6:
            values["offset_mm"] = clamped_offset
            try:
                ctx.inspector.update_value("offset_mm", clamped_offset, notify=False)
            except Exception:
                pass
            settings = split_settings_from_values(values)
        check = validate_split_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if not check.ok:
            ctx.status.error(check.message)
            self._set_report(ctx, check.message, ok=False)
            self._sync_feedback(ctx, status=check.message)
            return False

        result = ctx.operations.split(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Split operation finished."), ok=result.ok)
        self._sync_selection_report(ctx, update_report=False)
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Split failed."
            ctx.status.error(message)
            self._sync_feedback(ctx, status=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Split preview")
        session.show_meshes(result.meshes)
        selected = tuple(int(i) for i in result.metadata.get("changed_indices", ()) if isinstance(i, int) or str(i).isdigit())
        if selected:
            self._updating_preview_selection = True
            try:
                ctx.scene_selection.select_indices(selected, active_index=selected[-1])
            finally:
                self._updating_preview_selection = False
        ctx.workflow.goto("preview")
        ctx.status.info("Split preview ready. Use Apply to keep it or Cancel to discard it.")
        self._sync_feedback(ctx, status="Preview ready. Apply to keep it.")
        self._sync_plane_projection(ctx, render=True)
        return True

    def _apply_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if event is not None:
            # Inspector buttons pass a frozen value snapshot.  Mirror it into the
            # live inspector first so automatic Preview -> Apply uses exactly
            # what the user sees in the Plane section.
            for field_id, field_value in dict(event.values or {}).items():
                try:
                    ctx.inspector.update_value(field_id, field_value, notify=False)
                except Exception:
                    pass
        changed = bool(self.on_apply(ctx))
        if changed:
            self._close_after_apply(ctx)
        return changed

    def _close_after_apply(self, ctx: Any) -> None:
        """Close Split when Apply is clicked inside the split overlay/inspector.

        The host toolbar Apply path already closes Creator tools after
        ``on_apply`` returns True.  The Split mini-overlay and inspector action
        buttons are routed directly to this tool, so they must request the same
        lifecycle cleanup themselves.
        """

        owner = getattr(ctx, "owner", None)
        close = getattr(owner, "close_active_tool", None) if owner is not None else None
        if callable(close):
            try:
                close(log_it=False, ask_preview=False)
                return
            except TypeError:
                try:
                    close()
                    return
                except Exception:
                    pass
            except Exception:
                pass
        try:
            ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        except Exception:
            pass
        if owner is not None:
            try:
                setattr(owner, "active_tool", getattr(owner, "TOOL_NONE", "none"))
            except Exception:
                pass

    def _close_after_cancel(self, ctx: Any) -> None:
        """Close Split even when no preview exists.

        The mini-overlay Cancel is an exit button, not only a preview discard.
        """

        owner = getattr(ctx, "owner", None)
        close = getattr(owner, "close_active_tool", None) if owner is not None else None
        if callable(close):
            try:
                close(log_it=False, ask_preview=False)
                return
            except TypeError:
                try:
                    close()
                    return
                except Exception:
                    pass
            except Exception:
                pass
        try:
            ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        except Exception:
            pass
        if owner is not None:
            try:
                setattr(owner, "active_tool", getattr(owner, "TOOL_NONE", "none"))
            except Exception:
                pass

    def _orientation_snap_action(self, ctx: Any, preset_id: str) -> bool:
        cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the plane orientation changed.")
        values = split_preset_values(preset_id)
        for field_id, field_value in values.items():
            if field_id == "plane_size_factor":
                continue
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.update_value("split_preset", preset_id, notify=False)
            ctx.inspector.set_display_value("preset_note", split_preset_note(preset_id))
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_size=True)
        self._sync_selection_report(ctx, default="Orientation snapped. Preview to stage the split result.")
        self._sync_feedback(ctx, status="Orientation snapped.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)
        try:
            getattr(self, "_rotation_snap_residuals", {}).clear()
        except Exception:
            pass
        return True

    def _tilt_nudge_action(self, ctx: Any, field_id: str, delta_degrees: float) -> bool:
        if field_id not in {"rx_deg", "ry_deg"}:
            return False
        cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the plane tilt changed.")
        try:
            current = float(ctx.inspector.value(field_id, 0.0))
        except Exception:
            current = 0.0
        new_angle = _snap_angle_degrees(current + float(delta_degrees), _SPLIT_ROTATION_SNAP_DEGREES)
        try:
            ctx.inspector.update_value(field_id, _bounded_angle_degrees(new_angle), notify=False)
            # Twist is intentionally not exposed.  Keep old persisted values from
            # reappearing through presets or legacy settings.
            try:
                ctx.inspector.update_value("rz_deg", 0.0, notify=False)
            except Exception:
                pass
            ctx.inspector.update_value("split_preset", CUSTOM_PRESET_ID, notify=False)
            ctx.inspector.set_display_value("preset_note", split_preset_note(CUSTOM_PRESET_ID))
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_size=True)
        self._sync_selection_report(ctx, default="Plane tilt snapped. Preview to stage the split result.")
        self._sync_feedback(ctx, status="Plane tilt snapped.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)
        return True

    def _tilt_reset_action(self, ctx: Any) -> bool:
        cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the plane tilt was reset.")
        try:
            ctx.inspector.update_value("rx_deg", 0.0, notify=False)
            ctx.inspector.update_value("ry_deg", 0.0, notify=False)
            try:
                ctx.inspector.update_value("rz_deg", 0.0, notify=False)
            except Exception:
                pass
            ctx.inspector.update_value("split_preset", CUSTOM_PRESET_ID, notify=False)
            ctx.inspector.set_display_value("preset_note", split_preset_note(CUSTOM_PRESET_ID))
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_size=True)
        self._sync_selection_report(ctx, default="Plane tilt reset. Preview to stage the split result.")
        self._sync_feedback(ctx, status="Plane tilt reset.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)
        return True

    def _reset_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:  # noqa: ARG002
        cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the plane was recentered.")
        self._initialize_defaults(ctx)
        self._sync_selection_report(ctx, default="Plane recentered on the current selection.")
        self._sync_plane_projection(ctx, render=True)
        ctx.status.info("Split plane recentered on selection.")
        return True

    def _initialize_defaults(self, ctx: Any, *, preserve_rotation: bool = False) -> None:
        try:
            meshes = list(ctx.document.meshes(include_preview=False))
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            points = tuple(scene_vertices(meshes, selected) if selected else scene_vertices(meshes))
            current_values = dict(ctx.inspector.values())
            rx = float(current_values.get("rx_deg", 0.0)) if preserve_rotation else 0.0
            ry = float(current_values.get("ry_deg", 0.0)) if preserve_rotation else 0.0
            from .mesh_split import normal_from_euler_xyz_deg

            normal = normal_from_euler_xyz_deg(rx, ry, 0.0)
            width, height, _x_axis, _y_axis = _plane_display_extents_from_points(points, normal)
            updates: dict[str, Any] = {"offset_mm": 0.0, "plane_size_mm": max(width, height), "rotation_snap_enabled": True}
            if not preserve_rotation:
                updates.update({"rx_deg": 0.0, "ry_deg": 0.0})
            ctx.inspector.update_values(updates, notify=False)
        except Exception:
            pass

    def _on_preset_change(self, ctx: Any, value: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the plane preset changed.")
        preset_id = str(value or CUSTOM_PRESET_ID)
        values = split_preset_values(preset_id)
        plane_factor = values.pop("plane_size_factor", None)
        if plane_factor is not None:
            try:
                meshes = list(ctx.document.meshes(include_preview=False))
                selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
                points = tuple(scene_vertices(meshes, selected) if selected else scene_vertices(meshes))
                rx = float(values.get("rx_deg", ctx.inspector.value("rx_deg", 0.0)))
                ry = float(values.get("ry_deg", ctx.inspector.value("ry_deg", 0.0)))
                from .mesh_split import normal_from_euler_xyz_deg

                normal = normal_from_euler_xyz_deg(rx, ry, 0.0)
                width, height, _x_axis, _y_axis = _plane_display_extents_from_points(points, normal)
                values["plane_size_mm"] = max(width, height, 20.0) * max(float(plane_factor), 1.0)
            except Exception:
                pass
        for field_id, field_value in values.items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.set_display_value("preset_note", split_preset_note(preset_id))
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_size=True)
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preset loaded." if preset_id != CUSTOM_PRESET_ID else "Custom split settings.")
        self._sync_plane_projection(ctx, render=True)

    def _on_setting_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because plane settings changed.")
        try:
            if ctx.inspector.value("split_preset", CUSTOM_PRESET_ID) != CUSTOM_PRESET_ID:
                ctx.inspector.update_value("split_preset", CUSTOM_PRESET_ID, notify=False)
                ctx.inspector.set_display_value("preset_note", split_preset_note(CUSTOM_PRESET_ID))
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_size=True)
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Split plane edited.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)

    def _refresh_host_inspector(self, ctx: Any) -> None:
        """Ask the live Creator inspector to repaint programmatic value edits."""

        try:
            owner = getattr(ctx, "owner", None)
            stack = getattr(owner, "tool_panel_stack", None) if owner is not None else None
            current = stack.currentWidget() if stack is not None and hasattr(stack, "currentWidget") else None
            widgets = [current] if current is not None else []
            if current is not None and hasattr(current, "findChildren"):
                try:
                    widgets.extend(list(current.findChildren(type(current))))
                except Exception:
                    pass
            for widget in widgets:
                refresh = getattr(widget, "refresh", None)
                if callable(refresh):
                    refresh()
                    return
        except Exception:
            pass
        try:
            owner = getattr(ctx, "owner", None)
            updater = getattr(owner, "update_inspector", None)
            if callable(updater):
                updater()
        except Exception:
            pass

    def _normalize_plane_values(self, ctx: Any, *, update_size: bool) -> None:
        """Clamp the plane inside the selected model and refresh derived size fields."""

        try:
            settings = split_settings_from_values(ctx.inspector.values())
            clamped = _clamp_split_offset_value(ctx, float(settings.offset_mm), settings.normal)
            updates: dict[str, Any] = {}
            if abs(float(clamped) - float(settings.offset_mm)) > 1.0e-6:
                updates["offset_mm"] = clamped
            if update_size:
                meshes = list(ctx.document.meshes(include_preview=False))
                selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
                points = tuple(scene_vertices(meshes, selected) if selected else scene_vertices(meshes))
                width, height, _x_axis, _y_axis = _plane_display_extents_from_points(points, settings.normal)
                derived_size = max(float(width), float(height))
                if abs(float(derived_size) - float(settings.plane_size_mm)) > 1.0e-6:
                    updates["plane_size_mm"] = derived_size
            if updates:
                ctx.inspector.update_values(updates, notify=False)
                self._refresh_host_inspector(ctx)
        except Exception:
            pass

    def _sync_plane_projection(self, ctx: Any, *, render: bool = True) -> bool:
        """Draw the split plane, cut line and centered drag handle in Projected Drawing 2D."""

        try:
            from laserprog_studio.tool_api import projected_drawing as pd

            self._normalize_plane_values(ctx, update_size=False)
            settings = split_settings_from_values(ctx.inspector.values())
            check = validate_split_targets(ctx, settings)
            registry = ctx.projected_drawing.for_tool(self.id)
            if not check.ok:
                registry.clear(render=render)
                return False
            normal = _normalize3_local(tuple(float(v) for v in check.normal))
            origin = tuple(float(v) for v in check.origin)
            meshes = list(ctx.document.meshes(include_preview=False))
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            points = tuple(scene_vertices(meshes, selected))
            width, height, x_axis, y_axis = _plane_display_extents_from_points(points, normal)
            derived_size = max(width, height)
            try:
                if abs(float(ctx.inspector.value("plane_size_mm", derived_size)) - float(derived_size)) > 1.0e-6:
                    ctx.inspector.update_value("plane_size_mm", derived_size, notify=False)
                    self._refresh_host_inspector(ctx)
            except Exception:
                pass
            corners = _plane_corners_rect(origin, x_axis, y_axis, width, height)
            cut_segments = _cut_line_segments_for_selection(ctx, origin, normal)
            primitives: list[Any] = [
                pd.face(
                    _SPLIT_PLANE_FACE_ID,
                    corners,
                    fill_color="#66D9FF",
                    fill_opacity=0.16,
                    outline_color="#FFFFFF",
                    outline_width_px=2.0,
                    outline_opacity=0.92,
                    layer=18,
                    interaction=pd.ProjectedInteraction.FIXED,
                    metadata={"modifier_role": "split_plane_face", "projected_no_selection_actor": True, "width_mm": width, "height_mm": height},
                ),
                pd.polyline(
                    _SPLIT_PLANE_OUTLINE_ID,
                    corners,
                    closed=True,
                    color="#FFFFFF",
                    width_px=2.0,
                    opacity=0.96,
                    layer=20,
                    interaction=pd.ProjectedInteraction.FIXED,
                    metadata={"modifier_role": "split_plane_outline", "projected_no_selection_actor": True},
                ),
                pd.point(
                    _SPLIT_PLANE_CENTER_ID,
                    origin,
                    color="#FF6E32",
                    size_px=9.0,
                    opacity=1.0,
                    layer=32,
                    interaction=pd.ProjectedInteraction.FIXED,
                    metadata={"modifier_role": "split_plane_center", "projected_no_selection_actor": True},
                ),
                pd.drag_arrow(
                    _SPLIT_PLANE_HANDLE_ID,
                    origin,
                    normal,
                    constraint=pd.ProjectedDragConstraint.FREE,
                    color="#FFD54F",
                    size_px=38.0,
                    layer=36,
                    metadata={"modifier_role": "split_plane_handle", "normal": normal, "handle_distance": 0.0, "attached_to_plane_center": True},
                ),
            ]
            snap_enabled = _split_rotation_snap_enabled(ctx)
            snap_label = f"{int(_SPLIT_ROTATION_SNAP_DEGREES)}°" if snap_enabled else "free"
            rotate_margin = max(8.0, min(float(width), float(height)) * 0.08)
            rotate_specs = (
                # Tilt U rotates the plane around its current local U axis.  The
                # handle sits on the V edge, so it reads as a stable lever rather
                # than a free-moving point.
                (_SPLIT_ROTATE_X_ID, "rx_deg", _add3(origin, _mul3(y_axis, float(height) * 0.5 + rotate_margin)), x_axis, y_axis, "#F26D6D", "Tilt U"),
                (_SPLIT_ROTATE_Y_ID, "ry_deg", _add3(origin, _mul3(x_axis, float(width) * 0.5 + rotate_margin)), y_axis, x_axis, "#67C587", "Tilt V"),
            )
            for handle_id, field_id, position, tilt_axis, drag_axis, color, label in rotate_specs:
                try:
                    angle_text = _format_degrees(ctx.inspector.value(field_id, 0.0))
                except Exception:
                    angle_text = "0°"
                label_position = _add3(position, _mul3(_normalize3_local((float(position[0]) - float(origin[0]), float(position[1]) - float(origin[1]), float(position[2]) - float(origin[2]))), 3.0))
                primitives.append(
                    pd.handle(
                        handle_id,
                        position,
                        shape=pd.ProjectedHandleShape.CHEVRON,
                        direction=drag_axis,
                        constraint=pd.ProjectedDragConstraint.FREE,
                        color=color,
                        size_px=34.0,
                        line_width_px=3.0,
                        layer=38,
                        metadata={
                            "modifier_role": "split_plane_tilt_handle",
                            "rotation_field": field_id,
                            "tilt_axis": tuple(float(v) for v in tilt_axis),
                            "drag_axis": tuple(float(v) for v in drag_axis),
                            "center": origin,
                            "label": label,
                            "snap_degrees": _SPLIT_ROTATION_SNAP_DEGREES,
                            "snap_enabled": snap_enabled,
                            "major_snap_degrees": _SPLIT_ROTATION_MAJOR_SNAP_DEGREES,
                            "rotation_mode": "relative_two_axis_snap",
                            "drag_model": "stable_screen_angle",
                            "stable_handle": True,
                        },
                    )
                )
                primitives.append(
                    pd.text(
                        _SPLIT_ROTATION_LABEL_ID_BY_HANDLE[handle_id],
                        f"{label} {angle_text} · {snap_label}",
                        label_position,
                        color=color,
                        size_px=12,
                        opacity=0.96,
                        anchor="center",
                        layer=39,
                        metadata={"modifier_role": "split_plane_tilt_label", "projected_no_selection_actor": True, "rotation_field": field_id},
                    )
                )
            if cut_segments:
                primitives.append(
                    pd.segment_batch(
                        _SPLIT_CUT_LINE_ID,
                        cut_segments,
                        color="#FF6E32",
                        width_px=4.0,
                        opacity=1.0,
                        layer=34,
                    )
                )
            registry.replace_all(tuple(primitives), render=render)
            return True
        except Exception:
            try:
                ctx.projected_drawing.clear_tool(self.id, render=render)
            except Exception:
                pass
            return False

    def resolve_drag_positions(self, event: Any, ctx: Any) -> dict[str, Any] | None:  # noqa: ARG002
        grabbed = tuple(str(value) for value in getattr(getattr(ctx.selection, "state", None), "grabbed_ids", ()) or ())
        if _SPLIT_PLANE_HANDLE_ID in grabbed:
            return self._resolve_plane_offset_drag(ctx)
        rotate_id = next((handle_id for handle_id in _SPLIT_ROTATE_HANDLE_IDS if handle_id in grabbed), None)
        if rotate_id is not None:
            return self._resolve_plane_rotation_drag(event, ctx, rotate_id)
        return None

    def _resolve_plane_offset_drag(self, ctx: Any) -> dict[str, Any] | None:
        actor = ctx.selection.actor(_SPLIT_PLANE_HANDLE_ID)
        if actor is None or not getattr(actor, "points", ()):  # pragma: no cover - defensive
            return None
        settings = split_settings_from_values(ctx.inspector.values())
        check = validate_split_targets(ctx, settings)
        if not check.ok:
            return None
        normal = _normalize3_local(tuple(float(v) for v in check.normal))
        actor_point = tuple(float(v) for v in actor.points[0])
        distance_delta = _axis_screen_delta_world(ctx, actor_point, normal)
        if distance_delta is None:
            raw_delta = getattr(getattr(ctx.selection, "state", None), "last_move_delta", None)
            if raw_delta is None:
                return None
            try:
                distance_delta = _dot3(tuple(float(v) for v in raw_delta), normal)
            except Exception:
                return None
        new_offset = _clamp_split_offset_value(ctx, float(settings.offset_mm) + float(distance_delta), normal)
        try:
            ctx.inspector.update_value("offset_mm", new_offset, notify=False)
            ctx.inspector.update_value("split_preset", CUSTOM_PRESET_ID, notify=False)
            ctx.inspector.set_display_value("preset_note", split_preset_note(CUSTOM_PRESET_ID))
            self._refresh_host_inspector(ctx)
        except Exception:
            pass
        # Keep reports and projected plane coherent during the drag without using
        # the retired PyVista split overlay path.
        self._sync_selection_report(ctx, update_report=False)
        self._sync_plane_projection(ctx, render=False)
        updated_settings = split_settings_from_values(ctx.inspector.values())
        updated_check = validate_split_targets(ctx, updated_settings)
        if not updated_check.ok:
            return None
        updated_normal = _normalize3_local(tuple(float(v) for v in updated_check.normal))
        handle_pos = tuple(float(v) for v in updated_check.origin)
        metadata = {**(getattr(actor, "metadata", {}) or {}), "normal": updated_normal, "handle_distance": 0.0, "attached_to_plane_center": True}
        return {_SPLIT_PLANE_HANDLE_ID: replace(actor, points=(handle_pos,), metadata=metadata)}

    def _event_screen_pos(self, event: Any, ctx: Any) -> tuple[float, float] | None:
        pos = getattr(event, "screen_pos", None)
        if pos is None:
            state = getattr(getattr(ctx, "selection", None), "state", None)
            pos = getattr(state, "current_screen_pos", None) if state is not None else None
        if pos is None:
            return None
        try:
            return (float(pos[0]), float(pos[1]))
        except Exception:
            return None

    def _start_split_rotation_drag(self, ctx: Any, handle_id: str, event: Any) -> bool:
        actor = ctx.selection.actor(handle_id)
        screen_pos = self._event_screen_pos(event, ctx)
        state_obj = getattr(getattr(ctx, "selection", None), "state", None)
        start_screen = getattr(state_obj, "start_screen_pos", None) if state_obj is not None else None
        if start_screen is not None:
            try:
                screen_pos = (float(start_screen[0]), float(start_screen[1]))
            except Exception:
                pass
        if actor is None or not getattr(actor, "points", ()) or screen_pos is None:
            return False
        settings = split_settings_from_values(ctx.inspector.values())
        check = validate_split_targets(ctx, settings)
        if not check.ok:
            return False
        metadata = dict(getattr(actor, "metadata", {}) or {})
        field_id = str(metadata.get("rotation_field") or _SPLIT_ROTATION_FIELD_BY_HANDLE.get(handle_id, ""))
        if field_id not in {"rx_deg", "ry_deg"}:
            return False
        normal = _normalize3_local(tuple(float(v) for v in check.normal))
        x_axis, y_axis = _plane_basis(normal)
        if field_id == "rx_deg":
            tilt_axis = x_axis
            drag_axis = y_axis
        else:
            tilt_axis = y_axis
            drag_axis = x_axis
        center_world = tuple(float(v) for v in check.origin)
        projector = getattr(getattr(ctx, "viewport", None), "world_to_screen", None)
        center_screen: tuple[float, float] | None = None
        start_angle: float | None = None
        drag_axis_screen: tuple[float, float] | None = None
        if callable(projector):
            try:
                c = projector(center_world)
                center_screen = (float(c[0]), float(c[1]))
                if math.hypot(float(screen_pos[0]) - center_screen[0], float(screen_pos[1]) - center_screen[1]) > 3.0:
                    start_angle = _screen_angle_degrees(screen_pos, center_screen)
                end = projector(_add3(center_world, drag_axis))
                sx = float(end[0]) - center_screen[0]
                sy = float(end[1]) - center_screen[1]
                length = math.hypot(sx, sy)
                if math.isfinite(length) and length > 1.0e-7:
                    drag_axis_screen = (sx / length, sy / length)
            except Exception:
                center_screen = None
                start_angle = None
                drag_axis_screen = None
        try:
            start_field_value = float(ctx.inspector.value(field_id, 0.0))
        except Exception:
            start_field_value = 0.0
        self._split_rotation_drag = {
            "handle_id": str(handle_id),
            "field_id": field_id,
            "start_screen_pos": screen_pos,
            "start_center_screen": center_screen,
            "start_screen_angle": start_angle,
            "start_normal": normal,
            "start_tilt_axis": _normalize3_local(tilt_axis),
            "start_field_value": start_field_value,
            "field_id": field_id,
            "drag_axis_screen": drag_axis_screen,
            "snap_enabled": _split_rotation_snap_enabled(ctx),
        }
        return True

    def _resolve_plane_rotation_drag(self, event: Any, ctx: Any, handle_id: str) -> dict[str, Any] | None:
        actor = ctx.selection.actor(handle_id)
        if actor is None or not getattr(actor, "points", ()):  # pragma: no cover - defensive
            return None
        state = getattr(self, "_split_rotation_drag", None)
        if not isinstance(state, dict) or state.get("handle_id") != str(handle_id):
            if not self._start_split_rotation_drag(ctx, handle_id, event):
                return None
            state = getattr(self, "_split_rotation_drag", None)
        if not isinstance(state, dict):
            return None
        screen_pos = self._event_screen_pos(event, ctx)
        if screen_pos is None:
            return {handle_id: actor}
        raw_delta = 0.0
        center_screen = state.get("start_center_screen")
        start_angle = state.get("start_screen_angle")
        if center_screen is not None and start_angle is not None:
            try:
                if math.hypot(float(screen_pos[0]) - float(center_screen[0]), float(screen_pos[1]) - float(center_screen[1])) > 3.0:
                    current_angle = _screen_angle_degrees(screen_pos, center_screen)
                    raw_delta = _normalize_delta_degrees(float(current_angle) - float(start_angle))
            except Exception:
                raw_delta = 0.0
        if abs(float(raw_delta)) <= 1.0e-9:
            start_pos = state.get("start_screen_pos")
            axis_screen = state.get("drag_axis_screen")
            if start_pos is not None and axis_screen is not None:
                try:
                    dx = float(screen_pos[0]) - float(start_pos[0])
                    dy = float(screen_pos[1]) - float(start_pos[1])
                    raw_delta = (dx * float(axis_screen[0]) + dy * float(axis_screen[1])) * 0.35
                except Exception:
                    raw_delta = 0.0
        if str(state.get("field_id", "")) == "rx_deg":
            raw_delta = -float(raw_delta)
        snap_enabled = bool(state.get("snap_enabled", _split_rotation_snap_enabled(ctx)))
        delta_degrees = _snap_angle_degrees(raw_delta, _SPLIT_ROTATION_SNAP_DEGREES) if snap_enabled else _bounded_angle_degrees(raw_delta)
        if abs(float(delta_degrees)) <= 1.0e-9:
            return {handle_id: actor}
        try:
            normal = tuple(float(v) for v in state.get("start_normal", (0.0, 0.0, 1.0)))
            tilt_axis = tuple(float(v) for v in state.get("start_tilt_axis", (1.0, 0.0, 0.0)))
            next_normal = _rotate_vector_about_axis(_normalize3_local(normal), _normalize3_local(tilt_axis), float(delta_degrees))
            rx, ry = _normal_to_two_tilt_degrees(next_normal)
            cancel_tool_preview_if_active(ctx, self.id, status="Split preview discarded because the plane tilt changed.")
            ctx.inspector.update_value("rx_deg", rx, notify=False)
            ctx.inspector.update_value("ry_deg", ry, notify=False)
            try:
                ctx.inspector.update_value("rz_deg", 0.0, notify=False)
            except Exception:
                pass
            ctx.inspector.update_value("split_preset", CUSTOM_PRESET_ID, notify=False)
            ctx.inspector.set_display_value("preset_note", split_preset_note(CUSTOM_PRESET_ID))
            self._normalize_plane_values(ctx, update_size=True)
            self._refresh_host_inspector(ctx)
        except Exception:
            return {handle_id: actor}
        self._sync_selection_report(ctx, update_report=False)
        self._sync_plane_projection(ctx, render=False)
        updated = ctx.selection.actor(handle_id)
        if updated is not None:
            return {handle_id: updated}
        return {handle_id: actor}

    def on_native_interaction_result(self, event: Any, ctx: Any, result: Any) -> None:  # noqa: ARG002
        action = str(getattr(result, "action", "") or "")
        grabbed = tuple(str(value) for value in getattr(result, "grabbed_ids", ()) or ())
        is_offset_drag = _SPLIT_PLANE_HANDLE_ID in grabbed
        is_rotation_drag = any(handle_id in grabbed for handle_id in _SPLIT_ROTATE_HANDLE_IDS)
        if not is_offset_drag and not is_rotation_drag:
            return
        if action in {"grab", "select"}:
            if is_rotation_drag:
                rotate_id = next((handle_id for handle_id in _SPLIT_ROTATE_HANDLE_IDS if handle_id in grabbed), None)
                if rotate_id is not None:
                    self._start_split_rotation_drag(ctx, rotate_id, event)
            cancel_tool_preview_if_active(
                ctx,
                self.id,
                status="Split preview discarded because the plane tilt changed." if is_rotation_drag else "Split preview discarded because the plane was moved.",
            )
        if action in {"grab", "drag", "release"}:
            self._sync_plane_projection(ctx, render=action == "release")
            if action == "release":
                if is_rotation_drag:
                    try:
                        setattr(self, "_split_rotation_drag", None)
                    except Exception:
                        pass
                message = "Plane tilt adjusted. Preview to stage the new split result." if is_rotation_drag else "Plane moved. Preview to stage the new split result."
                self._sync_selection_report(ctx, default=message)
                self._sync_feedback(ctx, status="Tilt adjusted." if is_rotation_drag else "Plane moved.")
                self._refresh_host_inspector(ctx)

    def _sync_selection_report(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        indices = tuple(ctx.scene_selection.selected_indices())
        summary = selected_indices_text(indices) if indices else "No mesh selected."
        ctx.inspector.set_display_value("selection_summary", summary)
        settings = split_settings_from_values(ctx.inspector.values())
        check = validate_split_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if default is not None and update_report:
            ctx.inspector.set_display_value("split_report", default)
        elif update_report:
            ctx.inspector.set_display_value(
                "split_report",
                _format_split_report(selected_count=len(check.target_indices), before=check.before_triangles),
            )
        self._sync_feedback(ctx, status=check.message)

    def _sync_preflight(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("preflight_check", text)
        if ok:
            ctx.inspector.clear_error("preflight_check")
        else:
            ctx.inspector.set_error("preflight_check", text)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("split_report", text)
        if ok:
            ctx.inspector.clear_error("split_report")
        else:
            ctx.inspector.set_error("split_report", text)

    def _sync_feedback(self, ctx: Any, *, status: str) -> None:
        try:
            settings = split_settings_from_values(ctx.inspector.values())
            selected = tuple(ctx.scene_selection.selected_indices())
            check = validate_split_targets(ctx, settings)
            ctx.overlay.show_window(
                build_split_feedback_window(
                    owner_tool=self.id,
                    settings=settings,
                    selected_indices=selected,
                    status=status,
                    total_triangles=int(check.before_triangles),
                )
            )
        except Exception:
            pass


class SplitPlaneTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Split CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=SplitPlaneCreatorTool())

    def preview_split(self, context: Any) -> OperationResult:
        ctx = self.tool_context(context)
        return ctx.operations.split(inputs=(), params=ctx.inspector.values(), preview=False, owner_tool=TOOL_MOD_SPLIT)


__all__ = ["SplitPlaneCreatorTool", "SplitPlaneTool"]
