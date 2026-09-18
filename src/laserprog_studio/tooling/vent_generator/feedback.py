# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from laserprog_studio.planar_tools import PlanarEditMode, VentPathDraft, plane_to_world
from laserprog_studio.tool_api import plan2d, projected_drawing as draw2d, visual
from laserprog_studio.tool_api.styles import LineStyleId
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR

from .workflow import VentRouteMachine, vent_route_summary, vent_selected_point_text
from .diagnostics import increment_perf, measure_perf, set_perf_value

VENT_TOOLBAR_ID = "vent.generator.toolbar"
VENT_STATUS_ID = "vent.generator.status"
VENT_MODE_GROUP = "vent.generator.mode"
VENT_MODE_PREFIX = "vent.generator.mode."
VENT_ACTION_PREFIX = "vent.generator.action."
VENT_COMMAND_STATUS_ID = "vent.generator.command_status"
VENT_MODE_BADGE_ID = "vent.generator.mode_badge"


@dataclass(frozen=True, slots=True)
class VentFeedbackSnapshot:
    """Small serialisable viewport feedback model for Vent Generator."""

    mode: str = "ADD"
    mode_label: str = "Add point"
    route_summary: str = "No route active."
    selected_point: str = "No selected waypoint."
    status: str = "Pick a plane, then draw at least two route points."
    snap: str = "Snap: none"
    waypoint_count: int = 0
    selected_index: int | None = None
    ready: bool = False
    warning: str = ""

    @classmethod
    def from_payload(cls, payload: VentPathDraft | None, *, state: Any | None = None, status: str | None = None) -> "VentFeedbackSnapshot":
        if not isinstance(payload, VentPathDraft):
            return cls(status=status or "Pick a plane, then draw at least two route points.")
        mode = VentRouteMachine.normalize_mode(getattr(payload, "mode", PlanarEditMode.ADD)).value
        warning = str(getattr(state, "last_edit_warning", "") or "") if state is not None else ""
        snap_label = str(getattr(state, "snap_preview_label", "") or "") if state is not None else ""
        ready = False
        message = "Pick a plane, then draw at least two route points."
        try:
            validation = payload.validation_result()
            ready = bool(validation.ok)
            message = "Ready to apply." if ready else validation.message()
        except Exception:
            try:
                ready = bool(payload.is_ready_for_mesh())
                message = "Ready to apply." if ready else message
            except Exception:
                pass
        if warning:
            message = warning
        if status:
            message = str(status)
        selected = getattr(payload, "selected_index", None)
        try:
            selected = int(selected) if selected is not None else None
        except Exception:
            selected = None
        return cls(
            mode=mode,
            mode_label=_mode_label(mode),
            route_summary=vent_route_summary(payload),
            selected_point=vent_selected_point_text(payload),
            status=message,
            snap=f"Snap: {snap_label}" if snap_label else "Snap: none",
            waypoint_count=len(getattr(payload, "waypoints", ()) or ()),
            selected_index=selected,
            ready=ready,
            warning=warning,
        )


def _mode_label(mode: str) -> str:
    return {
        "ADD": "Add point",
        "MOD": "Move point",
        "SUPP": "Delete point",
        "RST": "Reset route",
    }.get(str(mode).upper(), str(mode).title())


def overlay_mode_from_button(button_id: str | None) -> str | None:
    raw = str(button_id or "")
    if raw.startswith(VENT_MODE_PREFIX):
        return raw[len(VENT_MODE_PREFIX):]
    return None


def overlay_action_from_button(button_id: str | None) -> str | None:
    raw = str(button_id or "")
    if raw.startswith(VENT_ACTION_PREFIX):
        return raw[len(VENT_ACTION_PREFIX):]
    return None


def _mode_spec(mode: str, *, label: str, icon: str, display_label: str, shortcut: str, tooltip: str, slot: int) -> visual.OverlayModeSpec:
    return visual.OverlayModeSpec(
        id=f"{VENT_MODE_PREFIX}{mode}",
        label=label,
        icon=icon,
        shortcut=shortcut,
        tooltip=tooltip,
        display_label=display_label,
        slot_width_px=slot,
    )


