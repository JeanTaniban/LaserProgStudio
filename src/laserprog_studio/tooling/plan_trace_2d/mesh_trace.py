# -*- coding: utf-8 -*-
"""Smart tracing of existing scene meshes into the active Plan Tracer plane.

The source selection/prediction engine is shared with Cloth.  This adapter adds
one important Plan Tracer contract: every selected 3D vertex is orthogonally
projected onto the currently locked semantic drawing plane before sketch
entities are created.  Source meshes can therefore live on another depth,
orientation or principal axis without introducing non-planar sketch geometry.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Any, Iterable, Sequence

from laserprog_studio.planar_tools import plane_to_world, world_to_plane
from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api import visual
from laserprog_studio.tool_api.core import MouseButton, ToolEventType
from laserprog_studio.tooling.cloth.geometry_trace import (
    ClothGeometryTraceController,
    SourceEdgeSelection,
    boundary_edges,
)

from .constants import _MODE_MODIFY
from .services import _PlanTrace2DService

PLAN_TRACE_MESH_TRACE_WINDOW_ID = "plan_trace_2d.mesh_trace"
PLAN_TRACE_MESH_TRACE_ACTION_PREFIX = "plan_trace_2d.mesh_trace.action."
_PICK_GROUP = "plan_trace_2d.mesh_trace.pick_kind"
_VISUAL_PREFIX = "plan_trace_2d:mesh_trace:"

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ProjectedTracePlan:
    segments: tuple[tuple[Point2, Point2], ...]
    source_edge_count: int
    collapsed_edge_count: int
    duplicate_edge_count: int
    maximum_projection_distance: float

    @property
    def can_create(self) -> bool:
        return bool(self.segments)


@dataclass(frozen=True, slots=True)
class PlanTraceMeshTraceOutcome:
    committed: bool
    created_line_ids: tuple[str, ...] = ()
    message: str = ""


def _point_plane_distance(plane: Any, point: Point3) -> float:
    return abs(
        float(plane.normal[0]) * float(point[0])
        + float(plane.normal[1]) * float(point[1])
        + float(plane.normal[2]) * float(point[2])
        - float(plane.depth)
    )


def _canonicalize_points(points: Sequence[Point2], tolerance: float) -> tuple[Point2, ...]:
    """Merge projected endpoints that differ only by mesh/numeric noise.

    A small spatial hash keeps dense imported outlines close to O(N).  The
    previous all-pairs search was acceptable for a few edges but became
    quadratic when a tessellated curved face contained thousands of boundary
    samples.
    """

    buckets: dict[tuple[int, int], list[Point2]] = defaultdict(list)
    result: list[Point2] = []
    tolerance_sq = tolerance * tolerance
    inverse = 1.0 / tolerance
    for point in points:
        value = (float(point[0]), float(point[1]))
        cell = (math.floor(value[0] * inverse), math.floor(value[1] * inverse))
        chosen = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for existing in buckets.get((cell[0] + dx, cell[1] + dy), ()):
                    delta_x = value[0] - existing[0]
                    delta_y = value[1] - existing[1]
                    if delta_x * delta_x + delta_y * delta_y <= tolerance_sq:
                        chosen = existing
                        break
                if chosen is not None:
                    break
            if chosen is not None:
                break
        if chosen is None:
            chosen = value
            buckets[cell].append(chosen)
        result.append(chosen)
    return tuple(result)


def build_projected_trace_plan(
    controller: ClothGeometryTraceController,
    plane: Any,
) -> ProjectedTracePlan:
    """Project selected source boundaries/edges into one clean 2D segment set."""

    source_edges: list[SourceEdgeSelection] = list(controller.selected_edges)
    faces_by_object: dict[str, set[int]] = defaultdict(set)
    for item in controller.selected_faces:
        faces_by_object[item.object_id].add(int(item.face_index))
    for object_id, face_indices in faces_by_object.items():
        snapshot = controller.snapshots.get(object_id)
        if snapshot is None:
            continue
        source_edges.extend(
            SourceEdgeSelection(object_id, edge)
            for edge in boundary_edges(snapshot, face_indices)
        )

    # Preserve deterministic order while removing the same source edge selected
    # both explicitly and as a selected-face boundary.
    source_edges = list(dict.fromkeys(source_edges))
    projected_raw: list[tuple[Point2, Point2]] = []
    max_distance = 0.0
    for item in source_edges:
        snapshot = controller.snapshots.get(item.object_id)
        if snapshot is None:
            continue
        start, end = snapshot.edge_vertices(item.edge)
        start_xy = tuple(float(v) for v in world_to_plane(plane, start))
        end_xy = tuple(float(v) for v in world_to_plane(plane, end))
        max_distance = max(max_distance, _point_plane_distance(plane, start), _point_plane_distance(plane, end))
        projected_raw.append((start_xy, end_xy))

    if not projected_raw:
        return ProjectedTracePlan((), len(source_edges), 0, 0, max_distance)

    coords = [point for segment in projected_raw for point in segment]
    xs = [point[0] for point in coords]
    ys = [point[1] for point in coords]
    scale = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    tolerance = max(1.0e-5, scale * 1.0e-7)
    canonical = _canonicalize_points(coords, tolerance)

    segments: list[tuple[Point2, Point2]] = []
    seen: set[tuple[Point2, Point2]] = set()
    collapsed = 0
    duplicates = 0
    for index in range(0, len(canonical), 2):
        start, end = canonical[index], canonical[index + 1]
        if math.dist(start, end) <= tolerance:
            collapsed += 1
            continue
        key = (start, end) if start <= end else (end, start)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        segments.append((start, end))
    return ProjectedTracePlan(tuple(segments), len(source_edges), collapsed, duplicates, max_distance)


class PlanTrace2DMeshTraceOverlay:
    def __init__(self, owner_tool: str, controller: ClothGeometryTraceController) -> None:
        self.owner_tool = str(owner_tool)
        self.controller = controller

    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        value = str(button_id or "")
        if value.startswith(PLAN_TRACE_MESH_TRACE_ACTION_PREFIX):
            return value[len(PLAN_TRACE_MESH_TRACE_ACTION_PREFIX) :]
        return None

    @staticmethod
    def _mode(action: str, label: str, icon: str, tooltip: str) -> visual.OverlayModeSpec:
        return visual.OverlayModeSpec(
            id=f"{PLAN_TRACE_MESH_TRACE_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=True,
            display_label=label,
            slot_width_px=max(62, len(label) * 8 + 22),
        )

    @staticmethod
    def _action(
        action: str,
        label: str,
        icon: str,
        tooltip: str,
        *,
        enabled: bool,
        style: str = "ghost",
    ) -> visual.OverlayActionSpec:
        return visual.OverlayActionSpec(
            id=f"{PLAN_TRACE_MESH_TRACE_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
            display_label=label,
            slot_width_px=max(68, min(116, len(label) * 8 + 26)),
        )

    def sync(self, ctx: Any, plan: ProjectedTracePlan | None) -> None:
        predictions = self.controller.predictions()
        active = f"{PLAN_TRACE_MESH_TRACE_ACTION_PREFIX}pick_{self.controller.pick_kind}"
        sections = (
            visual.OverlayToolbarSectionSpec(
                "pick",
                "Pick",
                modes=(
                    self._mode("pick_face", "Faces", "sketch.face", "Select source mesh faces; their external boundaries are projected into the active sketch plane."),
                    self._mode("pick_edge", "Edges", "sketch.line", "Select source mesh edges to project into the active sketch plane."),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "smart",
                "Smart help",
                actions=(
                    self._action("grow_coplanar", "Coplanar", "tool.add", "Add connected triangles belonging to the same planar source face.", enabled=bool(predictions.coplanar_faces)),
                    self._action("use_boundary", "Boundary", "sketch.polyline", "Select only the external boundary of the selected source faces.", enabled=bool(predictions.boundary_edges)),
                    self._action("extend_direction", "Continue", "sketch.line", "Add conjoint edges that continue in the current selection direction.", enabled=bool(predictions.directional_edges)),
                    self._action("select_connected", "Connected", "sketch.modify", "Add all unselected source edges connected to the current edge selection.", enabled=bool(predictions.connected_edges)),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "build",
                "Build",
                actions=(
                    self._action("trace_selection", "Trace", "tool.apply", "Project the selection onto the active plane, create sketch lines/faces and return to Modify.", enabled=bool(plan and plan.can_create), style="primary"),
                    self._action("clear_selection", "Clear", "tool.reset", "Clear source geometry selection.", enabled=bool(self.controller.selection_count)),
                    self._action("cancel", "Back", "tool.close", "Leave Mesh trace without creating geometry.", enabled=True),
                ),
            ),
        )
        if plan and plan.can_create:
            projection = "same plane" if plan.maximum_projection_distance <= 1.0e-5 else f"projected from up to {plan.maximum_projection_distance:.3g} mm"
            status = f"{len(plan.segments)} clean segment(s) · {projection}"
            if plan.collapsed_edge_count:
                status += f" · {plan.collapsed_edge_count} collapsed edge(s) ignored"
        elif self.controller.selection_count:
            status = "The current selection collapses on the active 2D plane. Select geometry with a visible projected extent."
        else:
            status = "Select source faces or edges. Geometry on another plane/axis is projected automatically onto this sketch."
        window = visual.build_command_deck_window(
            window_id=PLAN_TRACE_MESH_TRACE_WINDOW_ID,
            owner_tool=self.owner_tool,
            group_id=_PICK_GROUP,
            sections=sections,
            active_mode_id=active,
            badge_id="plan_trace_2d.mesh_trace.mode",
            badge_label="Source",
            badge_value="Faces" if self.controller.pick_kind == "face" else "Edges",
            badge_tooltip="Source mesh element type selected by viewport clicks.",
            status_id="plan_trace_2d.mesh_trace.status",
            status_label="2D projection",
            status_value=status,
            title="Plan Tracer · Smart Mesh Trace",
            anchor="viewport_top_right",
            width_px=0,
            persistent=True,
            cursor_offset_px=(0, 0),
        )
        ctx.overlay.show_window(window)
        try:
            ctx.overlay.set_group_active(_PICK_GROUP, active)
        except Exception:
            pass

    @staticmethod
    def hide(ctx: Any) -> None:
        try:
            ctx.overlay.hide_window(PLAN_TRACE_MESH_TRACE_WINDOW_ID)
        except Exception:
            pass


class PlanTrace2DMeshTraceService(_PlanTrace2DService):
    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        self.controller = ClothGeometryTraceController()
        self.overlay = PlanTrace2DMeshTraceOverlay(self.id, self.controller)
        self._visual_ids: tuple[str, ...] = ()

    def activate(self, ctx: Any) -> None:
        self.controller.clear()
        self._sync(ctx, render=True)
        ctx.status.info("Mesh trace: select faces or edges from another part. They are projected onto the active 2D plane.")

    def deactivate(self, ctx: Any, *, clear: bool = True, render: bool = True) -> None:
        self.overlay.hide(ctx)
        self._clear_visuals(ctx, render=False)
        if clear:
            self.controller.clear()
        if render:
            self.services.rendering._render(ctx, sync_overlays=True, render=True)

    def handle_button(self, ctx: Any, button_id: str) -> bool:
        action = self.overlay.action_from_button(button_id)
        if action is None:
            return False
        if action == "pick_face":
            self.controller.set_pick_kind("face")
            self._sync(ctx, render=False)
            return True
        if action == "pick_edge":
            self.controller.set_pick_kind("edge")
            self._sync(ctx, render=False)
            return True
        if action == "clear_selection":
            self.controller.clear_selection()
            self._sync(ctx, render=True)
            return True
        if action == "cancel":
            self.services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="mesh_trace_cancel", render=True)
            return True
        prediction_map = {
            "grow_coplanar": "coplanar",
            "use_boundary": "boundary",
            "extend_direction": "direction",
            "select_connected": "connected",
        }
        if action in prediction_map:
            count = self.controller.apply_prediction(prediction_map[action])
            self._sync(ctx, render=True)
            ctx.status.info(
                f"Mesh trace added {count} predicted element(s)." if count else "No reliable prediction is available for this selection."
            )
            return True
        if action == "trace_selection":
            outcome = self.create(ctx)
            if outcome.committed:
                self.services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="mesh_trace_commit", render=True)
                ctx.status.info(f"{outcome.message} Modify mode is active.")
            else:
                self._sync(ctx, render=True)
                ctx.status.info(outcome.message)
            return True
        return True

    def handle_event(self, ctx: Any, event: Any) -> bool:
        if event.screen_pos is None:
            return False
        picker = ctx.pick.face_at if self.controller.pick_kind == "face" else ctx.pick.edge_at
        if event.type is ToolEventType.MOUSE_MOVE:
            try:
                pick = picker(event.screen_pos)
            except Exception:
                pick = None
            if self.controller.set_hover_from_pick(ctx, pick):
                self._sync(ctx, render=True)
            return True
        if event.type is ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
            try:
                pick = picker(event.screen_pos)
            except Exception:
                pick = None
            if pick is None or not getattr(pick, "hit", False):
                ctx.status.info("No source mesh element was found under the pointer.")
                return True
            if not self.controller.toggle_from_pick(ctx, pick):
                ctx.status.info("This source mesh element could not be interpreted.")
                return True
            self._sync(ctx, render=True)
            predictions = self.controller.predictions()
            hints = [
                label
                for available, label in (
                    (predictions.coplanar_faces, "Coplanar"),
                    (predictions.boundary_edges, "Boundary"),
                    (predictions.directional_edges, "Continue"),
                    (predictions.connected_edges, "Connected"),
                )
                if available
            ]
            suffix = f" Smart help: {', '.join(hints)}." if hints else ""
            ctx.status.info(f"Mesh trace: {self.controller.selection_count} source element(s) selected.{suffix}")
            return True
        return False

    def create(self, ctx: Any) -> PlanTraceMeshTraceOutcome:
        plane = self._state.plane
        if plane is None:
            return PlanTraceMeshTraceOutcome(False, message="Lock a Plan Tracer drawing plane before using Mesh trace.")
        plan = build_projected_trace_plan(self.controller, plane)
        if not plan.segments:
            return PlanTraceMeshTraceOutcome(
                False,
                message="The selected source geometry has no usable extent after projection onto the active 2D plane.",
            )
        before = self.services.history._snapshot_state()
        created: list[str] = []
        existing_pairs = {
            frozenset((line.start_point_id, line.end_point_id))
            for line in self._state.sketch.lines.values()
        }
        for start_xy, end_xy in plan.segments:
            start = self.services.sketch_sync._add_or_reuse_sketch_point(start_xy)
            end = self.services.sketch_sync._add_or_reuse_sketch_point(end_xy)
            if start.id == end.id:
                continue
            pair = frozenset((start.id, end.id))
            if pair in existing_pairs:
                continue
            line = self._state.sketch.add_line(start.id, end.id)
            line.metadata.update({
                "generated_by": "mesh_trace",
                "source_projected_to_plan": True,
            })
            existing_pairs.add(pair)
            created.append(line.id)
        if not created:
            return PlanTraceMeshTraceOutcome(False, message="All projected source edges already exist in this sketch.")
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
        self.services.history._record_snapshot_command(ctx, "Trace mesh into Plan Tracer", before)
        details = f"Projected {len(created)} edge(s)"
        if plan.maximum_projection_distance > 1.0e-5:
            details += f" from 3D onto the active plane (maximum offset {plan.maximum_projection_distance:.3g} mm)"
        else:
            details += " from the active plane"
        if plan.collapsed_edge_count:
            details += f"; ignored {plan.collapsed_edge_count} edge(s) that collapsed in projection"
        return PlanTraceMeshTraceOutcome(True, tuple(created), f"{details}.")

    def _sync(self, ctx: Any, *, render: bool) -> None:
        plane = self._state.plane
        plan = build_projected_trace_plan(self.controller, plane) if plane is not None else None
        self.overlay.sync(ctx, plan)
        self._sync_visuals(ctx, plan, render=render)
        self.services.overlay._sync_reports(ctx)

    def _clear_visuals(self, ctx: Any, *, render: bool) -> None:
        if not self._visual_ids:
            return
        try:
            ctx.projected_drawing.for_tool(self.id).remove_many(self._visual_ids, render=render)
        except Exception:
            for item_id in self._visual_ids:
                try:
                    ctx.projected_drawing.for_tool(self.id).hide(item_id, render=False)
                except Exception:
                    pass
        self._visual_ids = ()

    def _sync_visuals(self, ctx: Any, plan: ProjectedTracePlan | None, *, render: bool) -> None:
        plane = self._state.plane
        display_plane = self._state.display_plane or plane
        if plane is None or display_plane is None:
            self._clear_visuals(ctx, render=render)
            return
        registry = ctx.projected_drawing.for_tool(self.id)
        primitives: list[Any] = []

        for index, triangle in enumerate(self.controller.selected_face_triangles()):
            primitives.append(draw2d.triangle_mesh(
                f"{_VISUAL_PREFIX}selected_face:{index}",
                triangle,
                ((0, 1, 2),),
                fill_color="#22D3EE",
                fill_opacity=0.16,
                outline_color="#67E8F9",
                outline_width_px=2.4,
                outline_opacity=0.96,
                layer=84,
                metadata={"plan_trace_role": "mesh_trace_source_face", "projected_no_selection_actor": True},
            ))
        hovered_face = self.controller.hovered_face_triangle()
        if hovered_face is not None:
            primitives.append(draw2d.triangle_mesh(
                f"{_VISUAL_PREFIX}hovered_face",
                hovered_face,
                ((0, 1, 2),),
                fill_color="#FDE047",
                fill_opacity=0.15,
                outline_color="#FDE047",
                outline_width_px=3.2,
                outline_opacity=0.98,
                layer=87,
                metadata={"plan_trace_role": "mesh_trace_source_hover", "projected_no_selection_actor": True},
            ))
        for index, (start, end) in enumerate(self.controller.selected_edge_segments()):
            primitives.append(draw2d.line(
                f"{_VISUAL_PREFIX}selected_edge:{index}", start, end,
                color="#22D3EE", width_px=4.0, opacity=1.0, layer=88,
                metadata={"plan_trace_role": "mesh_trace_source_edge", "projected_no_selection_actor": True},
            ))
        hovered_edge = self.controller.hovered_edge_segment()
        if hovered_edge is not None:
            primitives.append(draw2d.line(
                f"{_VISUAL_PREFIX}hovered_edge", hovered_edge[0], hovered_edge[1],
                color="#FDE047", width_px=4.8, opacity=1.0, layer=89,
                metadata={"plan_trace_role": "mesh_trace_source_hover", "projected_no_selection_actor": True},
            ))

        # Green preview lives exactly on the active display plane.  This makes
        # the projection result explicit before Trace, especially when source
        # geometry belongs to a differently oriented part.
        if plan is not None:
            for index, (start_xy, end_xy) in enumerate(plan.segments):
                semantic_start = plane_to_world(plane, start_xy[0], start_xy[1])
                semantic_end = plane_to_world(plane, end_xy[0], end_xy[1])
                display_start = self.services.coordinates.semantic_world_to_display(semantic_start)
                display_end = self.services.coordinates.semantic_world_to_display(semantic_end)
                primitives.append(draw2d.line(
                    f"{_VISUAL_PREFIX}projected:{index}", display_start, display_end,
                    color="#86EFAC", width_px=2.6, opacity=0.92, layer=90,
                    metadata={"plan_trace_role": "mesh_trace_projection_preview", "projected_no_selection_actor": True},
                ))

        next_ids = tuple(str(getattr(primitive, "id", "")) for primitive in primitives if getattr(primitive, "id", None))
        stale = tuple(item_id for item_id in self._visual_ids if item_id not in set(next_ids))
        with registry.batch():
            if stale:
                registry.remove_many(stale, render=False)
            for primitive in primitives:
                registry.add(primitive, replace=True, render=False)
        self._visual_ids = next_ids
        self.services.rendering._render(ctx, sync_overlays=True, render=render)


__all__ = [
    "PLAN_TRACE_MESH_TRACE_ACTION_PREFIX",
    "PLAN_TRACE_MESH_TRACE_WINDOW_ID",
    "PlanTrace2DMeshTraceService",
    "PlanTraceMeshTraceOutcome",
    "ProjectedTracePlan",
    "build_projected_trace_plan",
]
