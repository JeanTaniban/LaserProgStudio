# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
from dataclasses import replace
from typing import Any

from laserprog_studio.geometry_ops.extrude_down import extrude_selected_meshes_down
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.inspector import (
    AutoPreview,
    ButtonRow,
    ChoiceField,
    FloatField,
    HelpText,
    InspectorActionEvent,
    Panel,
    ReadonlyField,
    Section,
    SliderField,
)

from .base import ToolSpec
from .ids import TOOL_MOD_EXTRUDE_DOWN
from .preview_staleness import cancel_tool_preview_if_active
from .mesh_extrude_down import (
    CUSTOM_PRESET_ID,
    EXTRUDE_DOWN_FEEDBACK_WINDOW_ID,
    SUPPORT_SHELF_PRESET_ID,
    build_extrude_down_feedback_window,
    extrude_down_preset_choices,
    extrude_down_preset_note,
    extrude_down_preset_values,
    extrude_down_settings_from_values,
    plane_z_from_ratio,
    selected_indices_text,
    triangle_count,
    validate_extrude_down_targets,
    z_limits,
)


_EXTRUDE_PLANE_FACE_ID = "modifier_extrude_down:plane_face"
_EXTRUDE_PLANE_OUTLINE_ID = "modifier_extrude_down:plane_outline"
_EXTRUDE_PLANE_HANDLE_ID = "modifier_extrude_down:plane_handle"
_EXTRUDE_PLANE_CENTER_ID = "modifier_extrude_down:plane_center"
_EXTRUDE_CUT_LINE_ID = "modifier_extrude_down:cut_line"
_EXTRUDE_PLANE_LABEL_ID = "modifier_extrude_down:plane_label"

_EXTRUDE_Z_NUDGE_MM = 1.0


def _extrude_selected_xy_bounds(ctx: Any, indices: tuple[int, ...]) -> tuple[float, float, float, float]:
    try:
        meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        meshes = []
    xs: list[float] = []
    ys: list[float] = []
    for index in indices:
        if not (0 <= int(index) < len(meshes)):
            continue
        for vertex in getattr(meshes[int(index)], "vertices", ()) or ():
            try:
                xs.append(float(vertex[0]))
                ys.append(float(vertex[1]))
            except Exception:
                continue
    if not xs or not ys:
        return (-60.0, -60.0, 60.0, 60.0)
    return (min(xs), min(ys), max(xs), max(ys))


def _extrude_plane_points(ctx: Any, indices: tuple[int, ...], z: float) -> tuple[tuple[float, float, float], ...]:
    x0, y0, x1, y1 = _extrude_selected_xy_bounds(ctx, indices)
    cx = (float(x0) + float(x1)) * 0.5
    cy = (float(y0) + float(y1)) * 0.5
    size = max(float(x1) - float(x0), float(y1) - float(y0), 20.0) * 1.25
    half = size * 0.5
    return (
        (cx - half, cy - half, float(z)),
        (cx + half, cy - half, float(z)),
        (cx + half, cy + half, float(z)),
        (cx - half, cy + half, float(z)),
    )


def _extrude_handle_pos(ctx: Any, indices: tuple[int, ...], z: float) -> tuple[float, float, float]:
    """Return the visible handle position.

    v65: the handle is attached to the support plane centre.  The previous
    offset-above-plane handle made the tool feel like it moved a different
    object than the actual cut/support plane.
    """

    x0, y0, x1, y1 = _extrude_selected_xy_bounds(ctx, indices)
    cx = (float(x0) + float(x1)) * 0.5
    cy = (float(y0) + float(y1)) * 0.5
    return (cx, cy, float(z))


def _extrude_plane_size_text(ctx: Any, indices: tuple[int, ...]) -> str:
    x0, y0, x1, y1 = _extrude_selected_xy_bounds(ctx, indices)
    width = max(float(x1) - float(x0), 0.0)
    height = max(float(y1) - float(y0), 0.0)
    return f"{width:g} × {height:g} mm"


