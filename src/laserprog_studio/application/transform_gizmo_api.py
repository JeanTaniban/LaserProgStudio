# -*- coding: utf-8 -*-
"""API-backed transform gizmo bridge for the main application viewport.

The historical transform gizmo is built from bespoke cone/cylinder/sphere
meshes.  The native path intentionally follows the Creator API model instead:
``ToolContext.gizmos`` + ``ToolContext.preview`` describe only points and lines.
A persistent foreground adapter renders those lightweight PyVista primitives,
while screen-space picking uses the exact same snapshot.

Translate, rotate and scale share this bridge.  The legacy mesh actors remain
behind the feature flag solely as a compatibility fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any
import math

from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tool_core.gizmos import visual_state_for_flags, get_point_style
from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event

OWNER_TOOL = "app_transform_gizmo"
MANIPULATOR_ID = "app.transform.translate"
ROTATE_MANIPULATOR_ID = "app.transform.rotate"
SCALE_MANIPULATOR_ID = "app.transform.scale"


@dataclass(frozen=True, slots=True)
class NativeTransformGizmoSnapshot:
    mode: str
    center: tuple[float, float, float]
    length: float
    axes: tuple[str, ...]
    positions: dict[str, tuple[float, float, float]]
    lines: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]]
    handle_ids: dict[str, str] = field(default_factory=dict)
    rings: dict[str, tuple[tuple[float, float, float], ...]] = field(default_factory=dict)
    axis_vectors: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    colors: dict[str, str] = field(default_factory=dict)


def native_transform_gizmo_enabled(owner: Any) -> bool:
    """Feature flag for incremental migration of the app transform gizmo."""

    try:
        import os

        value = str(os.environ.get("LPS_NATIVE_TRANSFORM_GIZMO", "1")).strip().lower()
        if value in {"0", "false", "off", "no", "legacy"}:
            return False
    except Exception:
        pass
    return bool(getattr(owner, "_native_transform_gizmo_enabled", True))


def _audit(owner: Any, name: str, value: int | float = 1) -> None:
    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        if isinstance(value, int):
            audit.increment(str(name), int(value))
        else:
            audit.set_value(str(name), float(value))
    except Exception:
        pass


def _ctx(owner: Any) -> ToolContext:
    ctx = getattr(owner, "_native_transform_gizmo_ctx", None)
    if not isinstance(ctx, ToolContext):
        ctx = ToolContext()
        try:
            attach_owner = getattr(ctx, "attach_owner", None)
            if callable(attach_owner):
                attach_owner(owner)
            else:
                ctx.owner = owner
        except Exception:
            pass
        setattr(owner, "_native_transform_gizmo_ctx", ctx)
    return ctx


def _axis_colors(axes: dict[str, tuple[tuple[float, float, float], str]]) -> dict[str, str]:
    return {str(axis).lower(): str(color) for axis, (_vec, color) in axes.items()}


def _rgb_to_rgba(hex_color: str) -> tuple[float, float, float, float]:
    try:
        from laserprog_studio.mesh_ops import parse_hex_color

        r, g, b = parse_hex_color(str(hex_color))
        return (float(r), float(g), float(b), 1.0)
    except Exception:
        return (0.1, 0.55, 0.95, 1.0)


def _normalize_vec(vec: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        x, y, z = (float(vec[0]), float(vec[1]), float(vec[2]))
        n = math.sqrt(x * x + y * y + z * z)
        if n <= 1.0e-12:
            return (0.0, 0.0, 0.0)
        return (x / n, y / n, z / n)
    except Exception:
        return (0.0, 0.0, 0.0)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _basis_for_axis(axis_vector: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    n = _normalize_vec(axis_vector)
    if n == (0.0, 0.0, 0.0):
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    ref = (0.0, 0.0, 1.0)
    if abs(n[2]) > 0.88:
        ref = (0.0, 1.0, 0.0)
    u = _normalize_vec(_cross(n, ref))
    v = _normalize_vec(_cross(n, u))
    return u, v


def _ring_points(center: tuple[float, float, float], normal: tuple[float, float, float], radius: float, *, samples: int = 72) -> tuple[tuple[float, float, float], ...]:
    c = tuple(float(v) for v in center)
    u, v = _basis_for_axis(normal)
    r = max(float(radius), 1.0e-9)
    pts: list[tuple[float, float, float]] = []
    count = max(16, int(samples))
    for i in range(count + 1):
        a = 2.0 * math.pi * float(i) / float(count)
        ca, sa = math.cos(a), math.sin(a)
        pts.append((c[0] + (u[0] * ca + v[0] * sa) * r, c[1] + (u[1] * ca + v[1] * sa) * r, c[2] + (u[2] * ca + v[2] * sa) * r))
    return tuple(pts)


def _apply_axis_handle_visual(ctx: ToolContext, handle_id: str, *, color: str, style_id: str, radius_px: int) -> None:
    handle = ctx.transform_gizmos.handle(handle_id, owner_tool=OWNER_TOOL)
    if handle is None:
        return
    try:
        state = visual_state_for_flags(
            selectable=bool(handle.selectable),
            hover=bool(handle.hover),
            grabbed=bool(handle.grabbed),
            selected=bool(handle.selected),
            visible=bool(handle.visible),
        )
        ctx.transform_gizmos.update_handle(
            handle.id,
            color=_rgb_to_rgba(color),
            radius_px=ctx.transform_gizmos.radius_for_style(style_id, int(radius_px), state),
            base_radius_px=int(radius_px),
        )
    except Exception:
        pass


def _render_snapshot(owner: Any, snapshot: NativeTransformGizmoSnapshot, *, render: bool) -> bool:
    """Render through the dedicated Transform backend, never the generic guide painter.

    The ToolContext remains the public/API state used by tests and future tools,
    while the specialized renderer owns the exact foreground geometry and its
    explicit lifecycle.
    """

    record_transform_gizmo_event(owner, "api.render_snapshot_begin", snapshot=snapshot, extra={"render": bool(render)})
    try:
        from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

        result = bool(get_transform_gizmo_renderer(owner).sync(snapshot, render=bool(render)))
        record_transform_gizmo_event(owner, "api.render_snapshot_end", snapshot=snapshot, extra={"result": result})
        return result
    except Exception as exc:
        record_transform_gizmo_event(owner, "api.render_snapshot_exception", snapshot=snapshot, error=exc, ui_log=True)
        return False


def sync_native_translate_gizmo(
    owner: Any,
    *,
    center: tuple[float, float, float],
    length: float,
    axes: dict[str, tuple[tuple[float, float, float], str]],
    render: bool = True,
) -> bool:
    """Declare and render the main Translate gizmo through the Creator API.

    It creates persistent API handles and line previews only. The viewport
    adapter renders GL/VTK lines and points; no solid arrow or sphere mesh is
    generated on the native path.
    """

    if not native_transform_gizmo_enabled(owner):
        record_transform_gizmo_event(owner, "api.sync_disabled", extra={"mode": "translate"})
        return False
    record_transform_gizmo_event(owner, "api.sync_requested", extra={"mode": "translate", "center": center, "length": length, "axes": tuple(axes)})
    try:
        ctx = _ctx(owner)
        axis_keys = tuple(axis for axis in ("x", "y", "z") if axis in axes)
        if not axis_keys:
            return False
        c = tuple(float(v) for v in center)
        l = max(float(length), 1.0e-9)
        axis_vectors = {axis: tuple(float(v) for v in axes[axis][0]) for axis in axis_keys}
        colors = _axis_colors(axes)
        shaft_end_factor = 0.86
        handle_factor = 1.00
        line_positions: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
        handle_positions: dict[str, tuple[float, float, float]] = {}

        # Keep the API state stable. Clearing only this owner keeps unrelated
        # Creator tools independent and lets the persistent painter hide stale
        # actors instead of forcing global overlay churn.
        ctx.preview.clear_tool(OWNER_TOOL)
        ctx.transform_gizmos.clear_tool(OWNER_TOOL)
        ctx.transform_gizmos.translate(
            id=MANIPULATOR_ID,
            owner_tool=OWNER_TOOL,
            origin=c,
            axes=axis_keys,
            radius_px=16,
            axis_length=l * handle_factor,
            axis_vectors=axis_vectors,
            include_center=True,
            center_selectable=False,
        )

        for axis in axis_keys:
            vx, vy, vz = axis_vectors[axis]
            p0 = c
            p1 = (c[0] + vx * l * shaft_end_factor, c[1] + vy * l * shaft_end_factor, c[2] + vz * l * shaft_end_factor)
            tip = (c[0] + vx * l * handle_factor, c[1] + vy * l * handle_factor, c[2] + vz * l * handle_factor)
            color = colors.get(axis, "#42A5F5")
            line_positions[axis] = (p0, p1)
            handle_positions[axis] = tip
            ctx.preview.show_line(
                f"{MANIPULATOR_ID}:axis:{axis}",
                OWNER_TOOL,
                p0,
                p1,
                payload={"color": color, "line_width": 4.0, "line_style": "axis"},
            )
            handle = ctx.transform_gizmos.handle(f"{MANIPULATOR_ID}:{axis}", owner_tool=OWNER_TOOL)
            if handle is not None:
                try:
                    style = get_point_style("translate_arrow")
                    state = visual_state_for_flags(
                        selectable=bool(handle.selectable),
                        hover=bool(handle.hover),
                        grabbed=bool(handle.grabbed),
                        selected=bool(handle.selected),
                        visible=bool(handle.visible),
                    )
                    # Use the real X/Y/Z transform color as the base.  Hover and
                    # grab are still driven through the official style size.
                    rgba = _rgb_to_rgba(color)
                    ctx.transform_gizmos.update_handle(
                        handle.id,
                        color=rgba,
                        radius_px=ctx.transform_gizmos.radius_for_style("translate_arrow", 16, state),
                        base_radius_px=16,
                    )
                except Exception:
                    pass

        snapshot = NativeTransformGizmoSnapshot(
            mode="translate",
            center=c,
            length=l,
            axes=axis_keys,
            positions=handle_positions,
            lines=line_positions,
            handle_ids={axis: f"{MANIPULATOR_ID}:{axis}" for axis in axis_keys},
            axis_vectors=axis_vectors,
            colors=colors,
        )
        setattr(owner, "_native_transform_gizmo_active", True)
        setattr(owner, "_native_transform_gizmo_snapshot", snapshot)
        setattr(owner, "_native_transform_gizmo_owner_tool", OWNER_TOOL)
        if not _render_snapshot(owner, snapshot, render=bool(render)):
            # Keep legacy transform usable if the dedicated renderer is not
            # available in a reduced runtime environment.
            return False
        record_transform_gizmo_event(owner, "api.sync_success", snapshot=snapshot, extra={"mode": "translate"})
        _audit(owner, "transform.gizmo.native.sync")
        return True
    except Exception:
        try:
            from laserprog_studio.studio_log import log_exception

            log_exception("sync_native_translate_gizmo")
        except Exception:
            pass
        record_transform_gizmo_event(owner, "api.sync_exception", extra={"mode": "translate"}, ui_log=True)
        return False


def sync_native_rotate_gizmo(
    owner: Any,
    *,
    center: tuple[float, float, float],
    length: float,
    axes: dict[str, tuple[tuple[float, float, float], str]],
    render: bool = True,
) -> bool:
    """Declare the Rotate gizmo through the API using lightweight preview rings."""

    if not native_transform_gizmo_enabled(owner):
        record_transform_gizmo_event(owner, "api.sync_disabled", extra={"mode": "rotate"})
        return False
    record_transform_gizmo_event(owner, "api.sync_requested", extra={"mode": "rotate", "center": center, "length": length, "axes": tuple(axes)})
    try:
        ctx = _ctx(owner)
        axis_keys = tuple(axis for axis in ("x", "y", "z") if axis in axes)
        if not axis_keys:
            return False
        c = tuple(float(v) for v in center)
        l = max(float(length), 1.0e-9)
        ring_radius = l * 0.92
        endpoint_radius = l * 0.92
        axis_vectors = {axis: tuple(float(v) for v in axes[axis][0]) for axis in axis_keys}
        colors = _axis_colors(axes)
        rings: dict[str, tuple[tuple[float, float, float], ...]] = {}
        handle_positions: dict[str, tuple[float, float, float]] = {}
        handle_ids: dict[str, str] = {}

        ctx.preview.clear_tool(OWNER_TOOL)
        ctx.transform_gizmos.clear_tool(OWNER_TOOL)
        ctx.transform_gizmos.rotate(
            id=ROTATE_MANIPULATOR_ID,
            owner_tool=OWNER_TOOL,
            origin=c,
            axes=axis_keys,
            radius_px=17,
            axis_length=endpoint_radius,
            axis_vectors=axis_vectors,
        )
        for axis in axis_keys:
            vec = _normalize_vec(axis_vectors[axis])
            color = colors.get(axis, "#FFB23F")
            ring = _ring_points(c, vec, ring_radius, samples=96)
            rings[axis] = ring
            ctx.preview.show_polyline(
                f"{ROTATE_MANIPULATOR_ID}:ring:{axis}",
                OWNER_TOOL,
                ring,
                payload={"color": color, "line_width": 3.5, "line_style": "rotation_ring", "axis": axis},
            )
            # Put the visible/grabbable marker on the ring itself. A marker on
            # the axis normal is not part of the visible ring and can overlap a
            # different projected axis, making Rotate select the wrong handle.
            pos = tuple(ring[len(ring) // 2])
            handle_positions[axis] = pos
            handle_id = f"{ROTATE_MANIPULATOR_ID}:rotate:{axis}"
            handle_ids[axis] = handle_id
            _apply_axis_handle_visual(ctx, handle_id, color=color, style_id="ring", radius_px=17)
            try:
                ctx.preview.show_text(f"{ROTATE_MANIPULATOR_ID}:label:{axis}", OWNER_TOOL, axis.upper(), (c[0] + vec[0] * l * 1.12, c[1] + vec[1] * l * 1.12, c[2] + vec[2] * l * 1.12), size_px=14)
            except Exception:
                pass

        snapshot = NativeTransformGizmoSnapshot(
            mode="rotate",
            center=c,
            length=l,
            axes=axis_keys,
            positions=handle_positions,
            lines={},
            handle_ids=handle_ids,
            rings=rings,
            axis_vectors=axis_vectors,
            colors=colors,
        )
        setattr(owner, "_native_transform_gizmo_active", True)
        setattr(owner, "_native_transform_gizmo_snapshot", snapshot)
        setattr(owner, "_native_transform_gizmo_owner_tool", OWNER_TOOL)
        if not _render_snapshot(owner, snapshot, render=bool(render)):
            return False
        record_transform_gizmo_event(owner, "api.sync_success", snapshot=snapshot, extra={"mode": "rotate"})
        _audit(owner, "transform.gizmo.native.rotate.sync")
        return True
    except Exception:
        try:
            from laserprog_studio.studio_log import log_exception

            log_exception("sync_native_rotate_gizmo")
        except Exception:
            pass
        record_transform_gizmo_event(owner, "api.sync_exception", extra={"mode": "rotate"}, ui_log=True)
        return False


def sync_native_scale_gizmo(
    owner: Any,
    *,
    center: tuple[float, float, float],
    length: float,
    axes: dict[str, tuple[tuple[float, float, float], str]],
    frame_specs: list[tuple[str, tuple[float, float, float], tuple[float, float, float], str]] | tuple[tuple[str, tuple[float, float, float], tuple[float, float, float], str], ...] = (),
    render: bool = True,
) -> bool:
    """Declare the Scale gizmo through the API using axis grips plus frame edges."""

    if not native_transform_gizmo_enabled(owner):
        record_transform_gizmo_event(owner, "api.sync_disabled", extra={"mode": "scale"})
        return False
    record_transform_gizmo_event(owner, "api.sync_requested", extra={"mode": "scale", "center": center, "length": length, "axes": tuple(axes), "frame_specs": len(tuple(frame_specs or ()))})
    try:
        ctx = _ctx(owner)
        axis_keys = tuple(axis for axis in ("x", "y", "z") if axis in axes)
        if not axis_keys:
            return False
        c = tuple(float(v) for v in center)
        l = max(float(length), 1.0e-9)
        axis_vectors = {axis: tuple(float(v) for v in axes[axis][0]) for axis in axis_keys}
        # Scale handles are UI, not geometry.  They must remain outside the
        # selected object even when the camera zoom-derived length is small.
        max_frame_radius = 0.0
        try:
            for _raw_handle, p0, p1, _color in tuple(frame_specs or ()):
                for p in (p0, p1):
                    max_frame_radius = max(
                        max_frame_radius,
                        math.sqrt((float(p[0]) - c[0]) ** 2 + (float(p[1]) - c[1]) ** 2 + (float(p[2]) - c[2]) ** 2),
                    )
        except Exception:
            max_frame_radius = 0.0
        axis_length = max(l * 0.74, max_frame_radius * 1.08)
        colors = _axis_colors(axes)
        lines: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
        handle_positions: dict[str, tuple[float, float, float]] = {}
        handle_ids: dict[str, str] = {}

        ctx.preview.clear_tool(OWNER_TOOL)
        ctx.transform_gizmos.clear_tool(OWNER_TOOL)
        ctx.transform_gizmos.scale(
            id=SCALE_MANIPULATOR_ID,
            owner_tool=OWNER_TOOL,
            origin=c,
            axes=axis_keys,
            radius_px=16,
            axis_length=axis_length,
            axis_vectors=axis_vectors,
        )
        for axis in axis_keys:
            vec = _normalize_vec(axis_vectors[axis])
            color = colors.get(axis, "#91E085")
            p1 = (c[0] + vec[0] * axis_length, c[1] + vec[1] * axis_length, c[2] + vec[2] * axis_length)
            lines[axis] = (c, p1)
            handle_positions[axis] = p1
            handle_id = f"{SCALE_MANIPULATOR_ID}:scale:{axis}"
            handle_ids[axis] = handle_id
            ctx.preview.show_line(
                f"{SCALE_MANIPULATOR_ID}:axis:{axis}",
                OWNER_TOOL,
                c,
                p1,
                payload={"color": color, "line_width": 3.4, "line_style": "scale_axis", "axis": axis},
            )
            _apply_axis_handle_visual(ctx, handle_id, color=color, style_id="square", radius_px=16)

        for raw_handle, p0, p1, color in tuple(frame_specs or ()):  # visible adaptive frame edges
            handle = str(raw_handle).lower().strip()
            if not handle:
                continue
            a = tuple(float(v) for v in p0)
            b = tuple(float(v) for v in p1)
            mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5, (a[2] + b[2]) * 0.5)
            key = handle
            lines[key] = (a, b)
            handle_positions[key] = mid
            ctx.preview.show_line(
                f"{SCALE_MANIPULATOR_ID}:frame:{key}",
                OWNER_TOOL,
                a,
                b,
                payload={"color": str(color), "line_width": 2.8, "line_style": "scale_frame", "axis": key},
            )
            handle_id = f"{SCALE_MANIPULATOR_ID}:scale:{key}"
            handle_ids[key] = handle_id
            ctx.transform_gizmos.upsert_handle(
                id=handle_id,
                owner_tool=OWNER_TOOL,
                position=mid,
                radius_px=12,
                base_radius_px=12,
                kind=f"scale:{key}",
                style_id="square",
            )
            _apply_axis_handle_visual(ctx, handle_id, color=str(color), style_id="square", radius_px=12)

        ctx.transform_gizmos.upsert_handle(
            id=f"{SCALE_MANIPULATOR_ID}:center",
            owner_tool=OWNER_TOOL,
            position=c,
            radius_px=10,
            base_radius_px=10,
            kind="scale:center",
            style_id="solid",
            selectable=False,
        )

        snapshot = NativeTransformGizmoSnapshot(
            mode="scale",
            center=c,
            length=l,
            axes=tuple(lines.keys()),
            positions=handle_positions,
            lines=lines,
            handle_ids=handle_ids,
            axis_vectors=axis_vectors,
            colors=colors,
        )
        setattr(owner, "_native_transform_gizmo_active", True)
        setattr(owner, "_native_transform_gizmo_snapshot", snapshot)
        setattr(owner, "_native_transform_gizmo_owner_tool", OWNER_TOOL)
        if not _render_snapshot(owner, snapshot, render=bool(render)):
            return False
        record_transform_gizmo_event(owner, "api.sync_success", snapshot=snapshot, extra={"mode": "scale"})
        _audit(owner, "transform.gizmo.native.scale.sync")
        return True
    except Exception:
        try:
            from laserprog_studio.studio_log import log_exception

            log_exception("sync_native_scale_gizmo")
        except Exception:
            pass
        record_transform_gizmo_event(owner, "api.sync_exception", extra={"mode": "scale"}, ui_log=True)
        return False


def _point_from_center(
    center: tuple[float, float, float],
    direction: tuple[float, float, float],
    distance: float,
) -> tuple[float, float, float]:
    unit = _normalize_vec(direction)
    return (
        float(center[0]) + unit[0] * float(distance),
        float(center[1]) + unit[1] * float(distance),
        float(center[2]) + unit[2] * float(distance),
    )


def resize_native_transform_gizmo_live(owner: Any, *, length: float, render: bool = False) -> bool:
    """Resize the active Transform gizmo in place after a camera zoom event.

    Only lightweight point coordinates are changed; actors, mappers and renderer
    assemblies remain alive.  The public Transform ToolContext and the
    screen-space picking snapshot are updated from the same geometry.
    """

    try:
        if not bool(getattr(owner, "_native_transform_gizmo_active", False)):
            return False
        snapshot = getattr(owner, "_native_transform_gizmo_snapshot", None)
        ctx = getattr(owner, "_native_transform_gizmo_ctx", None)
        if snapshot is None or not isinstance(ctx, ToolContext):
            return False
        # A true vtkActor2D overlay is projected before every rendered frame.
        # Camera zoom therefore changes its display geometry automatically and
        # does not require rebuilding world-space handles/rings.
        try:
            from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

            renderer = get_transform_gizmo_renderer(owner)
            if bool(getattr(renderer, "screen_space_overlay", False)):
                update = getattr(renderer, "update_geometry", None)
                if callable(update):
                    update(snapshot, render=False)
                _audit(owner, "transform.gizmo.overlay2d.camera_auto_project")
                return True
        except Exception:
            pass
        old_length = max(float(getattr(snapshot, "length", 0.0)), 1.0e-12)
        new_length = max(float(length), 1.0e-9)
        if abs(new_length - old_length) <= max(old_length, new_length) * 1.0e-5:
            return True

        mode = str(getattr(snapshot, "mode", "")).lower()
        center = tuple(float(v) for v in snapshot.center)
        axes = tuple(str(axis) for axis in snapshot.axes)
        vectors = dict(getattr(snapshot, "axis_vectors", {}) or {})
        colors = dict(getattr(snapshot, "colors", {}) or {})
        handle_ids = dict(getattr(snapshot, "handle_ids", {}) or {})
        positions: dict[str, tuple[float, float, float]] = {}
        lines: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {}
        rings: dict[str, tuple[tuple[float, float, float], ...]] = {}

        if mode == "translate":
            for axis in axes:
                direction = vectors.get(axis, (1.0, 0.0, 0.0))
                positions[axis] = _point_from_center(center, direction, new_length)
                lines[axis] = (center, _point_from_center(center, direction, new_length * 0.86))
        elif mode == "rotate":
            for axis in axes:
                direction = _normalize_vec(vectors.get(axis, (1.0, 0.0, 0.0)))
                ring = _ring_points(center, direction, new_length * 0.92, samples=96)
                rings[axis] = ring
                positions[axis] = tuple(ring[len(ring) // 2])
        elif mode == "scale":
            old_lines = dict(getattr(snapshot, "lines", {}) or {})
            old_positions = dict(getattr(snapshot, "positions", {}) or {})
            frame_keys = [key for key in old_lines if str(key) not in {"x", "y", "z"}]
            max_frame_radius = 0.0
            for key in frame_keys:
                a, b = old_lines[key]
                lines[str(key)] = (tuple(float(v) for v in a), tuple(float(v) for v in b))
                if key in old_positions:
                    positions[str(key)] = tuple(float(v) for v in old_positions[key])
                for point in (a, b):
                    max_frame_radius = max(
                        max_frame_radius,
                        math.sqrt(
                            (float(point[0]) - center[0]) ** 2
                            + (float(point[1]) - center[1]) ** 2
                            + (float(point[2]) - center[2]) ** 2
                        ),
                    )
            axis_length = max(new_length * 0.74, max_frame_radius * 1.08)
            for axis in axes:
                tip = _point_from_center(center, vectors.get(axis, (1.0, 0.0, 0.0)), axis_length)
                positions[axis] = tip
                lines[axis] = (center, tip)
        else:
            return False

        new_snapshot = replace(
            snapshot,
            length=new_length,
            positions=positions,
            lines=lines,
            rings=rings,
            colors=colors,
        )

        handle_updates: dict[str, tuple[float, float, float]] = {}
        for key, position in positions.items():
            handle_id = str(handle_ids.get(key) or "")
            if handle_id:
                handle_updates[handle_id] = position
        if handle_updates:
            ctx.transform_gizmos.begin_interactive_update()
            try:
                ctx.transform_gizmos.update_positions_only(handle_updates)
            finally:
                ctx.transform_gizmos.end_interactive_update()

        if mode == "translate":
            for axis, (p0, p1) in lines.items():
                item_id = f"{MANIPULATOR_ID}:axis:{axis}"
                existing = next((item for item in ctx.preview.items(owner_tool=OWNER_TOOL) if item.id == item_id), None)
                ctx.preview.show_line(item_id, OWNER_TOOL, p0, p1, payload=getattr(existing, "payload", None))
        elif mode == "rotate":
            for axis, points in rings.items():
                item_id = f"{ROTATE_MANIPULATOR_ID}:ring:{axis}"
                existing = next((item for item in ctx.preview.items(owner_tool=OWNER_TOOL) if item.id == item_id), None)
                ctx.preview.show_polyline(item_id, OWNER_TOOL, points, payload=getattr(existing, "payload", None))
        elif mode == "scale":
            existing_items = {str(item.id): item for item in ctx.preview.items(owner_tool=OWNER_TOOL)}
            for key, (p0, p1) in lines.items():
                item_id = f"{SCALE_MANIPULATOR_ID}:axis:{key}" if key in {"x", "y", "z"} else f"{SCALE_MANIPULATOR_ID}:frame:{key}"
                ctx.preview.show_line(item_id, OWNER_TOOL, p0, p1, payload=getattr(existing_items.get(item_id), "payload", None))

        from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

        renderer = get_transform_gizmo_renderer(owner)
        if not renderer.update_geometry(new_snapshot, render=bool(render)):
            # Rare compatibility fallback: a stale renderer created before this
            # pass can rebuild once, then subsequent wheel events stay in-place.
            if not renderer.sync(new_snapshot, render=bool(render)):
                return False
        setattr(owner, "_native_transform_gizmo_snapshot", new_snapshot)
        _audit(owner, "transform.gizmo.native.camera_resize")
        record_transform_gizmo_event(
            owner,
            "api.camera_resize",
            snapshot=new_snapshot,
            extra={"old_length": old_length, "new_length": new_length, "render": bool(render)},
        )
        return True
    except Exception as exc:
        record_transform_gizmo_event(owner, "api.camera_resize_failed", error=exc)
        return False


def _add_point(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _offset_line(line: tuple[tuple[float, float, float], tuple[float, float, float]], offset: tuple[float, float, float]) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    return (_add_point(line[0], offset), _add_point(line[1], offset))


def move_native_translate_gizmo_live(owner: Any, *, offset: tuple[float, float, float], render: bool = False) -> bool:
    """Move the API translate gizmo during a live drag without rebuilding it.

    The old transform gizmo intentionally stayed fixed while the mesh moved,
    because moving cone/cylinder actors on every mouse tick was too expensive.
    The API gizmo is persistent and has a fast point-range updater, so the
    manipulator can now follow the dragged selection center.  ``offset`` is the
    current drag offset relative to the gizmo snapshot captured at drag start.
    """

    try:
        if not bool(getattr(owner, "_native_transform_gizmo_active", False)):
            return False
        ctx = getattr(owner, "_native_transform_gizmo_ctx", None)
        if not isinstance(ctx, ToolContext):
            return False
        base = getattr(owner, "_native_transform_gizmo_drag_base_snapshot", None) or getattr(owner, "_native_transform_gizmo_snapshot", None)
        if base is None or str(getattr(base, "mode", "")).lower() != "translate":
            return False
        off = (float(offset[0]), float(offset[1]), float(offset[2]))
        last = getattr(owner, "_native_transform_gizmo_drag_live_offset", None)
        if last is not None:
            try:
                if abs(float(last[0]) - off[0]) + abs(float(last[1]) - off[1]) + abs(float(last[2]) - off[2]) <= 1.0e-10:
                    return True
            except Exception:
                pass
        new_center = _add_point(tuple(getattr(base, "center", (0.0, 0.0, 0.0))), off)
        new_positions = {str(axis): _add_point(tuple(pos), off) for axis, pos in dict(getattr(base, "positions", {}) or {}).items()}
        new_lines = {str(axis): _offset_line(tuple(line), off) for axis, line in dict(getattr(base, "lines", {}) or {}).items()}
        handle_ids = dict(getattr(base, "handle_ids", {}) or {})
        handle_updates: dict[str, tuple[float, float, float]] = {}
        for axis, position in new_positions.items():
            handle_id = str(handle_ids.get(axis) or f"{MANIPULATOR_ID}:{axis}")
            handle_updates[handle_id] = position
        center_handle_id = f"{MANIPULATOR_ID}:center"
        if ctx.transform_gizmos.handle(center_handle_id, owner_tool=OWNER_TOOL) is not None:
            handle_updates[center_handle_id] = new_center
        if handle_updates:
            ctx.transform_gizmos.begin_interactive_update()
            try:
                ctx.transform_gizmos.update_positions_only(handle_updates)
            finally:
                ctx.transform_gizmos.end_interactive_update()

        existing_items = {str(item.id): item for item in ctx.preview.items(owner_tool=OWNER_TOOL)}
        preview_ids: list[str] = []
        for axis, (p0, p1) in new_lines.items():
            item_id = f"{MANIPULATOR_ID}:axis:{axis}"
            payload = getattr(existing_items.get(item_id), "payload", None)
            ctx.preview.show_line(item_id, OWNER_TOOL, p0, p1, payload=payload)
            preview_ids.append(item_id)

        new_snapshot = replace(base, center=new_center, positions=new_positions, lines=new_lines)
        try:
            from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

            # The dedicated renderer moves one foreground assembly.  No mesh,
            # guide or actor is recreated while the mouse is moving.
            get_transform_gizmo_renderer(owner).move_translate(offset=off, render=bool(render))
        except Exception:
            pass
        setattr(owner, "_native_transform_gizmo_snapshot", new_snapshot)
        setattr(owner, "_native_transform_gizmo_drag_live_offset", off)
        _audit(owner, "transform.gizmo.native.translate.live_move")
        return True
    except Exception:
        try:
            from laserprog_studio.studio_log import log_exception

            log_exception("move_native_translate_gizmo_live")
        except Exception:
            pass
        return False

def clear_native_transform_gizmo(owner: Any, *, render: bool = False) -> None:
    try:
        ctx = getattr(owner, "_native_transform_gizmo_ctx", None)
        if isinstance(ctx, ToolContext):
            ctx.preview.clear_tool(OWNER_TOOL)
            ctx.transform_gizmos.clear_tool(OWNER_TOOL)
        try:
            from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

            get_transform_gizmo_renderer(owner).clear(render=bool(render))
        except Exception:
            pass
        setattr(owner, "_native_transform_gizmo_active", False)
        setattr(owner, "_native_transform_gizmo_snapshot", None)
        record_transform_gizmo_event(owner, "api.clear", ui_log=True)
        _audit(owner, "transform.gizmo.native.clear")
    except Exception:
        pass


def _world_to_qt(owner: Any, point: tuple[float, float, float]) -> tuple[float, float] | None:
    try:
        sx, sy_vtk, _depth = owner._world_to_display(point)
        h = float(owner.plotter.height())
        return (float(sx), h - float(sy_vtk))
    except Exception:
        return None


def _point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    if denom <= 1.0e-9:
        return (wx * wx + wy * wy) ** 0.5
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    cx, cy = ax + t * vx, ay + t * vy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _lerp2(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return (float(a[0]) + (float(b[0]) - float(a[0])) * float(t), float(a[1]) + (float(b[1]) - float(a[1])) * float(t))


def _sticky_transform_handle(owner: Any) -> str | None:
    """Return the interaction handle that should win close hover ties."""

    for attr in ("_drag_axis", "_gizmo_pressed_axis", "_hovered_transform_axis", "_highlighted_transform_axis"):
        raw = (getattr(owner, attr, None) or "").lower().strip()
        if raw:
            return raw
    return None


def _best_with_hysteresis(owner: Any, candidates: list[tuple[str, float]], threshold: float) -> str | None:
    clean = [(str(handle), float(dist)) for handle, dist in candidates if math.isfinite(float(dist)) and float(dist) <= float(threshold)]
    if not clean:
        return None
    clean.sort(key=lambda item: (item[1], item[0]))
    best_handle, best_distance = clean[0]
    sticky = _sticky_transform_handle(owner)
    if sticky:
        sticky_logical = sticky[:1] if sticky[:1] in {"x", "y", "z"} else sticky
        for handle, distance in clean:
            logical = handle[:1] if handle[:1] in {"x", "y", "z"} else handle
            if handle == sticky or logical == sticky_logical:
                # Keep the current hover/grab while it remains plausibly under
                # the cursor.  This removes X/Y/Z flicker at projected crossings
                # without making it difficult to leave one axis for another.
                if distance <= float(threshold) * 1.05 and distance <= best_distance + 5.0:
                    return handle
                break
    return best_handle


def _polyline_distance(owner: Any, qx: float, qy: float, points: tuple[tuple[float, float, float], ...]) -> float:
    best = 1.0e9
    if len(points) < 2:
        return best
    projected: list[tuple[float, float]] = []
    for point in points:
        p = _world_to_qt(owner, point)
        if p is None:
            return best
        projected.append(p)
    for a, b in zip(projected, projected[1:]):
        best = min(best, _point_segment_distance(float(qx), float(qy), a[0], a[1], b[0], b[1]))
    return best


def pick_native_transform_gizmo(owner: Any, qx: float, qy: float, *, generous: bool = False) -> tuple[str, str] | None:
    """Pick exactly one visible Transform handle in screen space.

    Visible point handles are deliberately given priority over strokes. This is
    especially important for Rotate, where three projected rings can overlap: a
    user can always grab the colored marker point for an unambiguous axis.
    """

    try:
        if not bool(getattr(owner, "_native_transform_gizmo_active", False)):
            return None
        snap = getattr(owner, "_native_transform_gizmo_snapshot", None)
        if snap is None:
            record_transform_gizmo_event(owner, "pick.miss", extra={"reason": "missing_snapshot", "force": True})
            return None
        mode = str(getattr(snap, "mode", "")).lower()
        px, py = float(qx), float(qy)
        diag: dict[str, Any] = {"mode": mode, "qx": round(px, 3), "qy": round(py, 3), "generous": bool(generous)}

        # The 2D backend exposes the exact geometry it draws. Use it for hover
        # and grab so visible strokes and hit targets can never diverge.
        try:
            from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

            renderer = get_transform_gizmo_renderer(owner)
            if bool(getattr(renderer, "screen_space_overlay", False)):
                handle = renderer.pick(px, py, generous=bool(generous))
                if handle is not None:
                    diag["handle"] = str(handle)
                    diag["backend"] = "overlay2d"
                    record_transform_gizmo_event(owner, "pick.hit", snapshot=snap, extra=diag)
                    _audit(owner, f"transform.gizmo.native.{mode or 'unknown'}.pick_hit")
                    return ("gizmo", str(handle))
                diag["backend"] = "overlay2d"
                record_transform_gizmo_event(owner, "pick.miss", snapshot=snap, extra=diag)
                _audit(owner, f"transform.gizmo.native.{mode or 'unknown'}.pick_miss")
                return None
        except Exception as exc:
            diag["overlay2d_error"] = type(exc).__name__

        if mode == "rotate":
            marker_threshold = 31.0 if generous else 18.0
            ring_threshold = 22.0 if generous else 9.5
            marker_candidates: list[tuple[str, float]] = []
            ring_candidates: list[tuple[str, float]] = []
            for handle, point in dict(getattr(snap, "positions", {}) or {}).items():
                projected = _world_to_qt(owner, tuple(point))
                if projected is not None:
                    marker_candidates.append((str(handle), math.hypot(px - projected[0], py - projected[1])))
            for handle, ring in dict(getattr(snap, "rings", {}) or {}).items():
                ring_candidates.append((str(handle), _polyline_distance(owner, px, py, tuple(ring))))
            best_handle = _best_with_hysteresis(owner, marker_candidates, marker_threshold)
            if best_handle is None:
                best_handle = _best_with_hysteresis(owner, ring_candidates, ring_threshold)
            diag["marker_candidates"] = [(h, round(d, 3)) for h, d in sorted(marker_candidates, key=lambda item: item[1])[:3]]
            diag["ring_candidates"] = [(h, round(d, 3)) for h, d in sorted(ring_candidates, key=lambda item: item[1])[:3]]
        else:
            tip_threshold = 31.0 if generous else 18.0
            shaft_threshold = 21.0 if generous else 10.5
            frame_threshold = 19.0 if generous else 9.0
            tip_candidates: list[tuple[str, float]] = []
            shaft_candidates: list[tuple[str, float]] = []
            frame_candidates: list[tuple[str, float]] = []
            positions = dict(getattr(snap, "positions", {}) or {})
            for handle, (p0, p1) in dict(getattr(snap, "lines", {}) or {}).items():
                key = str(handle)
                a = _world_to_qt(owner, p0)
                visible_end = positions.get(key, p1) if key in {"x", "y", "z"} else p1
                b = _world_to_qt(owner, visible_end)
                if a is None or b is None:
                    continue
                projected_length = math.hypot(b[0] - a[0], b[1] - a[1])
                if key in {"x", "y", "z"}:
                    if projected_length < 7.0:
                        continue
                    tip_candidates.append((key, math.hypot(px - b[0], py - b[1])))
                    shaft_start = _lerp2(a, b, 0.34)
                    shaft_end = _lerp2(a, b, 0.94)
                    shaft_candidates.append((key, _point_segment_distance(px, py, shaft_start[0], shaft_start[1], shaft_end[0], shaft_end[1])))
                else:
                    marker = positions.get(key)
                    marker_qt = _world_to_qt(owner, marker) if marker is not None else None
                    if marker_qt is not None:
                        tip_candidates.append((key, math.hypot(px - marker_qt[0], py - marker_qt[1])))
                    frame_candidates.append((key, _point_segment_distance(px, py, a[0], a[1], b[0], b[1])))

            best_handle = _best_with_hysteresis(owner, tip_candidates, tip_threshold)
            if best_handle is None:
                best_handle = _best_with_hysteresis(owner, frame_candidates, frame_threshold)
            if best_handle is None:
                best_handle = _best_with_hysteresis(owner, shaft_candidates, shaft_threshold)
            diag["tip_candidates"] = [(h, round(d, 3)) for h, d in sorted(tip_candidates, key=lambda item: item[1])[:4]]
            diag["frame_candidates"] = [(h, round(d, 3)) for h, d in sorted(frame_candidates, key=lambda item: item[1])[:4]]
            diag["shaft_candidates"] = [(h, round(d, 3)) for h, d in sorted(shaft_candidates, key=lambda item: item[1])[:4]]

        if best_handle is not None:
            diag["handle"] = str(best_handle)
            record_transform_gizmo_event(owner, "pick.hit", snapshot=snap, extra=diag)
            _audit(owner, f"transform.gizmo.native.{mode or 'unknown'}.pick_hit")
            return ("gizmo", best_handle)
        record_transform_gizmo_event(owner, "pick.miss", snapshot=snap, extra=diag)
        _audit(owner, f"transform.gizmo.native.{mode or 'unknown'}.pick_miss")
        return None
    except Exception as exc:
        record_transform_gizmo_event(owner, "pick.exception", error=exc, extra={"qx": qx, "qy": qy}, ui_log=True)
        return None

def native_transform_drag_basis(
    owner: Any,
    handle: str,
    *,
    world_length: float | None = None,
) -> tuple[float, float, float, float] | None:
    """Return the displayed 2D drag direction and camera-facing sign.

    The tuple is ``(screen_dx_qt, screen_dy_qt, world_per_pixel, sign)``.
    It lets translation follow a camera-facing arrow even when that arrow is
    drawn on the negative side of its logical world axis.
    """

    try:
        from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

        renderer = get_transform_gizmo_renderer(owner)
        if not bool(getattr(renderer, "screen_space_overlay", False)):
            return None
        return renderer.drag_basis(str(handle), world_length=world_length)
    except Exception:
        return None


def native_transform_gizmo_near(owner: Any, qx: float, qy: float) -> bool:
    try:
        return pick_native_transform_gizmo(owner, qx, qy, generous=True) is not None
    except Exception:
        return False


def sync_native_transform_interaction(owner: Any, *, active_axis: str | None = None, pinned_axis: str | None = None, render: bool = False) -> bool:
    """Apply hover/grab/pinned state to API handles without rebuilding actors."""

    try:
        if not bool(getattr(owner, "_native_transform_gizmo_active", False)):
            return False
        ctx = getattr(owner, "_native_transform_gizmo_ctx", None)
        snap = getattr(owner, "_native_transform_gizmo_snapshot", None)
        if not isinstance(ctx, ToolContext) or snap is None:
            return False
        active = (active_axis or "").lower().strip() or None
        pinned = (pinned_axis or "").lower().strip() or None
        grabbed = (getattr(owner, "_drag_axis", None) or "").lower().strip() or None
        handle_ids = dict(getattr(snap, "handle_ids", {}) or {})
        if not handle_ids:
            handle_ids = {axis: f"{MANIPULATOR_ID}:{axis}" for axis in getattr(snap, "axes", ())}
        changed = 0
        ctx.transform_gizmos.begin_interactive_update()
        try:
            for handle_key, handle_id in handle_ids.items():
                key = str(handle_key).lower().strip()
                handle = ctx.transform_gizmos.handle(str(handle_id), owner_tool=OWNER_TOOL)
                if handle is None:
                    continue
                logical_key = key[0] if key[:1] in {"x", "y", "z"} else key
                grabbed_logical = grabbed[0] if grabbed and grabbed[:1] in {"x", "y", "z"} else grabbed
                active_logical = active[0] if active and active[:1] in {"x", "y", "z"} else active
                pinned_logical = pinned[0] if pinned and pinned[:1] in {"x", "y", "z"} else pinned
                is_grabbed = bool(grabbed and (key == grabbed or logical_key == grabbed_logical))
                is_hover = bool(active and (key == active or logical_key == active_logical) and not is_grabbed)
                is_selected = bool(pinned and (key == pinned or logical_key == pinned_logical) and not is_grabbed and not is_hover)
                if handle.hover == is_hover and handle.grabbed == is_grabbed and handle.selected == is_selected:
                    continue
                if ctx.transform_gizmos.update_visual_state(str(handle_id), hover=is_hover, grabbed=is_grabbed, selected=is_selected):
                    changed += 1
        finally:
            ctx.transform_gizmos.end_interactive_update()
        renderer_changed = False
        try:
            from laserprog_studio.application.transform_gizmo_renderer import get_transform_gizmo_renderer

            renderer_changed = bool(
                get_transform_gizmo_renderer(owner).set_interaction(
                    active_handle=active,
                    pinned_handle=pinned,
                    grabbed_handle=grabbed,
                    render=bool(render),
                )
            )
        except Exception:
            renderer_changed = False
        return bool(changed or renderer_changed)
    except Exception:
        return False