def _action_spec(action: str, *, label: str, icon: str, display_label: str, tooltip: str, slot: int, enabled: bool = True, style: str = "ghost") -> visual.OverlayActionSpec:
    return visual.OverlayActionSpec(
        id=f"{VENT_ACTION_PREFIX}{action}",
        label=label,
        icon=icon,
        tooltip=tooltip,
        display_label=display_label,
        enabled=bool(enabled),
        style=style,  # type: ignore[arg-type]
        slot_width_px=slot,
    )


def build_vent_toolbar(snapshot: VentFeedbackSnapshot) -> visual.OverlayWindowSpec:
    """Build the Vent Generator command deck.

    The old bottom toolbar was functionally correct but visually disconnected
    from Plan Tracer.  The new deck deliberately reuses the same overlay API and
    button grammar: big vector cells, one row, explicit mode sections.
    """

    route_section = visual.OverlayToolbarSectionSpec(
        id="route",
        label="Route edit",
        modes=(
            _mode_spec("ADD", label="Add point", icon="sketch.point", display_label="Add", shortcut="A", tooltip="Add inlet, outlet and intermediate route points.", slot=94),
            _mode_spec("MOD", label="Move point", icon="sketch.modify", display_label="Move", shortcut="M", tooltip="Select and drag a waypoint, then tune its bend.", slot=96),
            _mode_spec("SUPP", label="Delete point", icon="sketch.delete", display_label="Delete", shortcut="Del", tooltip="Delete the nearest waypoint.", slot=98),
        ),
    )
    path_section = visual.OverlayToolbarSectionSpec(
        id="path",
        label="Path",
        actions=(
            _action_spec("reset_path", label="Clear route", icon="tool.clear", display_label="Clear", tooltip="Clear all waypoints without changing duct dimensions.", slot=94, style="danger"),
            _action_spec("start_over", label="Start over", icon="tool.restart", display_label="Restart", tooltip="Reset the route and restore default duct settings.", slot=104),
        ),
    )
    build_section = visual.OverlayToolbarSectionSpec(
        id="build",
        label="Build",
        actions=(
            _action_spec("refresh", label="Refresh preview", icon="tool.preview", display_label="Preview", tooltip="Refresh the generated duct preview.", slot=106),
            _action_spec("apply_mesh", label="Apply mesh", icon="tool.apply", display_label="Apply", tooltip="Apply the generated duct mesh.", slot=96, enabled=bool(snapshot.ready), style="primary"),
        ),
    )
    value = f"{snapshot.mode_label} · {snapshot.waypoint_count} pt"
    if snapshot.waypoint_count > 1:
        value += "s"
    return visual.build_command_deck_window(
        window_id=VENT_TOOLBAR_ID,
        owner_tool=TOOL_VENT_GENERATOR,
        group_id=VENT_MODE_GROUP,
        sections=(route_section, path_section, build_section),
        active_mode_id=f"{VENT_MODE_PREFIX}{snapshot.mode}",
        badge_id=VENT_MODE_BADGE_ID,
        badge_label="Mode",
        badge_value=value,
        badge_tooltip="Current Vent Generator edit mode and waypoint count.",
        status_id=VENT_COMMAND_STATUS_ID,
        status_label="Status",
        status_value=snapshot.status,
        title="Vent Generator",
        anchor="viewport_top_left",
        width_px=0,
        movable=True,
        persistent=True,
    )


def build_vent_status(snapshot: VentFeedbackSnapshot) -> visual.OverlayWindowSpec:
    """Legacy status palette kept for API compatibility with old tests/tools."""

    return visual.OverlayWindowSpec(
        id=VENT_STATUS_ID,
        title="Vent generator",
        owner_tool=TOOL_VENT_GENERATOR,
        overlay_kind="palette",
        anchor="viewport_top_right",
        width_px=360,
        movable=True,
        persistent=False,
        visible=False,
        fields=[
            visual.OverlayFieldSpec("vent.generator.status.route", "Route", snapshot.route_summary, kind="info"),
            visual.OverlayFieldSpec("vent.generator.status.selection", "Selection", snapshot.selected_point, kind="info"),
            visual.OverlayFieldSpec("vent.generator.status.snap", "Snap", snapshot.snap, kind="info"),
            visual.OverlayFieldSpec("vent.generator.status.message", "Status", snapshot.status, kind="info"),
        ],
    )


