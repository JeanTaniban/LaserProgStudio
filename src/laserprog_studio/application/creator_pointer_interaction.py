# -*- coding: utf-8 -*-
"""Bridge Qt pointer events to interactive Creator API actors.

The public interaction logic lives in :mod:`laserprog_studio.tool_api.interaction`.
This module only adapts the application viewport coordinates to the generic tool
API event model so controller files stay thin.
"""
from __future__ import annotations

from typing import Any

from ..studio_log import log_exception


def _is_plan_trace_tool(tool: Any, owner: Any | None = None) -> bool:
    try:
        if str(getattr(tool, "id", "")) == "plan_trace":
            return True
    except Exception:
        pass
    try:
        return str(getattr(owner, "active_tool", "")) == "plan_trace"
    except Exception:
        return False


def _record_plan_trace_bridge(stage: str, owner: Any, ctx: Any, tool: Any, etype: Any, event: Any, qx: float, qy: float, buttons: Any, *, Qt: Any, QEvent: Any, **payload: Any) -> None:
    if not _is_plan_trace_tool(tool, owner):
        return
    try:
        from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_creator_bridge_event

        record_creator_bridge_event(stage, owner, ctx, tool, etype, event, qx, qy, buttons, Qt=Qt, QEvent=QEvent, **payload)
    except Exception:
        pass


def active_creator_tool_for_pointer(owner: Any):
    """Return the active Creator tool only when it can receive API events."""
    try:
        active = getattr(owner, "active_tool", getattr(owner, "TOOL_NONE", "none"))
        if active == getattr(owner, "TOOL_NONE", "none"):
            return None
        from ..tooling.registry import get_studio_tool

        tool = get_studio_tool(active)
        if tool is None or not callable(getattr(tool, "on_event", None)) or not callable(getattr(tool, "tool_context", None)):
            return None
        return tool
    except Exception:
        return None


def creator_world_at_qt(owner: Any, qx: float, qy: float, depth: float):
    """Project a Qt viewport point back to world coordinates at a display depth."""
    try:
        h = float(owner.plotter.height())
        return tuple(float(v) for v in owner._display_to_world_at_depth(float(qx), h - float(qy), float(depth)))
    except Exception:
        return None


def creator_depth_for_hit_or_selection(owner: Any, ctx: Any, qx: float, qy: float) -> float:
    """Choose a stable depth for Creator actor drag from hit/selection context."""
    try:
        actor = None
        # During a native grab the actor is already known.  Re-hit-testing the
        # whole Creator scene on every mouse move is unnecessary and was one of
        # the remaining differences with Tool Core Diagnostic.
        state = getattr(ctx.selection, "state", None)
        grabbed_ids = tuple(getattr(state, "grabbed_ids", ()) or ())
        if bool(getattr(state, "grab_active", False)) and grabbed_ids:
            actor = ctx.selection.actor(grabbed_ids[0])
        if actor is None:
            try:
                from ..tool_api.scene import projection_cache_signature

                projection_key = projection_cache_signature(ctx)
            except Exception:
                projection_key = None
            hit = ctx.selection.hit_test(
                (float(qx), float(qy)),
                ctx.viewport.world_to_screen,
                owner_tool=getattr(owner, "active_tool", None),
                selectable_only=True,
                projection_key=projection_key,
            )
            actor = None if hit is None else ctx.selection.actor(hit.actor_id)
        if actor is None and grabbed_ids:
            actor = ctx.selection.actor(grabbed_ids[0])
        if actor is None and ctx.selection.ids():
            actor = ctx.selection.actor(ctx.selection.ids()[0])
        if actor is not None and actor.primary_position is not None:
            _x, _y, z = owner._world_to_display(tuple(float(v) for v in actor.primary_position))
            return float(z)
    except Exception:
        pass
    return 0.5




