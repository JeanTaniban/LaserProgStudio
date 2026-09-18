# -*- coding: utf-8 -*-
"""Historical aggregate for boolean, clipboard, scene-edit and history actions."""
from __future__ import annotations

from laserprog_studio.controllers.boolean_actions import BooleanActionsLayer
from laserprog_studio.controllers.clipboard_actions import ClipboardActionsLayer
from laserprog_studio.controllers.history_actions import HistoryActionsLayer
from laserprog_studio.controllers.scene_edit_actions import SceneEditActionsLayer


class BooleanClipboardHistoryLayer(
    BooleanActionsLayer,
    ClipboardActionsLayer,
    SceneEditActionsLayer,
    HistoryActionsLayer,
):
    """Composition aggregate; new code should use the focused layers."""

    pass


__all__ = ["BooleanClipboardHistoryLayer"]
