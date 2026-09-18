# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from laserprog_studio.tool_api.core import ToolEvent

from .services import _PlanTrace2DService

class PlanTrace2DDimensionsService(_PlanTrace2DService):
    def _handle_dimension_press(self, ctx: Any, event: "ToolEvent", world: tuple[float, float, float]) -> None:
        """Create passive dimensions from semantic sketch references.

        The tool asks the API selection layer what was clicked, then delegates the
        actual dimension entity construction to ``tool_api.dimensions``.  This
        keeps the workflow compact for tool authors while allowing the dimension
        subsystem to grow by entity type instead of becoming tool-local logic.
        """

        from laserprog_studio.tool_api.plan2d import dimensions as dimension_api

        hit_actor = self._dimension_hit_actor(ctx, event)
        if hit_actor is not None:
            role = str(hit_actor.metadata.get("plan_trace_role", "") or "")
            if role == "edge":
                sketch_line_id = hit_actor.metadata.get("plan_trace_sketch_line_id")
                if sketch_line_id is not None and self._handle_dimension_line_reference(ctx, event, str(sketch_line_id)):
                    return
            if role == "circle":
                sketch_circle_id = hit_actor.metadata.get("plan_trace_sketch_circle_id")
                if sketch_circle_id is not None and self._handle_dimension_circle_reference(ctx, event, str(sketch_circle_id)):
                    return
            if role == "point":
                self._handle_dimension_point_reference(ctx, str(hit_actor.id))
                return

        point = self.services.coordinates.add_or_reuse_point_from_display_world(world)
        self._handle_dimension_point_reference(ctx, point.id)

    def _dimension_hit_actor(self, ctx: Any, event: "ToolEvent"):
        if event.screen_pos is None:
            return None
        from laserprog_studio.tool_api.plan2d import dimensions as dimension_api

        preferred_roles: tuple[str, ...] = ()
        if bool(getattr(event, "alt", False)):
            preferred_roles = ("circle", "arc")
        elif bool(getattr(event, "shift", False)):
            preferred_roles = ("edge",)
        try:
            hit = dimension_api.find_dimension_reference_hit(
                ctx,
                owner_tool=self.id,
                screen_pos=event.screen_pos,
                world_to_screen=getattr(ctx.viewport, "world_to_screen", None),
                preferred_roles=preferred_roles,
                selectable_only=True,
            )
        except Exception:
            return None
        return None if hit is None else hit.actor

    def _handle_dimension_point_reference(self, ctx: Any, point_id: str) -> None:
        from laserprog_studio.tool_api.plan2d import dimensions as dimension_api

        self._state.pending_dimension_line_id = None
        if self._state.pending_dimension_start_id is None:
            self._state.pending_dimension_start_id = str(point_id)
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            ctx.status.info("Dimension first point reference selected. Click the second point/reference.")
            return
        start_id = self._state.pending_dimension_start_id
        self._state.pending_dimension_start_id = None
        if start_id in self._state.sketch.points and point_id in self._state.sketch.points and start_id != point_id:
            dimension_api.add_dimension(
                self._state.sketch,
                dimension_api.DimensionSpec.aligned_distance(start_id, point_id, offset=10.0),
            )
            ctx.status.info(f"Aligned dimension added. Sketch now has {len(self._state.sketch.dimensions)} dimension(s).")
        else:
            ctx.status.info("Dimension ignored: references are identical or missing.")
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)

    def _handle_dimension_line_reference(self, ctx: Any, event: ToolEvent, line_id: str) -> bool:
        from laserprog_studio.tool_api.plan2d import dimensions as dimension_api

        self._state.pending_dimension_start_id = None
        if bool(getattr(event, "shift", False)):
            if self._state.pending_dimension_line_id is None:
                self._state.pending_dimension_line_id = str(line_id)
                self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
                ctx.status.info("Angle dimension first edge selected. Shift-click a second edge.")
                return True
            first_id = self._state.pending_dimension_line_id
            self._state.pending_dimension_line_id = None
            if first_id != line_id and first_id in self._state.sketch.lines and line_id in self._state.sketch.lines:
                dimension_api.add_dimension(self._state.sketch, dimension_api.DimensionSpec.angle(first_id, line_id, offset=16.0))
                ctx.status.info(f"Angle dimension added. Sketch now has {len(self._state.sketch.dimensions)} dimension(s).")
            else:
                ctx.status.info("Angle dimension ignored: choose two distinct edges.")
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            return True
        self._state.pending_dimension_line_id = None
        if line_id in self._state.sketch.lines:
            dimension_api.add_dimension(self._state.sketch, dimension_api.DimensionSpec.edge_length(line_id, offset=10.0))
            ctx.status.info(f"Edge length dimension added. Sketch now has {len(self._state.sketch.dimensions)} dimension(s).")
            self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
            return True
        return False

    def _handle_dimension_circle_reference(self, ctx: Any, event: ToolEvent, circle_id: str) -> bool:
        from laserprog_studio.tool_api.plan2d import dimensions as dimension_api

        self._state.pending_dimension_start_id = None
        self._state.pending_dimension_line_id = None
        if circle_id not in self._state.sketch.circles:
            return False
        spec = dimension_api.DimensionSpec.circle_radius(circle_id) if bool(getattr(event, "alt", False)) else dimension_api.DimensionSpec.circle_diameter(circle_id)
        dimension_api.add_dimension(self._state.sketch, spec)
        kind_label = "Radius" if bool(getattr(event, "alt", False)) else "Diameter"
        ctx.status.info(f"{kind_label} dimension added. Sketch now has {len(self._state.sketch.dimensions)} dimension(s).")
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
        return True


__all__ = ["PlanTrace2DDimensionsService"]