_CAMERA_NAV_ACTIVE_ATTR = "_creator_camera_navigation_active"
_CAMERA_NAV_MODE_ATTR = "_creator_camera_navigation_mode"
_CAMERA_NAV_POS_ATTR = "_creator_camera_navigation_screen_pos"
_CAMERA_NAV_GENERATION_ATTR = "_creator_camera_navigation_generation"
_CAMERA_NAV_TOOL_ATTR = "_creator_camera_navigation_tool"
_PASSTHROUGH_PRESS_POS_ATTR = "_creator_passthrough_press_screen_pos"
_PASSTHROUGH_PRESS_TOOL_ATTR = "_creator_passthrough_press_tool"
_PASSTHROUGH_DRAG_THRESHOLD_PX = 6.0


def _remember_passthrough_press(owner: Any, tool: Any, screen_pos: tuple[float, float] | None) -> None:
    try:
        setattr(owner, _PASSTHROUGH_PRESS_TOOL_ATTR, tool)
        setattr(
            owner,
            _PASSTHROUGH_PRESS_POS_ATTR,
            None if screen_pos is None else (float(screen_pos[0]), float(screen_pos[1])),
        )
    except Exception:
        pass


def _clear_passthrough_press(owner: Any) -> None:
    try:
        setattr(owner, _PASSTHROUGH_PRESS_TOOL_ATTR, None)
        setattr(owner, _PASSTHROUGH_PRESS_POS_ATTR, None)
    except Exception:
        pass


def _passthrough_drag_exceeds_threshold(owner: Any, tool: Any, screen_pos: tuple[float, float]) -> bool | None:
    """Return True/False for a recorded click candidate, or None if absent."""

    if getattr(owner, _PASSTHROUGH_PRESS_TOOL_ATTR, None) is not tool:
        return None
    origin = getattr(owner, _PASSTHROUGH_PRESS_POS_ATTR, None)
    if origin is None:
        return None
    try:
        dx = float(screen_pos[0]) - float(origin[0])
        dy = float(screen_pos[1]) - float(origin[1])
        return max(abs(dx), abs(dy)) > _PASSTHROUGH_DRAG_THRESHOLD_PX
    except Exception:
        return None


def _finish_consumed_passthrough_release(owner: Any) -> None:
    """Balance the VTK press when a Creator tool consumes its short release.

    Folding, Cloth and Plan Tracer intentionally pass the press to VTK so a
    left drag can orbit.  When the gesture resolves as a click, Creator consumes
    the release before the controller/VTK path sees it.  Explicitly reset both
    host latches and VTK button state here; otherwise the next hover/click can
    look like a still-active camera drag.
    """

    reset = getattr(owner, "_reset_viewport_pointer_state", None)
    if callable(reset):
        try:
            reset(release_vtk=True)
            return
        except Exception:
            pass
    try:
        setattr(owner, "_viewport_pointer_buttons_down", False)
        setattr(owner, "_creator_camera_navigation_candidate_mode", "")
        setattr(owner, "_qt_click_pos", None)
    except Exception:
        pass
    release = getattr(owner, "_release_vtk_mouse_buttons", None)
    if callable(release):
        try:
            release()
        except Exception:
            pass


def creator_camera_navigation_active(owner: Any) -> bool:
    """Return whether the host viewport currently owns pointer navigation."""

    return bool(getattr(owner, _CAMERA_NAV_ACTIVE_ATTR, False))


def _camera_navigation_callback(tool: Any, ctx: Any, name: str, **payload: Any) -> None:
    try:
        creator = getattr(tool, "creator", tool)
        callback = getattr(creator, name, None)
        if callable(callback):
            callback(ctx, **payload)
    except Exception:
        log_exception(f"creator_{name}")


