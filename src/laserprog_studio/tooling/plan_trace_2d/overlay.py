# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import platform
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from laserprog_studio.tool_api.visual import OverlayActionSpec, OverlayModeSpec, OverlayToolbarSectionSpec

from .constants import (
    _ANCHOR_OVERLAY_ID,
    _DELETE_BUTTON_ID,
    _RESTORE_FACES_BUTTON_ID,
    _PATTERN_FACE_BUTTON_ID,
    _VALIDATE_ADD_BUTTON_ID,
    _VALIDATE_SUBTRACT_BUTTON_ID,
    _IMPLEMENTED_DRAW_MODES,
    _MODE_ARC,
    _MODE_BEZIER,
    _MODE_BADGE_ID,
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
    _TOOLBOX_ID,
    _TOOL_GROUP,
)
from .panel import build_plan_trace_2d_panel
from .services import _PlanTrace2DService

# V2 toolbar note:
# Plan Tracer no longer carries per-button pixel widths or short-caption hacks.
# The shared overlay builder owns sizing from semantic sections, making future
# Creator tools much easier to author: describe intent, not Qt geometry.


class PlanTrace2DOverlayService(_PlanTrace2DService):

    def __init__(self, tool: Any) -> None:
        super().__init__(tool)
        # Per-tool cache of the values most recently pushed to the inspector/overlay.
        # ``_sync_reports`` runs on every mouse move via the snap-cursor update; the
        # underlying Qt overlay/inspector setters are individually cheap but call
        # ``_replace_button_everywhere`` and bump revision counters even when the
        # value is unchanged. Caching the last-emitted text/flag per field keeps
        # mouse hover in dense sketches under one Qt write per real change.
        self._last_report_cache: dict[str, Any] = {}

    @staticmethod
    def _visual_api():
        # Lazy import keeps the built-in tool registry from re-entering while the
        # Plan Tracer service graph is being constructed. Tool code still uses
        # the public visual facade at runtime, not the private overlay module.
        from laserprog_studio.tool_api import visual

        return visual
    def _panel(self):
        return build_plan_trace_2d_panel(
            on_mode_changed=lambda _field_id, value: self._on_panel_mode_changed(value),
            on_settings_changed=lambda field_id, value: self._on_panel_settings_changed(field_id, value),
            on_action=lambda event: self._on_panel_action(event),
        )

    def _on_panel_mode_changed(self, value: Any) -> None:
        ctx = getattr(self, "_last_ctx", None)
        if ctx is None:
            self._state.active_tool = self.services.mode_state._normalize_tool_mode(value)
            return
        self.services.mode_state._set_active_tool(ctx, str(value), reason="inspector", render=True)

    def _on_panel_settings_changed(self, field_id: str, value: Any) -> None:
        ctx = getattr(self, "_last_ctx", None)
        if ctx is None:
            return
        # Mirror motif/pattern panel edits into the dedicated motif overlay so
        # both views always reflect the same state.
        self.services.motif_overlay.apply_inspector_change(ctx, str(field_id), value)
        self._apply_panel_settings(ctx)
        self._sync_reports(ctx)

    def _on_panel_action(self, event: Any) -> None:
        ctx = getattr(self, "_last_ctx", None)
        if ctx is None:
            return
        action_id = str(getattr(event, "action_id", "") or "")
        if action_id == "refresh":
            self.services.rendering._render(ctx, sync_overlays=True, render=True)
            self._sync_reports(ctx)
            return
        if action_id == "export_timings":
            self._export_timing_snapshot(ctx)
            return
        if action_id == "copy_selection":
            self.services.selection_edit.copy_selected(ctx)
            self._sync_reports(ctx)
            return
        if action_id == "paste_selection":
            self.services.selection_edit.paste_clipboard(ctx)
            return
        if action_id == "delete_selection":
            self.services.selection._delete_selected_points(ctx)
            return
        if action_id == "restore_faces":
            self.services.selection._restore_generated_faces(ctx)
            return
        if action_id == "save_draft":
            self._tool._save_current_sketch_as_draft_and_return_to_pick(ctx)
            return
        if action_id == "reset":
            self.services.mode_state._reset(ctx)
            return

    def _apply_panel_settings(self, ctx: Any) -> None:
        values = {}
        try:
            values = ctx.inspector.values()
        except Exception:
            values = {}
        try:
            ctx.snap.set_smart_snap(bool(values.get("plan_trace_2d.smart_snap", True)))
            self._state.snap_active_object_only = bool(values.get("plan_trace_2d.active_part_snap", False))
            grid_enabled = bool(values.get("plan_trace_2d.grid_snap", False))
            try:
                grid_size = max(0.001, float(values.get("plan_trace_2d.grid_step", 5.0)))
            except Exception:
                grid_size = 5.0
            if grid_enabled and grid_size >= 100000.0:
                # Repair a polluted persisted setting produced by stress tests.
                # A 100000 mm grid snaps every normal-sized face to its origin,
                # making the Plan Tracer cursor look frozen even though input is
                # flowing correctly.
                grid_enabled = False
                grid_size = 5.0
                try:
                    ctx.inspector.update_value("plan_trace_2d.grid_snap", False, notify=False)
                    ctx.inspector.update_value("plan_trace_2d.grid_step", 5.0, notify=False)
                except Exception:
                    pass
                try:
                    profiler = getattr(ctx, "profiler", None)
                    increment = getattr(profiler, "increment", None)
                    if callable(increment):
                        increment("plan_trace.settings.repaired_huge_grid")
                except Exception:
                    pass
            ctx.snap.set_grid_snap(grid_enabled)
            ctx.snap.grid_provider.grid_size = grid_size
            ctx.snap.grid_provider.enabled = grid_enabled
        except Exception:
            pass

    def _sync_overlay_palette_now(self, ctx: Any) -> None:
        """Materialise overlay-only state changes immediately in the desktop UI.

        Plan Tracer changes the visible palette at the exact moment the height
        anchor is clicked: the anchor prompt is hidden and the drawing toolbox is
        shown.  That transition must not depend on the later 3D actor refresh
        succeeding, otherwise a viewport-render exception can leave the user in
        draw phase with no way to pick Line/Circle/Point from the floating
        toolbar.  The shared Creator renderer still performs its normal overlay
        sync afterwards; this is a cheap, defensive first sync for the palette
        itself.
        """

        self.services.rendering._sync_overlays(ctx)
        try:
            values = ctx.inspector.values()
            grid_visible = bool(values.get("plan_trace_2d.grid_snap", False))
            ctx.inspector.set_visible("plan_trace_2d.grid_step", grid_visible)
        except Exception:
            pass

    def _show_anchor_prompt(self, ctx: Any) -> None:
        self._last_ctx = ctx
        ctx.overlay.hide_window(_TOOLBOX_ID)
        ctx.overlay.show_window(
            self._visual_api().OverlayWindowSpec(
                id=_ANCHOR_OVERLAY_ID,
                title="2D Plan Tracer",
                owner_tool=self.id,
                overlay_kind="palette",
                anchor="viewport_top_left",
                width_px=380,
                movable=True,
                persistent=False,
                fields=[
                    self._visual_api().OverlayFieldSpec(
                        "plan_trace_2d.anchor_prompt",
                        "",
                        "Select a scene surface to align the camera and start drawing on that face.",
                        kind="info",
                    )
                ],
                buttons=[],
            )
        )
        self._sync_overlay_palette_now(ctx)

    def _show_toolbox(self, ctx: Any) -> None:
        self._last_ctx = ctx
        ctx.overlay.hide_window(_ANCHOR_OVERLAY_ID)
        ctx.overlay.show_window(
            self._visual_api().build_command_deck_window(
                window_id=_TOOLBOX_ID,
                owner_tool=self.id,
                group_id=_TOOL_GROUP,
                sections=self._toolbar_sections(ctx),
                active_mode_id=self._button_id(self._state.active_tool),
                badge_id=_MODE_BADGE_ID,
                badge_label="Mode",
                badge_value=self._label_for_tool(self._state.active_tool),
                badge_tooltip="Current Plan Tracer drawing mode.",
                status_id="plan_trace_2d.command_status",
                status_label="Status",
                status_value=self._overlay_step_text(),
                title="Plan Tracer",
                anchor="viewport_top_left",
                width_px=0,
                persistent=True,
                cursor_offset_px=(0, 0),
            )
        )
        ctx.overlay.set_group_active(_TOOL_GROUP, self._button_id(self._state.active_tool))
        self._sync_overlay_palette_now(ctx)

    def _toolbar_sections(self, ctx: Any | None = None) -> tuple["OverlayToolbarSectionSpec", ...]:
        v = self._visual_api()
        implemented = set(_IMPLEMENTED_DRAW_MODES) | {_MODE_MODIFY, _MODE_MESH_TRACE, _MODE_DUPLICATE, _MODE_MIRROR}
        return (
            v.OverlayToolbarSectionSpec(
                "select",
                "Select",
                modes=(self._mode_spec(_MODE_MODIFY, "Modify", shortcut="Esc", implemented=True),),
            ),
            v.OverlayToolbarSectionSpec(
                "draw",
                "Draw",
                modes=(
                    self._mode_spec(_MODE_POINT, "Point", implemented=True),
                    self._mode_spec(_MODE_LINE, "Line", implemented=True),
                    self._mode_spec(_MODE_POLYLINE, "Polyline", implemented=True),
                ),
            ),
            v.OverlayToolbarSectionSpec(
                "shapes",
                "Shapes",
                modes=(
                    self._mode_spec(_MODE_RECTANGLE, "Rectangle", implemented=True),
                    self._mode_spec(_MODE_CIRCLE, "Circle", implemented=True),
                    self._mode_spec(_MODE_HALF_CIRCLE, "Half-circle", implemented=True),
                    self._mode_spec(_MODE_ARC, "Arc", implemented=_MODE_ARC in implemented),
                    self._mode_spec(_MODE_BEZIER, "Curve", implemented=_MODE_BEZIER in implemented),
                ),
            ),
            v.OverlayToolbarSectionSpec(
                "measure",
                "Measure",
                modes=(self._mode_spec(_MODE_DIMENSION, "Dimension", implemented=_MODE_DIMENSION in implemented),),
            ),
            v.OverlayToolbarSectionSpec(
                "build",
                "Build",
                modes=(
                    self._mode_spec(_MODE_MESH_TRACE, "Mesh trace", implemented=True),
                    self._mode_spec(_MODE_DUPLICATE, "Duplicate", implemented=True),
                    self._mode_spec(_MODE_MIRROR, "Mirror", implemented=True),
                ),
                actions=self._toolbar_actions(ctx),
            ),
            v.OverlayToolbarSectionSpec(
                "validation",
                "Validation",
                actions=self._validation_actions(ctx),
            ),
        )


    def _validation_actions(self, ctx: Any | None = None) -> tuple["OverlayActionSpec", ...]:
        v = self._visual_api()
        can_validate = self._state.plane is not None and bool(getattr(self._state.sketch, "faces", None))
        return (
            v.OverlayActionSpec(
                id=_VALIDATE_ADD_BUTTON_ID,
                label="Add",
                icon="sketch.face",
                tooltip="Validate the sketch and create a green board using the preference thickness.",
                enabled=can_validate,
                style="primary",
                display_label="Add",
                slot_width_px=78,
            ),
            v.OverlayActionSpec(
                id=_VALIDATE_SUBTRACT_BUTTON_ID,
                label="Subtract",
                icon="sketch.delete",
                tooltip="Subtract the sketch from touched models through their full thickness.",
                enabled=can_validate,
                style="danger",
                display_label="Subtract",
                slot_width_px=92,
            ),
        )

    def _toolbar_actions(self, ctx: Any | None = None) -> tuple["OverlayActionSpec", ...]:
        v = self._visual_api()
        motif_enabled = self._motif_button_enabled(ctx)
        return (
            v.OverlayActionSpec(
                id=_RESTORE_FACES_BUTTON_ID,
                label="Rebuild",
                icon="sketch.face",
                tooltip="Restore deleted/generated sketch faces from the existing closed boundaries.",
                enabled=self._has_suppressed_faces(),
                style="ghost",
                display_label="Rebuild",
                slot_width_px=74,
            ),
            v.OverlayActionSpec(
                id=_PATTERN_FACE_BUTTON_ID,
                label="Pattern",
                icon="sketch.face",
                tooltip=(
                    "Open the Pattern panel for the selected face. "
                    "Tip: switch to Modify mode to select the target face."
                ),
                enabled=motif_enabled,
                style="primary" if bool(getattr(self._state, "motif_overlay_visible", False)) else "ghost",
                display_label="Pattern",
                slot_width_px=70,
            ),
            v.OverlayActionSpec(
                id=_DELETE_BUTTON_ID,
                label="Delete",
                icon="sketch.delete",
                shortcut="Del",
                tooltip="Delete selected points, edges, arcs, Bezier curves or faces.",
                enabled=self._has_plan_selection(ctx),
                style="ghost",
                display_label="Delete",
                slot_width_px=70,
            ),
        )

    def _motif_button_enabled(self, ctx: Any | None) -> bool:
        """Enable Pattern only for a real Modify-selected Plan Tracer face.

        The previous permissive state made the button look actionable even when
        no face was selected.  The selection API already calls ``_sync_reports``
        on select/clear, so this can be strict without requiring a camera pan to
        refresh the toolbar.
        """

        if self._state.plane is None:
            return False
        try:
            if self.services.motif_overlay.is_open():
                return True
        except Exception:
            pass
        if ctx is None:
            return False
        try:
            return bool(self.services.motif_overlay.has_eligible_face(ctx))
        except Exception:
            return False

    def _has_suppressed_faces(self) -> bool:
        try:
            return bool(self._state.sketch.suppressed_face_signatures)
        except Exception:
            return False

    def _has_plan_selection(self, ctx: Any | None) -> bool:
        if ctx is None:
            return False
        try:
            for actor_id in ctx.selection.ids():
                actor = ctx.selection.actor(str(actor_id))
                if actor is not None and actor.owner_tool == self.id:
                    return True
        except Exception:
            return False
        return False

    def _mode_spec(self, mode: str, label: str, *, shortcut: str | None = None, implemented: bool) -> "OverlayModeSpec":
        if mode == _MODE_BEZIER and implemented:
            tooltip = "Complex curve: click start, end, then the two curvature handles."
        else:
            tooltip = "Implemented in this pass" if implemented else "Staged for a later Plan tracer pass"
        return self._visual_api().OverlayModeSpec(
            id=self._button_id(mode),
            label=label,
            icon=self._icon_for_tool(mode),
            shortcut=shortcut,
            tooltip=tooltip,
            display_label=self._display_label_for_tool(mode),
            slot_width_px=self._slot_width_for_tool(mode),
        )

    @staticmethod
    def _icon_for_tool(mode: str) -> str:
        return {
            _MODE_MODIFY: "sketch.modify",
            _MODE_DUPLICATE: "tool.add",
            _MODE_MIRROR: "tool.mirror",
            _MODE_POINT: "sketch.point",
            _MODE_LINE: "sketch.line",
            _MODE_POLYLINE: "sketch.line",
            _MODE_RECTANGLE: "sketch.rectangle",
            _MODE_CIRCLE: "sketch.circle",
            _MODE_HALF_CIRCLE: "sketch.half_circle",
            _MODE_ARC: "sketch.arc",
            _MODE_BEZIER: "sketch.arc",
            _MODE_DIMENSION: "sketch.dimension",
            _MODE_MESH_TRACE: "sketch.face",
        }.get(str(mode), "")

    @staticmethod
    def _button_id(mode: str) -> str:
        return f"plan_trace_2d.tool.{mode}"

    def _mode_from_button_id(self, button_id: str | None) -> str | None:
        prefix = "plan_trace_2d.tool."
        if not button_id or not str(button_id).startswith(prefix):
            return None
        return str(button_id)[len(prefix):]

    def _maybe_invalidate_report_cache(self, ctx: Any) -> None:
        """Drop cached values when the inspector panel/overlay manager changes.

        ``set_panel`` and tool resets rebuild the inspector value table from
        defaults; without an invalidation hook the dedupe cache would silently
        skip the first refresh and the right-hand inspector would show empty or
        stale labels. The cheap identity check keeps the hot path one dict
        lookup per call.
        """

        try:
            inspector = getattr(ctx, "inspector", None)
            overlay = getattr(ctx, "overlay", None)
            panel = getattr(inspector, "panel", None) if inspector is not None else None
            sentinel = (id(inspector) if inspector is not None else 0, id(panel) if panel is not None else 0, id(overlay) if overlay is not None else 0)
        except Exception:
            return
        if self._last_report_cache.get("_sentinel") != sentinel:
            self._last_report_cache.clear()
            self._last_report_cache["_sentinel"] = sentinel

    def _sync_reports(self, ctx: Any) -> None:
        self._maybe_invalidate_report_cache(ctx)
        plane = self._state.plane
        phase = "Pick height" if plane is None else "Draw"
        plane_text = "not locked" if plane is None else f"{plane.view.value}, anchor depth {plane.depth:.3f}"
        anchor = self._state.anchor_world
        anchor_text = "not selected" if anchor is None else f"({anchor[0]:.2f}, {anchor[1]:.2f}, {anchor[2]:.2f})"
        if self._state.editing_source_object_id:
            if str(getattr(self._state, "editing_source_kind", "")) == "plan_trace_2d_draft":
                editing_text = f"Draft {self._state.editing_source_label or self._state.editing_source_object_id} · Apply promotes it to a volume"
            else:
                editing_text = f"Editing {self._state.editing_source_label or self._state.editing_source_object_id} · extrusion {float(self._state.editing_source_extrusion_depth or 0.0):.1f} mm"
        elif self._state.editable_hover_object_id:
            editing_text = f"Editable/draft: {self._state.editable_hover_label or self._state.editable_hover_object_id} · click to edit"
        else:
            editing_text = "New volume"
        tool_text = self._label_for_tool(self._state.active_tool)
        counts_text = self._sketch_counts_text()
        # ``_has_plan_selection`` and ``_selection_summary`` both iterate the
        # entire selection. Run a single pass and reuse the result so the Qt
        # overlay sync stays cheap on mouse hover.
        selection_total, selection_text = self._selection_state(ctx)
        try:
            from .selection_measure import measure_selected_path

            selected_path = measure_selected_path(ctx, self._state.sketch, owner_tool=self.id)
            selection_length_text = selected_path.display_text() if selected_path is not None else "—"
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "overlay.selection_length.computed",
                    owner=getattr(ctx, "owner", None),
                    ctx=ctx,
                    include_selection=True,
                    include_inspector=True,
                    selection_total=selection_total,
                    selection_text=selection_text,
                    selected_path=(
                        {
                            "entity_count": selected_path.entity_count,
                            "total_length": selected_path.total_length,
                            "component_count": selected_path.component_count,
                            "closed_components": selected_path.closed_components,
                            "display_text": selected_path.display_text(),
                        }
                        if selected_path is not None
                        else None
                    ),
                    display_value=selection_length_text,
                )
            except Exception:
                pass
        except Exception as exc:
            selection_length_text = "—"
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "overlay.selection_length.exception",
                    owner=getattr(ctx, "owner", None),
                    ctx=ctx,
                    include_selection=True,
                    include_inspector=True,
                    error=repr(exc),
                )
            except Exception:
                pass
        has_selection = selection_total > 0
        status_text = self._status_text(selection_text=selection_text)
        metric_text = self._metric_text()
        perf_text = self._perf_summary_text(ctx)
        view_text = self._state.view.value
        snap_text = self._state.last_snap_label
        mode_text = self._state.active_tool
        badge_text = self._label_for_tool(self._state.active_tool)
        step_text = self._overlay_step_text()
        has_suppressed = self._has_suppressed_faces()
        try:
            grid_step_visible = bool(ctx.inspector.value("plan_trace_2d.grid_snap", False))
        except Exception:
            grid_step_visible = bool(self._last_report_cache.get("plan_trace_2d.grid_step.visible", False))

        cache = self._last_report_cache

        def _push_button(key: str, enabled: bool) -> None:
            cache_key = f"button.{key}.enabled"
            if cache.get(cache_key) == enabled:
                return
            try:
                ctx.overlay.set_button_enabled(key, enabled)
                cache[cache_key] = enabled
            except Exception:
                pass

        def _push_inspector(field_id: str, value: Any) -> None:
            cache_key = f"inspector.{field_id}"
            if cache.get(cache_key) == value:
                if field_id == "plan_trace_2d.selection_length":
                    try:
                        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                        record_selection_length_event(
                            "overlay.inspector_write.skipped_cache",
                            owner=getattr(ctx, "owner", None),
                            ctx=ctx,
                            include_selection=True,
                            include_inspector=True,
                            field_id=field_id,
                            requested=value,
                            cached=cache.get(cache_key),
                        )
                    except Exception:
                        pass
                return
            try:
                before = ctx.inspector.value(field_id, "<missing>")
                validated = ctx.inspector.set_display_value(field_id, value)
                cache[cache_key] = value
                if field_id == "plan_trace_2d.selection_length":
                    try:
                        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                        record_selection_length_event(
                            "overlay.inspector_write.done",
                            owner=getattr(ctx, "owner", None),
                            ctx=ctx,
                            include_selection=True,
                            include_inspector=True,
                            field_id=field_id,
                            requested=value,
                            before=before,
                            validated=validated,
                            cache_after=cache.get(cache_key),
                        )
                    except Exception:
                        pass
            except Exception as exc:
                if field_id == "plan_trace_2d.selection_length":
                    try:
                        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                        record_selection_length_event(
                            "overlay.inspector_write.exception",
                            owner=getattr(ctx, "owner", None),
                            ctx=ctx,
                            include_selection=True,
                            include_inspector=True,
                            field_id=field_id,
                            requested=value,
                            error=repr(exc),
                        )
                    except Exception:
                        pass

        def _push_inspector_value(field_id: str, value: Any) -> None:
            cache_key = f"inspector_value.{field_id}"
            if cache.get(cache_key) == value:
                return
            try:
                ctx.inspector.update_value(field_id, value, notify=False)
                cache[cache_key] = value
            except Exception:
                pass

        def _push_visible(field_id: str, visible: bool) -> None:
            cache_key = f"inspector_visible.{field_id}"
            if cache.get(cache_key) == visible:
                return
            try:
                ctx.inspector.set_visible(field_id, visible)
                cache[cache_key] = visible
            except Exception:
                pass

        def _push_overlay_field(window_id: str, field_id: str, value: Any) -> None:
            cache_key = f"overlay_field.{window_id}.{field_id}"
            if cache.get(cache_key) == value:
                return
            try:
                ctx.overlay.update_field(window_id, field_id, value)
                cache[cache_key] = value
            except Exception:
                pass

        can_validate = self._state.plane is not None and bool(getattr(self._state.sketch, "faces", None))
        _push_button(_DELETE_BUTTON_ID, has_selection)
        _push_button(_RESTORE_FACES_BUTTON_ID, has_suppressed)
        _push_button(_PATTERN_FACE_BUTTON_ID, self._motif_button_enabled(ctx))
        # Validation buttons are created disabled when the toolbox opens before
        # any closed face exists.  Geometry placement (not a later mode switch)
        # must make them clickable as soon as the sketch compiler creates a face.
        _push_button(_VALIDATE_ADD_BUTTON_ID, can_validate)
        _push_button(_VALIDATE_SUBTRACT_BUTTON_ID, can_validate)
        _push_inspector("plan_trace_2d.phase", phase)
        _push_inspector("plan_trace_2d.view", view_text)
        _push_inspector("plan_trace_2d.plane", plane_text)
        _push_inspector("plan_trace_2d.tool", tool_text)
        _push_inspector("plan_trace_2d.anchor", anchor_text)
        _push_inspector("plan_trace_2d.editing", editing_text)
        _push_inspector("plan_trace_2d.counts", counts_text)
        _push_inspector("plan_trace_2d.selection", selection_text)
        _push_inspector("plan_trace_2d.selection_length", selection_length_text)
        _push_inspector("plan_trace_2d.snap", snap_text)
        _push_inspector("plan_trace_2d.status", status_text)
        _push_inspector("plan_trace_2d.metric", metric_text)
        _push_inspector("plan_trace_2d.perf", perf_text)
        _push_inspector("plan_trace_2d.pattern_face", self.services.patterns.selected_face_text())
        _push_inspector("plan_trace_2d.pattern_status", self._pattern_status_text())
        _push_inspector_value("plan_trace_2d.mode", mode_text)
        _push_visible("plan_trace_2d.grid_step", grid_step_visible)
        _push_overlay_field(_TOOLBOX_ID, _MODE_BADGE_ID, badge_text)
        _push_overlay_field(_TOOLBOX_ID, "plan_trace_2d.command_status", step_text)

    def _sync_cursor_report(self, ctx: Any) -> None:
        """Lightweight report sync run on every mouse move.

        ``_sync_reports`` refreshes selection counts, button states, the badge
        label and many inspector fields. None of those change between two
        consecutive mouse-move events; the only value that does is the snap
        label/kind. Running the full report on hover dominated the Plan tracer
        snap loop in dense sketches, so the mouse-move path now only pushes the
        snap label (and any cached counterpart) through the dedupe cache below.
        """

        self._maybe_invalidate_report_cache(ctx)
        snap_text = self._state.last_snap_label
        cache = self._last_report_cache
        cache_key = "inspector.plan_trace_2d.snap"
        if cache.get(cache_key) == snap_text:
            return
        try:
            ctx.inspector.set_display_value("plan_trace_2d.snap", snap_text)
            cache[cache_key] = snap_text
        except Exception:
            pass

    def _reset_report_cache(self) -> None:
        self._last_report_cache.clear()

    def _sketch_counts_text(self) -> str:
        sketch = self._state.sketch
        return (
            f"{len(sketch.points)} point · "
            f"{len(sketch.lines)} edge · "
            f"{len(sketch.arcs)} arc · {len(getattr(sketch, 'beziers', {}))} Bezier · "
            f"{len(sketch.circles)} circle · "
            f"{len(sketch.faces)} face · "
            f"{len(sketch.dimensions)} dimension"
        )

    def _status_text(self, *, selection_text: str) -> str:
        apply_error = str(getattr(self._state, "apply_last_error", "") or "").strip()
        if apply_error:
            return f"Validation failed: {apply_error}"
        if self._state.plane is None:
            if self._state.editable_hover_object_id:
                return f"Editable Plan Tracer volume detected: {self._state.editable_hover_label or self._state.editable_hover_object_id}. Click to edit it."
            return "Pick a face or editable Plan Tracer volume to lock the 2D drawing height."
        if self._state.metric_draft is not None:
            return "Metric edit is active. Validate it or keep drawing to accept the value."
        if selection_text != "0 selected":
            return f"Modify selection: {selection_text}."
        tool = self._label_for_tool(self._state.active_tool)
        if self._state.active_tool == _MODE_MODIFY:
            return "Select, drag or delete sketch elements."
        if self._state.active_tool == _MODE_POLYLINE and self._state.pending_polyline_last_id is not None:
            return "Polyline active. Click the next point, or press Esc / double-click to finish the chain."
        return f"{tool} mode ready. Click in the viewport to place geometry."

    def _metric_text(self) -> str:
        draft = self._state.metric_draft
        if draft is None:
            return "No active metric edit."
        return f"{self._label_for_tool(draft.mode)} metric · {draft.session_id}"

    def _pattern_status_text(self) -> str:
        if self._state.plane is None:
            return "Lock a drawing plane first."
        if bool(getattr(self._state, "pattern_pick_face_active", False)):
            return "Click a face in the viewport."
        face_id = getattr(self._state, "pattern_face_id", None)
        if not face_id:
            return "Select a face, choose a pattern, then Generate."
        count = int(getattr(self._state, "pattern_generated_count", 0) or 0)
        if count > 0:
            return f"Last generation: {count} opening(s)."
        return "Face selected. Adjust parameters, then Generate."

    def _perf_summary_text(self, ctx: Any) -> str:
        snapshot = self._profiler_snapshot(ctx)
        if not snapshot:
            return "No timing samples yet."
        keys = (
            ("cursor", "plan_trace.cursor.update.avg_ms"),
            ("p95", "plan_trace.cursor.update.p95_ms"),
            ("targets", "plan_trace.cursor.targets.avg_ms"),
            ("snap", "plan_trace.cursor.smart_snap.avg_ms"),
            ("preview", "plan_trace.cursor.pending_preview.avg_ms"),
            ("render", "plan_trace.render.avg_ms"),
        )
        parts: list[str] = []
        for label, key in keys:
            value = snapshot.get(key)
            if isinstance(value, (int, float)) and float(value) > 0.0:
                parts.append(f"{label} {float(value):.2f} ms")
        moves = snapshot.get("plan_trace.cursor.moves")
        if isinstance(moves, (int, float)) and int(moves) > 0:
            parts.append(f"moves {int(moves)}")
        return " · ".join(parts) if parts else "Timing enabled; move the cursor to collect samples."

    def _export_timing_snapshot(self, ctx: Any, *, reason: str = "manual") -> Path | None:
        try:
            output_dir = Path.cwd() / "diagnostics"
            output_dir.mkdir(parents=True, exist_ok=True)
            base = output_dir / "plan_trace_2d_timings"
            detailed = self._profiler_detailed(ctx)
            snapshot = self._profiler_snapshot(ctx)
            markdown = base.with_suffix(".md")
            json_path = base.with_suffix(".json")
            csv_path = base.with_suffix(".csv")
            detailed.setdefault("plan_trace", {})
            detailed["plan_trace"].update(self._diagnostic_context(ctx, reason=reason))
            self._write_timing_markdown(markdown, detailed, snapshot, reason=reason)
            json_path.write_text(json.dumps(detailed, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
            self._write_timing_csv(csv_path, detailed)
            try:
                ctx.status.info(f"Plan Tracer diagnostics exported: {markdown} + JSON/CSV")
            except Exception:
                pass
            self._sync_reports(ctx)
            return markdown
        except Exception as exc:
            try:
                ctx.status.info(f"Plan Tracer timing export failed: {exc}")
            except Exception:
                pass
            return None

    def _diagnostic_context(self, ctx: Any, *, reason: str) -> dict[str, Any]:
        sketch = self._state.sketch
        scene_summary: dict[str, Any] = {}
        try:
            summary = ctx.scene_cache.summary()
            scene_summary = {
                "version": int(getattr(summary, "version", 0)),
                "valid": bool(getattr(summary, "valid", False)),
                "scope": str(getattr(summary, "scope", "")),
                "points": int(getattr(summary, "points", 0)),
                "segments": int(getattr(summary, "segments", 0)),
                "bounds": int(getattr(summary, "bounds", 0)),
                "extra_targets": int(getattr(summary, "extra_targets", 0)),
                "tool_points": int(getattr(summary, "tool_points", 0)),
                "tool_segments": int(getattr(summary, "tool_segments", 0)),
                "ui_targets": int(getattr(summary, "ui_targets", 0)),
            }
        except Exception:
            scene_summary = {}
        try:
            from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import plan_trace_input_diagnostics_path

            input_diag_path = str(plan_trace_input_diagnostics_path())
        except Exception:
            input_diag_path = "diagnostics/plan_trace_input_debug.jsonl"
        try:
            from laserprog_studio.diagnostics.projected_overlay_debug import projected_overlay_diagnostics_path, projected_overlay_renderer_snapshot

            projected_diag_path = str(projected_overlay_diagnostics_path())
            projected_renderer = projected_overlay_renderer_snapshot(getattr(ctx, "owner", None), self.id)
        except Exception:
            projected_diag_path = "diagnostics/projected_overlay_debug.jsonl"
            projected_renderer = {}
        try:
            from laserprog_studio.diagnostics.plan_trace_selection_length_debug import selection_length_diagnostics_path, selection_length_summary_path

            selection_length_diag_path = str(selection_length_diagnostics_path())
            selection_length_summary = str(selection_length_summary_path())
        except Exception:
            selection_length_diag_path = "diagnostics/plan_trace_selection_length_debug.jsonl"
            selection_length_summary = "diagnostics/plan_trace_selection_length_debug.md"
        return {
            "reason": str(reason),
            "input_diagnostics": input_diag_path,
            "projected_overlay_diagnostics": projected_diag_path,
            "selection_length_diagnostics": selection_length_diag_path,
            "selection_length_summary": selection_length_summary,
            "projected_overlay_renderer": projected_renderer,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "active_tool": str(self._state.active_tool),
            "phase": str(self._state.phase),
            "view": str(getattr(self._state.view, "value", self._state.view)),
            "plane_locked": self._state.plane is not None,
            "pending_preview_ids": tuple(str(value) for value in getattr(self._state, "pending_preview_ids", ()) or ()),
            "sketch": {
                "points": len(sketch.points),
                "lines": len(sketch.lines),
                "arcs": len(sketch.arcs),
                "beziers": len(getattr(sketch, "beziers", {})),
                "circles": len(sketch.circles),
                "faces": len(sketch.faces),
                "dimensions": len(sketch.dimensions),
                "suppressed_faces": len(getattr(sketch, "suppressed_face_signatures", ()) or ()),
            },
            "scene_cache": scene_summary,
        }

    def _write_timing_markdown(self, output_path: Path, detailed: dict[str, Any], snapshot: dict[str, Any], *, reason: str) -> None:
        prefixes = ("plan_trace.", "plan2d.", "snap.", "scene_cache.", "render.", "drag.", "creator_ui.", "projected_drawing_2d.")
        counters = dict(detailed.get("counters", {}) or {})
        values = dict(detailed.get("values", {}) or {})
        gauges = dict(detailed.get("gauges", {}) or {})
        slow_events = list(detailed.get("slow_events", []) or [])
        context = dict(detailed.get("plan_trace", {}) or {})
        sketch = dict(context.get("sketch", {}) or {})
        scene_cache = dict(context.get("scene_cache", {}) or {})
        hot = [
            (name, data)
            for name, data in counters.items()
            if any(str(name).startswith(prefix) for prefix in prefixes)
        ]
        hot_by_total = sorted(hot, key=lambda item: float(item[1].get("total_ms", 0.0) or 0.0), reverse=True)[:30]
        hot_by_p95 = sorted(hot, key=lambda item: float(item[1].get("p95_ms", 0.0) or 0.0), reverse=True)[:20]
        lines = [
            "# Plan Tracer 2D diagnostic report",
            "",
            f"- reason: {reason}",
            f"- exported_at: {context.get('exported_at', '?')}",
            f"- active_tool: {context.get('active_tool', '?')}",
            f"- phase: {context.get('phase', '?')}",
            f"- plane_locked: {context.get('plane_locked', '?')}",
            f"- input_diagnostics: {context.get('input_diagnostics', 'diagnostics/plan_trace_input_debug.jsonl')}",
            f"- projected_overlay_diagnostics: {context.get('projected_overlay_diagnostics', 'diagnostics/projected_overlay_debug.jsonl')}",
            f"- selection_length_diagnostics: {context.get('selection_length_diagnostics', 'diagnostics/plan_trace_selection_length_debug.jsonl')}",
            f"- selection_length_summary: {context.get('selection_length_summary', 'diagnostics/plan_trace_selection_length_debug.md')}",
            "",
            "## Sketch",
            "",
        ]
        if sketch:
            lines.extend(f"- {key}: {value}" for key, value in sketch.items())
        else:
            lines.append("- no sketch context")
        lines.extend(["", "## Scene cache", ""])
        if scene_cache:
            lines.extend(f"- {key}: {value}" for key, value in scene_cache.items())
        else:
            lines.append("- no scene-cache context")
        projected_renderer = dict(context.get("projected_overlay_renderer", {}) or {})
        lines.extend(["", "## Projected Drawing 2D renderer", ""])
        if projected_renderer:
            for key, value in projected_renderer.items():
                lines.append(f"- {key}: {value}")
        else:
            lines.append("- no renderer snapshot available")
        lines.extend(["", "## Overlay pipeline state", ""])
        try:
            live = dict(projected_renderer.get("live_actor_audit", {}) or {})
            generated = int(sketch.get("points", 0) or 0) + int(sketch.get("lines", 0) or 0) + int(sketch.get("arcs", 0) or 0) + int(sketch.get("beziers", 0) or 0) + int(sketch.get("circles", 0) or 0) + int(sketch.get("faces", 0) or 0)
            manager_count = int(projected_renderer.get("actors", 0) or 0)
            batches = int(projected_renderer.get("batches", 0) or 0)
            handles = int(projected_renderer.get("handles", 0) or 0)
            present = int(live.get("present", 0) or 0)
            missing = int(live.get("missing", 0) or 0)
            visible = int(live.get("visible", 0) or 0)
            lines.extend([
                f"- tool_sketch_generated_items: {generated}",
                f"- projected_renderer_actor_objects: {manager_count}",
                f"- projected_batches: {batches}",
                f"- projected_handles: {handles}",
                f"- live_vtk_present_actors: {present}",
                f"- live_vtk_missing_actors: {missing}",
                f"- live_vtk_visible_actors: {visible}",
                f"- likely_breakpoint: {'generation_or_bridge' if manager_count <= 0 else 'vtk_attachment_or_visibility' if present <= 0 or missing > 0 else 'projection_or_depth_or_visibility' if visible <= 0 else 'unknown_viewport_composition'}",
            ])
            if live.get("samples"):
                lines.append(f"- live_actor_samples: {live.get('samples')}")
        except Exception as exc:
            lines.append(f"- pipeline summary unavailable: {type(exc).__name__}")
        lines.extend([
            "",
            "## Most expensive counters by total time",
            "",
            "| counter | count | total ms | avg ms | p95 ms | max ms |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        if hot_by_total:
            for name, data in hot_by_total:
                lines.append(
                    f"| `{name}` | {int(data.get('count', 0) or 0)} | "
                    f"{float(data.get('total_ms', 0.0) or 0.0):.3f} | "
                    f"{float(data.get('avg_ms', 0.0) or 0.0):.3f} | "
                    f"{float(data.get('p95_ms', 0.0) or 0.0):.3f} | "
                    f"{float(data.get('max_ms', 0.0) or 0.0):.3f} |"
                )
        else:
            lines.append("| no samples | 0 | 0 | 0 | 0 | 0 |")
        lines.extend([
            "",
            "## Worst jitter by p95",
            "",
            "| counter | count | p95 ms | max ms | last ms |",
            "|---|---:|---:|---:|---:|",
        ])
        if hot_by_p95:
            for name, data in hot_by_p95:
                lines.append(
                    f"| `{name}` | {int(data.get('count', 0) or 0)} | "
                    f"{float(data.get('p95_ms', 0.0) or 0.0):.3f} | "
                    f"{float(data.get('max_ms', 0.0) or 0.0):.3f} | "
                    f"{float(data.get('last_ms', 0.0) or 0.0):.3f} |"
                )
        else:
            lines.append("| no samples | 0 | 0 | 0 | 0 |")
        lines.extend(["", "## Slow events", ""])
        if slow_events:
            for event in slow_events[-40:]:
                lines.append(f"- `{event.get('name')}`: {float(event.get('elapsed_ms', 0.0) or 0.0):.3f} ms at +{event.get('at_s', '?')} s")
        else:
            lines.append("- no slow event above profiler threshold")
        lines.extend(["", "## Values and gauges", ""])
        raw_keys = sorted(key for key in {**values, **gauges, **snapshot} if any(str(key).startswith(prefix) for prefix in prefixes))
        if raw_keys:
            for key in raw_keys:
                value = values.get(key, gauges.get(key, snapshot.get(key)))
                lines.append(f"- `{key}`: {value}")
        else:
            lines.append("- No profiler samples collected yet. Move the mouse in Plan Tracer, draw or drag some elements, then export again.")
        lines.extend([
            "",
            "## Files to send",
            "",
            "Send `diagnostics/plan_trace_selection_length_debug.jsonl`, `diagnostics/plan_trace_selection_length_debug.md`, `diagnostics/plan_trace_2d_timings.md`, `diagnostics/plan_trace_2d_timings.json`, `diagnostics/plan_trace_2d_timings.csv`, `diagnostics/plan_trace_input_debug.jsonl`, and the normal app log.",
        ])
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _write_timing_csv(output_path: Path, detailed: dict[str, Any]) -> None:
        counters = dict(detailed.get("counters", {}) or {})
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("name", "count", "total_ms", "avg_ms", "min_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "last_ms"))
            for name, data in sorted(counters.items()):
                writer.writerow((
                    name,
                    int(data.get("count", 0) or 0),
                    f"{float(data.get('total_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('avg_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('min_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('p50_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('p95_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('p99_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('max_ms', 0.0) or 0.0):.6f}",
                    f"{float(data.get('last_ms', 0.0) or 0.0):.6f}",
                ))

    @staticmethod
    def _profiler_snapshot(ctx: Any) -> dict[str, Any]:
        profiler = getattr(ctx, "profiler", None)
        snapshot = getattr(profiler, "snapshot", None)
        if not callable(snapshot):
            return {}
        try:
            data = snapshot()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _profiler_detailed(ctx: Any) -> dict[str, Any]:
        profiler = getattr(ctx, "profiler", None)
        detailed = getattr(profiler, "snapshot_detailed", None)
        if callable(detailed):
            try:
                data = detailed()
                if isinstance(data, dict):
                    return dict(data)
            except Exception:
                pass
        return {"values": {}, "gauges": {}, "counters": {}, "slow_events": []}

    def _selection_summary(self, ctx: Any) -> str:
        return self._selection_state(ctx)[1]

    def _selection_state(self, ctx: Any) -> tuple[int, str]:
        """Return ``(total_owned_selection, summary_text)`` in one pass.

        The mouse-hover report sync needs both the Delete button enable flag
        (``total > 0``) and the human-readable summary; running ``selection.ids()``
        twice and looking up each actor twice was a measurable chunk of the
        snap-loop cost.
        """

        counts: dict[str, int] = {}
        try:
            actor_ids = tuple(ctx.selection.ids())
        except Exception:
            actor_ids = ()
        for actor_id in actor_ids:
            try:
                actor = ctx.selection.actor(str(actor_id))
            except Exception:
                actor = None
            if actor is None or actor.owner_tool != self.id:
                continue
            role = str(actor.metadata.get("plan_trace_role", "item") or "item")
            counts[role] = counts.get(role, 0) + 1
        total = sum(counts.values())
        if total <= 0:
            return 0, "0 selected"
        order = ("point", "edge", "arc", "circle", "face", "dimension")
        parts = [f"{counts[role]} {role}(s)" for role in order if counts.get(role)]
        for role in sorted(set(counts) - set(order)):
            parts.append(f"{counts[role]} {role}(s)")
        return total, ", ".join(parts)

    def _overlay_step_text(self) -> str:
        if self._state.plane is None:
            return f"Click anchor height point · {self._state.view.value} view"
        return f"Anchor height locked · {self._state.view.value} view"

    def _overlay_mode_text(self) -> str:
        if self._state.plane is None:
            return f"Selected tool: {self._label_for_tool(self._state.active_tool)}"
        return f"Selected tool: {self._label_for_tool(self._state.active_tool)} · Snap {self._state.last_snap_kind} · Constraint {self._state.last_constraint_label} · {len(self._state.points)} point(s) · {len(self._state.sketch.lines)} edge(s) · {len(self._state.sketch.arcs)} arc(s) · {len(getattr(self._state.sketch, "beziers", {}))} Bezier curve(s) · {len(self._state.sketch.faces)} face(s) · {len(self._state.sketch.dimensions)} dimension(s)"

    @staticmethod
    def _display_label_for_tool(mode: str) -> str:
        return {
            "modify": "Modify",
            "line": "Line",
            "polyline": "Polyline",
            "rectangle": "Rectangle",
            "circle": "Circle",
            "arc": "Arc",
            "bezier": "Curve",
            "half_circle": "Half-circle",
            "point": "Point",
            "dimension": "Dimension",
            "mesh_trace": "Mesh trace",
            "duplicate": "Dup.",
            "mirror": "Mir.",
        }.get(str(mode), str(mode).title())

    @staticmethod
    def _slot_width_for_tool(mode: str) -> int:
        return {
            "modify": 72,
            "point": 68,
            "line": 64,
            "polyline": 78,
            "rectangle": 86,
            "circle": 70,
            "arc": 55,
            "bezier": 54,
            "half_circle": 86,
            "dimension": 86,
            "mesh_trace": 86,
            "duplicate": 82,
            "mirror": 54,
        }.get(str(mode), 72)

    @staticmethod
    def _label_for_tool(mode: str) -> str:
        return {
            "modify": "Modify",
            "line": "Line",
            "polyline": "Polyline",
            "rectangle": "Rectangle",
            "circle": "Circle",
            "arc": "Arc",
            "bezier": "Curve",
            "half_circle": "Half-circle",
            "point": "Point",
            "dimension": "Dimension",
            "mesh_trace": "Mesh trace",
            "duplicate": "Duplicate",
            "mirror": "Mirror",
        }.get(str(mode), str(mode).title())


__all__ = ["PlanTrace2DOverlayService"]