def _triangle_z_segment(
    vertices: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    z: float,
    *,
    eps: float = 1.0e-7,
) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    distances = [float(p[2]) - float(z) for p in vertices]
    points: list[tuple[float, float, float]] = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a = vertices[i]
        b = vertices[j]
        da = float(distances[i])
        db = float(distances[j])
        if abs(da) <= eps and abs(db) <= eps:
            points.extend(((float(a[0]), float(a[1]), float(z)), (float(b[0]), float(b[1]), float(z))))
            continue
        if abs(da) <= eps:
            points.append((float(a[0]), float(a[1]), float(z)))
            continue
        if abs(db) <= eps:
            points.append((float(b[0]), float(b[1]), float(z)))
            continue
        if (da < 0.0 < db) or (db < 0.0 < da):
            t = da / (da - db)
            points.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, float(z)))
    unique: list[tuple[float, float, float]] = []
    for pnt in points:
        q = (float(pnt[0]), float(pnt[1]), float(pnt[2]))
        if not any(math.dist(q, existing) <= eps * 10.0 for existing in unique):
            unique.append(q)
    if len(unique) < 2:
        return None
    if len(unique) > 2:
        best = (unique[0], unique[1])
        best_len = -1.0
        for a_i in range(len(unique)):
            for b_i in range(a_i + 1, len(unique)):
                length = math.dist(unique[a_i], unique[b_i])
                if length > best_len:
                    best_len = length
                    best = (unique[a_i], unique[b_i])
        return best
    if math.dist(unique[0], unique[1]) <= eps * 10.0:
        return None
    return (unique[0], unique[1])


def _extrude_cut_line_segments(ctx: Any, indices: tuple[int, ...], z: float) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...]:
    try:
        meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        return ()
    out: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for index in indices:
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
            segment = _triangle_z_segment(pts, float(z))
            if segment is not None:
                out.append(segment)
    return tuple(out)


def _axis_z_screen_delta_world(ctx: Any, actor_point: tuple[float, float, float]) -> float | None:
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
    try:
        start = projector(actor_point)
        end = projector((actor_point[0], actor_point[1], actor_point[2] + 1.0))
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


def _format_extrude_down_report(*, selected_count: int, before: int, after: int | None = None, plane_z: float | None = None, message: str = "") -> str:
    if message:
        return str(message)
    if after is None:
        return f"Selected: {int(selected_count)}\nTriangles before: {int(before)}"
    plane = f"\nPlane Z: {plane_z:g} mm" if plane_z is not None else ""
    return f"Extrude-down preview ready.\nSelected: {int(selected_count)}\nTriangles: {int(before)} → {int(after)}{plane}"


