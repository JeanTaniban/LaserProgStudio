"""Surface anchoring and arbitrary-normal camera helpers for Plan 2D tools."""
from __future__ import annotations

import math
from typing import Any

from laserprog_studio.planar_tools import (
    FixedPlanarView,
    LockedPlaneSpec,
    clamp_world_point_to_plane,
    make_locked_plane,
    plane_to_world,
)

from .plane import (
    PLAN_TRACE_ANCHOR_FALLBACK_DEPTH,
    PLAN_TRACE_DEFAULT_SURFACE_OFFSET,
    Plan2DAnchorPick,
    Point2,
    Point3,
    _log_plan_trace_raycast,
    _pick_all_scene_parts_with_vtk,
    _point3,
    nearest_plan_view,
    project_screen_to_locked_plane,
)


def make_locked_plane_from_surface(
    ctx: Any,
    *,
    anchor_world: Point3,
    normal: Point3,
    view: FixedPlanarView | str | None = None,
) -> LockedPlaneSpec:
    """Create a locked 2D drawing plane from an actually picked scene face.

    The plane normal follows the picked surface normal, oriented toward the
    current camera when possible. Its in-plane axes preserve the current
    screen-up direction, so Plan Tracer does not force top/front/side semantics
    before the user has selected the surface they want to draw on.
    """

    resolved_view = _resolve_view(ctx, view)
    anchor = _point3(anchor_world)
    n = _orient_normal_toward_camera(ctx, _point3(normal), anchor)
    v_axis = _surface_v_axis_from_camera(ctx, n)
    u_axis = _unit(_cross(v_axis, n), fallback=(1.0, 0.0, 0.0))
    v_axis = _unit(_cross(n, u_axis), fallback=v_axis)
    return LockedPlaneSpec(resolved_view, n, u_axis, v_axis, _dot(n, anchor))


def align_camera_to_plan_surface(ctx: Any, plane: LockedPlaneSpec, *, anchor_world: Point3 | None = None, focus_bounds: tuple[float, float, float, float, float, float] | None = None) -> bool:
    """Align the host camera with an arbitrary picked drawing surface."""

    owner = getattr(ctx, "owner", None)
    if owner is None:
        return False
    origin = _point3(anchor_world) if anchor_world is not None else plane_to_world(plane, 0.0, 0.0)
    method = getattr(owner, "align_camera_to_plan_surface", None)
    if callable(method):
        try:
            method(origin=origin, normal=plane.normal, up_axis=plane.v_axis, focus_bounds=focus_bounds)
            return True
        except TypeError:
            # Compatibility with lightweight hosts/tests that implemented the
            # older keyword-only signature before focus_bounds was introduced.
            try:
                method(origin=origin, normal=plane.normal, up_axis=plane.v_axis)
                return True
            except TypeError:
                try:
                    method(origin, plane.normal, plane.v_axis)
                    return True
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass
    return _align_camera_to_plan_surface_fallback(owner, origin, plane, focus_bounds=focus_bounds)


def pick_plan_surface_anchor_by_raycast(
    ctx: Any,
    screen_pos: Point2,
    *,
    view: FixedPlanarView | str | None = None,
    fallback_depth: float = PLAN_TRACE_ANCHOR_FALLBACK_DEPTH,
    display_margin_world: float = PLAN_TRACE_DEFAULT_SURFACE_OFFSET,
    log_diagnostics: bool = False,
    diagnostics_label: str = "surface-anchor",
) -> Plan2DAnchorPick:
    """Pick a real scene surface and build an arbitrary-normal drawing plane.

    Object-only hits are not considered a successful Plan Tracer anchor.  A miss
    returns a fallback pick object for hover/status only; callers should check
    ``hit`` before entering drawing mode.
    """

    resolved_view = _resolve_view(ctx, view)
    pick, diagnostics = _pick_surface_by_raycast(ctx, screen_pos)
    if pick is not None and getattr(pick, "world_pos", None) is not None:
        anchor_world = _point3(pick.world_pos)
        raw_normal = getattr(pick, "normal", None)
        if raw_normal is None:
            raw_normal = make_locked_plane(resolved_view, depth=0.0).normal
            diagnostics["normal_fallback"] = "nearest_view"
        plane = make_locked_plane_from_surface(ctx, anchor_world=anchor_world, normal=_point3(raw_normal), view=resolved_view)
        hit = True
        diagnostics["result"] = "surface_hit"
        diagnostics["normal"] = tuple(float(v) for v in plane.normal)
        diagnostics["depth"] = float(plane.depth)
    else:
        plane = make_locked_plane(resolved_view, depth=float(fallback_depth))
        hit = False
        diagnostics["result"] = "surface_miss"
        diagnostics["depth"] = float(plane.depth)
        try:
            projected = project_screen_to_locked_plane(ctx, screen_pos, plane, event_world_pos=None)
        except Exception:
            projected = plane_to_world(plane, float(screen_pos[0]), float(screen_pos[1]))
        anchor_world = clamp_world_point_to_plane(plane, projected)

    display_plane = plane.with_depth(float(plane.depth) + max(float(display_margin_world), 0.0))
    anchor_world = clamp_world_point_to_plane(plane, anchor_world)
    display_world = clamp_world_point_to_plane(display_plane, anchor_world)
    diagnostics.update({
        "screen_pos": (float(screen_pos[0]), float(screen_pos[1])),
        "view": resolved_view.value,
        "display_depth": float(display_plane.depth),
        "object_id": None if pick is None else getattr(pick, "object_id", None),
        "object_index": None if pick is None else getattr(pick, "object_index", None),
        "hit_kind": "none" if pick is None else str(getattr(pick, "kind", "point")),
    })
    if log_diagnostics:
        _log_plan_trace_raycast(ctx, diagnostics_label, diagnostics)
    return Plan2DAnchorPick(
        plane=plane,
        display_plane=display_plane,
        anchor_world=anchor_world,
        display_world=display_world,
        view=resolved_view,
        object_id=None if pick is None else getattr(pick, "object_id", None),
        object_index=None if pick is None else getattr(pick, "object_index", None),
        hit_kind="none" if pick is None else str(getattr(pick, "kind", "point")),
        hit=hit,
        diagnostics=diagnostics,
    )