def begin_creator_camera_navigation(
    owner: Any,
    tool: Any,
    *,
    mode: str,
    screen_pos: tuple[float, float] | None = None,
    renew: bool = False,
) -> int:
    """Enter the camera-exclusive fast path for one Creator tool.

    ``renew`` is used by wheel/trackpad zoom pulses to re-arm the end debounce
    without emitting a second begin callback. Pointer drags use the persistent
    owner flag so transient QVTK ``NoButton`` move events cannot fall back into
    expensive Creator hover/snap handling.
    """

    was_active = creator_camera_navigation_active(owner)
    old_mode = str(getattr(owner, _CAMERA_NAV_MODE_ATTR, "") or "")
    resolved_mode = str(mode or old_mode or "mixed")
    generation = int(getattr(owner, _CAMERA_NAV_GENERATION_ATTR, 0) or 0)
    if renew or not was_active:
        generation += 1
        try:
            setattr(owner, _CAMERA_NAV_GENERATION_ATTR, generation)
        except Exception:
            pass
    try:
        setattr(owner, _CAMERA_NAV_ACTIVE_ATTR, True)
        setattr(owner, _CAMERA_NAV_MODE_ATTR, resolved_mode)
        setattr(owner, _CAMERA_NAV_TOOL_ATTR, tool)
        if screen_pos is not None:
            setattr(owner, _CAMERA_NAV_POS_ATTR, (float(screen_pos[0]), float(screen_pos[1])))
    except Exception:
        pass

    if not was_active:
        try:
            ctx = tool.tool_context(owner.context)
            _camera_navigation_callback(
                tool,
                ctx,
                "on_camera_interaction_begin",
                mode=resolved_mode,
                screen_pos=screen_pos,
            )
        except Exception:
            log_exception("creator_camera_navigation_begin")
    try:
        from ..diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.increment("creator.camera_navigation.begin" if not was_active else "creator.camera_navigation.extend")
        audit.increment(f"creator.camera_navigation.mode.{resolved_mode}")
        audit.set_value("creator.camera_navigation.last_mode", resolved_mode)
    except Exception:
        pass
    return generation


def finish_creator_camera_navigation(
    owner: Any,
    tool: Any,
    *,
    screen_pos: tuple[float, float] | None = None,
    generation: int | None = None,
) -> bool:
    """Leave camera-exclusive mode and run one deferred tool catch-up."""

    if generation is not None and int(generation) != int(getattr(owner, _CAMERA_NAV_GENERATION_ATTR, 0) or 0):
        return False
    if not creator_camera_navigation_active(owner):
        return False
    mode = str(getattr(owner, _CAMERA_NAV_MODE_ATTR, "mixed") or "mixed")
    if screen_pos is None:
        stored = getattr(owner, _CAMERA_NAV_POS_ATTR, None)
        if stored is not None:
            try:
                screen_pos = (float(stored[0]), float(stored[1]))
            except Exception:
                screen_pos = None
    stored_tool = getattr(owner, _CAMERA_NAV_TOOL_ATTR, None)
    callback_tool = stored_tool if stored_tool is not None else tool
    if callback_tool is not None and not callable(getattr(callback_tool, "tool_context", None)):
        callback_tool = tool if callable(getattr(tool, "tool_context", None)) else None
    try:
        setattr(owner, _CAMERA_NAV_ACTIVE_ATTR, False)
        setattr(owner, _CAMERA_NAV_MODE_ATTR, "static")
        setattr(owner, _CAMERA_NAV_TOOL_ATTR, None)
        if screen_pos is not None:
            setattr(owner, _CAMERA_NAV_POS_ATTR, screen_pos)
    except Exception:
        pass

    if callback_tool is not None:
        try:
            ctx = callback_tool.tool_context(owner.context)
            _camera_navigation_callback(
                callback_tool,
                ctx,
                "on_camera_interaction_end",
                mode=mode,
                screen_pos=screen_pos,
            )
        except Exception:
            log_exception("creator_camera_navigation_end")
    try:
        from ..diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.increment("creator.camera_navigation.end")
        audit.increment(f"creator.camera_navigation.end_mode.{mode}")
    except Exception:
        pass
    return True


def _camera_mode_from_buttons(owner: Any, buttons: Any, *, Qt: Any) -> str:
    try:
        if bool(buttons & Qt.RightButton):
            return "pan"
        if bool(buttons & Qt.MiddleButton):
            return "pan"
        if bool(buttons & Qt.LeftButton):
            return "orbit"
    except Exception:
        pass
    if bool(getattr(owner, "_right_pan_active", False)):
        return "pan"
    candidate = str(getattr(owner, "_creator_camera_navigation_candidate_mode", "") or "")
    if candidate:
        return candidate
    return str(getattr(owner, _CAMERA_NAV_MODE_ATTR, "mixed") or "mixed")


