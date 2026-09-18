# -*- coding: utf-8 -*-
"""Production rubber-band rendering for Creator API box selection.

The box-selection manager intentionally owns only semantic screen-space state.
This bridge is the single application/Qt adapter that mirrors that state into a
persistent VTK 2D overlay.  Keeping it outside individual tools prevents each
Creator workflow from implementing a slightly different and fragile rectangle.
"""
from __future__ import annotations

from typing import Any

from ..studio_log import log_exception

_OVERLAY_ATTR = "_creator_selection_box_overlay"


def selection_box_pending(ctx: Any) -> bool:
    try:
        return bool(ctx.selection_box.pending)
    except Exception:
        return False



def ensure_renderer_props(renderer: Any, actors: tuple[Any, ...]) -> bool:
    """Compatibility helper for targeted overlay props.

    The selection widget no longer imports this application module at runtime;
    keeping the helper public preserves API/tests without coupling the global
    projected-drawing renderer to the rubber-band implementation.
    """

    if renderer is None or any(actor is None for actor in actors):
        return False
    try:
        props = renderer.GetViewProps() if hasattr(renderer, "GetViewProps") else None
    except Exception:
        props = None
    for actor in actors:
        present = False
        try:
            has_prop = getattr(renderer, "HasViewProp", None)
            if callable(has_prop):
                present = bool(has_prop(actor))
            elif props is not None and hasattr(props, "IsItemPresent"):
                present = bool(props.IsItemPresent(actor))
        except Exception:
            present = False
        if present:
            continue
        try:
            add2d = getattr(renderer, "AddActor2D", None)
            if callable(add2d):
                add2d(actor)
            else:
                renderer.AddActor(actor)
        except Exception:
            return False
    return True

def sync_creator_selection_box_overlay(owner: Any, ctx: Any) -> None:
    """Show or update the active Creator rectangle, otherwise hide it."""

    try:
        manager = ctx.selection_box
        state = manager.state
        rect = state.rect
        if not bool(state.pending and state.active) or rect is None:
            hide_creator_selection_box_overlay(owner)
            return
        from PySide6.QtCore import QPoint, QRect

        qt_rect = QRect(
            QPoint(int(round(rect.left)), int(round(rect.top))),
            QPoint(int(round(rect.right)), int(round(rect.bottom))),
        ).normalized()
        overlay = _ensure_overlay(owner)
        if overlay is None:
            return
        overlay.set_selection_rect(qt_rect)
        overlay.raise_()
        if not overlay.isVisible():
            overlay.show()
    except Exception:
        log_exception("creator_selection_box_overlay_sync")


def hide_creator_selection_box_overlay(owner: Any) -> None:
    try:
        overlay = getattr(owner, _OVERLAY_ATTR, None)
        if overlay is None:
            return
        try:
            overlay.clear_selection_rect()
        except Exception:
            pass
        overlay.hide()
    except Exception:
        pass


def dispose_creator_selection_box_overlay(owner: Any) -> None:
    """Remove the persistent overlay when a viewport is being destroyed."""

    overlay = getattr(owner, _OVERLAY_ATTR, None)
    if overlay is None:
        return
    try:
        overlay.dispose()
    except Exception:
        try:
            overlay.hide()
        except Exception:
            pass
    try:
        delattr(owner, _OVERLAY_ATTR)
    except Exception:
        pass


def _ensure_overlay(owner: Any) -> Any | None:
    overlay = getattr(owner, _OVERLAY_ATTR, None)
    if overlay is not None:
        return overlay
    try:
        from ..ui.selection_box_overlay import SelectionBoxOverlay

        overlay = SelectionBoxOverlay(owner.plotter)
        setattr(owner, _OVERLAY_ATTR, overlay)
        return overlay
    except Exception:
        log_exception("creator_selection_box_overlay_create")
        return None


__all__ = [
    "dispose_creator_selection_box_overlay",
    "ensure_renderer_props",
    "hide_creator_selection_box_overlay",
    "selection_box_pending",
    "sync_creator_selection_box_overlay",
]
