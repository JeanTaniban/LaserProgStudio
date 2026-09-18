"""Public plane and coordinate-mapping helpers for Plan 2D tools."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Iterable

from laserprog_studio.planar_tools import (
    FixedPlanarView,
    LockedPlaneSpec,
    clamp_world_point_to_plane,
    make_locked_plane,
    nearest_locked_view_from_camera,
    nearest_locked_view_from_forward,
    plane_from_first_hit,
    plane_to_world,
    world_to_plane,
)

Point3 = tuple[float, float, float]
Point2 = tuple[float, float]

PLAN_TRACE_DEFAULT_SURFACE_OFFSET = 0.75
PLAN_TRACE_ANCHOR_FALLBACK_DEPTH = 0.0

class Plan2DPhase(str, Enum):
    """Lifecycle phase for a locked 2D drawing tool."""

    PICK_HEIGHT = "pick_height"
    DRAW = "draw"


class Plan2DTool(str, Enum):
    """Official tool palette ids for the Plan tracer overlay."""

    MODIFY = "modify"
    POINT = "point"
    LINE = "line"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ARC = "arc"
    HALF_CIRCLE = "half_circle"
    DIMENSION = "dimension"

@dataclass(frozen=True, slots=True)
class Plan2DPlanePick:
    """Result of selecting the locked drawing plane height."""

    plane: LockedPlaneSpec
    world_pos: Point3
    view: FixedPlanarView
    object_id: str | None = None
    object_index: int | None = None
    hit_kind: str = "none"


@dataclass(frozen=True, slots=True)
class Plan2DAnchorPick:
    """Raycast-only anchor selection for a 2D plan tracer.

    ``plane`` is the semantic construction plane: every generated point must be
    clamped to this depth.  ``display_plane`` is the same 2D plane moved a small
    distance toward the camera so official UI motifs remain visible and do not
    z-fight with the picked face.  Tool authors should not compute this offset
    themselves.
    """

    plane: LockedPlaneSpec
    display_plane: LockedPlaneSpec
    anchor_world: Point3
    display_world: Point3
    view: FixedPlanarView
    object_id: str | None = None
    object_index: int | None = None
    hit_kind: str = "none"
    hit: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Plan2DStateSummary:
    """Serializable summary for inspector fields, tests and docs."""

    phase: Plan2DPhase
    active_tool: Plan2DTool
    view: FixedPlanarView
    plane_depth: float | None
    points: int
    last_snap: str = "none"


def normalize_plan_tool(value: Plan2DTool | str | None, *, default: Plan2DTool = Plan2DTool.MODIFY) -> Plan2DTool:
    """Return a valid official drawing-tool id."""

    if isinstance(value, Plan2DTool):
        return value
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"halfcircle": "half_circle", "half_circle": "half_circle", "semi_circle": "half_circle", "semicircle": "half_circle", "arc_de_cercle": "arc", "arc_circle": "arc"}
    text = aliases.get(text, text)
    for item in Plan2DTool:
        if text == item.value:
            return item
    return default

def nearest_plan_view(ctx: Any) -> FixedPlanarView:
    """Return the closest official drawing view from the active camera.

    This is part of the API because planar tools must not implement their own
    camera-direction heuristics.  The function accepts normal ToolContext
    objects and test fakes.
    """

    owner = getattr(ctx, "owner", None)
    try:
        forward_fn = getattr(owner, "_camera_forward_vector", None)
        if callable(forward_fn):
            return nearest_locked_view_from_forward(tuple(float(v) for v in forward_fn()))
    except Exception:
        pass
    try:
        cam = getattr(getattr(owner, "plotter", None), "camera", None)
        if cam is not None:
            return nearest_locked_view_from_camera(tuple(cam.GetPosition()), tuple(cam.GetFocalPoint()))
    except Exception:
        pass
    try:
        mode = str(getattr(owner, "_camera_view_mode", "top") or "top").lower()
        if mode in {view.value for view in FixedPlanarView}:
            return FixedPlanarView(mode)
    except Exception:
        pass
    return FixedPlanarView.TOP


def lock_camera_to_plan_view(ctx: Any, view: FixedPlanarView | str) -> bool:
    """Ask the host to switch to the selected orthographic drawing view.

    Tool authors call the API helper; they do not reach into Qt or camera
    methods directly.  The helper is a no-op in headless tests.
    """

    owner = getattr(ctx, "owner", None)
    if owner is None:
        return False
    view_id = FixedPlanarView(str(view)).value if not isinstance(view, FixedPlanarView) else view.value
    try:
        setter = getattr(owner, "_set_fixed_orthographic_view", None)
        if callable(setter):
            setter(view_id)
            return True
    except Exception:
        pass
    try:
        method = getattr(owner, f"view_{view_id}", None)
        if callable(method):
            method()
            return True
    except Exception:
        pass
    return False


def release_plan_view_camera(ctx: Any) -> bool:
    """Return the host viewport to the normal iso/free-orbit camera.

    Locked Plan 2D tools temporarily switch the camera to a precise orthographic
    drawing plane.  This public API hook lets tools release that contract without
    reaching into application-specific camera methods directly.
    """

    owner = getattr(ctx, "owner", None)
    if owner is None:
        return False
    try:
        view_iso = getattr(owner, "view_iso", None)
        if callable(view_iso):
            view_iso()
            return True
    except Exception:
        pass
    try:
        setattr(owner, "_camera_view_mode", "free")
        plotter = getattr(owner, "plotter", None)
        if plotter is not None and callable(getattr(plotter, "view_isometric", None)):
            plotter.view_isometric()
            if callable(getattr(plotter, "reset_camera", None)):
                plotter.reset_camera()
            if callable(getattr(plotter, "render", None)):
                plotter.render()
            return True
    except Exception:
        pass
    return False


def project_screen_to_locked_plane(ctx: Any, screen_pos: Point2, plane: LockedPlaneSpec, *, event_world_pos: Point3 | None = None) -> Point3:
    """Project a viewport point onto a locked drawing plane.

    The host may expose a camera-aware ``screen_to_world_on_plane`` method; if it
    does not, the deterministic fallback treats screen X/Y as plane U/V.  The
    returned point is always clamped to the locked plane depth.
    """

    viewport = getattr(ctx, "viewport", None)
    method = getattr(viewport, "screen_to_world_on_plane", None)
    if callable(method):
        for arg in (plane, plane.depth):
            try:
                world = method(screen_pos, arg)
                if world is not None:
                    return clamp_world_point_to_plane(plane, _point3(world))
            except Exception:
                continue
        try:
            world = method(screen_pos)
            if world is not None:
                return clamp_world_point_to_plane(plane, _point3(world))
        except Exception:
            pass
    if event_world_pos is not None:
        return clamp_world_point_to_plane(plane, event_world_pos)
    return plane_to_world(plane, float(screen_pos[0]), float(screen_pos[1]))


def pick_plan_height(ctx: Any, screen_pos: Point2, *, event_world_pos: Point3 | None = None, view: FixedPlanarView | str | None = None) -> Plan2DPlanePick:
    """Pick the constant-depth plane used by a 2D drawing tool.

    The API first tries a face pick, then an object pick, then the event world
    point, then a fallback plane projection.  This keeps built-in and external
    tools from hand-writing inconsistent raycast fallbacks.
    """

    if view is None:
        view = nearest_plan_view(ctx)
    elif isinstance(view, FixedPlanarView):
        view = view
    else:
        view = FixedPlanarView(str(getattr(view, "value", view)))
    pick = None
    for picker_name in ("face_at", "object_at"):
        try:
            picker = getattr(getattr(ctx, "pick", None), picker_name, None)
            if callable(picker):
                candidate = picker(screen_pos)
                if getattr(candidate, "hit", False) and getattr(candidate, "world_pos", None) is not None:
                    pick = candidate
                    break
        except Exception:
            continue
    if pick is not None and getattr(pick, "world_pos", None) is not None:
        world = _point3(pick.world_pos)
    elif event_world_pos is not None:
        world = _point3(event_world_pos)
    else:
        base = make_locked_plane(view, depth=0.0)
        world = project_screen_to_locked_plane(ctx, screen_pos, base)
    plane = plane_from_first_hit(view, world)
    return Plan2DPlanePick(
        plane=plane,
        world_pos=clamp_world_point_to_plane(plane, world),
        view=view,
        object_id=None if pick is None else getattr(pick, "object_id", None),
        object_index=None if pick is None else getattr(pick, "object_index", None),
        hit_kind="none" if pick is None else str(getattr(pick, "kind", "point")),
    )


def pick_plan_anchor_by_raycast(
    ctx: Any,
    screen_pos: Point2,
    *,
    view: FixedPlanarView | str | None = None,
    fallback_depth: float = PLAN_TRACE_ANCHOR_FALLBACK_DEPTH,
    display_margin_world: float = PLAN_TRACE_DEFAULT_SURFACE_OFFSET,
    log_diagnostics: bool = False,
    diagnostics_label: str = "anchor",
) -> Plan2DAnchorPick:
    """Pick the Plan tracer anchor height using raycast hits only.

    This is the preferred API for Plan tracer-like tools.  The depth is derived
    from an actual face/object raycast so the 2D plan is anchored to the clicked
    surface.  If the raycast does not hit anything, the semantic depth falls back
    to ``0`` for the selected view.  The event world position is intentionally
    ignored here: a viewport fallback point must never masquerade as a part/face
    height.
    """

    if view is None:
        resolved_view = nearest_plan_view(ctx)
    elif isinstance(view, FixedPlanarView):
        resolved_view = view
    else:
        resolved_view = FixedPlanarView(str(getattr(view, "value", view)))

    pick, diagnostics = _pick_all_scene_parts_by_raycast(ctx, screen_pos)

    if pick is not None and getattr(pick, "world_pos", None) is not None:
        anchor_world = _point3(pick.world_pos)
        plane = plane_from_first_hit(resolved_view, anchor_world)
        hit = True
        diagnostics["result"] = "hit"
        diagnostics["depth"] = float(plane.depth)
    else:
        plane = make_locked_plane(resolved_view, depth=float(fallback_depth))
        hit = False
        diagnostics["result"] = "fallback"
        diagnostics["depth"] = float(plane.depth)
        try:
            projected = project_screen_to_locked_plane(ctx, screen_pos, plane, event_world_pos=None)
        except Exception:
            projected = plane_to_world(plane, float(screen_pos[0]), float(screen_pos[1]))
        anchor_world = clamp_world_point_to_plane(plane, projected)

    anchor_world = clamp_world_point_to_plane(plane, anchor_world)
    display_plane = plane.with_depth(float(plane.depth) + max(float(display_margin_world), 0.0))
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



def _pick_all_scene_parts_by_raycast(ctx: Any, screen_pos: Point2):
    """Return the first surface hit among all visible scene mesh actors.

    The public ``ctx.pick.face_at`` facade may be backed by a selected-object or
    viewport fallback implementation depending on the host.  Plan tracer anchor
    selection needs a stricter rule: cast against every scene part rendered in the
    3D view.  The VTK branch is attempted first when a real Studio window exists,
    then the facade is used as a headless/test fallback.
    """

    diagnostics: dict[str, Any] = {"backend": "none", "attempts": []}
    owner = getattr(ctx, "owner", None)
    vtk_pick = _pick_all_scene_parts_with_vtk(owner, screen_pos, diagnostics)
    if vtk_pick is not None:
        return vtk_pick, diagnostics

    facade = getattr(ctx, "pick", None)
    for picker_name in ("face_at", "object_at"):
        try:
            picker = getattr(facade, picker_name, None)
            if callable(picker):
                candidate = picker(screen_pos, all_parts=True, only_selected=False)
                diagnostics["attempts"].append({"backend": f"ctx.pick.{picker_name}", "hit": bool(getattr(candidate, "hit", False))})
                if getattr(candidate, "hit", False) and getattr(candidate, "world_pos", None) is not None:
                    diagnostics["backend"] = f"ctx.pick.{picker_name}"
                    return candidate, diagnostics
        except Exception as exc:
            diagnostics["attempts"].append({"backend": f"ctx.pick.{picker_name}", "error": type(exc).__name__})
            continue
    diagnostics["backend"] = "miss"
    return None, diagnostics


def _pick_all_scene_parts_with_vtk(owner: Any, screen_pos: Point2, diagnostics: dict[str, Any]):
    if owner is None:
        diagnostics["attempts"].append({"backend": "vtk", "skipped": "no_owner"})
        return None
    plotter = getattr(owner, "plotter", None)
    renderer = getattr(plotter, "renderer", None)
    actors_by_index = getattr(owner, "actors_by_index", None)
    if plotter is None or renderer is None or not isinstance(actors_by_index, dict) or not actors_by_index:
        diagnostics["attempts"].append({
            "backend": "vtk",
            "skipped": "missing_plotter_renderer_or_actors",
            "actors": 0 if not isinstance(actors_by_index, dict) else len(actors_by_index),
        })
        return None
    try:
        import vtk
        from laserprog_studio.tool_core.app_services import PickResult

        picker = vtk.vtkCellPicker()
        picker.SetTolerance(0.0015)
        picker.PickFromListOn()
        pick_list_count = 0
        for actor in actors_by_index.values():
            if actor is None:
                continue
            try:
                picker.AddPickList(actor)
                pick_list_count += 1
            except Exception:
                continue
        diagnostics["pick_list_count"] = pick_list_count
        if pick_list_count <= 0:
            diagnostics["attempts"].append({"backend": "vtk", "skipped": "empty_pick_list"})
            return None
        candidates = _qt_to_vtk_candidates(owner, screen_pos)
        for vx, vy, label in candidates:
            try:
                ok = bool(picker.Pick(int(vx), int(vy), 0, renderer))
                actor = picker.GetActor() or picker.GetViewProp()
                cell_id = int(picker.GetCellId())
                resolved = None
                resolver = getattr(owner, "_resolve_picked_actor", None)
                if callable(resolver):
                    resolved = resolver(actor)
                diagnostics["attempts"].append({
                    "backend": "vtk",
                    "candidate": label,
                    "vtk": (int(vx), int(vy)),
                    "ok": ok,
                    "cell_id": cell_id,
                    "resolved": resolved,
                })
                if not ok or cell_id < 0 or not resolved or resolved[0] != "mesh":
                    continue
                point = picker.GetPickPosition()
                try:
                    normal = tuple(float(v) for v in picker.GetPickNormal())
                except Exception:
                    normal = None
                idx = int(resolved[1])
                diagnostics["backend"] = "vtk_cell_picker_all_parts"
                diagnostics["candidate"] = label
                diagnostics["vtk"] = (int(vx), int(vy))
                diagnostics["cell_id"] = cell_id
                return PickResult(
                    "face",
                    screen_pos=screen_pos,
                    world_pos=_point3(point),
                    object_id=f"mesh:{idx}",
                    object_index=idx,
                    element_index=cell_id,
                    normal=normal,
                    metadata={"backend": "vtk_cell_picker_all_parts", "candidate": label, "pick_list_count": pick_list_count},
                )
            except Exception as exc:
                diagnostics["attempts"].append({"backend": "vtk", "candidate": label, "error": type(exc).__name__})
                continue
    except Exception as exc:
        diagnostics["attempts"].append({"backend": "vtk", "error": type(exc).__name__})
        return None
    return None


def _qt_to_vtk_candidates(owner: Any, screen_pos: Point2) -> list[tuple[int, int, str]]:
    qx, qy = float(screen_pos[0]), float(screen_pos[1])
    converter = getattr(owner, "_qt_to_vtk_candidates", None)
    if callable(converter):
        try:
            return [(int(x), int(y), str(label)) for x, y, label in converter(qx, qy)]
        except Exception:
            pass
    plotter = getattr(owner, "plotter", None)
    try:
        h = float(plotter.height())
        dpr = float(plotter.devicePixelRatioF()) if hasattr(plotter, "devicePixelRatioF") else 1.0
    except Exception:
        h, dpr = 0.0, 1.0
    base = [(int(round(qx)), int(round(h - qy)), "qt_no_dpr")]
    if abs(dpr - 1.0) > 0.01:
        base.append((int(round(qx * dpr)), int(round((h - qy) * dpr)), f"qt_dpr_{dpr:.2f}"))
    out = []
    for x, y, label in base:
        for dx, dy in ((0, 0), (3, 0), (-3, 0), (0, 3), (0, -3), (5, 5), (-5, -5)):
            out.append((max(0, x + dx), max(0, y + dy), label))
    return out


def _log_plan_trace_raycast(ctx: Any, label: str, diagnostics: dict[str, Any]) -> None:
    summary = (
        f"[PLAN_TRACE_RAYCAST] {label} result={diagnostics.get('result')} "
        f"backend={diagnostics.get('backend')} view={diagnostics.get('view')} "
        f"depth={diagnostics.get('depth')} display_depth={diagnostics.get('display_depth')} "
        f"object={diagnostics.get('object_id') or diagnostics.get('object_index')} "
        f"pick_list={diagnostics.get('pick_list_count', '?')} attempts={len(diagnostics.get('attempts') or [])}"
    )
    logged = False
    for target in (getattr(ctx, "owner", None), getattr(ctx, "scene", None), ctx):
        logger = getattr(target, "ui_log", None)
        if callable(logger):
            try:
                logger(summary)
                logged = True
                break
            except Exception:
                pass
    if not logged:
        try:
            from laserprog_studio.studio_log import log

            log(summary)
        except Exception:
            pass



def world_to_plan_xy(plane: LockedPlaneSpec, world_pos: Point3) -> Point2:
    """Project a world-space point into a locked plan local XY frame.

    Plan-like tools should use this public facade instead of importing
    ``planar_tools.world_to_plane`` directly.  The facade keeps semantic
    sketch coordinates and display-plane UI coordinates under the same API
    boundary as the rest of Plan Tracer placement.
    """

    return tuple(float(v) for v in world_to_plane(plane, world_pos))


def plan_xy_to_world(plane: LockedPlaneSpec, xy: Point2) -> Point3:
    """Convert a locked-plan XY coordinate back to semantic world space."""

    return tuple(float(v) for v in plane_to_world(plane, float(xy[0]), float(xy[1])))

def display_point_for_plan_world(plane: LockedPlaneSpec, display_plane: LockedPlaneSpec, world_pos: Point3) -> Point3:
    """Return the visible UI position for a semantic point on a locked plan."""

    clamped = clamp_world_point_to_plane(plane, world_pos)
    u, v = world_to_plan_xy(plane, clamped)
    return plan_xy_to_world(display_plane, (u, v))


def semantic_point_for_display_world(plane: LockedPlaneSpec, display_plane: LockedPlaneSpec, display_world_pos: Point3) -> Point3:
    """Return the semantic construction point for a visible UI point."""

    clamped = clamp_world_point_to_plane(display_plane, display_world_pos)
    u, v = world_to_plan_xy(display_plane, clamped)
    return plan_xy_to_world(plane, (u, v))



def offset_plan_height_pick_for_visibility(pick: Plan2DPlanePick, *, margin_world: float = PLAN_TRACE_DEFAULT_SURFACE_OFFSET) -> Plan2DPlanePick:
    """Move a picked drawing plane slightly toward the locked camera view.

    Plan tracer starts by raycasting a visible part/face.  Drawing exactly on
    that surface can make the official Creator UI motifs z-fight with the part
    or sit inside the volume.  The API therefore owns the small display offset:
    tools receive an already-visible drawing plane and should not invent their
    own surface margins.

    The fixed planar view normal is defined toward the corresponding camera, so
    increasing the plane depth by ``margin_world`` moves the 2D drawing plane
    toward the viewer for `top`, `front`, `left`, etc.
    """

    margin = max(float(margin_world), 0.0)
    if margin <= 0.0:
        return pick
    plane = pick.plane.with_depth(float(pick.plane.depth) + margin)
    world = clamp_world_point_to_plane(plane, pick.world_pos)
    return replace(pick, plane=plane, world_pos=world)


def sample_plan_arc_xy(start: Point2, end: Point2, control: Point2, *, segments: int = 24) -> tuple[Point2, ...]:
    """Sample a circular arc in locked-plane local coordinates.

    Built-in sketch tools use this public facade when they need a display
    preview from semantic sketch points.  The lower-level curve kernel remains
    private to ``tool_core.geometry``.
    """

    from laserprog_studio.tool_core.geometry import sample_circular_arc_through_points

    return tuple(
        (float(x), float(y))
        for x, y in sample_circular_arc_through_points(
            (float(start[0]), float(start[1])),
            (float(end[0]), float(end[1])),
            (float(control[0]), float(control[1])),
            segments=max(4, int(segments)),
        )
    )

def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))

@dataclass(frozen=True, slots=True)
class Plan2DCoordinateMapper:
    """Canonical semantic/display/sketch mapper for a locked Plan 2D surface.

    ``plane`` is the semantic construction plane. ``display_plane`` is the same
    plane offset toward the camera for UI motifs.  Tools should pass this mapper
    around instead of depending on a snap service to perform conversions.
    """

    plane: LockedPlaneSpec
    display_plane: LockedPlaneSpec | None = None

    @classmethod
    def from_anchor(cls, anchor: Plan2DAnchorPick) -> "Plan2DCoordinateMapper":
        return cls(anchor.plane, anchor.display_plane)

    @property
    def resolved_display_plane(self) -> LockedPlaneSpec:
        return self.display_plane or self.plane

    def world_to_sketch_xy(self, world_pos: Point3) -> Point2:
        return world_to_plan_xy(self.plane, world_pos)

    def sketch_xy_to_world(self, xy: Point2) -> Point3:
        return plan_xy_to_world(self.plane, xy)

    def sketch_xy_to_display_world(self, xy: Point2) -> Point3:
        return plan_xy_to_world(self.resolved_display_plane, xy)

    def display_world_to_sketch_xy(self, display_world_pos: Point3) -> Point2:
        return world_to_plan_xy(self.resolved_display_plane, display_world_pos)

    def semantic_to_display_world(self, world_pos: Point3) -> Point3:
        return display_point_for_plan_world(self.plane, self.resolved_display_plane, world_pos)

    def display_to_semantic_world(self, display_world_pos: Point3) -> Point3:
        return semantic_point_for_display_world(self.plane, self.resolved_display_plane, display_world_pos)

    def sample_arc_display_points(self, start_xy: Point2, end_xy: Point2, control_xy: Point2, *, segments: int = 24) -> tuple[Point3, ...]:
        return tuple(self.sketch_xy_to_display_world(xy) for xy in sample_plan_arc_xy(start_xy, end_xy, control_xy, segments=segments))


def create_coordinate_mapper(anchor_or_plane: Plan2DAnchorPick | LockedPlaneSpec, display_plane: LockedPlaneSpec | None = None) -> Plan2DCoordinateMapper:
    """Create the canonical Plan 2D coordinate mapper from an anchor pick or planes."""

    if isinstance(anchor_or_plane, Plan2DAnchorPick):
        return Plan2DCoordinateMapper.from_anchor(anchor_or_plane)
    return Plan2DCoordinateMapper(anchor_or_plane, display_plane)


__all__ = [
    "FixedPlanarView",
    "LockedPlaneSpec",
    "PLAN_TRACE_DEFAULT_SURFACE_OFFSET",
    "PLAN_TRACE_ANCHOR_FALLBACK_DEPTH",
    "Plan2DPhase",
    "Plan2DPlanePick",
    "Plan2DAnchorPick",
    "Plan2DStateSummary",
    "Plan2DTool",
    "Plan2DCoordinateMapper",
    "create_coordinate_mapper",
    "display_point_for_plan_world",
    "lock_camera_to_plan_view",
    "release_plan_view_camera",
    "nearest_plan_view",
    "normalize_plan_tool",
    "offset_plan_height_pick_for_visibility",
    "pick_plan_anchor_by_raycast",
    "pick_plan_height",
    "plan_xy_to_world",
    "project_screen_to_locked_plane",
    "sample_plan_arc_xy",
    "semantic_point_for_display_world",
    "world_to_plan_xy",
]
