# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import replace
from typing import Any

from laserprog_studio.planar_tools import PlanarEditMode, VentPathDraft, make_locked_plane, plane_to_world, world_to_plane
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, MouseButton, ToolEvent, ToolEventType, ToolSpec
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR

from .vent_generator import (
    CUSTOM_PRESET_ID,
    VentGeneratorSettings,
    VentRouteMachine,
    apply_settings_to_payload,
    build_vent_generator_panel,
    overlay_action_from_button,
    overlay_mode_from_button,
    preflight_vent_apply_mesh,
    clear_vent_creator_visuals,
    sync_vent_feedback,
    sync_vent_route_visuals,
    validate_vent_apply_payload,
    vent_report_text,
    vent_route_summary,
    values_for_vent_preset,
    vent_preset_description,
    vent_selected_point_text,
)
from .vent_generator.acoustics import estimate_vent_acoustics
from .vent_generator.snap import (
    VENT_ROUTE_API_SNAP_RADIUS_PX,
    VENT_ROUTE_SNAP_TOLERANCE,
    snap_vent_route_point,
    vent_route_alignment_targets,
)
from .vent_generator.diagnostics import (
    export_vent_timings,
    increment_perf as _increment_perf,
    measure_perf as _measure_perf,
    set_perf_value as _set_perf_value,
    vent_perf_summary_text,
)



