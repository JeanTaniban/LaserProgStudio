# -*- coding: utf-8 -*-
"""Topology-safe selection editing and sketch-local clipboard for Plan Tracer 2D.

This module deliberately contains no overlay or Qt code.  It translates the
semantic Creator selection into sketch entities, detaches shared boundary
vertices before group moves, and serializes selected geometry for copy/paste or
persistent prefabs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import copy
import math
from typing import Any, Iterable, Mapping

from .services import _PlanTrace2DService
from .selection_transform import SelectionTransformSession

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class SketchSelection:
    point_ids: frozenset[str] = frozenset()
    line_ids: frozenset[str] = frozenset()
    arc_ids: frozenset[str] = frozenset()
    bezier_ids: frozenset[str] = frozenset()
    circle_ids: frozenset[str] = frozenset()
    face_ids: frozenset[str] = frozenset()

    @property
    def entity_count(self) -> int:
        return (
            len(self.point_ids)
            + len(self.line_ids)
            + len(self.arc_ids)
            + len(self.bezier_ids)
            + len(self.circle_ids)
            + len(self.face_ids)
        )

    @property
    def has_structural_entities(self) -> bool:
        return bool(self.line_ids or self.arc_ids or self.bezier_ids or self.circle_ids or self.face_ids)


@dataclass(slots=True)
class SketchPayload:
    """Portable sketch geometry expressed relative to a user-controlled pivot."""

    points: dict[str, Point2] = field(default_factory=dict)
    lines: list[dict[str, Any]] = field(default_factory=list)
    arcs: list[dict[str, Any]] = field(default_factory=list)
    beziers: list[dict[str, Any]] = field(default_factory=list)
    circles: list[dict[str, Any]] = field(default_factory=list)
    pivot: Point2 = (0.0, 0.0)
    source_name: str = ""
    schema_version: int = 1

    @property
    def is_empty(self) -> bool:
        return not self.points

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [float(p[0]) for p in self.points.values()]
        ys = [float(p[1]) for p in self.points.values()]
        return (min(xs), max(xs), min(ys), max(ys))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "source_name": str(self.source_name),
            "pivot": [float(self.pivot[0]), float(self.pivot[1])],
            "points": {str(key): [float(value[0]), float(value[1])] for key, value in self.points.items()},
            "lines": copy.deepcopy(self.lines),
            "arcs": copy.deepcopy(self.arcs),
            "beziers": copy.deepcopy(self.beziers),
            "circles": copy.deepcopy(self.circles),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> "SketchPayload":
        raw = dict(payload or {})
        points: dict[str, Point2] = {}
        for key, value in dict(raw.get("points") or {}).items():
            try:
                points[str(key)] = (float(value[0]), float(value[1]))
            except Exception:
                continue
        try:
            pivot_raw = raw.get("pivot") or (0.0, 0.0)
            pivot = (float(pivot_raw[0]), float(pivot_raw[1]))
        except Exception:
            pivot = (0.0, 0.0)
        return cls(
            points=points,
            lines=[dict(row) for row in list(raw.get("lines") or ()) if isinstance(row, dict)],
            arcs=[dict(row) for row in list(raw.get("arcs") or ()) if isinstance(row, dict)],
            beziers=[dict(row) for row in list(raw.get("beziers") or ()) if isinstance(row, dict)],
            circles=[dict(row) for row in list(raw.get("circles") or ()) if isinstance(row, dict)],
            pivot=pivot,
            source_name=str(raw.get("source_name") or ""),
            schema_version=max(1, int(raw.get("schema_version") or 1)),
        )


@dataclass(frozen=True, slots=True)
class PasteResult:
    point_ids: tuple[str, ...]
    line_ids: tuple[str, ...]
    arc_ids: tuple[str, ...]
    bezier_ids: tuple[str, ...]
    circle_ids: tuple[str, ...]

    @property
    def created_count(self) -> int:
        return sum(len(items) for items in (self.point_ids, self.line_ids, self.arc_ids, self.bezier_ids, self.circle_ids))


class PlanTrace2DSelectionEditService(_PlanTrace2DService):
    """Selection graph, safe group move and local copy/paste operations."""

    def selected_entities(self, ctx: Any, *, expand_faces: bool = True) -> SketchSelection:
        sketch = self._state.sketch
        points: set[str] = set()
        lines: set[str] = set()
        arcs: set[str] = set()
        beziers: set[str] = set()
        circles: set[str] = set()
        faces: set[str] = set()
        try:
            selected_actor_ids = tuple(str(value) for value in ctx.selection.ids())
        except Exception:
            selected_actor_ids = ()
        for actor_id in selected_actor_ids:
            actor = ctx.selection.actor(actor_id)
            if actor is None or str(getattr(actor, "owner_tool", "")) != self.id:
                continue
            metadata = dict(getattr(actor, "metadata", {}) or {})
            role = str(metadata.get("plan_trace_role") or "")
            if role == "point" and actor_id in sketch.points:
                points.add(actor_id)
            elif role == "edge":
                entity_id = metadata.get("plan_trace_sketch_line_id")
                if entity_id is not None and str(entity_id) in sketch.lines:
                    lines.add(str(entity_id))
            elif role == "arc":
                arc_id = metadata.get("plan_trace_sketch_arc_id")
                bezier_id = metadata.get("plan_trace_sketch_bezier_id")
                if arc_id is not None and str(arc_id) in sketch.arcs:
                    arcs.add(str(arc_id))
                if bezier_id is not None and str(bezier_id) in sketch.beziers:
                    beziers.add(str(bezier_id))
            elif role == "circle":
                entity_id = metadata.get("plan_trace_sketch_circle_id")
                if entity_id is not None and str(entity_id) in sketch.circles:
                    circles.add(str(entity_id))
            elif role == "face":
                face_id = metadata.get("plan_trace_sketch_face_id")
                if face_id is not None and str(face_id) in sketch.faces:
                    faces.add(str(face_id))

        if expand_faces:
            for face_id in tuple(faces):
                face = sketch.faces.get(face_id)
                if face is None:
                    continue
                boundary_ids: list[str] = list(face.boundary_entity_ids)
                for hole_ids in tuple(getattr(face, "hole_boundary_entity_ids", ()) or ()):
                    boundary_ids.extend(str(value) for value in hole_ids)
                for entity_id in boundary_ids:
                    entity_id = str(entity_id)
                    if entity_id in sketch.lines:
                        lines.add(entity_id)
                    elif entity_id in sketch.arcs:
                        arcs.add(entity_id)
                    elif entity_id in sketch.beziers:
                        beziers.add(entity_id)
                    elif entity_id in sketch.circles:
                        circles.add(entity_id)

        for line_id in lines:
            line = sketch.lines.get(line_id)
            if line is not None:
                points.update((line.start_point_id, line.end_point_id))
        for arc_id in arcs:
            arc = sketch.arcs.get(arc_id)
            if arc is not None:
                points.update((arc.start_point_id, arc.end_point_id, arc.control_point_id))
        for bezier_id in beziers:
            bezier = sketch.beziers.get(bezier_id)
            if bezier is not None:
                points.update((bezier.start_point_id, bezier.end_point_id, bezier.control_1_point_id, bezier.control_2_point_id))
        for circle_id in circles:
            circle = sketch.circles.get(circle_id)
            if circle is not None:
                points.update((circle.center_point_id, circle.radius_point_id))
        points.intersection_update(sketch.points)
        return SketchSelection(
            point_ids=frozenset(points),
            line_ids=frozenset(lines),
            arc_ids=frozenset(arcs),
            bezier_ids=frozenset(beziers),
            circle_ids=frozenset(circles),
            face_ids=frozenset(faces),
        )

    def select_support_points(self, ctx: Any) -> SketchSelection:
        selection = self.selected_entities(ctx, expand_faces=True)
        for point_id in sorted(selection.point_ids):
            try:
                ctx.selection.select(point_id, replace=False)
            except Exception:
                pass
        return selection

    def prepare_drag_from_support_point(self, ctx: Any, event: Any) -> bool:
        """Promote support points only when a selected group is grabbed.

        Keeping face/edge selection explicit is important: deleting a selected
        face should suppress only that generated face, not its boundary.  Native
        dragging, however, starts only from selected draggable point actors. This
        bridge performs the promotion immediately before the native runtime sees
        the press, and only when the pressed point belongs to the selected
        topology.
        """

        try:
            from laserprog_studio.tool_api.core import MouseButton, ToolEventType

            if event.type is not ToolEventType.MOUSE_PRESS or event.button != MouseButton.LEFT:
                return False
            if event.screen_pos is None or bool(getattr(event, "shift", False)):
                return False
        except Exception:
            return False
        selection = self.selected_entities(ctx, expand_faces=True)
        if not selection.has_structural_entities or not selection.point_ids:
            return False
        try:
            from laserprog_studio.tool_api.scene import projection_cache_signature

            hit = ctx.selection.hit_test(
                event.screen_pos,
                ctx.viewport.world_to_screen,
                owner_tool=self.id,
                selectable_only=True,
                projection_key=projection_cache_signature(ctx),
            )
        except Exception:
            return False
        if hit is None or str(hit.actor_id) not in selection.point_ids:
            return False
        actor = ctx.selection.actor(str(hit.actor_id))
        metadata = dict(getattr(actor, "metadata", {}) or {}) if actor is not None else {}
        if str(metadata.get("plan_trace_role") or "") != "point":
            return False
        try:
            self._state.active_drag_selection_before_ids = tuple(str(value) for value in ctx.selection.ids())
        except Exception:
            self._state.active_drag_selection_before_ids = ()
        self.select_support_points(ctx)
        return True

    def payload_from_selection(
        self,
        ctx: Any,
        *,
        pivot: Point2 | None = None,
        source_name: str = "",
    ) -> SketchPayload:
        selection = self.selected_entities(ctx, expand_faces=True)
        return self.payload_from_entity_selection(selection, pivot=pivot, source_name=source_name)

    def payload_from_entity_selection(
        self,
        selection: SketchSelection,
        *,
        pivot: Point2 | None = None,
        source_name: str = "",
    ) -> SketchPayload:
        sketch = self._state.sketch
        point_ids = tuple(sorted(point_id for point_id in selection.point_ids if point_id in sketch.points))
        if not point_ids:
            return SketchPayload(source_name=source_name)
        if pivot is None:
            xs = [float(sketch.points[point_id].position[0]) for point_id in point_ids]
            ys = [float(sketch.points[point_id].position[1]) for point_id in point_ids]
            pivot = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5)
        pivot = (float(pivot[0]), float(pivot[1]))
        local_points = {
            point_id: (
                float(sketch.points[point_id].position[0]) - pivot[0],
                float(sketch.points[point_id].position[1]) - pivot[1],
            )
            for point_id in point_ids
        }

        def metadata(value: Any) -> dict[str, Any]:
            result = copy.deepcopy(dict(getattr(value, "metadata", {}) or {}))
            # Derived/source ids are not stable across paste. Keep visual/user
            # metadata, but remove known topology-generation links.
            for key in tuple(result):
                if str(key).startswith("generated_for_") or str(key).endswith("_arc_id"):
                    result.pop(key, None)
            return result

        lines = [
            {"start": line.start_point_id, "end": line.end_point_id, "metadata": metadata(line)}
            for line_id in sorted(selection.line_ids)
            if (line := sketch.lines.get(line_id)) is not None
            and line.start_point_id in local_points
            and line.end_point_id in local_points
        ]
        arcs = [
            {
                "start": arc.start_point_id,
                "end": arc.end_point_id,
                "control": arc.control_point_id,
                "metadata": metadata(arc),
            }
            for arc_id in sorted(selection.arc_ids)
            if (arc := sketch.arcs.get(arc_id)) is not None
            and all(point_id in local_points for point_id in (arc.start_point_id, arc.end_point_id, arc.control_point_id))
        ]
        beziers = [
            {
                "start": bezier.start_point_id,
                "end": bezier.end_point_id,
                "control_1": bezier.control_1_point_id,
                "control_2": bezier.control_2_point_id,
                "metadata": metadata(bezier),
            }
            for bezier_id in sorted(selection.bezier_ids)
            if (bezier := sketch.beziers.get(bezier_id)) is not None
            and all(
                point_id in local_points
                for point_id in (
                    bezier.start_point_id,
                    bezier.end_point_id,
                    bezier.control_1_point_id,
                    bezier.control_2_point_id,
                )
            )
        ]
        circles = [
            {
                "center": circle.center_point_id,
                "radius": circle.radius_point_id,
                "metadata": metadata(circle),
            }
            for circle_id in sorted(selection.circle_ids)
            if (circle := sketch.circles.get(circle_id)) is not None
            and circle.center_point_id in local_points
            and circle.radius_point_id in local_points
        ]
        return SketchPayload(
            points=local_points,
            lines=lines,
            arcs=arcs,
            beziers=beziers,
            circles=circles,
            pivot=pivot,
            source_name=str(source_name),
        )

    def paste_payload(
        self,
        ctx: Any,
        payload: SketchPayload,
        *,
        target: Point2,
        rotation_rad: float = 0.0,
        scale: float = 1.0,
        mirror_x: bool = False,
        mirror_y: bool = False,
        compile_after: bool = True,
        select_created: bool = True,
    ) -> PasteResult:
        if payload.is_empty:
            return PasteResult((), (), (), (), ())
        sketch = self._state.sketch
        cos_a = math.cos(float(rotation_rad))
        sin_a = math.sin(float(rotation_rad))
        scale = float(scale)
        target = (float(target[0]), float(target[1]))
        point_map: dict[str, str] = {}
        point_ids: list[str] = []
        for source_id, local in payload.points.items():
            lx = float(local[0]) * scale
            ly = float(local[1]) * scale
            if mirror_x:
                lx = -lx
            if mirror_y:
                ly = -ly
            xy = (target[0] + lx * cos_a - ly * sin_a, target[1] + lx * sin_a + ly * cos_a)
            point_id = f"{self.id}:point:{self._state.next_point_index:04d}"
            self._state.next_point_index += 1
            point = sketch.add_point(xy, point_id=point_id)
            point.metadata.update({"generated_by": "duplicate", "prefab_source_point": str(source_id)})
            point_map[str(source_id)] = point.id
            point_ids.append(point.id)

        def map_point(key: Any) -> str | None:
            return point_map.get(str(key))

        line_ids: list[str] = []
        for row in payload.lines:
            start, end = map_point(row.get("start")), map_point(row.get("end"))
            if not start or not end or start == end:
                continue
            line = sketch.add_line(start, end)
            line.metadata.update(copy.deepcopy(dict(row.get("metadata") or {})))
            line.metadata["generated_by"] = "duplicate"
            line_ids.append(line.id)
        arc_ids: list[str] = []
        for row in payload.arcs:
            start, end, control = map_point(row.get("start")), map_point(row.get("end")), map_point(row.get("control"))
            if not start or not end or not control:
                continue
            arc = sketch.add_arc(start, end, control)
            arc.metadata.update(copy.deepcopy(dict(row.get("metadata") or {})))
            arc.metadata["generated_by"] = "duplicate"
            arc_ids.append(arc.id)
        bezier_ids: list[str] = []
        for row in payload.beziers:
            values = (
                map_point(row.get("start")),
                map_point(row.get("end")),
                map_point(row.get("control_1")),
                map_point(row.get("control_2")),
            )
            if any(value is None for value in values):
                continue
            bezier = sketch.add_bezier(values[0], values[1], values[2], values[3], metadata=copy.deepcopy(dict(row.get("metadata") or {})))
            bezier.metadata["generated_by"] = "duplicate"
            bezier_ids.append(bezier.id)
        circle_ids: list[str] = []
        for row in payload.circles:
            center, radius = map_point(row.get("center")), map_point(row.get("radius"))
            if not center or not radius or center == radius:
                continue
            circle = sketch.add_circle(center, radius)
            circle.metadata.update(copy.deepcopy(dict(row.get("metadata") or {})))
            circle.metadata["generated_by"] = "duplicate"
            circle_ids.append(circle.id)

        result = PasteResult(tuple(point_ids), tuple(line_ids), tuple(arc_ids), tuple(bezier_ids), tuple(circle_ids))
        if compile_after:
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
        if select_created:
            self.select_paste_result(ctx, result)
        return result

    def select_paste_result(self, ctx: Any, result: PasteResult) -> None:
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            pass
        actor_ids: list[str] = list(result.point_ids)
        actor_ids.extend(self.services.sketch_sync._line_actor_id(value) for value in result.line_ids)
        actor_ids.extend(self.services.sketch_sync._arc_actor_id(value) for value in result.arc_ids)
        actor_ids.extend(self.services.sketch_sync._bezier_actor_id(value) for value in result.bezier_ids)
        actor_ids.extend(self.services.sketch_sync._circle_actor_id(value) for value in result.circle_ids)
        for actor_id in actor_ids:
            try:
                ctx.selection.select(actor_id, replace=False)
            except Exception:
                pass

    def copy_selected(self, ctx: Any) -> bool:
        payload = self.payload_from_selection(ctx, source_name="Clipboard")
        if payload.is_empty:
            try:
                ctx.status.info("Plan Tracer: select points, edges or faces before Copy.")
            except Exception:
                pass
            return False
        self._state.sketch_clipboard_payload = payload
        self._state.sketch_clipboard_paste_index = 0
        try:
            ctx.status.info(f"Copied {len(payload.points)} sketch point(s) and {len(payload.lines) + len(payload.arcs) + len(payload.beziers) + len(payload.circles)} curve(s).")
        except Exception:
            pass
        return True

    def paste_clipboard(self, ctx: Any) -> bool:
        payload = getattr(self._state, "sketch_clipboard_payload", None)
        if not isinstance(payload, SketchPayload) or payload.is_empty:
            try:
                ctx.status.info("Plan Tracer clipboard is empty.")
            except Exception:
                pass
            return False
        before = self.services.history._snapshot_state()
        index = int(getattr(self._state, "sketch_clipboard_paste_index", 0) or 0) + 1
        self._state.sketch_clipboard_paste_index = index
        offset = 10.0 * index
        result = self.paste_payload(ctx, payload, target=(payload.pivot[0] + offset, payload.pivot[1] + offset), compile_after=True, select_created=True)
        if not result.created_count:
            return False
        self.services.history._record_snapshot_command(ctx, "Paste Plan Tracer selection", before)
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            ctx.status.info(f"Pasted {result.created_count} Plan Tracer element(s). Drag a selected point to position them with Smart Snap.")
        except Exception:
            pass
        return True

    def begin_safe_drag(self, ctx: Any, grabbed_ids: Iterable[str]) -> tuple[str, ...]:
        """Expand a structural selection to points and detach unselected branches.

        The point that remains selected keeps its id and moves.  When that point
        is shared by selected and unselected curves, the unselected curves are
        rewired to a duplicate at the original coordinates.  This preserves the
        untouched topology instead of stretching it as a side effect.
        """

        selection = self.selected_entities(ctx, expand_faces=True)
        grabbed = tuple(str(value) for value in grabbed_ids)
        if not tuple(getattr(self._state, "active_drag_selection_before_ids", ()) or ()):
            try:
                self._state.active_drag_selection_before_ids = tuple(str(value) for value in ctx.selection.ids())
            except Exception:
                self._state.active_drag_selection_before_ids = grabbed
        if not selection.point_ids:
            self._state.active_drag_changed = False
            self._state.active_transform_session = None
            return grabbed
        sketch = self._state.sketch
        self._state.active_drag_snapshot = self.services.history._snapshot_state()
        moving_points = set(selection.point_ids)

        # Preserve the historical direct-edit behaviour for a genuinely isolated
        # point selection. Moving one point is an intentional vertex edit: every
        # incident line/arc/curve must deform with that same point. Detaching it
        # would create a stationary clone, disconnect the selected point and make
        # only the dot move. Topology detachment is reserved for structural/group
        # selections where unselected neighbouring geometry must remain intact.
        single_vertex_edit = len(moving_points) == 1 and not selection.has_structural_entities
        if single_vertex_edit:
            point_id = next(iter(moving_points))
            try:
                ctx.selection.select(point_id, replace=False)
            except Exception:
                pass
            actor = ctx.selection.actor(point_id)
            expanded = (point_id,) if actor is not None and bool(getattr(actor, "grabbable", False)) else grabbed
            state = ctx.selection.state
            if expanded:
                state.grabbed_ids = tuple(expanded)
                state.grab_active = True
            self._state.active_transform_session = SelectionTransformSession(
                point_ids=(point_id,),
                pivot_point_id=point_id,
            )
            self._state.active_drag_changed = False
            self._state.active_drag_detached_count = 0
            return tuple(expanded) or grabbed

        selected_entity_ids = set(selection.line_ids) | set(selection.arc_ids) | set(selection.bezier_ids) | set(selection.circle_ids)
        # A selected generated face can share a semantic boundary entity with a
        # neighbouring unselected face. The selected boundary must move, while a
        # stationary copy keeps the neighbour closed. Faces themselves are
        # derived, so this has to be resolved at the boundary graph level.
        selected_face_ids = set(selection.face_ids)
        shared_face_boundary_ids: set[str] = set()
        if selected_face_ids:
            selected_boundaries: set[str] = set()
            unselected_boundaries: set[str] = set()
            for face_id, face in sketch.faces.items():
                ids = set(str(value) for value in face.boundary_entity_ids)
                for hole_ids in tuple(getattr(face, "hole_boundary_entity_ids", ()) or ()):
                    ids.update(str(value) for value in hole_ids)
                (selected_boundaries if str(face_id) in selected_face_ids else unselected_boundaries).update(ids)
            shared_face_boundary_ids = selected_boundaries & unselected_boundaries & selected_entity_ids

        duplicated = 0
        duplicate_point_ids: list[str] = []
        duplicate_point_map: dict[str, str] = {}
        for point_id in tuple(sorted(moving_points)):
            if point_id not in sketch.points:
                continue
            selected_incident: list[tuple[str, Any]] = []
            unselected_incident: list[tuple[str, Any]] = []
            for kind, entity_id, entity in self._incident_entities(point_id):
                (selected_incident if entity_id in selected_entity_ids else unselected_incident).append((kind, entity))
            needs_shared_boundary_copy = any(entity_id in shared_face_boundary_ids for _kind, entity_id, _entity in self._incident_entities(point_id))
            point_only_detach = not selected_incident and bool(unselected_incident)
            structural_detach = bool(selected_incident) and bool(unselected_incident)
            if not (point_only_detach or structural_detach or needs_shared_boundary_copy):
                continue
            original = sketch.points[point_id]
            duplicate_id = f"{self.id}:point:{self._state.next_point_index:04d}"
            self._state.next_point_index += 1
            duplicate = sketch.add_point(original.position, point_id=duplicate_id)
            duplicate.metadata.update(copy.deepcopy(original.metadata))
            duplicate.metadata["detached_from"] = point_id
            duplicate_point_ids.append(duplicate.id)
            duplicate_point_map[point_id] = duplicate.id
            for kind, entity in unselected_incident:
                self._rewire_entity_point(kind, entity, point_id, duplicate_id)
            duplicated += 1

        if shared_face_boundary_ids:
            for entity_id in sorted(shared_face_boundary_ids):
                if entity_id in sketch.lines:
                    entity = sketch.lines[entity_id]
                    start = duplicate_point_map.get(entity.start_point_id)
                    end = duplicate_point_map.get(entity.end_point_id)
                    if start and end:
                        duplicate_entity = sketch.add_line(start, end)
                    else:
                        continue
                elif entity_id in sketch.arcs:
                    entity = sketch.arcs[entity_id]
                    values = (
                        duplicate_point_map.get(entity.start_point_id),
                        duplicate_point_map.get(entity.end_point_id),
                        duplicate_point_map.get(entity.control_point_id),
                    )
                    if all(values):
                        duplicate_entity = sketch.add_arc(values[0], values[1], values[2])
                    else:
                        continue
                elif entity_id in sketch.beziers:
                    entity = sketch.beziers[entity_id]
                    values = (
                        duplicate_point_map.get(entity.start_point_id),
                        duplicate_point_map.get(entity.end_point_id),
                        duplicate_point_map.get(entity.control_1_point_id),
                        duplicate_point_map.get(entity.control_2_point_id),
                    )
                    if all(values):
                        duplicate_entity = sketch.add_bezier(values[0], values[1], values[2], values[3])
                    else:
                        continue
                elif entity_id in sketch.circles:
                    entity = sketch.circles[entity_id]
                    center = duplicate_point_map.get(entity.center_point_id)
                    radius = duplicate_point_map.get(entity.radius_point_id)
                    if center and radius:
                        duplicate_entity = sketch.add_circle(center, radius)
                    else:
                        continue
                else:
                    continue
                duplicate_entity.metadata.update(copy.deepcopy(dict(getattr(entity, "metadata", {}) or {})))
                duplicate_entity.metadata["detached_boundary_copy"] = entity_id

        if duplicated:
            # Do not compile while the duplicate still overlaps the moving point:
            # the sketch compiler intentionally merges coincident vertices. The
            # selected point will separate on the first drag frame; full topology
            # normalization remains a release-time operation.
            sketch.faces.clear()
            sketch.polylines.clear()
            try:
                self.services.sketch_sync._sync_points_only(ctx, render=False, changed_point_ids=tuple(duplicate_point_ids))
                self.services.sketch_sync._sync_drag_moved_points(
                    ctx, tuple(dict.fromkeys((*moving_points, *duplicate_point_ids))), render=False
                )
            except Exception:
                pass
        for point_id in sorted(moving_points):
            try:
                ctx.selection.select(point_id, replace=False)
            except Exception:
                pass
        expanded = tuple(
            point_id
            for point_id in ctx.selection.ids()
            if point_id in moving_points
            and (actor := ctx.selection.actor(point_id)) is not None
            and bool(getattr(actor, "grabbable", False))
        )
        state = ctx.selection.state
        if expanded:
            state.grabbed_ids = expanded
            state.grab_active = True
        resolved_grabbed = expanded or grabbed
        pressed_id = str(getattr(ctx.selection.state, "pressed_id", "") or "")
        pivot_id = pressed_id if pressed_id in moving_points else next(
            (str(value) for value in reversed(resolved_grabbed) if str(value) in moving_points),
            next(iter(sorted(moving_points))),
        )
        self._state.active_transform_session = SelectionTransformSession(
            point_ids=tuple(sorted(moving_points)),
            pivot_point_id=pivot_id,
        )
        self._state.active_drag_changed = False
        self._state.active_drag_detached_count = duplicated
        return resolved_grabbed

    def latch_rotation(self, ctx: Any, screen_pos: Point2 | None) -> bool:
        session = getattr(self._state, "active_transform_session", None)
        if not isinstance(session, SelectionTransformSession) or screen_pos is None:
            return False
        positions = {
            point_id: tuple(float(v) for v in self._state.sketch.points[point_id].position)
            for point_id in session.point_ids
            if point_id in self._state.sketch.points
        }
        changed = session.latch_rotation(screen_pos=screen_pos, positions=positions)
        if changed:
            try:
                ctx.status.info("Rotate selection: move horizontally around the grabbed pivot. Release Ctrl to resume moving, or release the mouse to validate.")
            except Exception:
                pass
        return changed

    def mark_drag_changed(self) -> None:
        self._state.active_drag_changed = True

    def cancel_noop_drag(self, ctx: Any) -> bool:
        before = getattr(self._state, "active_drag_snapshot", None)
        changed = bool(getattr(self._state, "active_drag_changed", False))
        if before is None or changed:
            return False

        original_selection = tuple(
            str(value)
            for value in tuple(getattr(self._state, "active_drag_selection_before_ids", ()) or ())
        )
        detached = int(getattr(self._state, "active_drag_detached_count", 0) or 0)

        if detached > 0:
            # Safe group preparation may already have duplicated/rewired shared
            # vertices before the first move.  Restore only in that case.
            self.services.history._restore_snapshot_state(ctx, before, render=False)
        else:
            # A native point press is represented as a grab even when the mouse
            # never moves.  No sketch mutation occurred, so restoring a history
            # snapshot would only clear the just-selected point and rebuild the
            # sketch for no reason.
            self._state.active_drag_snapshot = None
            self._state.active_transform_session = None

        # Support-point promotion is temporary until a real transform begins.
        # Restore the explicit pre-press selection, keeping a single point
        # visibly selected after press -> release.
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
            for actor_id in original_selection:
                if ctx.selection.actor(actor_id) is not None:
                    ctx.selection.select(actor_id, replace=False)
        except Exception:
            pass

        self._state.active_drag_snapshot = None
        self._state.active_drag_detached_count = 0
        self._state.active_transform_session = None
        self._state.active_drag_selection_before_ids = ()
        return True

    def _incident_entities(self, point_id: str) -> Iterable[tuple[str, str, Any]]:
        sketch = self._state.sketch
        for entity_id, line in sketch.lines.items():
            if point_id in (line.start_point_id, line.end_point_id):
                yield "line", str(entity_id), line
        for entity_id, arc in sketch.arcs.items():
            if point_id in (arc.start_point_id, arc.end_point_id, arc.control_point_id):
                yield "arc", str(entity_id), arc
        for entity_id, bezier in sketch.beziers.items():
            if point_id in (bezier.start_point_id, bezier.end_point_id, bezier.control_1_point_id, bezier.control_2_point_id):
                yield "bezier", str(entity_id), bezier
        for entity_id, circle in sketch.circles.items():
            if point_id in (circle.center_point_id, circle.radius_point_id):
                yield "circle", str(entity_id), circle

    @staticmethod
    def _rewire_entity_point(kind: str, entity: Any, old_id: str, new_id: str) -> None:
        fields = {
            "line": ("start_point_id", "end_point_id"),
            "arc": ("start_point_id", "end_point_id", "control_point_id"),
            "bezier": ("start_point_id", "end_point_id", "control_1_point_id", "control_2_point_id"),
            "circle": ("center_point_id", "radius_point_id"),
        }.get(str(kind), ())
        for field_name in fields:
            if str(getattr(entity, field_name, "")) == str(old_id):
                setattr(entity, field_name, str(new_id))


__all__ = [
    "PasteResult",
    "PlanTrace2DSelectionEditService",
    "SketchPayload",
    "SketchSelection",
]