class ExtrudeDownCreatorTool(CreatorTool):
    """Product-ready downward extrusion modifier built on the Creator API."""

    id = TOOL_MOD_EXTRUDE_DOWN
    label = "Extrude down"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select meshes", help="Select one or more parts to extrude down."),
                ctx.workflow.step("tune", "Tune support plane", help="Choose a cut plane preset or adjust the exact Z values."),
                ctx.workflow.step("preview", "Preview extrusion", help="Stage the downward extrusion before applying it.", optional=True),
            ),
        )
        ctx.operations.register("extrude_down", self._operation_extrude_down, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._initialize_defaults(ctx)
        self._sync_selection_report(ctx, default="Choose a support preset, then Preview.")
        ctx.status.info("Extrude down ready. Select parts, preview, then Apply.")
        self._sync_plane_projection(ctx, render=True)

    def on_close(self, ctx: Any) -> None:
        try:
            ctx.projected_drawing.clear_tool(self.id, render=False)
        except Exception:
            pass
        ctx.overlay.hide_window(EXTRUDE_DOWN_FEEDBACK_WINDOW_ID)
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        message = "Extrude-down preview cancelled." if changed else "No active extrude-down preview."
        self._set_report(ctx, message, ok=True)
        self._sync_feedback(ctx, status=message)
        self._sync_plane_projection(ctx, render=True)
        return changed

    def on_apply(self, ctx: Any) -> bool:
        if not bool(getattr(ctx.document, "has_preview", False)):
            if not self._preview_action(ctx, None):
                message = "Extrude down failed: preview could not be generated."
                self._set_report(ctx, message, ok=False)
                self._sync_feedback(ctx, status=message)
                return False
        changed = bool(ctx.preview_session.apply(label="Extrude down applied", operation_type="modifier_extrude_down"))
        message = "Extrude down applied." if changed else "Preview first, then apply."
        self._set_report(ctx, message, ok=changed)
        self._sync_feedback(ctx, status=message)
        if changed:
            ctx.status.info("Extrude down applied.")
        return changed

    def on_event(self, event: Any, ctx: Any) -> bool:
        action_id = str(getattr(event, "action_id", "") or getattr(event, "id", ""))
        return self._handle_action_id(action_id, ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        self._handle_action_id(str(button_id), ctx)

    def _handle_action_id(self, action_id: str, ctx: Any) -> bool:
        if action_id in {"extrude_down_overlay_preview", "preview"}:
            return self._preview_action(ctx, None)
        if action_id in {"extrude_down_overlay_apply", "apply_extrude_down"}:
            return self._apply_action(ctx, None)
        if action_id in {"extrude_down_overlay_cancel", "cancel_preview"}:
            return self.on_cancel(ctx)
        if action_id in {"plane_z_minus", "extrude_down_z_minus"}:
            return self._z_nudge_action(ctx, -_EXTRUDE_Z_NUDGE_MM)
        if action_id in {"plane_z_plus", "extrude_down_z_plus"}:
            return self._z_nudge_action(ctx, _EXTRUDE_Z_NUDGE_MM)
        if action_id in {"plane_z_mid", "extrude_down_z_mid"}:
            return self._z_mid_action(ctx)
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        self._initialize_defaults(ctx, preserve_existing=True)
        self._sync_selection_report(ctx)
        if ctx.scene_selection.selected_indices():
            ctx.status.info("Extrude-down selection updated. Preview to stage the selected parts.")
        self._sync_plane_projection(ctx, render=True)
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        setting_change = lambda _field, _value: self._on_setting_changed(ctx)
        return Panel(
            "Extrude down",
            id="modifier.extrude_down",
            owner_tool=self.id,
            description="Create vertical support geometry down to a ground plane with presets, preflight checks and a non-destructive preview.",
            auto_preview=AutoPreview(
                action_id="preview",
                debounce_ms=350,
                include_fields=("extrude_down_preset", "plane_z", "ground_z", "tolerance"),
            ),
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("extrude_down_help", "Select one or more real parts. Preview stages the extrusion; Apply commits it."),
                        ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                        ReadonlyField("preflight_check", "Check", default="No extrude-down target checked yet."),
                        ReadonlyField("bounds_summary", "Usable Z", default="No bounds yet."),
                    ),
                ),
                Section(
                    "Quick support",
                    fields=(
                        ChoiceField("extrude_down_preset", "Preset", default=SUPPORT_SHELF_PRESET_ID, choices=extrude_down_preset_choices(), on_change=lambda _field, value: self._on_preset_change(ctx, value)),
                        ReadonlyField("preset_note", "Preset note", default=extrude_down_preset_note(SUPPORT_SHELF_PRESET_ID)),
                    ),
                ),
                Section(
                    "Support plane",
                    fields=(
                        HelpText("extrude_down_plane_help", "Extrude Down is a vertical operation: the support plane stays horizontal. Drag the center handle or edit Plane Z to move it up/down."),
                        SliderField(
                            "plane_ratio",
                            "Plane height",
                            default=33.0,
                            min_value=1.0,
                            max_value=99.0,
                            step=1.0,
                            unit="%",
                            tooltip="Relative height inside the selected part. Updating this also updates Plane Z.",
                            on_change=lambda _field, value: self._on_ratio_changed(ctx, value),
                        ),
                        ButtonRow(
                            "extrude_down_z_nudges",
                            "Z nudges",
                            buttons=(("plane_z_minus", "Z -1 mm"), ("plane_z_plus", "Z +1 mm"), ("plane_z_mid", "Mid")),
                            callbacks={
                                "plane_z_minus": lambda _event: self._z_nudge_action(ctx, -_EXTRUDE_Z_NUDGE_MM),
                                "plane_z_plus": lambda _event: self._z_nudge_action(ctx, _EXTRUDE_Z_NUDGE_MM),
                                "plane_z_mid": lambda _event: self._z_mid_action(ctx),
                            },
                        ),
                        FloatField("plane_z", "Plane Z", default=0.0, min_value=-1000000.0, max_value=1000000.0, step=1.0, unit="mm", tooltip="Horizontal support-plane height inside the selected part.", on_change=setting_change),
                        FloatField("ground_z", "Ground Z", default=0.0, min_value=-1000000.0, max_value=1000000.0, step=1.0, unit="mm", tooltip="Bottom target for the generated vertical support.", on_change=setting_change),
                        ReadonlyField("support_plane_size", "Plane size", default="No bounds yet."),
                        FloatField("tolerance", "Tolerance", default=0.001, min_value=0.00000001, max_value=10.0, step=0.001, unit="mm", tooltip="Geometric tolerance used to rebuild the cut contour.", on_change=setting_change),
                    ),
                ),
                Section(
                    "Preview and apply",
                    fields=(
                        ButtonRow(
                            "extrude_down_actions",
                            "Actions",
                            buttons=(("preview", "Preview"), ("apply_extrude_down", "Apply"), ("cancel_preview", "Cancel")),
                            callbacks={
                                "preview": lambda event: self._preview_action(ctx, event),
                                "apply_extrude_down": lambda event: self._apply_action(ctx, event),
                                "cancel_preview": lambda _event: self.on_cancel(ctx),
                            },
                        ),
                        ReadonlyField("extrude_down_report", "Report", default="Ready. Preview extrusion to stage selected parts."),
                    ),
                ),
            ),
        )

    def _operation_extrude_down(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        settings = extrude_down_settings_from_values(params)
        check = validate_extrude_down_targets(ctx, settings)
        if not check.ok:
            return OperationResult.failure(check.message, report=check.message)

        base = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        chosen = tuple(int(i) for i in check.target_indices)
        before = sum(triangle_count(base[i]) for i in chosen)
        backend_result = extrude_selected_meshes_down(
            [copy.deepcopy(mesh) for mesh in base],
            list(chosen),
            plane_z=settings.plane_z,
            ground_z=settings.ground_z,
            tolerance=settings.tolerance,
        )
        if not backend_result.ok:
            message = "\n".join(getattr(backend_result, "errors", ()) or ()) or "Extrude down failed."
            return OperationResult.failure(message, report=message, warnings=getattr(backend_result, "warnings", ()))
        meshes = tuple(backend_result.meshes)
        after = sum(triangle_count(meshes[i]) for i in chosen if 0 <= i < len(meshes))
        report = _format_extrude_down_report(selected_count=len(chosen), before=before, after=after, plane_z=settings.plane_z)
        warnings = tuple(getattr(backend_result, "warnings", ()) or ())
        if warnings:
            report += "\n" + "\n".join(str(w) for w in warnings[:4])
        return OperationResult.success(
            meshes,
            report=report,
            warnings=warnings,
            metadata={
                "changed_indices": tuple(chosen),
                "selected_indices": tuple(chosen),
                "before_triangles": before,
                "after_triangles": after,
                "plane_z": settings.plane_z,
                "ground_z": settings.ground_z,
                "settings_summary": settings.summary,
                "preset_id": settings.preset_id,
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        settings = extrude_down_settings_from_values(values)
        check = validate_extrude_down_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if not check.ok:
            ctx.status.error(check.message)
            self._set_report(ctx, check.message, ok=False)
            self._sync_feedback(ctx, status=check.message)
            return False

        result = ctx.operations.extrude_down(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Extrude down operation finished."), ok=result.ok)
        self._sync_selection_report(ctx, update_report=False)
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Extrude down failed."
            ctx.status.error(message)
            self._sync_feedback(ctx, status=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Extrude down preview")
        session.show_meshes(result.meshes)
        selected = tuple(int(i) for i in result.metadata.get("changed_indices", ()) if isinstance(i, int) or str(i).isdigit())
        if selected:
            ctx.scene_selection.select_indices(selected, active_index=selected[-1])
        ctx.workflow.goto("preview")
        ctx.status.info("Extrude-down preview ready. Use Apply to keep it or Cancel to discard it.")
        self._sync_feedback(ctx, status="Preview ready. Apply to keep it.")
        self._sync_plane_projection(ctx, render=True)
        return True

    def _apply_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if event is not None:
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

    def _on_preset_change(self, ctx: Any, value: Any) -> None:
        preset_id = str(value or CUSTOM_PRESET_ID)
        for field_id, field_value in extrude_down_preset_values(preset_id).items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        self._update_plane_from_ratio(ctx, notify=False)
        try:
            ctx.inspector.set_display_value("preset_note", extrude_down_preset_note(preset_id))
        except Exception:
            pass
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preset loaded." if preset_id != CUSTOM_PRESET_ID else "Custom extrusion settings.")
        self._sync_plane_projection(ctx, render=True)

    def _on_ratio_changed(self, ctx: Any, value: Any) -> None:
        self._mark_custom(ctx)
        try:
            ctx.inspector.update_value("plane_ratio", float(value), notify=False)
        except Exception:
            pass
        self._update_plane_from_ratio(ctx, notify=False)
        self._normalize_plane_values(ctx, update_ratio=False, update_size=True)
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Plane height adjusted.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)

    def _on_setting_changed(self, ctx: Any) -> None:
        self._mark_custom(ctx)
        self._normalize_plane_values(ctx, update_ratio=True, update_size=True)
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Extrude-down settings edited.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)

    def _mark_custom(self, ctx: Any) -> None:
        try:
            if ctx.inspector.value("extrude_down_preset", CUSTOM_PRESET_ID) != CUSTOM_PRESET_ID:
                ctx.inspector.update_value("extrude_down_preset", CUSTOM_PRESET_ID, notify=False)
                ctx.inspector.set_display_value("preset_note", extrude_down_preset_note(CUSTOM_PRESET_ID))
        except Exception:
            pass

    def _initialize_defaults(self, ctx: Any, *, preserve_existing: bool = False) -> None:
        try:
            if preserve_existing and ctx.inspector.value("plane_z", None) not in (None, ""):
                self._normalize_plane_values(ctx, update_ratio=True, update_size=True)
                return
        except Exception:
            pass
        self._update_plane_from_ratio(ctx, notify=False)
        self._normalize_plane_values(ctx, update_ratio=True, update_size=True)

    def _update_plane_from_ratio(self, ctx: Any, *, notify: bool = False) -> None:
        try:
            meshes = list(ctx.document.meshes(include_preview=False))
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            if not selected:
                return
            ratio = float(ctx.inspector.value("plane_ratio", 33.0))
            plane_z = plane_z_from_ratio(meshes, selected, ratio)
            ctx.inspector.update_value("plane_z", plane_z, notify=notify)
            ctx.inspector.set_display_value("support_plane_size", _extrude_plane_size_text(ctx, selected))
        except Exception:
            pass

    def _refresh_host_inspector(self, ctx: Any) -> None:
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

    def _clamp_plane_z(self, ctx: Any, value: float) -> float:
        try:
            meshes = list(ctx.document.meshes(include_preview=False))
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            if not selected:
                return float(value)
            settings = extrude_down_settings_from_values(ctx.inspector.values())
            lo, hi = z_limits(meshes, selected)
            eps = max(float(settings.tolerance), 1.0e-7)
            # The preflight intentionally rejects values exactly on the usable
            # bounds.  Clamp slightly inside the model so drag/edit never lands
            # on an invalid equality edge.
            low = max(float(lo) + eps * 2.0, float(settings.ground_z) + eps * 2.0)
            high = float(hi) - eps * 2.0
            if high < low:
                return float(value)
            return float(min(max(float(value), low), high))
        except Exception:
            return float(value)

    def _normalize_plane_values(self, ctx: Any, *, update_ratio: bool = False, update_size: bool = False) -> None:
        try:
            meshes = list(ctx.document.meshes(include_preview=False))
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            updates: dict[str, Any] = {}
            if selected:
                current = float(ctx.inspector.value("plane_z", 0.0))
                clamped = self._clamp_plane_z(ctx, current)
                if abs(float(clamped) - float(current)) > 1.0e-6:
                    updates["plane_z"] = clamped
                if update_ratio:
                    lo, hi = z_limits(meshes, selected)
                    span = float(hi) - float(lo)
                    if span > 1.0e-9:
                        ratio = max(1.0, min(99.0, (float(clamped) - float(lo)) / span * 100.0))
                        if abs(float(ctx.inspector.value("plane_ratio", ratio)) - ratio) > 1.0e-6:
                            updates["plane_ratio"] = ratio
                if update_size:
                    ctx.inspector.set_display_value("support_plane_size", _extrude_plane_size_text(ctx, selected))
            if updates:
                ctx.inspector.update_values(updates, notify=False)
                self._refresh_host_inspector(ctx)
        except Exception:
            pass

    def _z_nudge_action(self, ctx: Any, delta_mm: float) -> bool:
        cancel_tool_preview_if_active(ctx, self.id, status="Extrude-down preview discarded because the support plane moved.")
        try:
            current = float(ctx.inspector.value("plane_z", 0.0))
        except Exception:
            current = 0.0
        new_z = self._clamp_plane_z(ctx, current + float(delta_mm))
        try:
            ctx.inspector.update_value("plane_z", new_z, notify=False)
            self._mark_custom(ctx)
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_ratio=True, update_size=True)
        self._sync_selection_report(ctx, default="Support plane moved. Preview to stage the new extrusion.")
        self._sync_feedback(ctx, status="Plane moved.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)
        return True

    def _z_mid_action(self, ctx: Any) -> bool:
        try:
            meshes = list(ctx.document.meshes(include_preview=False))
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            lo, hi = z_limits(meshes, selected)
            target = (float(lo) + float(hi)) * 0.5
        except Exception:
            target = 0.0
        cancel_tool_preview_if_active(ctx, self.id, status="Extrude-down preview discarded because the support plane was centered.")
        try:
            ctx.inspector.update_value("plane_z", self._clamp_plane_z(ctx, target), notify=False)
            self._mark_custom(ctx)
        except Exception:
            pass
        self._normalize_plane_values(ctx, update_ratio=True, update_size=True)
        self._sync_selection_report(ctx, default="Support plane centered. Preview to stage the new extrusion.")
        self._sync_feedback(ctx, status="Plane centered.")
        self._sync_plane_projection(ctx, render=True)
        self._refresh_host_inspector(ctx)
        return True

    def _sync_plane_projection(self, ctx: Any, *, render: bool = True) -> bool:
        """Draw the support plane and Z handle through Projected Drawing 2D."""

        try:
            from laserprog_studio.tool_api import projected_drawing as pd

            self._normalize_plane_values(ctx, update_ratio=True, update_size=True)
            settings = extrude_down_settings_from_values(ctx.inspector.values())
            check = validate_extrude_down_targets(ctx, settings)
            registry = ctx.projected_drawing.for_tool(self.id)
            if not check.ok:
                registry.clear(render=render)
                return False
            indices = tuple(int(i) for i in check.target_indices)
            corners = _extrude_plane_points(ctx, indices, float(check.plane_z))
            handle_pos = _extrude_handle_pos(ctx, indices, float(check.plane_z))
            cut_segments = _extrude_cut_line_segments(ctx, indices, float(check.plane_z))
            primitives: list[Any] = [
                pd.face(
                    _EXTRUDE_PLANE_FACE_ID,
                    corners,
                    fill_color="#69F0AE",
                    fill_opacity=0.18,
                    outline_color="#FFFFFF",
                    outline_width_px=2.0,
                    outline_opacity=0.95,
                    layer=18,
                    interaction=pd.ProjectedInteraction.FIXED,
                    metadata={"modifier_role": "extrude_down_plane_face", "projected_no_selection_actor": True, "horizontal_only": True},
                ),
                pd.polyline(
                    _EXTRUDE_PLANE_OUTLINE_ID,
                    corners,
                    closed=True,
                    color="#FFFFFF",
                    width_px=2.0,
                    opacity=0.95,
                    layer=20,
                    interaction=pd.ProjectedInteraction.FIXED,
                    metadata={"modifier_role": "extrude_down_plane_outline", "projected_no_selection_actor": True},
                ),
                pd.point(
                    _EXTRUDE_PLANE_CENTER_ID,
                    handle_pos,
                    color="#FF6E32",
                    size_px=9.0,
                    opacity=1.0,
                    layer=32,
                    interaction=pd.ProjectedInteraction.FIXED,
                    metadata={"modifier_role": "extrude_down_plane_center", "projected_no_selection_actor": True},
                ),
                pd.drag_arrow(
                    _EXTRUDE_PLANE_HANDLE_ID,
                    handle_pos,
                    (0.0, 0.0, 1.0),
                    constraint=pd.ProjectedDragConstraint.AXIS_Z,
                    color="#FFD54F",
                    size_px=38.0,
                    layer=35,
                    metadata={
                        "modifier_role": "extrude_down_plane_handle",
                        "attached_to_plane_center": True,
                        "vertical_only": True,
                        "plane_z": float(check.plane_z),
                    },
                ),
                pd.text(
                    _EXTRUDE_PLANE_LABEL_ID,
                    f"Horizontal Z {float(check.plane_z):g} mm",
                    handle_pos,
                    color="#FFD54F",
                    size_px=12,
                    opacity=0.96,
                    anchor="center",
                    layer=39,
                    metadata={"modifier_role": "extrude_down_plane_label", "projected_no_selection_actor": True},
                ),
            ]
            if cut_segments:
                primitives.append(
                    pd.segment_batch(
                        _EXTRUDE_CUT_LINE_ID,
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
        if _EXTRUDE_PLANE_HANDLE_ID not in grabbed:
            return None
        actor = ctx.selection.actor(_EXTRUDE_PLANE_HANDLE_ID)
        if actor is None or not getattr(actor, "points", ()):
            return None
        settings = extrude_down_settings_from_values(ctx.inspector.values())
        check = validate_extrude_down_targets(ctx, settings)
        if not check.ok:
            return None
        actor_point = tuple(float(v) for v in actor.points[0])
        dz = _axis_z_screen_delta_world(ctx, actor_point)
        if dz is None:
            raw_delta = getattr(getattr(ctx.selection, "state", None), "last_move_delta", None)
            if raw_delta is None:
                return None
            try:
                dz = float(raw_delta[2])
            except Exception:
                return None
        new_z = self._clamp_plane_z(ctx, float(settings.plane_z) + float(dz))
        try:
            ctx.inspector.update_value("plane_z", new_z, notify=False)
            ctx.inspector.update_value("extrude_down_preset", CUSTOM_PRESET_ID, notify=False)
            ctx.inspector.set_display_value("preset_note", extrude_down_preset_note(CUSTOM_PRESET_ID))
            self._normalize_plane_values(ctx, update_ratio=True, update_size=True)
            self._refresh_host_inspector(ctx)
        except Exception:
            pass
        self._sync_selection_report(ctx, update_report=False)
        self._sync_plane_projection(ctx, render=False)
        updated_settings = extrude_down_settings_from_values(ctx.inspector.values())
        updated_check = validate_extrude_down_targets(ctx, updated_settings)
        if not updated_check.ok:
            return None
        handle_pos = _extrude_handle_pos(ctx, tuple(int(i) for i in updated_check.target_indices), float(updated_check.plane_z))
        return {_EXTRUDE_PLANE_HANDLE_ID: replace(actor, points=(handle_pos,), metadata={**(getattr(actor, "metadata", {}) or {}), "plane_z": float(updated_check.plane_z)})}

    def on_native_interaction_result(self, event: Any, ctx: Any, result: Any) -> None:  # noqa: ARG002
        action = str(getattr(result, "action", "") or "")
        grabbed = tuple(str(value) for value in getattr(result, "grabbed_ids", ()) or ())
        if _EXTRUDE_PLANE_HANDLE_ID not in grabbed:
            return
        if action == "grab":
            cancel_tool_preview_if_active(ctx, self.id, status="Extrude-down preview discarded because the plane was moved.")
        if action in {"grab", "drag", "release"}:
            self._sync_plane_projection(ctx, render=action == "release")
            if action == "release":
                self._sync_selection_report(ctx, default="Support plane moved. Preview to stage the new extrusion.")
                self._sync_feedback(ctx, status="Plane moved.")
                self._refresh_host_inspector(ctx)

    def _sync_selection_report(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
        ctx.inspector.set_display_value("selection_summary", selected_indices_text(indices) if indices else "No mesh selected.")
        settings = extrude_down_settings_from_values(ctx.inspector.values())
        check = validate_extrude_down_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if default is not None and update_report:
            ctx.inspector.set_display_value("extrude_down_report", default)
        elif update_report:
            ctx.inspector.set_display_value(
                "extrude_down_report",
                _format_extrude_down_report(selected_count=len(check.target_indices), before=check.before_triangles, plane_z=check.plane_z),
            )
        self._sync_bounds_display(ctx)
        self._sync_feedback(ctx, status=check.message)

    def _sync_bounds_display(self, ctx: Any) -> None:
        # Keep this tiny and failure-safe: it is useful for future hosts but not a user-facing field yet.
        try:
            meshes = list(ctx.document.meshes(include_preview=False))
            indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            lo, hi = z_limits(meshes, indices)
            ctx.inspector.set_display_value("bounds_summary", f"{lo:g} → {hi:g} mm" if indices else "No bounds yet.")
            if indices:
                ctx.inspector.set_display_value("support_plane_size", _extrude_plane_size_text(ctx, indices))
        except Exception:
            pass

    def _sync_preflight(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("preflight_check", text)
        if ok:
            ctx.inspector.clear_error("preflight_check")
        else:
            ctx.inspector.set_error("preflight_check", text)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("extrude_down_report", text)
        if ok:
            ctx.inspector.clear_error("extrude_down_report")
        else:
            ctx.inspector.set_error("extrude_down_report", text)

    def _sync_feedback(self, ctx: Any, *, status: str) -> None:
        try:
            settings = extrude_down_settings_from_values(ctx.inspector.values())
            selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
            ctx.overlay.show_window(
                build_extrude_down_feedback_window(
                    owner_tool=self.id,
                    settings=settings,
                    selected_indices=selected,
                    status=status,
                    total_triangles=int(validate_extrude_down_targets(ctx, settings).before_triangles),
                )
            )
        except Exception:
            pass


class ExtrudeDownTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Extrude Down CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=ExtrudeDownCreatorTool())

    def preview_extrude_down(self, context: Any) -> OperationResult:
        ctx = self.tool_context(context)
        return ctx.operations.extrude_down(inputs=(), params=ctx.inspector.values(), preview=False, owner_tool=TOOL_MOD_EXTRUDE_DOWN)


__all__ = ["ExtrudeDownCreatorTool", "ExtrudeDownTool"]