def _creator_press_passthrough_requested(tool: Any, ctx: Any, tool_event: Any) -> bool:
    """Let tools opt out of consuming press events used for camera gestures.

    Some Creator workflows start with a click pick but must still allow the host
    viewport to orbit on left-drag.  The tool can record the press and return
    True here; the bridge then lets Qt/VTK handle the press and forwards the
    release later so the tool can decide whether it was a click or a drag.
    """

    try:
        creator = getattr(tool, "creator", tool)
        callback = getattr(creator, "wants_pointer_press_passthrough", None)
        if callable(callback):
            return bool(callback(tool_event, ctx))
    except Exception:
        log_exception("creator_pointer_press_passthrough")
    return False


def _creator_release_passthrough_requested(tool: Any, ctx: Any, tool_event: Any) -> bool:
    """Return whether a camera-owned release must still be offered to a tool.

    Press passthrough workflows use VTK for possible camera drags but still need
    a short release to complete a click-like action.  Without this hook a tiny
    pointer jitter could start camera-exclusive mode and starve the release,
    leaving Plan Tracer stuck in camera navigation after surface selection.
    """

    try:
        creator = getattr(tool, "creator", tool)
        callback = getattr(creator, "wants_pointer_release_passthrough", None)
        if callable(callback):
            return bool(callback(tool_event, ctx))
    except Exception:
        log_exception("creator_pointer_release_passthrough")
    return False