def sync_vent_feedback(ctx: Any, payload: VentPathDraft | None, *, status: str | None = None) -> VentFeedbackSnapshot:
    """Publish Vent Generator route, overlays and status using the Plan2D API."""

    owner = getattr(ctx, "owner", None)
    state = getattr(owner, "planar_tool_state", None) if owner is not None else None
    snapshot = VentFeedbackSnapshot.from_payload(payload, state=state, status=status)
    with measure_perf(ctx, "vent.feedback.snapshot.route_visuals"):
        sync_vent_route_visuals(ctx, payload, state=state, snapshot=snapshot, render=False, full=True, position_only=False)
    try:
        ctx.overlay.set_group_active(VENT_MODE_GROUP, f"{VENT_MODE_PREFIX}{snapshot.mode}")
        ctx.overlay.show_window(build_vent_toolbar(snapshot))
        # One clean command deck is the new visual contract.  Keep a hidden
        # status spec for legacy tests/extensions that read the feedback model,
        # but do not paint the old second palette in the viewport.
        ctx.overlay.show_window(build_vent_status(snapshot))
    except Exception:
        pass
    try:
        if owner is not None:
            from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui

            with measure_perf(ctx, "vent.feedback.render_overlay"):
                render_creator_viewport_ui(owner, ctx, TOOL_VENT_GENERATOR, render=True, sync_overlays=True)
    except Exception:
        pass
    return snapshot


def _projected_registry(ctx: Any):
    return ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR)


def clear_vent_creator_visuals(ctx: Any) -> None:
    """Clear Vent viewport feedback from the Projected Drawing registry only."""

    try:
        _projected_registry(ctx).clear(render=False)
    except Exception:
        try:
            ctx.selection.clear_tool(TOOL_VENT_GENERATOR)
        except Exception:
            pass


def _route_point_id(index: int) -> str:
    return f"vent.generator.route.waypoint.{int(index):02d}"


def _route_segment_id(index: int) -> str:
    return f"vent.generator.route.segment.{int(index):02d}"


FORBIDDEN_VENT_SNAP_CURSOR_IDS = ("vent.generator.route.snap",)


def _route_visual_actor_ids(waypoints: list[tuple[float, float]]) -> set[str]:
    ids = {_route_point_id(index) for index in range(len(waypoints))}
    ids.update(_route_segment_id(index) for index in range(max(0, len(waypoints) - 1)))
    # The pending cursor is the only Vent route cursor allowed.  A separate snap
    # cursor would materialise as an extra point gizmo and is explicitly banned.
    ids.add("vent.generator.route.pending")
    return ids


def _vent_compat_visual_ids(waypoint_count: int) -> set[str]:
    ids = {
        "vent.generator.preview.centerline",
        "vent.generator.preview.selection",
        "vent.generator.preview.pending_link",
        *FORBIDDEN_VENT_SNAP_CURSOR_IDS,
    }
    for index in range(max(0, int(waypoint_count))):
        ids.add(f"vent.generator.preview.waypoint.{index:02d}")
        ids.add(f"vent.generator.preview.label.{index:02d}")
    return ids


def _purge_forbidden_vent_snap_cursors(ctx: Any) -> None:
    """Remove legacy Vent snap cursors from the projected registry/selection."""

    try:
        _projected_registry(ctx).remove_many(FORBIDDEN_VENT_SNAP_CURSOR_IDS, render=False)
    except Exception:
        pass
    for actor_id in FORBIDDEN_VENT_SNAP_CURSOR_IDS:
        try:
            ctx.selection.unregister(actor_id)
        except Exception:
            pass


