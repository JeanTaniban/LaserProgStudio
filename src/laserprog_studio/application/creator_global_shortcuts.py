# -*- coding: utf-8 -*-
"""Route application-level shortcuts through active Creator tools first.

Qt ``QAction`` shortcuts can fire before the main window ``keyPressEvent``.
This module keeps global Esc/Delete behavior aligned with the public Creator
ToolEvent API so tools such as Plan Tracer can cancel placements or delete
sketch elements without closing the whole tool or touching scene-part selection.
"""
from __future__ import annotations

from typing import Any

from ..studio_log import log_exception


def dispatch_creator_key_shortcut(owner: Any, key_name: str, *, modifiers: frozenset[str] | None = None) -> bool:
    try:
        from .creator_pointer_interaction import active_creator_tool_for_pointer
        from ..tool_core.events import ToolEvent, ToolEventType

        creator_tool = active_creator_tool_for_pointer(owner)
        if creator_tool is None:
            return False
        return bool(
            creator_tool.on_event(
                ToolEvent(ToolEventType.KEY_PRESS, key=str(key_name), modifiers=frozenset(modifiers or ())),
                getattr(owner, "context", None),
            )
        )
    except Exception:
        log_exception("creator_global_shortcut_dispatch")
        return False


def handle_creator_escape_shortcut(owner: Any) -> None:
    if dispatch_creator_key_shortcut(owner, "escape"):
        return
    # Some Qt shortcut paths can fire without the viewport pointer adapter being
    # able to build a full key event.  Before falling back to a destructive tool
    # close, give the active runtime its public cancel hook.  Plan Tracer
    # overrides CreatorTool.cancel so this cancels only the current placement and
    # keeps the tool open.
    try:
        from ..tooling.registry import get_studio_tool

        active = getattr(owner, "active_tool", None)
        tool = get_studio_tool(active)
        cancel = getattr(tool, "cancel", None)
        if callable(cancel) and bool(cancel(getattr(owner, "context", None))):
            return
    except Exception:
        pass
    owner.close_active_tool()


def handle_creator_delete_shortcut(owner: Any) -> None:
    if dispatch_creator_key_shortcut(owner, "delete"):
        return
    owner.delete_selected()


def handle_creator_undo_shortcut(owner: Any) -> None:
    if dispatch_creator_key_shortcut(owner, "z", modifiers=frozenset({"ctrl"})):
        return
    owner.undo_scene()


def handle_creator_redo_shortcut(owner: Any) -> None:
    if dispatch_creator_key_shortcut(owner, "y", modifiers=frozenset({"ctrl"})):
        return
    owner.redo_scene()


__all__ = [
    "dispatch_creator_key_shortcut",
    "handle_creator_escape_shortcut",
    "handle_creator_delete_shortcut",
    "handle_creator_undo_shortcut",
    "handle_creator_redo_shortcut",
]