def handle_creator_tool_pointer_event(
    owner: Any,
    tool: Any,
    etype: Any,
    event: Any,
    qx: float,
    qy: float,
    buttons: Any,
    *,
    Qt: Any,
    QEvent: Any,
) -> bool:
    """Forward Qt mouse events to the active Creator tool, preserving camera misses."""
    try:
        from ..tool_core.events import MouseButton, ToolEvent, ToolEventType

        if etype not in {QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick}:
            return False
        button = MouseButton.NONE
        if etype == QEvent.MouseButtonPress or etype == QEvent.MouseButtonRelease or etype == QEvent.MouseButtonDblClick:
            qt_button = event.button()
            if qt_button == Qt.LeftButton:
                button = MouseButton.LEFT
            elif qt_button == Qt.MiddleButton:
                button = MouseButton.MIDDLE
            elif qt_button == Qt.RightButton:
                button = MouseButton.RIGHT
        elif bool(buttons & Qt.LeftButton):
            button = MouseButton.LEFT
        if button not in {MouseButton.LEFT, MouseButton.NONE}:
            return False
        ctx = tool.tool_context(owner.context)
        from .creator_box_selection_overlay import (
            hide_creator_selection_box_overlay,
            selection_box_pending,
            sync_creator_selection_box_overlay,
        )

        box_pending_at_entry = selection_box_pending(ctx)
        _record_plan_trace_bridge(
            "creator_bridge.entry",
            owner,
            ctx,
            tool,
            etype,
            event,
            qx,
            qy,
            buttons,
            Qt=Qt,
            QEvent=QEvent,
            resolved_button=str(getattr(button, "value", button)),
        )

        # Camera-exclusive fast path. QVTK may transiently report NoButton while
        # a host-owned drag is still active, so raw event.buttons() alone is not
        # sufficient. Persist the navigation state until release and suppress all
        # Creator hover/snap/hit-test work during pan/orbit/zoom.
        # Do not use the controller's generic "a button went down" latch to
        # *start* camera-exclusive mode.  Some Qt/QVTK release paths can leave
        # that latch stale for one event; if a plain hover then sees it as true,
        # Plan Tracer suppresses cursor/snap forever and the cursor appears stuck
        # at the center.  Once navigation has started, the persistent creator flag
        # below is enough to survive transient QVTK NoButton drag frames.
        right_context_pending = bool(
            getattr(owner, "_right_context_candidate", False)
            and not getattr(owner, "_right_pan_active", False)
        )
        camera_owned_pointer = bool(
            (buttons != Qt.NoButton and not right_context_pending)
            or getattr(owner, "_right_pan_active", False)
            or creator_camera_navigation_active(owner)
        )
        _record_plan_trace_bridge(
            "creator_bridge.camera_gate",
            owner,
            ctx,
            tool,
            etype,
            event,
            qx,
            qy,
            buttons,
            Qt=Qt,
            QEvent=QEvent,
            camera_owned_pointer=camera_owned_pointer,
            grab_active=bool(ctx.selection.state.grab_active),
            buttons_not_nobutton=bool(buttons != Qt.NoButton),
            right_context_pending=right_context_pending,
            right_pan_active=bool(getattr(owner, "_right_pan_active", False)),
            owner_camera_active=creator_camera_navigation_active(owner),
        )
        if etype == QEvent.MouseMove and right_context_pending:
            # The viewport controller owns the small right-click/right-drag
            # threshold.  Do not let Creator mark the gesture as camera-owned
            # or forward it as hover, otherwise Plan Tracer 2D never reaches
            # the controller path that starts the custom right-pan.
            _record_plan_trace_bridge(
                "creator_bridge.drop.pending_right_context",
                owner,
                ctx,
                tool,
                etype,
                event,
                qx,
                qy,
                buttons,
                Qt=Qt,
                QEvent=QEvent,
            )
            return False
        if (
            etype == QEvent.MouseMove
            and camera_owned_pointer
            and not bool(ctx.selection.state.grab_active)
            and not selection_box_pending(ctx)
        ):
            candidate_drag = _passthrough_drag_exceeds_threshold(owner, tool, (float(qx), float(qy)))
            if candidate_drag is False and not creator_camera_navigation_active(owner):
                # Keep a short left click available to the Creator tool. VTK may
                # still observe the move, but the bridge does not enter its
                # camera-exclusive fast path until the shared drag threshold is
                # crossed. This prevents ordinary pointer jitter from starving
                # Folding/Cloth hover and release picking.
                return False
            mode = _camera_mode_from_buttons(owner, buttons, Qt=Qt)
            begin_creator_camera_navigation(
                owner,
                tool,
                mode=mode,
                screen_pos=(float(qx), float(qy)),
            )
            try:
                from ..diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                audit.increment("creator.camera_navigation.skipped_move")
                audit.increment(f"creator.camera_navigation.skipped_move.{mode}")
            except Exception:
                pass
            _record_plan_trace_bridge(
                "creator_bridge.drop.camera_navigation_move",
                owner,
                ctx,
                tool,
                etype,
                event,
                qx,
                qy,
                buttons,
                Qt=Qt,
                QEvent=QEvent,
                mode=mode,
            )
            return False
        if (
            etype == QEvent.MouseButtonRelease
            and creator_camera_navigation_active(owner)
            and not bool(ctx.selection.state.grab_active)
            and not selection_box_pending(ctx)
        ):
            # A press-passthrough tool may still need the release to decide
            # between "short click" and "camera drag".  Offer it the release
            # before suppressing normal Creator work; if it consumes the click,
            # end camera-exclusive state immediately so Plan Tracer does not stay
            # blocked in orbit mode after locking the drawing plane.
            release_event = ToolEvent(
                ToolEventType.MOUSE_RELEASE,
                screen_pos=(float(qx), float(qy)),
                world_pos=None,
                button=button,
                raw=event,
            )
            if _creator_release_passthrough_requested(tool, ctx, release_event):
                try:
                    if bool(tool.on_event(release_event, owner.context)):
                        _finish_consumed_passthrough_release(owner)
                        _clear_passthrough_press(owner)
                        finish_creator_camera_navigation(owner, tool, screen_pos=(float(qx), float(qy)))
                        return True
                except Exception:
                    log_exception("creator_pointer_release_passthrough_event")
            # The controller finishes this state on the next Qt turn, after VTK
            # has consumed the release and committed its final camera position.
            try:
                setattr(owner, _CAMERA_NAV_POS_ATTR, (float(qx), float(qy)))
            except Exception:
                pass
            _clear_passthrough_press(owner)
            _record_plan_trace_bridge(
                "creator_bridge.drop.camera_navigation_release",
                owner,
                ctx,
                tool,
                etype,
                event,
                qx,
                qy,
                buttons,
                Qt=Qt,
                QEvent=QEvent,
            )
            return False

        # Hover does not need a world position.  Avoid the extra depth hit-test;
        # the native interaction runtime will perform the single required
        # screen-space hit-test for hover state.
        if etype == QEvent.MouseMove and button == MouseButton.NONE:
            world = None
        else:
            depth = creator_depth_for_hit_or_selection(owner, ctx, qx, qy)
            world = creator_world_at_qt(owner, qx, qy, depth)
        modifiers = set()
        try:
            mods = event.modifiers()
            if mods & Qt.ShiftModifier:
                modifiers.add("shift")
            if mods & Qt.ControlModifier:
                modifiers.add("ctrl")
            if mods & Qt.AltModifier:
                modifiers.add("alt")
        except Exception:
            pass
        event_type = {
            QEvent.MouseButtonPress: ToolEventType.MOUSE_PRESS,
            QEvent.MouseMove: ToolEventType.MOUSE_MOVE,
            QEvent.MouseButtonRelease: ToolEventType.MOUSE_RELEASE,
            QEvent.MouseButtonDblClick: ToolEventType.MOUSE_DOUBLE_CLICK,
        }[etype]
        tool_event = ToolEvent(
            event_type,
            screen_pos=(float(qx), float(qy)),
            world_pos=world,
            button=button,
            modifiers=frozenset(modifiers),
            raw=event,
        )
        if etype == QEvent.MouseButtonPress and _creator_press_passthrough_requested(tool, ctx, tool_event):
            _remember_passthrough_press(owner, tool, tool_event.screen_pos)
            _record_plan_trace_bridge(
                "creator_bridge.press_passthrough",
                owner,
                ctx,
                tool,
                etype,
                event,
                qx,
                qy,
                buttons,
                Qt=Qt,
                QEvent=QEvent,
                world=world,
            )
            return False
        _record_plan_trace_bridge(
            "creator_bridge.forward_tool",
            owner,
            ctx,
            tool,
            etype,
            event,
            qx,
            qy,
            buttons,
            Qt=Qt,
            QEvent=QEvent,
            world=world,
            event_type=str(getattr(event_type, "value", event_type)),
        )
        passthrough_release = bool(
            etype == QEvent.MouseButtonRelease
            and getattr(owner, _PASSTHROUGH_PRESS_TOOL_ATTR, None) is tool
        )
        handled = bool(tool.on_event(tool_event, owner.context))
        box_pending_after = selection_box_pending(ctx)
        box_owned_gesture = bool(box_pending_at_entry or box_pending_after)
        if etype == QEvent.MouseButtonRelease:
            hide_creator_selection_box_overlay(owner)
        elif box_pending_after:
            sync_creator_selection_box_overlay(owner, ctx)
        else:
            hide_creator_selection_box_overlay(owner)
        if passthrough_release and handled:
            _finish_consumed_passthrough_release(owner)
        if etype == QEvent.MouseButtonRelease:
            _clear_passthrough_press(owner)
        _record_plan_trace_bridge(
            "creator_bridge.forward_tool_result",
            owner,
            ctx,
            tool,
            etype,
            event,
            qx,
            qy,
            buttons,
            Qt=Qt,
            QEvent=QEvent,
            handled=handled,
            box_owned_gesture=box_owned_gesture,
        )
        # Once a Creator selection-box gesture begins, the bridge owns every
        # move and the matching release even when the rectangle never crosses
        # the minimum drag threshold.  Letting those events leak to QVTK is what
        # previously left the camera/button latch active until the next click.
        return bool(handled or box_owned_gesture)
    except Exception:
        log_exception("creator_tool_pointer_event")
        return False


__all__ = [
    "active_creator_tool_for_pointer",
    "begin_creator_camera_navigation",
    "creator_camera_navigation_active",
    "creator_depth_for_hit_or_selection",
    "finish_creator_camera_navigation",
    "_creator_press_passthrough_requested",
    "_creator_release_passthrough_requested",
    "creator_world_at_qt",
    "handle_creator_tool_pointer_event",
]