def _hide_legacy_compat_preview(ctx: Any, item_id: str) -> None:
    """Hide a compatibility primitive in Projected Drawing storage."""

    try:
        _projected_registry(ctx).hide(item_id, render=False)
    except Exception:
        pass


def _remove_stale_route_visuals(ctx: Any, desired_actor_ids: set[str], *, waypoint_count: int) -> None:
    """Mirror Plan Tracer's stale-topology cleanup for Vent route primitives."""

    _purge_forbidden_vent_snap_cursors(ctx)
    keep = set(desired_actor_ids) | _vent_compat_visual_ids(waypoint_count)
    try:
        registry = _projected_registry(ctx)
        stale = []
        for primitive in registry.items():
            primitive_id = str(getattr(primitive, "id", "") or "")
            if primitive_id.startswith("vent.generator.route.") or primitive_id.startswith("vent.generator.preview."):
                if primitive_id not in keep:
                    stale.append(primitive_id)
        if stale:
            registry.remove_many(stale, render=False)
    except Exception:
        pass


def sync_vent_route_visuals(
    ctx: Any,
    payload: VentPathDraft | None,
    *,
    state: Any | None = None,
    snapshot: VentFeedbackSnapshot | None = None,
    render: bool = True,
    full: bool = True,
    changed_indices: tuple[int, ...] | None = None,
    position_only: bool = False,
) -> None:
    """Synchronise Vent route visuals through the exact Plan Tracer Plan2D API.

    This function is intentionally narrow: no PyVista fallback points, no custom
    Vent line actors, no legacy spheres.  The route is declared as official
    Plan2D point/line/cursor actors, then materialised by
    ``plan2d.sync_plan_actor_visuals``—the same public path used by Plan Tracer.
    """

    if not isinstance(payload, VentPathDraft):
        if full:
            clear_vent_creator_visuals(ctx)
        return
    waypoints = [(float(u), float(v)) for u, v in (getattr(payload, "waypoints", ()) or ())]
    desired_actor_ids = _route_visual_actor_ids(waypoints)
    if full:
        _remove_stale_route_visuals(ctx, desired_actor_ids, waypoint_count=len(waypoints))
    if not waypoints:
        if full:
            clear_vent_creator_visuals(ctx)
        return
    snapshot = snapshot or VentFeedbackSnapshot.from_payload(payload, state=state)
    changed: list[str] = []
    extra_dirty_preview_ids: list[str] = []

    pending = getattr(state, "pending_plane_point", None) if state is not None else None
    mode = VentRouteMachine.normalize_mode(getattr(payload, "mode", PlanarEditMode.ADD))

    if changed_indices is None:
        # Fast interactive path: during ADD hover/drag the real route topology is
        # unchanged.  Only the pending cursor and the pending-link preview move.
        # Re-registering every waypoint/segment on each throttled mouse move made
        # Vent Generator feel sticky on dense drawings even after the snap cache
        # was fixed.
        if not full and position_only and pending is not None and mode is PlanarEditMode.ADD:
            waypoint_indices = set()
            segment_indices = set()
            increment_perf(ctx, "vent.visual.fast_path.pending_only")
        elif not full and position_only and mode is PlanarEditMode.MOD and getattr(payload, "selected_index", None) is not None:
            try:
                selected_index = int(getattr(payload, "selected_index"))
                waypoint_indices = {selected_index} if 0 <= selected_index < len(waypoints) else set()
            except Exception:
                waypoint_indices = set(range(len(waypoints)))
            segment_indices = set()
            for index in waypoint_indices:
                if index > 0:
                    segment_indices.add(index - 1)
                if index < len(waypoints) - 1:
                    segment_indices.add(index)
            increment_perf(ctx, "vent.visual.fast_path.selected_only")
        else:
            waypoint_indices = set(range(len(waypoints)))
            segment_indices = set(range(max(0, len(waypoints) - 1)))
    else:
        waypoint_indices = {int(index) for index in changed_indices if 0 <= int(index) < len(waypoints)}
        segment_indices: set[int] = set()
        for index in waypoint_indices:
            if index > 0:
                segment_indices.add(index - 1)
            if index < len(waypoints) - 1:
                segment_indices.add(index)
    set_perf_value(ctx, "vent.visual.last_waypoints_synced", len(waypoint_indices))
    set_perf_value(ctx, "vent.visual.last_segments_synced", len(segment_indices))

    try:
        with _projected_registry(ctx).batch():
            if full:
                # Legacy item id kept for headless/API compatibility, but hidden.
                try:
                    centerline, _scales = payload.sampled_centerline_with_flare_scales(samples_per_segment=18)
                except Exception:
                    centerline = waypoints
                if len(centerline) >= 2:
                    _projected_registry(ctx).add(
                        draw2d.polyline(
                            "vent.generator.preview.centerline",
                            [plane_to_world(payload.plane, u, v) for u, v in centerline],
                            color="#7FC8FF",
                            width_px=1.5,
                            opacity=0.0,
                            visible=False,
                            interaction="fixed",
                            metadata={"role": "centerline", "style_id": LineStyleId.GRABBABLE.value, "projected_drawing_only": True, "projected_no_selection_actor": True},
                        ),
                        replace=True,
                        render=False,
                    )

            for index in sorted(segment_indices):
                if not (0 <= index < len(waypoints) - 1):
                    continue
                start, end = waypoints[index], waypoints[index + 1]
                actor = plan2d.register_plan_line(
                    ctx,
                    owner_tool=TOOL_VENT_GENERATOR,
                    line_id=_route_segment_id(index),
                    start_world_pos=plane_to_world(payload.plane, start[0], start[1]),
                    end_world_pos=plane_to_world(payload.plane, end[0], end[1]),
                    selectable=True,
                    sketch_line_id=f"vent.route.segment.{index:02d}",
                )
                try:
                    actor.metadata["vent_generator_segment_index"] = index
                    actor.metadata["vent_generator_role"] = "segment"
                except Exception:
                    pass
                changed.append(actor.id)

            for index in sorted(waypoint_indices):
                point = waypoints[index]
                world = plane_to_world(payload.plane, point[0], point[1])
                actor = plan2d.register_plan_point(
                    ctx,
                    owner_tool=TOOL_VENT_GENERATOR,
                    point_id=_route_point_id(index),
                    world_pos=world,
                    grabbable=True,
                    semantic_world_pos=world,
                )
                try:
                    actor.metadata["vent_generator_waypoint_index"] = index
                    actor.metadata["vent_generator_role"] = "waypoint"
                    actor.metadata["label"] = "IN" if index == 0 else ("OUT" if index == len(waypoints) - 1 else str(index + 1))
                except Exception:
                    pass
                changed.append(actor.id)
                if full:
                    # Compatibility ids only.  Hidden because Plan Tracer does not put
                    # text bubbles on every grabbable point.
                    legacy_id = f"vent.generator.preview.waypoint.{index:02d}"
                    _projected_registry(ctx).add(
                        draw2d.point(
                            legacy_id,
                            world,
                            color="#DCE7F2",
                            size_px=1.0,
                            opacity=0.0,
                            visible=False,
                            interaction="fixed",
                            metadata={"role": "waypoint", "index": index, "projected_drawing_only": True, "projected_no_selection_actor": True},
                        ),
                        replace=True,
                        render=False,
                    )
                    label_id = f"vent.generator.preview.label.{index:02d}"
                    _projected_registry(ctx).add(
                        draw2d.text(
                            label_id,
                            " ",
                            world,
                            size_px=1,
                            opacity=0.0,
                            visible=False,
                            metadata={"role": "waypoint_label", "index": index, "projected_drawing_only": True, "projected_no_selection_actor": True},
                        ),
                        replace=True,
                        render=False,
                    )

            selected_index = getattr(payload, "selected_index", None)
            if selected_index is not None:
                try:
                    selected_index = int(selected_index)
                    if 0 <= selected_index < len(waypoints):
                        ctx.selection.select(_route_point_id(selected_index), replace=True)
                        if full:
                            selected_world = plane_to_world(payload.plane, *waypoints[selected_index])
                            _projected_registry(ctx).add(
                                draw2d.text(
                                    "vent.generator.preview.selection",
                                    " ",
                                    selected_world,
                                    size_px=1,
                                    opacity=0.0,
                                    visible=False,
                                    metadata={"role": "selection", "projected_drawing_only": True, "projected_no_selection_actor": True},
                                ),
                                replace=True,
                                render=False,
                            )
                except Exception:
                    pass

            if pending is not None and mode is PlanarEditMode.ADD:
                pending_world = plane_to_world(payload.plane, float(pending[0]), float(pending[1]))
                cursor = plan2d.register_plan_cursor(
                    ctx,
                    owner_tool=TOOL_VENT_GENERATOR,
                    cursor_id="vent.generator.route.pending",
                    world_pos=pending_world,
                    visible=True,
                    snap_kind="free",
                    snap_label="Next point",
                )
                changed.append(cursor.id)
                if waypoints:
                    last_world = plane_to_world(payload.plane, *waypoints[-1])
                    _projected_registry(ctx).add(
                        draw2d.line(
                            "vent.generator.preview.pending_link",
                            last_world,
                            pending_world,
                            color="#F0A805",
                            width_px=1.5,
                            opacity=0.72,
                            interaction="fixed",
                            metadata={"role": "pending_link", "style_id": LineStyleId.PREVIEW.value, "projected_drawing_only": True, "projected_no_selection_actor": True},
                        ),
                        replace=True,
                        render=False,
                    )
                    # ``pending_link`` is a projected drawing primitive, not a ToolActor.
                    # Keep the dirty-preview bridge populated for older renderer/UI
                    # adapters that still observe this field during fast ADD drags.
                    extra_dirty_preview_ids.append("vent.generator.preview.pending_link")
                    try:
                        current_dirty = tuple(getattr(ctx.selection.state, "dirty_visual_preview_ids", ()) or ())
                        ctx.selection.state.dirty_visual_preview_ids = tuple(dict.fromkeys((*current_dirty, "vent.generator.preview.pending_link")))
                    except Exception:
                        pass
            elif full:
                _hide_legacy_compat_preview(ctx, "vent.generator.preview.pending_link")

            # Deliberately no ``vent.generator.route.snap`` cursor here.  Snap
            # information remains available in the status/inspector text, while the
            # viewport uses guide lines and the moving route point only.  Registering
            # an API cursor would create a second point gizmo over the scene.
            if full:
                _purge_forbidden_vent_snap_cursors(ctx)

            if changed:
                unique_changed = tuple(dict.fromkeys(changed))
                unique_preview = tuple(dict.fromkeys(extra_dirty_preview_ids))
                set_perf_value(ctx, "vent.visual.last_changed_actor_ids", len(unique_changed))
                set_perf_value(ctx, "vent.visual.last_extra_preview_ids", len(unique_preview))
                with measure_perf(ctx, "vent.visual.sync_plan_actor_visuals"):
                    plan2d.sync_plan_actor_visuals(
                        ctx,
                        owner_tool=TOOL_VENT_GENERATOR,
                        changed_actor_ids=unique_changed,
                        extra_preview_ids=unique_preview,
                        position_only=bool(position_only),
                        render=bool(render),
                    )
    except Exception:
        # Viewport feedback must never block route editing.
        return


__all__ = [
    "VENT_ACTION_PREFIX",
    "VENT_COMMAND_STATUS_ID",
    "VENT_MODE_BADGE_ID",
    "VENT_MODE_PREFIX",
    "VENT_STATUS_ID",
    "VENT_TOOLBAR_ID",
    "VentFeedbackSnapshot",
    "build_vent_status",
    "build_vent_toolbar",
    "clear_vent_creator_visuals",
    "overlay_action_from_button",
    "overlay_mode_from_button",
    "sync_vent_feedback",
    "sync_vent_route_visuals",
]