def _pick_surface_by_raycast(ctx: Any, screen_pos: Point2):
    """Return a face hit, ignoring object-only hits."""

    diagnostics: dict[str, Any] = {"backend": "none", "attempts": []}
    owner = getattr(ctx, "owner", None)
    vtk_pick = _pick_all_scene_parts_with_vtk(owner, screen_pos, diagnostics)
    if _is_surface_pick(vtk_pick):
        return vtk_pick, diagnostics

    facade = getattr(ctx, "pick", None)
    try:
        picker = getattr(facade, "face_at", None)
        if callable(picker):
            candidate = picker(screen_pos, all_parts=True, only_selected=False)
            ok = _is_surface_pick(candidate)
            diagnostics["attempts"].append({"backend": "ctx.pick.face_at", "hit": ok})
            if ok:
                diagnostics["backend"] = "ctx.pick.face_at"
                return candidate, diagnostics
    except Exception as exc:
        diagnostics["attempts"].append({"backend": "ctx.pick.face_at", "error": type(exc).__name__})
    diagnostics["backend"] = "surface_miss"
    return None, diagnostics


def _is_surface_pick(candidate: Any) -> bool:
    return bool(getattr(candidate, "hit", False)) and str(getattr(candidate, "kind", "")) == "face" and getattr(candidate, "world_pos", None) is not None


def _resolve_view(ctx: Any, view: FixedPlanarView | str | None) -> FixedPlanarView:
    if view is None:
        return nearest_plan_view(ctx)
    if isinstance(view, FixedPlanarView):
        return view
    return FixedPlanarView(str(getattr(view, "value", view)))




def _bounds_corners(bounds: tuple[float, float, float, float, float, float]) -> tuple[Point3, ...]:
    x0, x1, y0, y1, z0, z1 = (float(v) for v in bounds)
    return tuple((x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1))


def _camera_focus_from_bounds(
    bounds: tuple[float, float, float, float, float, float] | None,
    *,
    plane: LockedPlaneSpec,
    fallback_origin: Point3,
    aspect: float,
) -> tuple[Point3, float] | None:
    if bounds is None:
        return None
    try:
        corners = _bounds_corners(bounds)
        if not corners:
            return None
        center = (
            (float(bounds[0]) + float(bounds[1])) * 0.5,
            (float(bounds[2]) + float(bounds[3])) * 0.5,
            (float(bounds[4]) + float(bounds[5])) * 0.5,
        )
        up = _unit(_point3(plane.v_axis), fallback=(0.0, 1.0, 0.0))
        normal = _unit(_point3(plane.normal), fallback=(0.0, 0.0, 1.0))
        right = _unit(_cross(up, normal), fallback=_point3(plane.u_axis))
        rel = [_sub(corner, center) for corner in corners]
        hs = [_dot(v, right) for v in rel]
        vs = [_dot(v, up) for v in rel]
        half_h = max((max(hs) - min(hs)) * 0.5, 0.5)
        half_v = max((max(vs) - min(vs)) * 0.5, 0.5)
        scale = max(half_v, half_h / max(float(aspect), 0.1), 1.0) * 1.18
        if not math.isfinite(scale) or scale <= 0.0:
            return None
        return center, scale
    except Exception:
        return None

