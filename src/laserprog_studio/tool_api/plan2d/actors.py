"""Public Plan 2D declarations backed by Projected Drawing 2D.

Plan tools declare semantic geometry here.  The module stores both the visible
screen-space primitive and its Tool Core selection actor in the single
``ctx.projected_drawing`` registry; it never mirrors content through the legacy
``ctx.preview`` / ``ctx.gizmos`` APIs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, pi, sin, sqrt
from typing import Any, Iterable

from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api.styles import (
    InteractionVisualState,
    LineStyleId,
    PointStyleId,
    line_style,
    point_style,
)
from laserprog_studio.tool_api.ui_motifs import API_UI_VISIBLE_METADATA_KEY
from laserprog_studio.tool_core.selection import ToolActor
from laserprog_studio.tool_core.snap.types import SnapKind, snap_label_for_kind

from .snap import PLAN_2D_SNAP_CURSOR_STYLES, snap_cursor_style_for_kind

Point3 = tuple[float, float, float]

PLAN_TRACE_MOTIF_FAMILY = "plan_trace_2d"
PLAN_TRACE_CURSOR_ROLE = "cursor"
PLAN_TRACE_POINT_ROLE = "point"
PLAN_TRACE_EDGE_ROLE = "edge"
PLAN_TRACE_FACE_ROLE = "face"
PLAN_TRACE_CIRCLE_ROLE = "circle"
PLAN_TRACE_ARC_ROLE = "arc"
PLAN_TRACE_DIMENSION_ROLE = "dimension"
PLAN_TRACE_ANCHOR_ROLE = "height_anchor"


@dataclass(frozen=True, slots=True)
class Plan2DPoint:
    """One placed point in a locked 2D plan."""

    id: str
    world_pos: Point3


def plan_point_actor_metadata(
    *,
    role: str = PLAN_TRACE_POINT_ROLE,
    point_style: str = PointStyleId.MINIMAL.value,
    base_radius_px: int = 5,
) -> dict[str, Any]:
    """Metadata shared by projected Plan Tracer handles and selection actors."""

    return {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "handle",
        "plan_trace_role": str(role),
        "point_style": str(point_style),
        "line_style": LineStyleId.GRABBABLE.value,
        "visual_state": InteractionVisualState.AUTO.value,
        "base_radius_px": int(base_radius_px),
        "kind_suffix": str(role),
        "selection_priority": 100 if str(role) == PLAN_TRACE_POINT_ROLE else 0,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
    }


def _registry(ctx: Any, owner_tool: str):
    return ctx.projected_drawing.for_tool(owner_tool)


def _register(ctx: Any, owner_tool: str, primitive: Any) -> ToolActor:
    _registry(ctx, owner_tool).add(primitive, replace=True, render=False)
    actor = ctx.selection.actor(str(primitive.id))
    if actor is None:
        raise RuntimeError(f"Projected primitive {primitive.id!r} did not create a selection actor.")
    return actor


def _rgba_hex(value: Iterable[float]) -> str:
    rgba = tuple(float(component) for component in value)
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(component * 255.0))) for component in rgba[:3])


def _rgba_alpha(value: Iterable[float]) -> float:
    rgba = tuple(float(component) for component in value)
    return max(0.0, min(1.0, rgba[3] if len(rgba) >= 4 else 1.0))


def _line_visual(style_id: str) -> tuple[str, float, float]:
    style = line_style(style_id)
    return (str(style.color), float(style.width_px), float(style.opacity))


def _handle(
    handle_id: str,
    position: Point3,
    *,
    metadata: dict[str, Any],
    point_style_id: str,
    interaction: str,
    base_radius_px: int,
    visible: bool = True,
    direction: Point3 = (1.0, 0.0, 0.0),
    constraint: str = "plane_xy",
) -> Any:
    style = point_style(point_style_id)
    idle_state = "grabbable" if interaction == "grabbable" else "fixed"
    normal = style.color_for(idle_state)
    hover = style.color_for("hover")
    selected = style.color_for("selected")
    grabbed = style.color_for("grabbed")
    disabled = style.color_for("disabled")
    size_px = 4.0 if point_style_id == PointStyleId.MINIMAL.value else float(max(6, int(base_radius_px) * 2))
    return draw2d.handle(
        handle_id,
        position,
        shape=point_style_id,
        direction=direction,
        size_px=size_px,
        line_width_px=2.0,
        color=_rgba_hex(normal),
        hover_color=_rgba_hex(hover),
        selected_color=_rgba_hex(selected),
        grabbed_color=_rgba_hex(grabbed),
        disabled_color=_rgba_hex(disabled),
        opacity=_rgba_alpha(normal),
        visible=visible,
        interaction=interaction,
        constraint=constraint,
        hit_radius_px=max(1.0, float(metadata.get("hit_radius_px", base_radius_px + 7))),
        metadata=metadata,
    )


def register_plan_point(
    ctx: Any,
    *,
    owner_tool: str,
    point_id: str,
    world_pos: Point3,
    grabbable: bool = True,
    semantic_world_pos: Point3 | None = None,
) -> ToolActor:
    """Register a placed plan point as one projected minimal-dot handle."""

    metadata = plan_point_actor_metadata(role=PLAN_TRACE_POINT_ROLE, point_style=PointStyleId.MINIMAL.value, base_radius_px=2)
    metadata["hit_radius_px"] = 12.0
    if semantic_world_pos is not None:
        metadata["plan_trace_semantic_world_pos"] = tuple(float(v) for v in semantic_world_pos)
    primitive = _handle(
        point_id,
        _point3(world_pos),
        metadata=metadata,
        point_style_id=PointStyleId.MINIMAL.value,
        interaction="grabbable" if grabbable else "selectable",
        base_radius_px=2,
    )
    return _register(ctx, owner_tool, primitive)


def register_plan_line(
    ctx: Any,
    *,
    owner_tool: str,
    line_id: str,
    start_world_pos: Point3,
    end_world_pos: Point3,
    selectable: bool = True,
    sketch_line_id: str | None = None,
) -> ToolActor:
    """Register or update one selectable projected sketch edge."""

    style_id = LineStyleId.GRABBABLE.value if selectable else LineStyleId.FIXED.value
    color, width, opacity = _line_visual(style_id)
    metadata = {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "line",
        "plan_trace_role": PLAN_TRACE_EDGE_ROLE,
        "line_style": style_id,
        "visual_state": InteractionVisualState.AUTO.value,
        "kind_suffix": PLAN_TRACE_EDGE_ROLE,
        "selection_priority": 70,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
        "projected_base_line_style": (color, width, opacity),
    }
    if sketch_line_id is not None:
        metadata["plan_trace_sketch_line_id"] = str(sketch_line_id)
    primitive = draw2d.line(
        line_id,
        _point3(start_world_pos),
        _point3(end_world_pos),
        color=color,
        width_px=width,
        opacity=opacity,
        interaction="selectable" if selectable else "fixed",
        hit_radius_px=10.0,
        metadata=metadata,
    )
    return _register(ctx, owner_tool, primitive)


def register_plan_circle(
    ctx: Any,
    *,
    owner_tool: str,
    circle_id: str,
    center_world_pos: Point3,
    radius_world_pos: Point3,
    selectable: bool = True,
    sketch_circle_id: str | None = None,
    basis_u: Point3 | None = None,
    basis_v: Point3 | None = None,
    samples: int = 64,
) -> ToolActor:
    """Register a circle sampled in the locked drawing plane."""

    center = _point3(center_world_pos)
    radius_point = _point3(radius_world_pos)
    radius = sqrt(sum((radius_point[index] - center[index]) ** 2 for index in range(3)))
    radius = max(radius, 1.0e-9)
    u = _normalize_vec3(basis_u or (1.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    v = _orthogonalize_vec3(basis_v or (0.0, 1.0, 0.0), u, (0.0, 1.0, 0.0))
    sample_count = max(16, int(samples))
    curve_points = tuple(
        (
            center[0] + radius * (cos(2.0 * pi * index / sample_count) * u[0] + sin(2.0 * pi * index / sample_count) * v[0]),
            center[1] + radius * (cos(2.0 * pi * index / sample_count) * u[1] + sin(2.0 * pi * index / sample_count) * v[1]),
            center[2] + radius * (cos(2.0 * pi * index / sample_count) * u[2] + sin(2.0 * pi * index / sample_count) * v[2]),
        )
        for index in range(sample_count)
    )
    style_id = LineStyleId.GRABBABLE.value if selectable else LineStyleId.FIXED.value
    color, width, opacity = _line_visual(style_id)
    metadata = {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "circle",
        "plan_trace_role": PLAN_TRACE_CIRCLE_ROLE,
        "line_style": style_id,
        "visual_state": InteractionVisualState.AUTO.value,
        "kind_suffix": PLAN_TRACE_CIRCLE_ROLE,
        "curve_type": "circle",
        "circle_hit_points": (center, radius_point),
        "selection_priority": 68,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
        "projected_base_line_style": (color, width, opacity),
    }
    if sketch_circle_id is not None:
        metadata["plan_trace_sketch_circle_id"] = str(sketch_circle_id)
    primitive = draw2d.polyline(
        circle_id,
        curve_points,
        closed=True,
        actor_kind="circle",
        color=color,
        width_px=width,
        opacity=opacity,
        interaction="selectable" if selectable else "fixed",
        hit_radius_px=10.0,
        metadata=metadata,
    )
    return _register(ctx, owner_tool, primitive)


def register_plan_arc(
    ctx: Any,
    *,
    owner_tool: str,
    arc_id: str,
    start_world_pos: Point3,
    end_world_pos: Point3,
    control_world_pos: Point3,
    selectable: bool = True,
    sketch_arc_id: str | None = None,
    samples: int = 32,
) -> ToolActor:
    """Register a sampled circular arc in Projected Drawing 2D."""

    curve_points = _sample_circular_arc_world(
        _point3(start_world_pos),
        _point3(end_world_pos),
        _point3(control_world_pos),
        samples=max(8, int(samples)),
    )
    style_id = LineStyleId.GRABBABLE.value if selectable else LineStyleId.FIXED.value
    color, width, opacity = _line_visual(style_id)
    metadata = {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "arc",
        "plan_trace_role": PLAN_TRACE_ARC_ROLE,
        "line_style": style_id,
        "visual_state": InteractionVisualState.AUTO.value,
        "kind_suffix": PLAN_TRACE_ARC_ROLE,
        "curve_type": "arc",
        "selection_priority": 68,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
        "projected_base_line_style": (color, width, opacity),
    }
    if sketch_arc_id is not None:
        metadata["plan_trace_sketch_arc_id"] = str(sketch_arc_id)
    primitive = draw2d.arc(
        arc_id,
        curve_points,
        color=color,
        width_px=width,
        opacity=opacity,
        interaction="selectable" if selectable else "fixed",
        hit_radius_px=10.0,
        metadata=metadata,
    )
    return _register(ctx, owner_tool, primitive)



def register_plan_bezier(
    ctx: Any,
    *,
    owner_tool: str,
    bezier_id: str,
    start_world_pos: Point3,
    end_world_pos: Point3,
    control_1_world_pos: Point3,
    control_2_world_pos: Point3,
    selectable: bool = True,
    sketch_bezier_id: str | None = None,
    samples: int = 48,
) -> ToolActor:
    """Register a selectable cubic Bézier curve in Projected Drawing 2D."""

    curve_points = _sample_cubic_bezier_world(
        _point3(start_world_pos),
        _point3(control_1_world_pos),
        _point3(control_2_world_pos),
        _point3(end_world_pos),
        samples=max(12, int(samples)),
    )
    style_id = LineStyleId.GRABBABLE.value if selectable else LineStyleId.FIXED.value
    color, width, opacity = _line_visual(style_id)
    metadata = {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "bezier",
        "plan_trace_role": PLAN_TRACE_ARC_ROLE,
        "line_style": style_id,
        "visual_state": InteractionVisualState.AUTO.value,
        "kind_suffix": PLAN_TRACE_ARC_ROLE,
        "curve_type": "bezier",
        "selection_priority": 68,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
        "projected_base_line_style": (color, width, opacity),
    }
    if sketch_bezier_id is not None:
        metadata["plan_trace_sketch_bezier_id"] = str(sketch_bezier_id)
    primitive = draw2d.arc(
        bezier_id,
        curve_points,
        color=color,
        width_px=width,
        opacity=opacity,
        interaction="selectable" if selectable else "fixed",
        hit_radius_px=10.0,
        metadata=metadata,
    )
    return _register(ctx, owner_tool, primitive)

def register_plan_face(
    ctx: Any,
    *,
    owner_tool: str,
    face_id: str,
    polygon_world_points: Iterable[Point3],
    hole_world_polygons: Iterable[Iterable[Point3]] = (),
    selectable: bool = True,
    sketch_face_id: str | None = None,
) -> ToolActor:
    """Register a selectable projected face, including all hole rings."""

    points = tuple(_point3(point) for point in polygon_world_points)
    holes = tuple(tuple(_point3(point) for point in polygon) for polygon in hole_world_polygons)
    base_style = ("#80B7DA", 0.26, "#2563eb", 3.0, 0.85)
    metadata = {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "face",
        "plan_trace_role": PLAN_TRACE_FACE_ROLE,
        "line_style": LineStyleId.PREVIEW.value,
        "visual_state": InteractionVisualState.AUTO.value,
        "kind_suffix": PLAN_TRACE_FACE_ROLE,
        "filled_polygon_hit": True,
        "filled_polygon_holes": holes,
        "has_holes": bool(holes),
        "hole_count": len(holes),
        "selection_priority": 10,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
        "projected_base_face_style": base_style,
    }
    if sketch_face_id is not None:
        metadata["plan_trace_sketch_face_id"] = str(sketch_face_id)
    primitive = draw2d.face(
        face_id,
        points,
        holes=holes,
        fill_color=base_style[0],
        fill_opacity=base_style[1],
        outline_color=base_style[2],
        outline_width_px=base_style[3],
        outline_opacity=base_style[4],
        interaction="selectable" if selectable else "fixed",
        hit_radius_px=64.0,
        metadata=metadata,
    )
    return _register(ctx, owner_tool, primitive)


def register_plan_dimension(
    ctx: Any,
    *,
    owner_tool: str,
    dimension_id: str,
    dimension_world_line: tuple[Point3, Point3],
    witness_world_lines: Iterable[tuple[Point3, Point3]] = (),
    label_world_pos: Point3,
    label: str,
    selectable: bool = True,
    sketch_dimension_id: str | None = None,
) -> ToolActor:
    """Register a dimension line, witness lines and persistent label."""

    p1, p2 = (_point3(dimension_world_line[0]), _point3(dimension_world_line[1]))
    label_pos = _point3(label_world_pos)
    color, width, opacity = _line_visual(LineStyleId.CONSTRUCTION.value)
    metadata = {
        "motif_family": PLAN_TRACE_MOTIF_FAMILY,
        "motif_kind": "dimension",
        "plan_trace_role": PLAN_TRACE_DIMENSION_ROLE,
        "line_style": LineStyleId.CONSTRUCTION.value,
        "visual_state": InteractionVisualState.AUTO.value,
        "kind_suffix": PLAN_TRACE_DIMENSION_ROLE,
        "dimension_label": str(label),
        "selection_priority": 60,
        API_UI_VISIBLE_METADATA_KEY: True,
        "projected_drawing_only": True,
        "projected_base_line_style": (color, width, opacity),
    }
    if sketch_dimension_id is not None:
        metadata["plan_trace_sketch_dimension_id"] = str(sketch_dimension_id)
    main = draw2d.line(
        dimension_id,
        p1,
        p2,
        color=color,
        width_px=width,
        opacity=opacity,
        interaction="selectable" if selectable else "fixed",
        hit_radius_px=12.0,
        metadata=metadata,
    )
    guide_color, guide_width, guide_opacity = _line_visual(LineStyleId.GUIDE.value)
    extras: list[Any] = []
    for index, (w1, w2) in enumerate(tuple(witness_world_lines)):
        extras.append(
            draw2d.line(
                f"{dimension_id}:witness:{index}",
                _point3(w1),
                _point3(w2),
                color=guide_color,
                width_px=guide_width,
                opacity=guide_opacity,
                interaction="fixed",
                metadata={
                    "plan_trace_role": "dimension_witness",
                    "projected_drawing_only": True,
                    "projected_no_selection_actor": True,
                },
            )
        )
    extras.append(
        draw2d.text(
            f"{dimension_id}:label",
            str(label),
            label_pos,
            # Deep cyan-blue stays consistent with LaserProg's accent while
            # remaining highly legible on the white Plan Tracer workspace.
            color="#075985",
            size_px=14,
            bold=True,
            anchor="center",
            layer=64,
            metadata={
                "plan_trace_role": "dimension_label",
                "projected_drawing_only": True,
                "projected_no_selection_actor": True,
                # The subtle cyan badge prevents geometry or a bright surface
                # from washing the measurement out without looking like a
                # detached dialog label.  These keys are renderer-neutral and
                # ignored by backends which do not support text decoration.
                "text_background_color": "#E0F2FE",
                "text_background_opacity": 0.90,
                "text_frame_color": "#38BDF8",
                "text_frame_width": 1,
                "text_frame": True,
            },
        )
    )
    registry = _registry(ctx, owner_tool)
    stale = tuple(
        primitive.id
        for primitive in registry.items()
        if str(primitive.id).startswith(f"{dimension_id}:witness:") or str(primitive.id) == f"{dimension_id}:label"
    )
    if stale:
        registry.remove_many(stale, render=False)
    registry.add_many((main, *extras), replace=True, render=False)
    actor = ctx.selection.actor(dimension_id)
    if actor is None:
        raise RuntimeError(f"Projected dimension {dimension_id!r} did not create a selection actor.")
    return actor


def register_plan_cursor(
    ctx: Any,
    *,
    owner_tool: str,
    cursor_id: str,
    world_pos: Point3,
    visible: bool = True,
    snap_kind: SnapKind | str | None = None,
    snap_label: str | None = None,
    snapped: bool | None = None,
) -> ToolActor:
    """Register the official projected Plan 2D snap cursor."""

    kind = str(snap_kind.value if isinstance(snap_kind, SnapKind) else snap_kind or SnapKind.FREE.value).strip().lower().replace("-", "_")
    if kind not in PLAN_2D_SNAP_CURSOR_STYLES:
        kind = SnapKind.FREE.value
    style = snap_cursor_style_for_kind(kind)
    label = str(snap_label or style.label or snap_label_for_kind(kind))
    metadata = plan_point_actor_metadata(role=PLAN_TRACE_CURSOR_ROLE, point_style=style.point_style, base_radius_px=style.base_radius_px)
    metadata.update(
        {
            API_UI_VISIBLE_METADATA_KEY: bool(visible),
            "snap_kind": kind,
            "snap_label": label,
            "snap_show_label": bool(style.show_label and (snapped if snapped is not None else kind != SnapKind.FREE.value)),
            "point_style": style.point_style,
            "line_style": style.line_style,
            "visual_state": style.visual_state,
            "base_radius_px": int(style.base_radius_px),
            "hit_radius_px": 1.0,
        }
    )
    primitive = _handle(
        cursor_id,
        _point3(world_pos),
        metadata=metadata,
        point_style_id=style.point_style,
        interaction="fixed",
        base_radius_px=int(style.base_radius_px),
        visible=visible,
    )
    registry = _registry(ctx, owner_tool)
    existing = registry.get(cursor_id)
    if existing is not None:
        try:
            same_visual_recipe = replace(existing, position=primitive.position) == primitive
        except Exception:
            same_visual_recipe = False
        if same_visual_recipe:
            registry.update_positions(
                {cursor_id: primitive.position},
                render=False,
                sync_selection=False,
            )
            actor = ctx.selection.actor(str(cursor_id))
            if actor is not None:
                # Keep the hit-test/selection actor in lockstep with the live
                # projected handle without routing the move back through the
                # whole projected-selection bridge.  The cursor is a fixed,
                # single-point actor, so this is the complete semantic delta.
                updated_actor = replace(actor, points=(primitive.position,))
                ctx.selection.update_actor(updated_actor)
                return updated_actor
    return _register(ctx, owner_tool, primitive)


def register_plan_anchor_target(
    ctx: Any,
    *,
    owner_tool: str,
    target_id: str,
    world_pos: Point3,
    visible: bool = True,
) -> ToolActor:
    """Register the projected fixed height anchor target."""

    metadata = plan_point_actor_metadata(role=PLAN_TRACE_ANCHOR_ROLE, point_style=PointStyleId.TARGET.value, base_radius_px=16)
    metadata[API_UI_VISIBLE_METADATA_KEY] = bool(visible)
    metadata["hit_radius_px"] = 1.0
    primitive = _handle(
        target_id,
        _point3(world_pos),
        metadata=metadata,
        point_style_id=PointStyleId.TARGET.value,
        interaction="fixed",
        base_radius_px=16,
        visible=visible,
    )
    return _register(ctx, owner_tool, primitive)


def mark_plan_actor_visuals_dirty(
    ctx: Any,
    *,
    owner_tool: str,
    changed_actor_ids: Iterable[str] | None = None,
    extra_preview_ids: Iterable[str] | None = None,
) -> tuple[str, ...]:
    """Bridge Plan2D/ProjectedDrawing updates into the native drag runtime.

    Native Creator drags collect ``selection.state.dirty_visual_*`` immediately
    after a tool-specific drag resolver runs.  ProjectedDrawing updates can
    already have refreshed the declarative registry at that point, so a resolver
    may leave no raw ToolActor delta for ``move_actors_to`` to detect.  Marking
    the changed Plan2D ids here makes the runtime issue the single live render
    for the current mouse frame instead of waiting for release.
    """

    changed = tuple(dict.fromkeys(str(value) for value in changed_actor_ids or ()))
    preview = tuple(dict.fromkeys(str(value) for value in extra_preview_ids or ()))
    state = getattr(getattr(ctx, "selection", None), "state", None)
    if state is None:
        return changed
    try:
        handle_ids: list[str] = []
        owner = str(owner_tool)
        for actor_id in changed:
            actor = ctx.selection.actor(actor_id)
            if actor is not None and getattr(actor, "owner_tool", None) == owner:
                handle_ids.append(actor_id)
        if handle_ids:
            current = tuple(getattr(state, "dirty_visual_handle_ids", ()) or ())
            state.dirty_visual_handle_ids = tuple(dict.fromkeys((*current, *handle_ids)))
        if preview:
            current_preview = tuple(getattr(state, "dirty_visual_preview_ids", ()) or ())
            state.dirty_visual_preview_ids = tuple(dict.fromkeys((*current_preview, *preview)))
        profiler = getattr(ctx, "profiler", None)
        if profiler is not None and (handle_ids or preview):
            profiler.increment("plan2d.actor_visuals.dirty_bridge", len(handle_ids) + len(preview))
            profiler.set_value("plan2d.actor_visuals.dirty_bridge_handles_last", len(handle_ids))
            profiler.set_value("plan2d.actor_visuals.dirty_bridge_previews_last", len(preview))
    except Exception:
        pass
    return changed


def sync_plan_actor_visuals(
    ctx: Any,
    *,
    owner_tool: str,
    changed_actor_ids: Iterable[str] | None = None,
    extra_preview_ids: Iterable[str] | None = None,
    position_only: bool = False,
    render: bool = True,
) -> None:
    """Synchronise Projected Drawing geometry and native interaction feedback."""

    import time

    changed = mark_plan_actor_visuals_dirty(
        ctx,
        owner_tool=owner_tool,
        changed_actor_ids=changed_actor_ids,
        extra_preview_ids=extra_preview_ids,
    )
    profiler = getattr(ctx, "profiler", None)
    started = time.perf_counter()
    path_name = "fast_drag" if position_only and changed else "full_interaction"
    registry = _registry(ctx, owner_tool)
    try:
        if position_only:
            if changed:
                registry.sync_moved_actors(changed, render=False)
        else:
            registry.sync_interaction_state(render=False)
        registry.render(render=render)
    finally:
        try:
            if profiler is not None:
                profiler.record_timing(
                    f"plan2d.actor_visuals.{path_name}",
                    (time.perf_counter() - started) * 1000.0,
                    details={"changed": len(changed), "render": bool(render), "projected": True},
                )
                profiler.increment(f"plan2d.actor_visuals.{path_name}.calls", 1)
                profiler.set_value("plan2d.actor_visuals.changed_last", len(changed))
                profiler.set_value("plan2d.actor_visuals.position_only_last", int(bool(position_only)))
        except Exception:
            pass


def hide_plan_cursor(ctx: Any, *, owner_tool: str, cursor_id: str, render: bool = True) -> None:
    """Hide the projected plan cursor without deleting placed points."""

    _registry(ctx, owner_tool).hide(cursor_id, render=render)



def _sample_cubic_bezier_world(
    start: Point3,
    control_1: Point3,
    control_2: Point3,
    end: Point3,
    *,
    samples: int = 48,
) -> tuple[Point3, ...]:
    count = max(8, int(samples))
    out: list[Point3] = []
    for index in range(count + 1):
        t = index / count
        omt = 1.0 - t
        out.append(tuple(
            omt * omt * omt * start[axis]
            + 3.0 * omt * omt * t * control_1[axis]
            + 3.0 * omt * t * t * control_2[axis]
            + t * t * t * end[axis]
            for axis in range(3)
        ))
    out[0] = start
    out[-1] = end
    return tuple(out)

def _sample_circular_arc_world(start: Point3, end: Point3, control: Point3, *, samples: int = 32) -> tuple[Point3, ...]:
    from laserprog_studio.tool_core.geometry import sample_circular_arc_through_points

    chord = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    u = _normalize_vec3(chord, (1.0, 0.0, 0.0))
    ctrl = (control[0] - start[0], control[1] - start[1], control[2] - start[2])
    normal = _cross_vec3(chord, ctrl)
    n = _normalize_vec3(normal, (0.0, 0.0, 1.0))
    v = _normalize_vec3(_cross_vec3(n, u), (0.0, 1.0, 0.0))
    end_2d = (_dot_vec3(chord, u), _dot_vec3(chord, v))
    control_2d = (_dot_vec3(ctrl, u), _dot_vec3(ctrl, v))
    sampled = sample_circular_arc_through_points((0.0, 0.0), end_2d, control_2d, segments=max(4, int(samples)))
    return tuple(
        (
            start[0] + x * u[0] + y * v[0],
            start[1] + x * u[1] + y * v[1],
            start[2] + x * u[2] + y * v[2],
        )
        for x, y in sampled
    )


def _dot_vec3(a: Point3, b: Point3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross_vec3(a: Point3, b: Point3) -> Point3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _normalize_vec3(value: Point3, fallback: Point3) -> Point3:
    length = sqrt(float(value[0]) ** 2 + float(value[1]) ** 2 + float(value[2]) ** 2)
    if length <= 1.0e-12:
        return fallback
    return (float(value[0]) / length, float(value[1]) / length, float(value[2]) / length)


def _orthogonalize_vec3(value: Point3, basis: Point3, fallback: Point3) -> Point3:
    dot = float(value[0]) * basis[0] + float(value[1]) * basis[1] + float(value[2]) * basis[2]
    candidate = (
        float(value[0]) - dot * basis[0],
        float(value[1]) - dot * basis[1],
        float(value[2]) - dot * basis[2],
    )
    return _normalize_vec3(candidate, fallback)


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


__all__ = [
    "PLAN_TRACE_ANCHOR_ROLE",
    "PLAN_TRACE_ARC_ROLE",
    "PLAN_TRACE_CIRCLE_ROLE",
    "PLAN_TRACE_CURSOR_ROLE",
    "PLAN_TRACE_DIMENSION_ROLE",
    "PLAN_TRACE_EDGE_ROLE",
    "PLAN_TRACE_FACE_ROLE",
    "PLAN_TRACE_MOTIF_FAMILY",
    "PLAN_TRACE_POINT_ROLE",
    "Plan2DPoint",
    "hide_plan_cursor",
    "plan_point_actor_metadata",
    "register_plan_anchor_target",
    "register_plan_arc",
    "register_plan_bezier",
    "register_plan_circle",
    "register_plan_cursor",
    "register_plan_dimension",
    "register_plan_face",
    "register_plan_line",
    "register_plan_point",
    "mark_plan_actor_visuals_dirty",
    "sync_plan_actor_visuals",
]
