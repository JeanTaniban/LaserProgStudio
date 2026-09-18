# -*- coding: utf-8 -*-
"""Small Creator-tool helpers for stale preview handling.

A preview is a commit-able document state.  When the user edits parameters,
changes the target selection or presses an action such as Recenter/Reset, the
old preview may no longer match the visible inspector values.  Tools should
cancel only their own active preview before reporting the new state.
"""
from __future__ import annotations

from typing import Any


def cancel_tool_preview_if_active(ctx: Any, owner_tool: str, *, status: str | None = None) -> bool:
    """Cancel the current preview session if it belongs to ``owner_tool``.

    Returns ``True`` when a preview was actually discarded.  The helper is
    intentionally defensive: stale-preview cleanup must never make a field
    callback fail.
    """

    try:
        session = getattr(getattr(ctx, "preview_session", None), "current", None)
        if session is None or not bool(getattr(session, "active", False)):
            return False
        if str(getattr(session, "owner_tool", "")) != str(owner_tool):
            return False
        changed = bool(ctx.preview_session.cancel())
        if changed and status:
            try:
                ctx.status.info(str(status))
            except Exception:
                pass
        return changed
    except Exception:
        return False
