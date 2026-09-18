# -*- coding: utf-8 -*-
"""Exact selected-path measurements for Plan Tracer 2D."""
from __future__ import annotations

from dataclasses import dataclass
from math import dist, hypot, pi
from typing import Any

from laserprog_studio.tool_api.plan2d.curves import circular_arc_length
from laserprog_studio.tool_api.plan2d.curves import sample_cubic_bezier
from laserprog_studio.tool_api.plan2d.dimensions import DEFAULT_UNIT_SYSTEM


@dataclass(frozen=True, slots=True)
class SelectedPathMeasurement:
    entity_count: int
    total_length: float
    component_count: int
    closed_components: int

    @property
    def contiguous(self) -> bool:
        return self.entity_count > 0 and self.component_count == 1

    def display_text(self) -> str:
        if self.entity_count <= 0:
            return "—"
        length = DEFAULT_UNIT_SYSTEM.format_length(self.total_length)
        if self.component_count == 1:
            suffix = " · closed" if self.closed_components else " · contiguous"
            return f"{length}{suffix}"
        return f"{length} · {self.component_count} separate chains"


def measure_selected_path(ctx: Any, sketch: Any, *, owner_tool: str) -> SelectedPathMeasurement | None:
    """Measure selected lines/arcs/Béziers/circles and classify connectivity.

    Lines and arcs connect through their canonical sketch endpoint ids, so a
    polyline selected segment-by-segment is measured as one chain.  Full circles
    are exact closed components.  Unknown projected polylines fall back to their
    sampled ToolActor points, keeping imported/future curve actors measurable.
    """

    edges: list[tuple[str, str | None, str | None, float, bool]] = []
    evaluations: list[dict[str, Any]] = []
    try:
        actor_ids = tuple(str(value) for value in ctx.selection.ids())
    except Exception as exc:
        actor_ids = ()
        evaluations.append({"stage": "selection_ids", "accepted": False, "reason": "ids_exception", "error": repr(exc)})
    try:
        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

        record_selection_length_event(
            "measurement.begin",
            owner=getattr(ctx, "owner", None),
            ctx=ctx,
            include_selection=True,
            include_inspector=True,
            actor_ids=actor_ids,
            owner_tool=owner_tool,
        )
    except Exception:
        pass
    for actor_id in actor_ids:
        try:
            actor = ctx.selection.actor(actor_id)
        except Exception:
            actor = None
        if actor is None:
            evaluations.append({"actor_id": actor_id, "accepted": False, "reason": "actor_missing"})
            continue
        if str(getattr(actor, "owner_tool", "")) != str(owner_tool):
            evaluations.append(
                {
                    "actor_id": actor_id,
                    "accepted": False,
                    "reason": "owner_tool_mismatch",
                    "actor_owner_tool": str(getattr(actor, "owner_tool", "")),
                    "expected_owner_tool": str(owner_tool),
                }
            )
            continue
        metadata = getattr(actor, "metadata", {}) or {}
        role = str(metadata.get("plan_trace_role", "") or "")
        if role == "edge":
            entity_id = str(metadata.get("plan_trace_sketch_line_id") or "")
            line = sketch.lines.get(entity_id)
            if line is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "line_missing"})
                continue
            start = sketch.points.get(line.start_point_id)
            end = sketch.points.get(line.end_point_id)
            if start is None or end is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "line_endpoint_missing"})
                continue
            length = hypot(float(end.position[0]) - float(start.position[0]), float(end.position[1]) - float(start.position[1]))
            edges.append((actor_id, str(line.start_point_id), str(line.end_point_id), length, False))
            evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": True, "length": float(length), "start_id": str(line.start_point_id), "end_id": str(line.end_point_id)})
        elif role == "arc":
            bezier_id = str(metadata.get("plan_trace_sketch_bezier_id") or "")
            if bezier_id:
                entity = sketch.beziers.get(bezier_id)
                if entity is None:
                    evaluations.append({"actor_id": actor_id, "role": role, "entity_id": bezier_id, "accepted": False, "reason": "bezier_missing"})
                    continue
                start = sketch.points.get(entity.start_point_id)
                end = sketch.points.get(entity.end_point_id)
                control_1 = sketch.points.get(entity.control_1_point_id)
                control_2 = sketch.points.get(entity.control_2_point_id)
                if start is None or end is None or control_1 is None or control_2 is None:
                    evaluations.append({"actor_id": actor_id, "role": role, "entity_id": bezier_id, "accepted": False, "reason": "bezier_point_missing"})
                    continue
                samples = sample_cubic_bezier(start.position, control_1.position, control_2.position, end.position, segments=96)
                length = sum(hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1])) for a, b in zip(samples, samples[1:]))
                edges.append((actor_id, str(entity.start_point_id), str(entity.end_point_id), float(length), False))
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": bezier_id, "accepted": True, "length": float(length), "curve_type": "bezier", "start_id": str(entity.start_point_id), "end_id": str(entity.end_point_id)})
                continue
            entity_id = str(metadata.get("plan_trace_sketch_arc_id") or "")
            entity = sketch.arcs.get(entity_id)
            if entity is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "arc_missing"})
                continue
            start = sketch.points.get(entity.start_point_id)
            end = sketch.points.get(entity.end_point_id)
            control = sketch.points.get(entity.control_point_id)
            if start is None or end is None or control is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "arc_point_missing"})
                continue
            arc_length = circular_arc_length(start.position, end.position, control.position)
            if arc_length is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "arc_length_none"})
                continue
            edges.append((actor_id, str(entity.start_point_id), str(entity.end_point_id), float(arc_length), False))
            evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": True, "length": float(arc_length), "start_id": str(entity.start_point_id), "end_id": str(entity.end_point_id)})
        elif role == "circle":
            entity_id = str(metadata.get("plan_trace_sketch_circle_id") or "")
            entity = sketch.circles.get(entity_id)
            if entity is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "circle_missing"})
                continue
            center = sketch.points.get(entity.center_point_id)
            radius_point = sketch.points.get(entity.radius_point_id)
            if center is None or radius_point is None:
                evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": False, "reason": "circle_point_missing"})
                continue
            radius = hypot(float(radius_point.position[0]) - float(center.position[0]), float(radius_point.position[1]) - float(center.position[1]))
            circle_length = 2.0 * pi * radius
            edges.append((actor_id, None, None, circle_length, True))
            evaluations.append({"actor_id": actor_id, "role": role, "entity_id": entity_id, "accepted": True, "length": float(circle_length), "closed": True})
        else:
            actor_kind = getattr(actor, "kind", "")
            actor_kind = getattr(actor_kind, "value", actor_kind)
            if str(actor_kind) not in {"polyline", "line", "arc"}:
                evaluations.append({"actor_id": actor_id, "role": role, "kind": str(actor_kind), "accepted": False, "reason": "unmeasurable_role_and_kind"})
                continue
            points = tuple(getattr(actor, "points", ()) or ())
            if len(points) < 2:
                evaluations.append({"actor_id": actor_id, "role": role, "kind": str(actor_kind), "accepted": False, "reason": "fallback_points_missing"})
                continue
            length = sum(
                dist(
                    tuple(float(value) for value in a[:3]),
                    tuple(float(value) for value in b[:3]),
                )
                for a, b in zip(points, points[1:])
            )
            edges.append((actor_id, f"{actor_id}:start", f"{actor_id}:end", length, False))
            evaluations.append({"actor_id": actor_id, "role": role, "kind": str(actor_kind), "accepted": True, "length": float(length), "fallback": True})

    if not edges:
        try:
            from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

            record_selection_length_event(
                "measurement.done",
                owner=getattr(ctx, "owner", None),
                ctx=ctx,
                include_selection=True,
                include_inspector=True,
                result=None,
                evaluations=evaluations,
            )
        except Exception:
            pass
        return None

    # Connected components through shared endpoint ids.  Circles are individual
    # closed components because they have no distinguished endpoint.
    endpoint_to_edges: dict[str, list[int]] = {}
    for index, (_actor_id, start_id, end_id, _length, closed) in enumerate(edges):
        if closed:
            continue
        for endpoint in (start_id, end_id):
            if endpoint is not None:
                endpoint_to_edges.setdefault(endpoint, []).append(index)
    remaining = set(range(len(edges)))
    components = 0
    closed_components = 0
    while remaining:
        seed = remaining.pop()
        components += 1
        stack = [seed]
        component_indices = {seed}
        while stack:
            index = stack.pop()
            _actor_id, start_id, end_id, _length, closed = edges[index]
            if closed:
                continue
            for endpoint in (start_id, end_id):
                for neighbour in endpoint_to_edges.get(str(endpoint), ()) if endpoint is not None else ():
                    if neighbour in remaining:
                        remaining.remove(neighbour)
                        component_indices.add(neighbour)
                        stack.append(neighbour)
        if any(edges[index][4] for index in component_indices):
            closed_components += 1
        else:
            degree: dict[str, int] = {}
            for index in component_indices:
                _actor_id, start_id, end_id, _length, _closed = edges[index]
                for endpoint in (start_id, end_id):
                    if endpoint is not None:
                        degree[endpoint] = degree.get(endpoint, 0) + 1
            if degree and all(value == 2 for value in degree.values()):
                closed_components += 1

    result = SelectedPathMeasurement(
        entity_count=len(edges),
        total_length=sum(float(item[3]) for item in edges),
        component_count=components,
        closed_components=closed_components,
    )
    try:
        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

        record_selection_length_event(
            "measurement.done",
            owner=getattr(ctx, "owner", None),
            ctx=ctx,
            include_selection=True,
            include_inspector=True,
            result={
                "entity_count": result.entity_count,
                "total_length": result.total_length,
                "component_count": result.component_count,
                "closed_components": result.closed_components,
                "display_text": result.display_text(),
            },
            edges=edges,
            evaluations=evaluations,
        )
    except Exception:
        pass
    return result


__all__ = ["SelectedPathMeasurement", "measure_selected_path"]
