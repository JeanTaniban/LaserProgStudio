# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api.tracing import normalize_trace_mode

from .constants import (
    _MODE_ARC,
    _MODE_BEZIER,
    _MODE_CIRCLE,
    _MODE_DIMENSION,
    _MODE_DUPLICATE,
    _MODE_HALF_CIRCLE,
    _MODE_LINE,
    _MODE_MESH_TRACE,
    _MODE_MIRROR,
    _MODE_MODIFY,
    _MODE_POINT,
    _MODE_POLYLINE,
    _MODE_RECTANGLE,
    _PHASE_DRAW,
    _PHASE_PICK_HEIGHT,
    _TOOL_GROUP,
    _TOOL_MODES,
)
from .services import _PlanTrace2DService
from .state import _PlanTrace2DState

class PlanTrace2DModeStateService(_PlanTrace2DService):
    @staticmethod
    def _normalize_tool_mode(mode: str | None) -> str:
        return normalize_trace_mode(
            mode,
            default=_MODE_MODIFY,
            allowed=_TOOL_MODES,
            extra_aliases={
                "half_circle": _MODE_HALF_CIRCLE,
                "halfcircle": _MODE_HALF_CIRCLE,
                "semicircle": _MODE_HALF_CIRCLE,
                "demi_cercle": _MODE_HALF_CIRCLE,
                "bezier": _MODE_BEZIER,
                "curve": _MODE_BEZIER,
                "spline": _MODE_BEZIER,
                "dimension": _MODE_DIMENSION,
                "measure": _MODE_DIMENSION,
                "measurement": _MODE_DIMENSION,
                "cote": _MODE_DIMENSION,
                "symmetry": _MODE_MIRROR,
                "symetrie": _MODE_MIRROR,
                "mirror": _MODE_MIRROR,
            },
        )


    def _register_creator_modes(self, ctx: Any, *, active: str | None = None) -> None:
        active_id = self._normalize_tool_mode(active or self._state.active_tool)
        try:
            ctx.modes.register(
                self.id,
                (
                    ctx.modes.define(_MODE_MODIFY, "Modify", shortcut="Esc", help="Select elements; Shift-drag draws a selection box. Drag from a selected point to move with Smart Snap, and hold Ctrl during the drag to rotate around that point."),
                    ctx.modes.define(_MODE_POINT, "Point", shortcut="P", help="Place standalone construction points."),
                    ctx.modes.define(_MODE_LINE, "Line", shortcut="L", help="Place start and end points for an edge."),
                    ctx.modes.define(_MODE_POLYLINE, "Polyline", shortcut="Y", help="Place chained line segments until Escape or double-click."),
                    ctx.modes.define(_MODE_RECTANGLE, "Rectangle", shortcut="R", help="Place two opposite corners."),
                    ctx.modes.define(_MODE_CIRCLE, "Circle", shortcut="C", help="Place center and radius points."),
                    ctx.modes.define(_MODE_ARC, "Arc", shortcut="A", help="Place start, end and one point on a circular arc."),
                    ctx.modes.define(_MODE_BEZIER, "Curve", shortcut="B", help="Place start, end and two curvature handles for a cubic Bézier curve."),
                    ctx.modes.define(_MODE_HALF_CIRCLE, "Half-circle", shortcut="H", help="Place start, end and side points."),
                    ctx.modes.define(_MODE_DIMENSION, "Dimension", shortcut="D", help="Attach a passive dimension to sketch geometry."),
                    ctx.modes.define(_MODE_MESH_TRACE, "Mesh trace", help="Project faces or edges from another part into this 2D sketch."),
                    ctx.modes.define(_MODE_DUPLICATE, "Duplicate", help="Create persistent prefabs and place them once, along curves or inside faces."),
                    ctx.modes.define(_MODE_MIRROR, "Mirror", help="Complete the whole sketch or the current selection symmetrically around a two-point axis."),
                ),
                active=active_id,
            )
        except Exception:
            pass

    def _clear_transient_state_for_mode(self, ctx: Any | None, mode: str) -> None:
        if ctx is not None:
            self.services.snap._clear_pending_geometry_preview(ctx)
        else:
            self._state.pending_preview_ids = ()
            self._state.pending_preview_signature = None
        if self._state.metric_draft is not None and (mode != self._state.metric_draft.mode):
            if ctx is not None:
                self.services.metrics._validate_metric_draft(ctx)
            else:
                self._state.metric_draft = None
        if mode != _MODE_LINE:
            self._state.pending_line_start_id = None
        if mode != _MODE_POLYLINE:
            self._state.pending_polyline_last_id = None
        if mode != _MODE_RECTANGLE:
            self._state.pending_rectangle_corner_id = None
        if mode != _MODE_CIRCLE:
            self._state.pending_circle_center_id = None
        if mode != _MODE_ARC:
            self._state.pending_arc_start_id = None
            self._state.pending_arc_end_id = None
        if mode != _MODE_BEZIER:
            self._state.pending_bezier_start_id = None
            self._state.pending_bezier_end_id = None
            self._state.pending_bezier_control_1_id = None
        if mode != _MODE_HALF_CIRCLE:
            self._state.pending_half_circle_start_id = None
        if mode != _MODE_DIMENSION:
            self._state.pending_dimension_start_id = None
            self._state.pending_dimension_line_id = None
        if mode not in {_MODE_MODIFY, _MODE_DUPLICATE, _MODE_MIRROR} and ctx is not None:
            try:
                ctx.selection.clear_selection(owner_tool=self.id)
            except Exception:
                pass

    def _activate_tool_state(self, ctx: Any | None, mode: str, *, render: bool = True) -> str:
        mode = self._normalize_tool_mode(mode)
        previous_mode = self._state.active_tool
        if ctx is not None and previous_mode == _MODE_MESH_TRACE and mode != _MODE_MESH_TRACE:
            self.services.mesh_trace.deactivate(ctx, clear=True, render=False)
        if ctx is not None and previous_mode == _MODE_DUPLICATE and mode != _MODE_DUPLICATE:
            self.services.duplicate.deactivate(ctx, render=False)
        if ctx is not None and previous_mode == _MODE_MIRROR and mode != _MODE_MIRROR:
            self.services.mirror.deactivate(ctx, render=False)
        self._state.active_tool = mode
        self._clear_transient_state_for_mode(ctx, mode)
        if ctx is not None and mode == _MODE_MESH_TRACE and previous_mode != _MODE_MESH_TRACE:
            self.services.mesh_trace.activate(ctx)
        if ctx is not None and mode == _MODE_DUPLICATE and previous_mode != _MODE_DUPLICATE:
            self.services.duplicate.activate(ctx)
        if ctx is not None and mode == _MODE_MIRROR and previous_mode != _MODE_MIRROR:
            self.services.mirror.activate(ctx)
        if ctx is not None:
            try:
                ctx.modes.set(self.id, mode)
            except Exception:
                pass
            ctx.overlay.set_group_active(_TOOL_GROUP, self.services.overlay._button_id(mode))
            self.services.overlay._show_toolbox(ctx)
            self.services.overlay._sync_reports(ctx)
            self.services.rendering._render(ctx, sync_overlays=True, render=render)
        return mode

    def _state_invariant_issues(self) -> tuple[str, ...]:
        issues: list[str] = []
        if self._state.phase not in {_PHASE_PICK_HEIGHT, _PHASE_DRAW}:
            issues.append(f"unknown_phase:{self._state.phase}")
        if self._state.active_tool not in _TOOL_MODES:
            issues.append(f"unknown_tool:{self._state.active_tool}")
        if self._state.phase == _PHASE_PICK_HEIGHT and self._state.plane is not None:
            issues.append("pick_height_phase_has_plane")
        if self._state.phase == _PHASE_DRAW and (self._state.plane is None or self._state.display_plane is None):
            issues.append("draw_phase_without_locked_plane")
        if self._state.pending_line_start_id is not None:
            if self._state.active_tool != _MODE_LINE:
                issues.append("pending_line_outside_line_mode")
            if self._state.pending_line_start_id not in self._state.sketch.points:
                issues.append("pending_line_start_missing")
        if self._state.pending_polyline_last_id is not None:
            if self._state.active_tool != _MODE_POLYLINE:
                issues.append("pending_polyline_outside_polyline_mode")
            if self._state.pending_polyline_last_id not in self._state.sketch.points:
                issues.append("pending_polyline_last_missing")
        if self._state.pending_rectangle_corner_id is not None:
            if self._state.active_tool != _MODE_RECTANGLE:
                issues.append("pending_rectangle_outside_rectangle_mode")
            if self._state.pending_rectangle_corner_id not in self._state.sketch.points:
                issues.append("pending_rectangle_corner_missing")
        if self._state.pending_circle_center_id is not None:
            if self._state.active_tool != _MODE_CIRCLE:
                issues.append("pending_circle_outside_circle_mode")
            if self._state.pending_circle_center_id not in self._state.sketch.points:
                issues.append("pending_circle_center_missing")
        if self._state.pending_arc_start_id is not None:
            if self._state.active_tool != _MODE_ARC:
                issues.append("pending_arc_outside_arc_mode")
            if self._state.pending_arc_start_id not in self._state.sketch.points:
                issues.append("pending_arc_start_missing")
        if self._state.pending_arc_end_id is not None:
            if self._state.active_tool != _MODE_ARC:
                issues.append("pending_arc_end_outside_arc_mode")
            if self._state.pending_arc_end_id not in self._state.sketch.points:
                issues.append("pending_arc_end_missing")
            if self._state.pending_arc_start_id is None:
                issues.append("pending_arc_end_without_start")
        if self._state.pending_bezier_start_id is not None:
            if self._state.active_tool != _MODE_BEZIER:
                issues.append("pending_bezier_outside_bezier_mode")
            if self._state.pending_bezier_start_id not in self._state.sketch.points:
                issues.append("pending_bezier_start_missing")
        if self._state.pending_bezier_end_id is not None:
            if self._state.active_tool != _MODE_BEZIER:
                issues.append("pending_bezier_end_outside_bezier_mode")
            if self._state.pending_bezier_end_id not in self._state.sketch.points:
                issues.append("pending_bezier_end_missing")
            if self._state.pending_bezier_start_id is None:
                issues.append("pending_bezier_end_without_start")
        if self._state.pending_bezier_control_1_id is not None:
            if self._state.active_tool != _MODE_BEZIER:
                issues.append("pending_bezier_control_outside_bezier_mode")
            if self._state.pending_bezier_control_1_id not in self._state.sketch.points:
                issues.append("pending_bezier_control_missing")
            if self._state.pending_bezier_end_id is None:
                issues.append("pending_bezier_control_without_end")
        if self._state.pending_half_circle_start_id is not None:
            if self._state.active_tool != _MODE_HALF_CIRCLE:
                issues.append("pending_half_circle_outside_half_circle_mode")
            if self._state.pending_half_circle_start_id not in self._state.sketch.points:
                issues.append("pending_half_circle_start_missing")
        if self._state.pending_dimension_start_id is not None:
            if self._state.active_tool != _MODE_DIMENSION:
                issues.append("pending_dimension_outside_dimension_mode")
            if self._state.pending_dimension_start_id not in self._state.sketch.points:
                issues.append("pending_dimension_start_missing")
        if self._state.pending_dimension_line_id is not None:
            if self._state.active_tool != _MODE_DIMENSION:
                issues.append("pending_dimension_line_outside_dimension_mode")
            if self._state.pending_dimension_line_id not in self._state.sketch.lines:
                issues.append("pending_dimension_line_missing")
        return tuple(issues)

    def _pull_active_tool_from_overlay(self, ctx: Any) -> None:
        mode = self.services.overlay._mode_from_button_id(ctx.overlay.group_active.get(_TOOL_GROUP))
        if mode and mode != self._state.active_tool:
            self._activate_tool_state(ctx, mode, render=True)

    def _set_active_tool(self, ctx: Any | None, mode: str, *, reason: str = "", render: bool = True) -> None:
        if ctx is None:
            return
        mode = self._activate_tool_state(ctx, mode, render=render)
        if reason:
            ctx.status.info(f"Plan tracer mode: {self.services.overlay._label_for_tool(mode)} ({reason}).")

    def _reset(self, ctx: Any | None) -> None:
        if ctx is None:
            return
        from laserprog_studio.tool_api import plan2d

        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        pattern_budget = 120000
        board_depth = 3.0
        try:
            pattern_budget = int(self._tool._pattern_max_segments(ctx))
        except Exception:
            pass
        try:
            board_depth = float(self._tool._default_board_thickness_mm(ctx))
        except Exception:
            pass
        self._state = _PlanTrace2DState(
            view=plan2d.nearest_plan_view(ctx),
            active_tool=_MODE_POINT,
            extrusion_depth=board_depth,
            motif_preview_segment_budget=pattern_budget,
            motif_apply_segment_budget=pattern_budget,
        )
        try:
            ctx.scene_cache.rebuild(ctx, scope="snap")
        except Exception:
            pass
        self.services.selection._configure_modify_selection_api(ctx)
        self._register_creator_modes(ctx, active=_MODE_POINT)
        ctx.inspector.set_panel(self.services.overlay._panel())
        self.services.overlay._apply_panel_settings(ctx)
        self.services.overlay._show_anchor_prompt(ctx)
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True)
        ctx.status.info("Plan tracer reset. Select a scene surface to align the camera and start drawing on that face.")


__all__ = ["PlanTrace2DModeStateService"]