def _align_camera_to_plan_surface_fallback(owner: Any, origin: Point3, plane: LockedPlaneSpec, *, focus_bounds: tuple[float, float, float, float, float, float] | None = None) -> bool:
    try:
        plotter = getattr(owner, "plotter", None)
        cam = getattr(plotter, "camera", None)
        if plotter is None or cam is None:
            return False
        try:
            dist = _norm(_sub(_point3(cam.GetPosition()), _point3(cam.GetFocalPoint())))
        except Exception:
            dist = 50.0
        if not math.isfinite(dist) or dist < 1.0e-6:
            dist = 50.0
        try:
            width = float(getattr(plotter, "width", lambda: 1.0)())
            height = float(getattr(plotter, "height", lambda: 1.0)())
        except Exception:
            width, height = 1.0, 1.0
        focus = _camera_focus_from_bounds(focus_bounds, plane=plane, fallback_origin=origin, aspect=max(width / max(height, 1.0), 0.1))
        focal = focus[0] if focus is not None else origin
        if focus is not None:
            try:
                dist = max(float(dist), max(abs(float(focus_bounds[1]) - float(focus_bounds[0])), abs(float(focus_bounds[3]) - float(focus_bounds[2])), abs(float(focus_bounds[5]) - float(focus_bounds[4]))) * 3.0, 50.0)
            except Exception:
                pass
        new_pos = _add(focal, _mul(_unit(plane.normal), dist))
        cam.SetFocalPoint(float(focal[0]), float(focal[1]), float(focal[2]))
        cam.SetPosition(float(new_pos[0]), float(new_pos[1]), float(new_pos[2]))
        cam.SetViewUp(float(plane.v_axis[0]), float(plane.v_axis[1]), float(plane.v_axis[2]))
        try:
            cam.SetParallelProjection(True)
            if focus is not None:
                cam.SetParallelScale(float(focus[1]))
            cam.OrthogonalizeViewUp()
        except Exception:
            pass
        try:
            setattr(owner, "_camera_view_mode", "plan_trace_surface")
        except Exception:
            pass
        try:
            renderer = getattr(plotter, "renderer", None)
            if renderer is not None and callable(getattr(renderer, "ResetCameraClippingRange", None)):
                renderer.ResetCameraClippingRange()
        except Exception:
            pass
        if callable(getattr(plotter, "render", None)):
            plotter.render()
        return True
    except Exception:
        return False


def _camera_position(ctx: Any) -> Point3 | None:
    try:
        cam = getattr(getattr(getattr(ctx, "owner", None), "plotter", None), "camera", None)
        if cam is not None:
            return _point3(cam.GetPosition())
    except Exception:
        pass
    return None


def _camera_view_up(ctx: Any) -> Point3 | None:
    try:
        cam = getattr(getattr(getattr(ctx, "owner", None), "plotter", None), "camera", None)
        if cam is not None:
            return _point3(cam.GetViewUp())
    except Exception:
        pass
    return None


def _orient_normal_toward_camera(ctx: Any, normal: Point3, anchor_world: Point3) -> Point3:
    n = _unit(normal, fallback=(0.0, 0.0, 1.0))
    cam_pos = _camera_position(ctx)
    if cam_pos is not None and _dot(n, _sub(cam_pos, anchor_world)) < 0.0:
        return (-n[0], -n[1], -n[2])
    return n


def _surface_v_axis_from_camera(ctx: Any, normal: Point3) -> Point3:
    n = _unit(normal, fallback=(0.0, 0.0, 1.0))
    up = _camera_view_up(ctx) or (0.0, 0.0, 1.0)
    projected = _sub(up, _mul(n, _dot(up, n)))
    if _norm(projected) <= 1.0e-8:
        fallback = (0.0, 1.0, 0.0) if abs(n[2]) > 0.95 else (0.0, 0.0, 1.0)
        projected = _sub(fallback, _mul(n, _dot(fallback, n)))
    return _unit(projected, fallback=(0.0, 1.0, 0.0))


def _dot(a: Point3, b: Point3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _sub(a: Point3, b: Point3) -> Point3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _norm(v: Point3) -> float:
    return math.sqrt(max(_dot(v, v), 0.0))


def _unit(v: Point3, fallback: Point3 = (0.0, 0.0, 1.0)) -> Point3:
    n = _norm(v)
    if not math.isfinite(n) or n <= 1.0e-12:
        return tuple(float(x) for x in fallback)  # type: ignore[return-value]
    return (float(v[0]) / n, float(v[1]) / n, float(v[2]) / n)


def _mul(v: Point3, scalar: float) -> Point3:
    return (float(v[0]) * float(scalar), float(v[1]) * float(scalar), float(v[2]) * float(scalar))


def _add(a: Point3, b: Point3) -> Point3:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


__all__ = [
    "align_camera_to_plan_surface",
    "make_locked_plane_from_surface",
    "pick_plan_surface_anchor_by_raycast",
]