class VentGeneratorCreatorTool(CreatorTool):
    """Creator API runtime for the Vent Generator workflow.

    The tool owns its declarative inspector, validated settings and a pure
    Python route state machine. The Qt planar services provide rich viewport
    picking/snap when available, while headless Creator events exercise the same
    ADD/MOD/SUPP/RST route rules.
    """

    id = TOOL_VENT_GENERATOR
    label = "Vent generator"

    def __init__(self) -> None:
        self._headless_payload: VentPathDraft | None = None

    @staticmethod
    def _planar_controller(ctx: Any) -> Any | None:
        owner = getattr(ctx, "owner", None)
        return getattr(owner, "planar_tool_controller", None) if owner is not None else None

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        try:
            ctx.scene_cache.rebuild(ctx, scope="snap")
        except Exception:
            pass
        self._headless_payload = None
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_face("pick_plane", "Pick plane", help="Click a model face or use the current view to lock the vent drawing plane."),
                ctx.workflow.step("draw_path", "Draw route", help="Add waypoints on the locked plane, then use Modify/Delete to clean the path."),
                ctx.workflow.step("apply_mesh", "Apply duct", help="Generate the printable duct mesh when the status is ready.", optional=True),
            ),
        )
        ctx.modes.register(
            self.id,
            (
                ctx.modes.define("ADD", "Add", shortcut="A", help="Add route waypoints."),
                ctx.modes.define("MOD", "Modify", shortcut="M", help="Move waypoints and tune selected bends."),
                ctx.modes.define("SUPP", "Delete", shortcut="Del", help="Remove route waypoints."),
                ctx.modes.define("RST", "Reset", shortcut="R", help="Clear the route."),
            ),
            active="ADD",
        )
        ctx.inspector.set_panel(
            build_vent_generator_panel(
                on_mode_changed=lambda field_id, value: self._set_mode(ctx, value),
                on_values_changed=lambda field_id, value: self._on_values_changed(ctx, field_id=field_id),
                on_preset_changed=lambda field_id, value: self._on_preset_changed(ctx, value),
                on_action=lambda event: self._handle_action(ctx, event),
            )
        )
        self._publish_settings(ctx)
        self._apply_snap_settings(ctx)
        controller = self._planar_controller(ctx)
        if controller is not None and callable(getattr(controller, "initialize_vent_generator_tool", None)):
            controller.initialize_vent_generator_tool()
        else:
            self._open_headless_state(ctx)
        self._sync_from_payload(ctx)
        self._refresh_ui_state(ctx)
        self._sync_acoustic_readouts(ctx)
        self._sync_report(ctx, "Vent generator ready. Pick a plane, then add route waypoints.")
        self._sync_view_feedback(ctx, "Vent generator ready. Pick a plane, then add route waypoints.")
        ctx.status.info("Vent generator ready. Draw the route, then apply when the duct is valid.")

    def on_close(self, ctx: Any) -> None:
        controller = self._planar_controller(ctx)
        if controller is not None and callable(getattr(controller, "clear_planar_tool_state", None)):
            controller.clear_planar_tool_state(restore_previous_view=True)
        else:
            owner = getattr(ctx, "owner", None)
            state = getattr(owner, "planar_tool_state", None) if owner is not None else None
            if state is not None and callable(getattr(state, "end", None)):
                state.end()
        try:
            clear_vent_creator_visuals(ctx)
        except Exception:
            pass
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import clear_creator_viewport_ui

                clear_creator_viewport_ui(owner, self.id, render=True)
            except Exception:
                pass
        self._headless_payload = None
        self._clear_settings(ctx)
        ctx.inspector.clear()

    def on_apply(self, ctx: Any) -> bool:
        with _measure_perf(ctx, "vent.apply.total"):
            return self._on_apply_measured(ctx)

    def _on_apply_measured(self, ctx: Any) -> bool:
        self._on_values_changed(ctx)
        payload = self._payload(ctx)
        preflight = preflight_vent_apply_mesh(payload)
        if not preflight.ok:
            self._sync_report(ctx, preflight.message)
            self._sync_apply_check(ctx, preflight)
            self._sync_view_feedback(ctx, preflight.message)
            ctx.status.warning(preflight.message)
            return False
        controller = self._planar_controller(ctx)
        if controller is not None and callable(getattr(controller, "ensure_preview_before_apply", None)):
            ok = bool(controller.ensure_preview_before_apply())
            if not ok:
                message = "Vent mesh could not be staged in the scene."
                self._sync_report(ctx, message)
                self._sync_apply_check(ctx, preflight, override_message=message, ok=False)
                self._sync_view_feedback(ctx, message)
                ctx.status.warning(message)
                return False
            self._sync_report(ctx, preflight.summary)
            self._sync_apply_check(ctx, preflight)
            self._sync_view_feedback(ctx, preflight.summary)
            return True
        self._sync_report(ctx, preflight.summary)
        self._sync_apply_check(ctx, preflight)
        self._sync_view_feedback(ctx, preflight.summary)
        return True

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        event_type = str(getattr(getattr(event, "type", None), "value", getattr(event, "type", "event"))).lower()
        _increment_perf(ctx, f"vent.event.{event_type}")
        with _measure_perf(ctx, "vent.event.total"):
            with _measure_perf(ctx, f"vent.event.{event_type}.total"):
                return self._on_event_measured(event, ctx)

    def _on_event_measured(self, event: ToolEvent, ctx: Any) -> bool:
        """Headless/world-position route editing for Creator API tests and hosts.

        The desktop Qt path continues to provide precise picking through the
        planar controller. When no controller is present, this method gives the
        tool a complete, testable route state machine instead of being a passive
        inspector-only shell.
        """

        controller = self._planar_controller(ctx)
        if controller is not None and getattr(event, "raw", None) is not None:
            return False
        if event.is_escape:
            self._set_mode(ctx, "ADD")
            return True
        if event.is_delete:
            payload = self._payload(ctx)
            if payload is not None and getattr(payload, "selected_index", None) is not None:
                point = payload.waypoints[int(payload.selected_index)]
                self._machine(ctx).delete_point(point)
                self._after_route_edit(ctx, "Selected waypoint deleted.")
                return True
            self._set_mode(ctx, "SUPP")
            return True
        if event.type not in {ToolEventType.MOUSE_RELEASE, ToolEventType.MOUSE_MOVE} or event.world_pos is None:
            return False
        machine = self._machine(ctx)
        point = machine.world_to_plane(event.world_pos)
        if event.type is ToolEventType.MOUSE_MOVE and machine.mode is PlanarEditMode.MOD and getattr(machine.payload, "selected_index", None) is not None:
            result = machine.move_selected(point)
        elif event.type is ToolEventType.MOUSE_RELEASE and event.button in {MouseButton.LEFT, MouseButton.NONE}:
            result = machine.click_plane(point)
        else:
            return False
        if result.handled:
            self._after_route_edit(ctx, result.message)
        return bool(result.handled)

    def _open_headless_state(self, ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        state = getattr(owner, "planar_tool_state", None) if owner is not None else None
        plane = make_locked_plane("top")
        payload = VentPathDraft(plane)
        apply_settings_to_payload(payload, self._settings(ctx))
        if state is None:
            self._headless_payload = payload
            return
        try:
            state.begin(tool_id=self.id, view="top", plane=plane, previous_camera_view_mode="free")
        except Exception:
            pass
        state.payload = payload
        self._headless_payload = None

    def _settings(self, ctx: Any) -> VentGeneratorSettings:
        return VentGeneratorSettings.from_values(ctx.inspector.values())

    def _publish_settings(self, ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        try:
            setattr(owner, "vent_generator_settings", self._settings(ctx).as_values())
        except Exception:
            pass

    @staticmethod
    def _clear_settings(ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        try:
            if hasattr(owner, "vent_generator_settings"):
                delattr(owner, "vent_generator_settings")
        except Exception:
            pass

    def _apply_snap_settings(self, ctx: Any) -> None:
        """Keep Vent snapping isolated from the global/grid snap stack."""

        settings = self._settings(ctx)
        # Vent uses the public smart-snap API for scene geometry, but filters out
        # tool actors/temp preview targets when querying.  Grid remains disabled:
        # route cleanliness comes from scene snap + alignment guides, not rounding.
        try:
            ctx.snap.set_smart_snap(bool(settings.smart_snap))
            ctx.snap.set_grid_snap(False)
            ctx.snap.grid_provider.enabled = False
        except Exception:
            pass
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                setattr(owner, "vent_route_smart_snap_enabled", bool(settings.smart_snap))
                setattr(owner, "grid_snap_enabled", False)
                setattr(owner, "smart_snap_enabled", False)
            except Exception:
                pass

    def _payload(self, ctx: Any) -> VentPathDraft | None:
        owner = getattr(ctx, "owner", None)
        state = getattr(owner, "planar_tool_state", None) if owner is not None else None
        payload = getattr(state, "payload", None) if state is not None else None
        if isinstance(payload, VentPathDraft):
            return payload
        return self._headless_payload if isinstance(self._headless_payload, VentPathDraft) else None

    def _machine(self, ctx: Any) -> VentRouteMachine:
        payload = self._payload(ctx)
        if payload is None:
            self._open_headless_state(ctx)
            payload = self._payload(ctx)
        if payload is None:
            payload = VentPathDraft(make_locked_plane("top"))
            apply_settings_to_payload(payload, self._settings(ctx))
            self._headless_payload = payload
        return VentRouteMachine(payload, tolerance=3.0)

    def _apply_values_to_payload(self, ctx: Any) -> None:
        payload = self._payload(ctx)
        if payload is not None:
            apply_settings_to_payload(payload, self._settings(ctx))

    def _on_values_changed(self, ctx: Any, *, field_id: str | None = None, from_preset: bool = False) -> None:
        with _measure_perf(ctx, "vent.values_changed.total"):
            return self._on_values_changed_measured(ctx, field_id=field_id, from_preset=from_preset)

    def _on_values_changed_measured(self, ctx: Any, *, field_id: str | None = None, from_preset: bool = False) -> None:
        if field_id and not from_preset and field_id not in {"quick_preset", "smart_snap"}:
            self._mark_custom_preset(ctx)
        self._publish_settings(ctx)
        self._apply_snap_settings(ctx)
        self._apply_values_to_payload(ctx)
        self._refresh_ui_state(ctx)
        self._sync_acoustic_readouts(ctx)
        controller = self._planar_controller(ctx)
        if controller is not None:
            for name, kwargs in (
                ("refresh_generated_preview_if_ready", {}),
                ("draw_planar_preview", {"render": True}),
                ("update_planar_tool_report", {}),
            ):
                method = getattr(controller, name, None)
                if not callable(method):
                    continue
                try:
                    method(**kwargs)
                except TypeError:
                    method()
                except Exception:
                    pass
        self._sync_report(ctx)
        self._sync_view_feedback(ctx)


    def _on_preset_changed(self, ctx: Any, value: Any) -> None:
        preset_id = str(value or CUSTOM_PRESET_ID)
        updates = values_for_vent_preset(preset_id)
        if not updates:
            try:
                ctx.inspector.set_display_value("preset_help", vent_preset_description(CUSTOM_PRESET_ID))
            except Exception:
                pass
            self._on_values_changed(ctx, field_id="quick_preset", from_preset=True)
            return
        for field_id, field_value in updates.items():
            try:
                if field_id == "preset_help":
                    ctx.inspector.set_display_value(field_id, field_value)
                else:
                    ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        self._on_values_changed(ctx, field_id="quick_preset", from_preset=True)
        try:
            ctx.status.info(f"Vent preset loaded: {ctx.inspector.value('quick_preset')}.")
        except Exception:
            pass

    def _mark_custom_preset(self, ctx: Any) -> None:
        try:
            if ctx.inspector.value("quick_preset", CUSTOM_PRESET_ID) != CUSTOM_PRESET_ID:
                ctx.inspector.update_value("quick_preset", CUSTOM_PRESET_ID, notify=False)
                ctx.inspector.set_display_value("preset_help", "Custom values — dimensions were edited after loading a preset.")
        except Exception:
            pass

    def _reset_to_defaults(self, ctx: Any) -> None:
        defaults = VentGeneratorSettings().as_values()
        defaults.update({
            "quick_preset": CUSTOM_PRESET_ID,
            "preset_help": vent_preset_description(CUSTOM_PRESET_ID),
            "target_length": 0.0,
            "curve_radius": 0.0,
            "curve_strength": 0.0,
        })
        for field_id, value in defaults.items():
            try:
                if field_id == "preset_help":
                    ctx.inspector.set_display_value(field_id, value)
                else:
                    ctx.inspector.update_value(field_id, value, notify=False)
            except Exception:
                pass
        self._apply_values_to_payload(ctx)

    def _start_over(self, ctx: Any) -> None:
        self._reset_to_defaults(ctx)
        self._reset_path(ctx, message="Started over with default duct settings. Add a new inlet point.")

    def _set_mode(self, ctx: Any, value: Any) -> None:
        mode = VentRouteMachine.normalize_mode(value)
        if mode is PlanarEditMode.RST:
            self._reset_path(ctx, message="Route reset. Add new waypoints to preview the duct.")
            return
        try:
            ctx.modes.set(self.id, mode.value)
        except Exception:
            pass
        try:
            ctx.inspector.update_value("mode", mode.value, notify=False)
        except Exception:
            pass
        controller = self._planar_controller(ctx)
        if controller is not None and callable(getattr(controller, "set_payload_mode", None)):
            try:
                controller.set_payload_mode(mode.value)
            except Exception:
                pass
        else:
            payload = self._payload(ctx)
            if payload is not None:
                VentRouteMachine(payload).set_mode(mode)
        self._after_route_edit(ctx, f"Mode: {mode.value}")

    def _handle_action(self, ctx: Any, event: Any) -> None:
        action_id = str(getattr(event, "action_id", "") or "")
        if action_id == "reset_path":
            self._reset_path(ctx)
            return
        if action_id == "start_over":
            self._start_over(ctx)
            return
        if action_id == "apply_mesh":
            ok = self.on_apply(ctx)
            ctx.status.info("Vent mesh applied." if ok else "Vent mesh cannot be applied yet.")
            return
        if action_id == "export_timings":
            self._export_timings(ctx, reason="manual")
            return
        self._on_values_changed(ctx)
        ctx.status.info("Vent generator preview refreshed.")

    def _reset_path(self, ctx: Any, *, message: str = "Route reset. Add new waypoints to preview the duct.") -> None:
        controller = self._planar_controller(ctx)
        if controller is not None and callable(getattr(controller, "set_payload_mode", None)):
            try:
                controller.set_payload_mode("RST")
            except Exception:
                pass
        payload = self._payload(ctx)
        if payload is not None:
            VentRouteMachine(payload).set_mode(PlanarEditMode.RST)
        try:
            ctx.modes.set(self.id, "ADD")
            ctx.inspector.update_value("mode", "ADD", notify=False)
        except Exception:
            pass
        self._after_route_edit(ctx, message)
        ctx.status.info(message)

    def _sync_from_payload(self, ctx: Any) -> None:
        payload = self._payload(ctx)
        if payload is None:
            return
        self._apply_values_to_payload(ctx)

    def _after_route_edit(self, ctx: Any, message: str = "") -> None:
        with _measure_perf(ctx, "vent.route_edit.after.total"):
            return self._after_route_edit_measured(ctx, message)

    def _after_route_edit_measured(self, ctx: Any, message: str = "") -> None:
        self._publish_settings(ctx)
        self._apply_snap_settings(ctx)
        controller = self._planar_controller(ctx)
        if controller is not None:
            for name, kwargs in (
                ("refresh_generated_preview_if_ready", {}),
                ("draw_planar_preview", {"render": True}),
                ("update_planar_tool_report", {}),
                ("_update_preview_button_state", {}),
            ):
                method = getattr(controller, name, None)
                if not callable(method):
                    continue
                try:
                    method(**kwargs)
                except TypeError:
                    method()
                except Exception:
                    pass
        self._refresh_ui_state(ctx)
        self._sync_acoustic_readouts(ctx)
        self._sync_report(ctx, message or None)
        self._sync_view_feedback(ctx, message or None)

    @staticmethod
    def _vent_validation_fields() -> tuple[str, ...]:
        return (
            "route_summary",
            "section_area",
            "rect_width",
            "rect_height",
            "wall_thickness",
            "flare_factor",
            "vent_report",
            "apply_check",
        )

    def _sync_apply_check(self, ctx: Any, check: Any | None = None, *, override_message: str | None = None, ok: bool | None = None) -> None:
        payload = self._payload(ctx)
        check = validate_vent_apply_payload(payload) if check is None else check
        message = str(override_message or getattr(check, "summary", "") or getattr(check, "message", "") or "Vent route is not ready.")
        valid = bool(getattr(check, "ok", False) if ok is None else ok)
        try:
            ctx.inspector.set_display_value("apply_check", message)
        except Exception:
            pass
        for field_id in self._vent_validation_fields():
            try:
                ctx.inspector.clear_error(field_id)
            except Exception:
                pass
        if not valid:
            errors = dict(getattr(check, "field_errors", {}) or {})
            if not errors:
                errors = {"apply_check": message}
            for field_id, error in errors.items():
                try:
                    ctx.inspector.set_error(str(field_id), str(error))
                except Exception:
                    pass
            try:
                ctx.inspector.set_error("apply_check", message)
            except Exception:
                pass
        try:
            ctx.inspector.update_field_state("vent_actions", enabled=valid or payload is not None, visible=True)
        except Exception:
            pass


    @staticmethod
    def _build_mode_summary_from_settings(settings: VentGeneratorSettings) -> str:
        if not settings.is_rectangle:
            return "Round pipe · imported-project sweep, no rectangular wall-only mode."
        if bool(settings.fill_area):
            return "Solid fill block · bounding stock with the airway cut through it."
        return "Wall-only rectangular duct · generated walls around an open airway."

    @staticmethod
    def _compact_route_guide_from_settings(settings: VentGeneratorSettings) -> str:
        if not settings.is_rectangle:
            return "Compact guide unavailable for round pipe presets."
        width = max(float(settings.rect_width), 0.001)
        wall = max(float(settings.wall_thickness), 0.001)
        compact_pitch = width + wall
        separate_pitch = width + 2.0 * wall
        return (
            f"Compact pitch ≥ {compact_pitch:.1f} mm for one shared wall; "
            f"separate runs ≥ {separate_pitch:.1f} mm. Inner airway width: {width:.1f} mm."
        )

    def _refresh_ui_state(self, ctx: Any) -> None:
        with _measure_perf(ctx, "vent.ui.refresh_state"):
            return self._refresh_ui_state_measured(ctx)

    def _refresh_ui_state_measured(self, ctx: Any) -> None:
        settings = self._settings(ctx)
        payload = self._payload(ctx)
        selected = False
        selected_curve: tuple[float, float] | None = None
        try:
            mode = getattr(payload, "mode", PlanarEditMode.ADD) if payload is not None else PlanarEditMode.ADD
            if not isinstance(mode, PlanarEditMode):
                mode = PlanarEditMode(str(mode))
            selected = bool(mode is PlanarEditMode.MOD and getattr(payload, "selected_index", None) is not None)
            if selected and payload is not None:
                payload._sync_curve_offsets()
                segment = payload.selected_segment_index()
                if segment is not None:
                    selected_curve = (float(payload.segment_curve_radii[int(segment)]), float(payload.segment_curve_strengths[int(segment)]))
        except Exception:
            selected = False
        if selected_curve is not None:
            try:
                ctx.inspector.update_value("curve_radius", selected_curve[0], notify=False)
                ctx.inspector.update_value("curve_strength", selected_curve[1], notify=False)
            except Exception:
                pass
        if not settings.is_rectangle and bool(ctx.inspector.value("fill_area", False)):
            try:
                ctx.inspector.update_value("fill_area", False, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.set_display_value("build_mode_summary", self._build_mode_summary_from_settings(settings))
            ctx.inspector.set_display_value("compact_route_guide", self._compact_route_guide_from_settings(settings))
        except Exception:
            pass
        field_states = {
            "section_area": (not settings.is_rectangle, not settings.is_rectangle),
            "rect_width": (settings.is_rectangle, settings.is_rectangle),
            "rect_height": (settings.is_rectangle, settings.is_rectangle),
            "fill_area": (settings.is_rectangle, settings.is_rectangle),
            "build_mode_summary": (True, True),
            "compact_route_guide": (settings.is_rectangle, settings.is_rectangle),
            "flare_factor": (settings.flare_enabled, settings.flare_enabled),
            "curve_radius": (selected, selected),
            "curve_strength": (selected, selected),
        }
        for field_id, (enabled, visible) in field_states.items():
            try:
                ctx.inspector.update_field_state(field_id, enabled=enabled, visible=visible)
            except Exception:
                pass

    def _sync_acoustic_readouts(self, ctx: Any) -> None:
        payload = self._payload(ctx)
        settings = self._settings(ctx)
        estimate = estimate_vent_acoustics(payload, enclosure_volume_l=float(settings.enclosure_volume_l)) if payload is not None else None
        length_text = "0.0 mm"
        height_text = f"{max(float(settings.rect_height), 0.0):.1f} mm" if settings.is_rectangle else "—"
        area_text = "0.0 cm²"
        tuning_text = "Enter a box volume and draw at least two waypoints."
        if estimate is not None:
            length_text = f"{estimate.physical_length_mm:.1f} mm"
            height_text = f"{estimate.inner_height_mm:.1f} mm"
            area_text = f"{estimate.section_area_mm2 / 100.0:.2f} cm²"
            tuning_text = estimate.tuning_text()
        try:
            ctx.inspector.set_display_value("vent_length_measure", length_text)
            ctx.inspector.set_display_value("vent_height_measure", height_text)
            ctx.inspector.set_display_value("vent_area_measure", area_text)
            ctx.inspector.set_display_value("vent_tuning_measure", tuning_text)
        except Exception:
            pass

    def _sync_report(self, ctx: Any, default: str | None = None) -> None:
        with _measure_perf(ctx, "vent.ui.sync_report"):
            return self._sync_report_measured(ctx, default)

    def _sync_report_measured(self, ctx: Any, default: str | None = None) -> None:
        payload = self._payload(ctx)
        settings = self._settings(ctx)
        text = vent_report_text(payload, fallback=default or "Pick a plane, then draw at least two route points.", enclosure_volume_l=float(settings.enclosure_volume_l))
        try:
            ctx.inspector.set_display_value("vent_report", text)
            ctx.inspector.set_display_value("route_summary", vent_route_summary(payload))
            ctx.inspector.set_display_value("selected_point", vent_selected_point_text(payload))
        except Exception:
            pass
        self._sync_apply_check(ctx)

    def _sync_view_feedback(self, ctx: Any, message: str | None = None) -> None:
        with _measure_perf(ctx, "vent.ui.sync_view_feedback"):
            return self._sync_view_feedback_measured(ctx, message)

    def _sync_view_feedback_measured(self, ctx: Any, message: str | None = None) -> None:
        payload = self._payload(ctx)
        snapshot = sync_vent_feedback(ctx, payload, status=message)
        try:
            ctx.inspector.set_display_value(
                "viewport_feedback",
                f"{snapshot.mode_label} · {snapshot.waypoint_count} waypoint(s) · {snapshot.snap}",
            )
            ctx.inspector.set_display_value("timing", vent_perf_summary_text(ctx))
        except Exception:
            pass

    def _export_timings(self, ctx: Any, *, reason: str = "manual") -> None:
        payload = self._payload(ctx)
        export_vent_timings(ctx, payload, reason=reason)
        try:
            ctx.inspector.set_display_value("timing", vent_perf_summary_text(ctx))
        except Exception:
            pass


    def wants_native_actor_interaction(self, event: ToolEvent, ctx: Any) -> bool:
        """Use Creator API grab/drag only for Vent waypoint Move mode.

        Add/Delete are domain gestures: clicks on existing points should not be
        consumed by the native actor runtime there.  In Move mode, however, the
        route points are official Plan2D actors, so native grab gives us the
        same interaction grammar as Plan Tracer.
        """

        payload = self._payload(ctx)
        if not isinstance(payload, VentPathDraft):
            return False
        try:
            mode = getattr(payload, "mode", PlanarEditMode.ADD)
            if not isinstance(mode, PlanarEditMode):
                mode = PlanarEditMode(str(mode))
        except Exception:
            mode = PlanarEditMode.ADD
        return mode is PlanarEditMode.MOD

    def _waypoint_actor_index(self, actor: Any) -> int | None:
        try:
            metadata = getattr(actor, "metadata", {}) or {}
            value = metadata.get("vent_generator_waypoint_index")
            if value is None:
                raw = str(getattr(actor, "id", "") or "")
                if ".waypoint." in raw:
                    value = raw.rsplit(".", 1)[-1]
            return int(value) if value is not None else None
        except Exception:
            return None

    @staticmethod
    def _near_existing_route_waypoint(
        payload: VentPathDraft,
        plane_point: tuple[float, float],
        *,
        exclude_indices: tuple[int, ...] = (),
        tolerance: float = 1.0e-6,
    ) -> bool:
        excluded = {int(value) for value in exclude_indices}
        try:
            u, v = float(plane_point[0]), float(plane_point[1])
        except Exception:
            return False
        for index, waypoint in enumerate(getattr(payload, "waypoints", ()) or ()):  # route points are forbidden direct targets.
            if int(index) in excluded:
                continue
            try:
                du = float(waypoint[0]) - u
                dv = float(waypoint[1]) - v
            except Exception:
                continue
            if (du * du + dv * dv) ** 0.5 <= float(tolerance):
                return True
        return False

    def _record_vent_drag_snap_preview(
        self,
        ctx: Any,
        payload: VentPathDraft,
        *,
        raw_plane: tuple[float, float],
        snapped_plane: tuple[float, float],
        label: str,
        snapped: bool,
    ) -> None:
        controller = self._planar_controller(ctx)
        state = getattr(controller, "state", None) if controller is not None else getattr(getattr(ctx, "owner", None), "planar_tool_state", None)
        if state is None:
            return
        try:
            if bool(snapped) and label:
                state.snap_preview_plane_point = (float(snapped_plane[0]), float(snapped_plane[1]))
                state.snap_preview_raw_plane = (float(raw_plane[0]), float(raw_plane[1]))
                state.snap_preview_label = str(label)
            else:
                state.snap_preview_plane_point = None
                state.snap_preview_raw_plane = None
                state.snap_preview_label = ""
        except Exception:
            pass

    def _snap_vent_drag_target(
        self,
        event: ToolEvent,
        ctx: Any,
        payload: VentPathDraft,
        *,
        exclude_ids: tuple[str, ...],
        exclude_indices: tuple[int, ...],
    ) -> tuple[tuple[float, float], str, bool]:
        with _measure_perf(ctx, "vent.drag.snap_target.total"):
            return self._snap_vent_drag_target_measured(event, ctx, payload, exclude_ids=exclude_ids, exclude_indices=exclude_indices)

    def _snap_vent_drag_target_measured(
        self,
        event: ToolEvent,
        ctx: Any,
        payload: VentPathDraft,
        *,
        exclude_ids: tuple[str, ...],
        exclude_indices: tuple[int, ...],
    ) -> tuple[tuple[float, float], str, bool]:
        from laserprog_studio.tool_api import plan2d

        if event.screen_pos is not None:
            candidate_world = plan2d.project_screen_to_locked_plane(ctx, event.screen_pos, payload.plane, event_world_pos=event.world_pos)
        elif event.world_pos is not None:
            candidate_world = tuple(float(v) for v in event.world_pos)
        else:
            raise ValueError("No drag position")
        settings = self._settings(ctx)
        candidate_plane = world_to_plane(payload.plane, candidate_world)
        snapped_plane = (float(candidate_plane[0]), float(candidate_plane[1]))
        snap_label = "Free"
        snapped_flag = False

        if bool(settings.smart_snap) and event.screen_pos is not None:
            try:
                from laserprog_studio.tool_api.snap import SnapKind, SnapSource

                extra_targets = vent_route_alignment_targets(
                    payload,
                    snapped_plane,
                    exclude_indices=exclude_indices,
                    tolerance=VENT_ROUTE_SNAP_TOLERANCE,
                    owner_tool=self.id,
                )
                with _measure_perf(ctx, "vent.drag.smart_snap"):
                    snap = plan2d.smart_snap_on_plan(
                        ctx,
                        owner_tool=self.id,
                        plane=payload.plane,
                        candidate_world=tuple(float(v) for v in candidate_world),
                        screen_pos=event.screen_pos,
                        exclude_ids=exclude_ids,
                        # The Vent route itself is represented by ToolActor points/lines;
                        # those are intentionally forbidden as snap targets. Scene mesh
                        # targets and Vent-owned custom alignment guides remain allowed.
                        exclude_sources=(
                            SnapSource.TOOL_ACTOR_POINT.value,
                            SnapSource.TOOL_ACTOR_EDGE.value,
                            SnapSource.TOOL_TEMP_POINT.value,
                            SnapSource.TOOL_TEMP_EDGE.value,
                            SnapSource.UI_POINT.value,
                            SnapSource.UI_EDGE.value,
                        ),
                        allowed_sources=(
                            SnapSource.MESH_VERTEX.value,
                            SnapSource.MESH_EDGE.value,
                            SnapSource.SCENE_POINT.value,
                            SnapSource.SCENE_EDGE.value,
                            SnapSource.CENTER.value,
                            SnapSource.INTERSECTION.value,
                            SnapSource.CUSTOM_POINT.value,
                            SnapSource.CUSTOM_EDGE.value,
                        ),
                        allowed_kinds=(
                            SnapKind.VERTEX.value,
                            SnapKind.EDGE.value,
                            SnapKind.MIDPOINT.value,
                            SnapKind.INTERSECTION.value,
                            SnapKind.CENTER.value,
                            SnapKind.ANGLE.value,
                        ),
                        extra_targets=extra_targets,
                        max_distance_px=VENT_ROUTE_API_SNAP_RADIUS_PX,
                        rebuild_cache=False,
                    )
                if bool(getattr(snap, "snapped", False)):
                    api_plane = world_to_plane(payload.plane, tuple(float(v) for v in snap.world_pos))
                    source_id = str(getattr(snap, "source_id", "") or "")
                    if source_id.startswith("vent.generator.snap.align") and self._near_existing_route_waypoint(
                        payload,
                        api_plane,
                        exclude_indices=exclude_indices,
                    ):
                        snapped_flag = False
                    else:
                        snapped_plane = api_plane
                        snap_label = str(getattr(snap, "label", "") or getattr(snap, "kind", "Snap") or "Snap")
                        snapped_flag = True
            except Exception:
                snapped_flag = False

        if not snapped_flag:
            snapped = snap_vent_route_point(
                payload,
                snapped_plane,
                enabled=bool(settings.smart_snap),
                exclude_indices=exclude_indices,
                tolerance=VENT_ROUTE_SNAP_TOLERANCE,
            )
            snapped_plane = snapped.point
            snap_label = str(snapped.label or "Free")
            snapped_flag = bool(snapped.snapped)

        world = plane_to_world(payload.plane, snapped_plane[0], snapped_plane[1])
        if bool(getattr(event, "shift", False)):
            world = self._shift_constrain_vent_world(payload, world, selected_index=exclude_indices[0] if exclude_indices else None)
            snapped_plane = world_to_plane(payload.plane, world)
            snap_label = (snap_label if snapped_flag else "Free") + " · 45°"
            snapped_flag = True
        self._record_vent_drag_snap_preview(
            ctx,
            payload,
            raw_plane=(float(candidate_plane[0]), float(candidate_plane[1])),
            snapped_plane=(float(snapped_plane[0]), float(snapped_plane[1])),
            label=snap_label,
            snapped=snapped_flag,
        )
        return (float(snapped_plane[0]), float(snapped_plane[1])), snap_label, snapped_flag

    def _shift_constrain_vent_world(self, payload: VentPathDraft, world: tuple[float, float, float], *, selected_index: int | None = None) -> tuple[float, float, float]:
        try:
            from laserprog_studio.tool_api import plan2d

            waypoints = list(getattr(payload, "waypoints", []) or [])
            anchor = None
            if selected_index is not None and 0 <= int(selected_index) < len(waypoints):
                idx = int(selected_index)
                if idx > 0:
                    anchor = waypoints[idx - 1]
                elif len(waypoints) > 1:
                    anchor = waypoints[1]
            elif waypoints:
                anchor = waypoints[-1]
            if anchor is None:
                return tuple(float(v) for v in world)
            result = plan2d.constrain_angle_step_on_plan(
                payload.plane,
                plane_to_world(payload.plane, float(anchor[0]), float(anchor[1])),
                world,
                angle_step_degrees=45.0,
            )
            if bool(getattr(result, "applied", False)):
                return tuple(float(v) for v in result.world_pos)
        except Exception:
            pass
        return tuple(float(v) for v in world)

    def resolve_drag_positions(self, event: ToolEvent, ctx: Any) -> dict[str, Any] | None:
        """Snap/plane aware Vent waypoint drag resolver.

        The native API can move the visible minimal dots, but the duct route is
        domain state.  This resolver updates the VentPathDraft first, then
        returns replacement ToolActors so the official fast drag path and the
        fallback PyVista route stay in sync.
        """

        payload = self._payload(ctx)
        if not isinstance(payload, VentPathDraft):
            return None
        try:
            mode = getattr(payload, "mode", PlanarEditMode.ADD)
            if not isinstance(mode, PlanarEditMode):
                mode = PlanarEditMode(str(mode))
            if mode is not PlanarEditMode.MOD:
                return None
        except Exception:
            return None
        grabbed_ids = tuple(str(value) for value in getattr(ctx.selection.state, "grabbed_ids", ()) or ())
        if not grabbed_ids:
            return None
        actors_by_id = {actor_id: ctx.selection.actor(actor_id) for actor_id in grabbed_ids}
        movable = {
            actor_id: actor
            for actor_id, actor in actors_by_id.items()
            if actor is not None
            and getattr(actor, "owner_tool", None) == self.id
            and (getattr(actor, "metadata", {}) or {}).get("vent_generator_role") == "waypoint"
            and getattr(actor, "points", ())
            and self._waypoint_actor_index(actor) is not None
        }
        if not movable:
            return None
        reference_id = next((actor_id for actor_id in reversed(grabbed_ids) if actor_id in movable), next(iter(movable)))
        reference_actor = movable[reference_id]
        reference_index = self._waypoint_actor_index(reference_actor)
        if reference_index is None or not (0 <= int(reference_index) < len(payload.waypoints)):
            return None
        try:
            from laserprog_studio.tool_api import plan2d

            target_plane, snap_label, _snapped_flag = self._snap_vent_drag_target(
                event,
                ctx,
                payload,
                exclude_ids=tuple((*grabbed_ids, "vent.generator.route.pending")),
                exclude_indices=(int(reference_index),),
            )
            current_reference = tuple(float(v) for v in payload.waypoints[int(reference_index)])
            check = payload.clamp_waypoint_candidate(target_plane, index=int(reference_index), anchor=current_reference)
            if not getattr(check, "valid", False):
                return None
            safe_reference = tuple(float(v) for v in check.point)
            delta = (safe_reference[0] - current_reference[0], safe_reference[1] - current_reference[1])
            replacements: dict[str, Any] = {}
            changed_ids: list[str] = []
            for actor_id, actor in movable.items():
                idx = self._waypoint_actor_index(actor)
                if idx is None or not (0 <= int(idx) < len(payload.waypoints)):
                    continue
                old = tuple(float(v) for v in payload.waypoints[int(idx)])
                new_plane = (old[0] + delta[0], old[1] + delta[1])
                # For multi-selection, keep relative offsets but do not allow a
                # dragged waypoint to invalidate route spacing/collision rules.
                check_i = payload.clamp_waypoint_candidate(new_plane, index=int(idx), anchor=old)
                if not getattr(check_i, "valid", False):
                    continue
                final_plane = tuple(float(v) for v in check_i.point)
                payload.waypoints[int(idx)] = final_plane
                payload.selected_index = int(idx) if actor_id == reference_id else payload.selected_index
                new_world = plane_to_world(payload.plane, final_plane[0], final_plane[1])
                metadata = {**(getattr(actor, "metadata", {}) or {}), "plan_trace_semantic_world_pos": new_world}
                replacements[actor_id] = replace(actor, points=(new_world,), metadata=metadata)
                changed_ids.append(actor_id)
            if not replacements:
                return None
            payload.selected_index = int(reference_index)
            payload._sync_curve_offsets()
            try:
                changed_indices: list[int] = []
                for actor_id in changed_ids:
                    actor = movable.get(actor_id)
                    idx = self._waypoint_actor_index(actor) if actor is not None else None
                    if idx is not None and int(idx) not in changed_indices:
                        changed_indices.append(int(idx))
                sync_vent_route_visuals(
                    ctx,
                    payload,
                    state=getattr(self._planar_controller(ctx), "state", None),
                    render=False,
                    full=False,
                    changed_indices=tuple(changed_indices),
                    position_only=True,
                )
            except Exception:
                try:
                    plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=tuple(changed_ids), position_only=True, render=False)
                except Exception:
                    pass
            return replacements
        except Exception:
            return None

    def on_native_interaction_result(self, event: ToolEvent, ctx: Any, result: Any) -> None:
        """Commit visual waypoint drags back into the Vent route model."""

        action = str(getattr(result, "action", "") or "")
        _increment_perf(ctx, f"vent.native.{action or 'unknown'}")
        with _measure_perf(ctx, f"vent.native.{action or 'unknown'}.total"):
            return self._on_native_interaction_result_measured(event, ctx, result, action=action)

    def _on_native_interaction_result_measured(self, event: ToolEvent, ctx: Any, result: Any, *, action: str) -> None:
        grabbed_ids = tuple(str(value) for value in getattr(result, "grabbed_ids", ()) or ())
        if action == "grab" and grabbed_ids:
            payload = self._payload(ctx)
            if isinstance(payload, VentPathDraft):
                self._apply_snap_settings(ctx)
                actor = ctx.selection.actor(grabbed_ids[-1])
                idx = self._waypoint_actor_index(actor)
                if idx is not None:
                    payload.selected_index = int(idx)
                    controller = self._planar_controller(ctx)
                    if controller is not None:
                        try:
                            state = getattr(controller, "state", None)
                            if state is not None:
                                state.pointer_drag_active = True
                                state.pointer_drag_mode = "mod"
                            controller._begin_planar_drag_snap_cache()
                        except Exception:
                            pass
                    self._refresh_ui_state(ctx)
            return
        if action == "release" and grabbed_ids:
            controller = self._planar_controller(ctx)
            if controller is not None:
                try:
                    state = getattr(controller, "state", None)
                    if state is not None:
                        state.pointer_drag_active = False
                        state.pointer_drag_mode = None
                    controller._end_planar_drag_snap_cache()
                    controller._clear_planar_snap_preview()
                except Exception:
                    pass
            # Heavy updates once, after the drag: route report, overlay badge,
            # Apply state and precise material outline.
            self._after_route_edit(ctx, "Waypoint moved.")
            return
        if action in {"select", "clear"} or bool(getattr(result, "selection_cleared", False)):
            self._refresh_ui_state(ctx)
            self._sync_report(ctx)
            self._sync_view_feedback(ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        mode = overlay_mode_from_button(button_id)
        if mode is not None:
            self._set_mode(ctx, mode)
            return
        action = overlay_action_from_button(button_id)
        if action == "refresh":
            self._on_values_changed(ctx)
            ctx.status.info("Vent generator preview refreshed.")
            return
        if action == "apply_mesh":
            ok = self.on_apply(ctx)
            ctx.status.info("Vent mesh applied." if ok else "Vent mesh cannot be applied yet.")
            return
        if action == "export_timings":
            self._export_timings(ctx, reason="overlay")
            return
        if action == "start_over":
            self._start_over(ctx)
            return
        if action == "reset_path":
            self._reset_path(ctx)
            return



class VentGeneratorTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Vent Generator CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=VentGeneratorCreatorTool())


__all__ = ["VentGeneratorCreatorTool", "VentGeneratorTool"]
