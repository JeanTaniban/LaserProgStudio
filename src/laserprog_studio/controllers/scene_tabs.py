# -*- coding: utf-8 -*-
from __future__ import annotations

from .scene_tabs_actions import SceneTabsActionLayer
from .scene_tabs_drag import SceneTabsDragLayer
from .scene_tabs_frame import DraggableSceneTabFrame
from .scene_tabs_sync import SceneTabsSyncLayer


class SceneTabsLayer(SceneTabsActionLayer, SceneTabsDragLayer, SceneTabsSyncLayer):
    """Scene tab behavior composed from focused tab modules."""

    pass


__all__ = ["DraggableSceneTabFrame", "SceneTabsLayer"]
