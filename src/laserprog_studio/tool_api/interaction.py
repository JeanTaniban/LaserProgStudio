"""Default interaction helpers for Creator API tools.

The important production rule is that hover/select/grab behaviour is part of the
Creator API.  Tool authors register :class:`ToolActor` objects and can then use
these helpers instead of writing tool-local hit-test or drag state machines.

The API also owns the empty-click policy: a simple click on no actor clears the
current tool selection, while an empty left drag is left to the host camera.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from laserprog_studio.tool_core.events import MouseButton, ToolEvent
from laserprog_studio.tool_core.selection import Point2, Point3, SelectionHit

WorldToScreen = Callable[[Point3], Point2]
VisualRefresh = Callable[[], None]
DragPositionResolver = Callable[[ToolEvent, Any], Mapping[str, Any] | None]


@dataclass(frozen=True, slots=True)
class ActorInteractionResult:
    """Result returned by the native Creator API actor interaction path."""

    handled: bool
    action: str
    hit: SelectionHit | None = None
    moved: int = 0
    grabbed_ids: tuple[str, ...] = ()
    selection_cleared: bool = False
    visual_changed: bool = False


def select_or_grab(event: ToolEvent, ctx, *, owner_tool: str | None = None, world_to_screen: WorldToScreen | None = None) -> bool:
    """Handle common actor selection and grab behaviour.

    - left press selects the hit actor, using Shift for additive selection;
    - pressing an already selected grabbable actor starts a grab;
    - mouse move applies incremental world-space deltas to selected grabbable actors;
    - release ends the grab.

    This helper clears selection on empty presses through
    ``SelectionManager.select_at``.  Normal Creator tools should not call it from
    ``on_event``; when registered as ``CreatorTool`` runtimes,
    ``CreatorStudioToolAdapter`` runs the native interaction policy before tool
    code.  Low-level diagnostics and adapters can use
    :func:`hover_select_grab_actors` directly when they need the policy without
    the full runtime wrapper.
    """

    projector = world_to_screen or ctx.viewport.world_to_screen
    if event.is_press and event.is_left and event.screen_pos is not None:
        hit = ctx.selection.select_at(event.screen_pos, projector, owner_tool=owner_tool, additive=event.shift)
        if hit is not None:
            ctx.selection.begin_grab(hit.actor_id, event.screen_pos, event.world_pos)
            return True
        return False
    if event.is_move and event.screen_pos is not None:
        ctx.selection.update_grab_screen(event.screen_pos)
        if event.world_pos is None:
            return bool(ctx.selection.state.grab_active)
        delta = ctx.selection.update_grab_world(event.world_pos)
        if delta is None:
            return bool(ctx.selection.state.grab_active)
        moved = ctx.selection.move_selected(delta, grabbable_only=True)
        if moved:
            ctx.scene_cache.invalidate()
            ctx.request_light_render()
        return bool(moved)
    if event.is_release:
        return bool(ctx.selection.end_grab())
    return False


def _refresh(refresh_visuals: VisualRefresh | None) -> None:
    if callable(refresh_visuals):
        refresh_visuals()


def _screen_distance(a: Point2 | None, b: Point2 | None) -> float:
    if a is None or b is None:
        return 0.0
    return max(abs(float(a[0]) - float(b[0])), abs(float(a[1]) - float(b[1])))


def _clear_empty_press_state(ctx) -> None:
    state = ctx.selection.state
    state.empty_press_owner = None
    state.empty_press_start = None
    state.empty_press_had_selection = False
    state.empty_press_cleared = False


def hover_select_grab_actors(
    event: ToolEvent,
    ctx,
    *,
    owner_tool: str | None = None,
    world_to_screen: WorldToScreen | None = None,
    refresh_visuals: VisualRefresh | None = None,
    clear_on_empty_click: bool = True,
    empty_click_threshold_px: float = 5.0,
    drag_position_resolver: DragPositionResolver | None = None,
) -> ActorInteractionResult:
    """Native hover/select/grab policy for Creator viewport actors.

    This is the low-level API policy used by Tool Core Analysis motifs, tests and
    runtime adapters.  Normal Creator tools do not call it directly; the adapter
    invokes :func:`handle_native_creator_ui_event` before ``on_event``.  The
    policy deliberately returns ``handled=False`` when a left press misses every
    actor, so the host camera can keep receiving orbit/pan gestures.

    Empty-click selection clearing is also native: on an empty left press the API
    remembers the press without repainting; on release, if the pointer did not
    move beyond ``empty_click_threshold_px``, it clears the tool selection,
    refreshes visuals and reports ``selection_cleared=True``.  An empty drag
    remains a camera operation and does not clear selection.
    """

    projector = world_to_screen or ctx.viewport.world_to_screen
    owner = str(owner_tool) if owner_tool is not None else None
    try:
        from laserprog_studio.tool_api.scene import projection_cache_signature

        hit_projection_key = projection_cache_signature(ctx)
    except Exception:
        hit_projection_key = None

    if event.is_move and event.screen_pos is not None and not event.is_left and not ctx.selection.state.grab_active:
        hit = ctx.selection.hit_test(
            event.screen_pos,
            projector,
            owner_tool=owner,
            selectable_only=True,
            projection_key=hit_projection_key,
        )
        actor_id = None if hit is None else hit.actor_id
        if actor_id != ctx.selection.state.hover_id:
            ctx.selection.set_hover(actor_id)
            _refresh(refresh_visuals)
            return ActorInteractionResult(bool(actor_id), "hover", hit=hit, visual_changed=True)
        return ActorInteractionResult(bool(actor_id), "hover", hit=hit, visual_changed=False)

    if event.is_press and event.is_left and event.screen_pos is not None:
        hit = ctx.selection.hit_test(
            event.screen_pos,
            projector,
            owner_tool=owner,
            selectable_only=True,
            projection_key=hit_projection_key,
        )
        if hit is None:
            had_selection = bool(ctx.selection.has_selection(owner_tool=owner)) if owner is not None else bool(ctx.selection.has_selection())
            ctx.selection.state.empty_press_owner = owner
            ctx.selection.state.empty_press_start = (float(event.screen_pos[0]), float(event.screen_pos[1]))
            ctx.selection.state.empty_press_had_selection = had_selection
            ctx.selection.state.empty_press_cleared = False
            cleared_hover = ctx.selection.state.hover_id is not None
            if cleared_hover:
                ctx.selection.set_hover(None)
            # Do not clear selection or consume here. This may be the beginning
            # of a camera drag; the API distinguishes an empty click from an
            # empty drag on release.  Clearing hover is still reported as a
            # visual change so the native runtime can repaint once.
            return ActorInteractionResult(False, "miss", selection_cleared=False, visual_changed=cleared_hover)
        _clear_empty_press_state(ctx)
        # Clicking an already-selected grabbable actor is a group-drag gesture,
        # not a request to collapse the selection to the actor under the cursor.
        # This distinction is essential after rectangle selection and for CAD
        # workflows where an edge/face promotes several support points before
        # the native runtime begins the grab.
        actor = ctx.selection.actor(hit.actor_id)
        preserve_group = bool(
            not event.shift
            and ctx.selection.is_selected(hit.actor_id)
            and actor is not None
            and actor.grabbable
        )
        if not preserve_group:
            ctx.selection.select(hit.actor_id, replace=not event.shift)
        ctx.selection.set_hover(hit.actor_id)
        grabbed = ctx.selection.begin_grab(hit.actor_id, event.screen_pos, event.world_pos)
        _refresh(refresh_visuals)
        return ActorInteractionResult(True, "grab" if grabbed else "select", hit=hit, grabbed_ids=grabbed, visual_changed=True)

    if event.is_move and event.screen_pos is not None and ctx.selection.state.grab_active:
        ctx.selection.update_grab_screen(event.screen_pos)
        grabbed_ids = ctx.selection.state.grabbed_ids
        resolved_positions = None
        resolver_dirty_ids: tuple[str, ...] = ()
        if callable(drag_position_resolver):
            try:
                resolved_positions = drag_position_resolver(event, ctx)
                # A resolver may update helper actors that are not selected, for
                # example the Plan tracer snap cursor.  Keep those dirty actor ids
                # and merge them into the final drag refresh; otherwise the drag
                # fast path refreshes only the moved selection and helper handles
                # appear frozen until the drag ends.
                state = ctx.selection.state
                resolver_dirty_ids = tuple(
                    str(value)
                    for value in (
                        tuple(getattr(state, "dirty_visual_handle_ids", ()) or ())
                        + tuple(getattr(state, "dirty_visual_preview_ids", ()) or ())
                    )
                )
            except Exception:
                resolved_positions = None
                resolver_dirty_ids = ()
        if resolved_positions:
            moved = ctx.selection.move_actors_to(dict(resolved_positions), grabbable_only=True)
            state = ctx.selection.state
            moved_ids = tuple(str(value) for value in getattr(state, "last_moved_ids", ()) or ())
            if resolver_dirty_ids:
                merged_ids = tuple(dict.fromkeys((*moved_ids, *resolver_dirty_ids)))
                state.last_moved_ids = merged_ids
            visual_changed = bool(moved or resolver_dirty_ids)
            if visual_changed:
                if moved:
                    ctx.scene_cache.invalidate()
                if callable(refresh_visuals):
                    refresh_visuals()
                else:
                    ctx.request_light_render()
            return ActorInteractionResult(True, "drag", moved=moved, grabbed_ids=grabbed_ids, visual_changed=visual_changed)
        if event.world_pos is None:
            return ActorInteractionResult(True, "drag", grabbed_ids=grabbed_ids)
        delta = ctx.selection.update_grab_world(event.world_pos)
        if delta is None:
            return ActorInteractionResult(True, "drag", grabbed_ids=grabbed_ids)
        moved = ctx.selection.move_selected(delta, grabbable_only=True)
        if moved:
            ctx.scene_cache.invalidate()
            if callable(refresh_visuals):
                refresh_visuals()
            else:
                ctx.request_light_render()
        return ActorInteractionResult(True, "drag", moved=moved, grabbed_ids=grabbed_ids, visual_changed=bool(moved))

    if event.is_release:
        had_grab = bool(ctx.selection.state.grab_active)
        grabbed = ctx.selection.end_grab()
        if had_grab or grabbed:
            _clear_empty_press_state(ctx)
            _refresh(refresh_visuals)
            return ActorInteractionResult(True, "release", grabbed_ids=grabbed, visual_changed=True)
        state = ctx.selection.state
        if state.empty_press_start is not None and state.empty_press_owner == owner:
            start = state.empty_press_start
            had_selection = bool(state.empty_press_had_selection)
            moved_px = _screen_distance(start, event.screen_pos)
            _clear_empty_press_state(ctx)
            if clear_on_empty_click and had_selection and moved_px <= float(empty_click_threshold_px):
                cleared_count = ctx.selection.clear_selection(owner_tool=owner) if owner is not None else ctx.selection.clear_selection()
                cleared = bool(cleared_count)
                if cleared:
                    _refresh(refresh_visuals)
                return ActorInteractionResult(cleared, "clear", selection_cleared=cleared, visual_changed=cleared)
            return ActorInteractionResult(False, "miss_release", selection_cleared=False)
        return ActorInteractionResult(False, "release")

    return ActorInteractionResult(False, "ignored")


def handle_native_creator_ui_event(
    event: ToolEvent,
    ctx,
    *,
    owner_tool: str | None = None,
    world_to_screen: WorldToScreen | None = None,
    render: bool = True,
    drag_position_resolver: DragPositionResolver | None = None,
) -> ActorInteractionResult:
    """Run the non-optional Creator UI actor runtime for a tool event.

    Creator tools register ``ToolActor`` objects and official gizmo/preview
    motifs.  They do not choose the repaint strategy on each mouse event: this
    API function owns the optimized policy validated in Tool Core Analysis.

    The native runtime uses four internal paths:

    * hover/press/release/empty-click state changes ->
      ``refresh_creator_ui_interaction``;
    * mouse-move while grabbing -> ``refresh_creator_ui_drag``;
    * empty drags with no grabbed actor -> ``handled=False`` so the host camera
      keeps panning/orbiting without any Creator UI rebuild;
    * unchanged hover/move state -> no repaint.
    """

    owner = None if owner_tool is None else str(owner_tool)
    before_hover_id = getattr(ctx.selection.state, "hover_id", None)
    before_selected_ids = {
        actor.id
        for actor in ctx.selection.selected_actors()
        if owner is None or actor.owner_tool == owner
    }
    before_grabbed_ids = set(getattr(ctx.selection.state, "grabbed_ids", ()) or ())

    result = hover_select_grab_actors(
        event,
        ctx,
        owner_tool=owner_tool,
        world_to_screen=world_to_screen,
        # Suppress the fallback render inside hover_select_grab_actors;
        # this wrapper performs the correct optimized Creator UI refresh below.
        refresh_visuals=lambda: None,
        drag_position_resolver=drag_position_resolver,
    )
    if owner is None:
        return result

    after_hover_id = getattr(ctx.selection.state, "hover_id", None)
    after_selected_ids = {
        actor.id
        for actor in ctx.selection.selected_actors()
        if actor.owner_tool == owner
    }
    after_grabbed_ids = set(getattr(ctx.selection.state, "grabbed_ids", ()) or ())
    interaction_actor_ids = set(before_selected_ids)
    interaction_actor_ids.update(after_selected_ids)
    interaction_actor_ids.update(before_grabbed_ids)
    interaction_actor_ids.update(after_grabbed_ids)
    if before_hover_id is not None:
        interaction_actor_ids.add(str(before_hover_id))
    if after_hover_id is not None:
        interaction_actor_ids.add(str(after_hover_id))

    # Projected Drawing actors share Tool Core's native selection manager, but
    # their persistent vtkActor2D geometry lives in a separate renderer. Mirror
    # moved ToolActors and transient hover/select/grab state back into the
    # declarative registry before the single final viewport render.
    projected = getattr(ctx, "projected_drawing", None)
    projected_changed = False
    projected_present = False
    legacy_present = True
    if projected is not None:
        try:
            projected_present = bool(projected.snapshot(owner).primitives)
        except Exception:
            projected_present = False
        if projected_present:
            try:
                legacy_present = any(
                    not bool(getattr(actor, "metadata", {}).get("projected_drawing_id"))
                    for actor in ctx.selection.actors(owner_tool=owner)
                )
            except Exception:
                legacy_present = True
            if result.action == "drag" and (result.moved or result.visual_changed):
                moved_ids = tuple(getattr(ctx.selection.state, "last_moved_ids", ()) or result.grabbed_ids)
                try:
                    projected_changed = bool(projected.sync_moved_actors(owner, moved_ids, render=False)) or projected_changed
                except Exception:
                    pass
            if result.visual_changed or result.selection_cleared or result.action in {"grab", "select", "release", "clear", "hover", "drag"}:
                try:
                    projected_changed = bool(
                        projected.sync_interaction_state(
                            owner,
                            render=False,
                            actor_ids=interaction_actor_ids,
                        )
                    ) or projected_changed
                except Exception:
                    pass

    if result.action == "drag" and (result.moved or result.visual_changed):
        moved_ids = tuple(getattr(ctx.selection.state, "last_moved_ids", ()) or result.grabbed_ids)
        if legacy_present:
            try:
                from .gizmos import refresh_creator_ui_drag

                # Mixed tools update legacy motifs without rendering, then let
                # the projected renderer issue the one final frame.
                refresh_creator_ui_drag(
                    ctx,
                    owner_tool=owner,
                    changed_actor_ids=moved_ids,
                    render=bool(render and not projected_present),
                )
            except Exception:
                if not projected_present:
                    try:
                        ctx.request_light_render()
                    except Exception:
                        pass
        if projected_present:
            try:
                projected.render_tool(owner, render=render)
            except Exception:
                try:
                    ctx.request_light_render()
                except Exception:
                    pass
        return result

    if result.visual_changed or result.selection_cleared:
        if legacy_present:
            try:
                from .gizmos import refresh_creator_ui_interaction

                refresh_creator_ui_interaction(
                    ctx,
                    owner_tool=owner,
                    render=bool(render and not projected_present),
                )
            except Exception:
                if not projected_present:
                    try:
                        ctx.request_light_render()
                    except Exception:
                        pass
        if projected_present:
            try:
                projected.render_tool(owner, render=render)
            except Exception:
                try:
                    ctx.request_light_render()
                except Exception:
                    pass
    elif projected_changed and projected_present:
        try:
            projected.render_tool(owner, render=render)
        except Exception:
            pass
    return result


def tool_event_uses_left_button(event: ToolEvent) -> ToolEvent:
    """Return ``event`` with left-button semantics for drag moves.

    Qt/VTK backends often report move events with buttons held in a backend
    field, not as a normal mouse button.  Application bridges may use this tiny
    helper when converting such moves into Creator API ``ToolEvent`` objects.
    """

    if event.button == MouseButton.LEFT:
        return event
    from dataclasses import replace

    return replace(event, button=MouseButton.LEFT)


__all__ = ["ActorInteractionResult", "DragPositionResolver", "handle_native_creator_ui_event", "hover_select_grab_actors", "select_or_grab", "tool_event_uses_left_button"]
