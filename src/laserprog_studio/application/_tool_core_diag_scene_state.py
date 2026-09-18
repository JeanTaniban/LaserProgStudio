# -*- coding: utf-8 -*-
"""Persistent actor state and cleanup helpers for Tool Core viewport UI scenes."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_ACTOR_PREFIX = "tool_core_diag_ui_"


def _diag(stage: str, owner: Any = None, owner_tool: str = "", **payload: Any) -> None:
    try:
        from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

        record_projected_overlay_event(f"diag_scene_state.{stage}", owner=owner, owner_tool=str(owner_tool or ""), **payload)
    except Exception:
        pass


@dataclass(slots=True)
class _DiagActorState:
    actor_names: set[str] = field(default_factory=set)
    actors: dict[str, Any] = field(default_factory=dict)
    meshes: dict[str, Any] = field(default_factory=dict)
    label_signature: tuple[tuple[str, tuple[float, float, float]], ...] = ()
    handle_point_refs: dict[str, list[tuple[str, int, int]]] = field(default_factory=dict)
    handle_positions: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    preview_point_refs: dict[str, list[tuple[str, int, int]]] = field(default_factory=dict)


def _state(owner: Any, state_attr: str = "_tool_core_diag_scene_state") -> _DiagActorState:
    state = getattr(owner, state_attr, None)
    if not isinstance(state, _DiagActorState):
        state = _DiagActorState()
        try:
            setattr(owner, state_attr, state)
        except Exception:
            pass
    return state


def clear_tool_core_ui_scene(
    owner: Any,
    *,
    actor_prefix: str = _ACTOR_PREFIX,
    state_attr: str = "_tool_core_diag_scene_state",
    actor_names_attr: str = "_tool_core_diag_actor_names",
    render: bool = True,
) -> int:
    """Remove actors created by a Tool Core UI painter without touching user meshes."""
    plotter = getattr(owner, "plotter", None)
    _diag("clear.start", owner=owner, owner_tool=str(actor_prefix), actor_prefix=actor_prefix, state_attr=state_attr, render=bool(render), has_plotter=plotter is not None)
    if plotter is None:
        _diag("clear.no_plotter", owner=owner, owner_tool=str(actor_prefix))
        return 0
    state = _state(owner, state_attr)
    names = set(state.actor_names)
    names.update(getattr(owner, actor_names_attr, []) or [])
    try:
        actors = getattr(plotter, "actors", {}) or {}
        names.update(str(name) for name in actors if str(name).startswith(actor_prefix))
    except Exception:
        pass
    removed = 0
    for name in sorted(names):
        try:
            plotter.remove_actor(name, render=False)
            removed += 1
        except Exception as exc:
            _diag("clear.remove_exception", owner=owner, owner_tool=str(actor_prefix), name=name, error_type=type(exc).__name__)
    state.actor_names.clear()
    state.actors.clear()
    state.meshes.clear()
    state.label_signature = ()
    state.handle_point_refs.clear()
    state.handle_positions.clear()
    state.preview_point_refs.clear()
    try:
        setattr(owner, actor_names_attr, [])
    except Exception:
        pass
    if render:
        try:
            plotter.render()
        except Exception as exc:
            _diag("clear.render_exception", owner=owner, owner_tool=str(actor_prefix), error_type=type(exc).__name__)
    _diag("clear.done", owner=owner, owner_tool=str(actor_prefix), removed=int(removed), names_count=len(names), names_sample=sorted(names)[:24])
    return removed


def clear_tool_core_diag_scene(owner: Any) -> int:
    """Remove actors created by the diagnostic showcase without touching user meshes."""
    return clear_tool_core_ui_scene(owner)
