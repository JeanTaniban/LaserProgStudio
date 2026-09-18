# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .services import _PlanTrace2DService


class PlanTrace2DCoordinateMapper(_PlanTrace2DService):
    """Tool-local adapter around the public Plan 2D coordinate mapper.

    Plan Tracer keeps this service because it reads the current tool state, but
    the actual semantic/display/sketch conversion contract lives in
    ``tool_api.plan2d.plane.Plan2DCoordinateMapper``.  New tools should use the
    public mapper directly instead of copying this adapter.
    """

    def _mapper(self):
        plane = self._state.plane
        if plane is None:
            return None
        from laserprog_studio.tool_api import plan2d

        return plan2d.Plan2DCoordinateMapper(plane, self._state.display_plane or plane)

    def display_world_to_semantic(self, world: tuple[float, float, float]) -> tuple[float, float, float]:
        mapper = self._mapper()
        if mapper is None:
            return tuple(float(v) for v in world)
        return mapper.display_to_semantic_world(world)

    def semantic_world_to_display(self, world: tuple[float, float, float]) -> tuple[float, float, float]:
        semantic = tuple(float(v) for v in world)
        mapper = self._mapper()
        if mapper is None:
            return semantic
        return mapper.semantic_to_display_world(semantic)

    def semantic_world_to_sketch_xy(self, world: tuple[float, float, float]) -> tuple[float, float]:
        mapper = self._mapper()
        if mapper is None:
            return (float(world[0]), float(world[1]))
        return mapper.world_to_sketch_xy(world)

    def sketch_xy_to_semantic_world(self, xy: tuple[float, float]) -> tuple[float, float, float]:
        mapper = self._mapper()
        if mapper is None:
            return (float(xy[0]), float(xy[1]), 0.0)
        return mapper.sketch_xy_to_world(xy)

    def sketch_xy_to_display_world(self, xy: tuple[float, float]) -> tuple[float, float, float]:
        mapper = self._mapper()
        if mapper is None:
            return (float(xy[0]), float(xy[1]), 0.0)
        return mapper.sketch_xy_to_display_world(xy)

    def sample_arc_display_points(self, arc: Any, *, segments: int = 24) -> tuple[tuple[float, float, float], ...]:
        mapper = self._mapper()
        start = self._state.sketch.points.get(arc.start_point_id)
        end = self._state.sketch.points.get(arc.end_point_id)
        control = self._state.sketch.points.get(arc.control_point_id)
        if mapper is None or start is None or end is None or control is None:
            return ()
        return mapper.sample_arc_display_points(start.position, end.position, control.position, segments=segments)

    def add_or_reuse_point_from_display_world(self, world: tuple[float, float, float]) -> Any:
        """Create/reuse a sketch point from a UI/display-plane placement."""

        semantic_world = self.display_world_to_semantic(world)
        xy = self.semantic_world_to_sketch_xy(semantic_world)
        return self.services.sketch_sync._add_or_reuse_sketch_point(xy)


__all__ = ["PlanTrace2DCoordinateMapper"]
