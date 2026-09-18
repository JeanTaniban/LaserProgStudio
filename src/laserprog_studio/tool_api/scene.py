"""Scene/document public contracts for creator tools.

Use this namespace when a tool needs to read or modify the real document,
inspect scene selection, run picking, manage preview sessions or access snap
and scene-cache data.
"""
from __future__ import annotations

from laserprog_studio.tool_core.box_selection import BoxSelectionActivationModifier, BoxSelectionConfig, BoxSelectionInsidePolicy, BoxSelectionManager, BoxSelectionMode, BoxSelectionResult, BoxSelectionState, BoxSelectionTarget, ScreenRect
from laserprog_studio.tool_core.app_services import (
    DocumentFacade,
    DocumentObject,
    PickResult,
    PickingFacade,
    PreviewSession,
    PreviewSessionManager,
    LinkedSceneOutputResult,
    ProjectScenesFacade,
    SceneSelectionFacade,
    ToolServiceError,
)
from laserprog_studio.tool_core.scene_cache import SceneBounds, SceneCache, SceneCacheSummary, ScenePoint, SceneSegment
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, SelectionManager, ToolActor
from laserprog_studio.tool_core.snap import SnapManager, SnapResult, SnapSource, SnapTarget

from . import actors, interaction, selection_box, snap


def projection_cache_signature(ctx):
    """Return a stable signature for cached scene projection/snap data.

    Plan-style Creator tools use this public wrapper to invalidate their own
    high-frequency caches without importing the historical scene-cache module.
    """

    from laserprog_studio.tool_core.scene_cache import projection_cache_signature as _projection_cache_signature

    return _projection_cache_signature(ctx)

__all__ = [
    "ActorInteraction",
    "ActorKind",
    "BoxSelectionActivationModifier",
    "BoxSelectionConfig",
    "BoxSelectionInsidePolicy",
    "BoxSelectionManager",
    "BoxSelectionMode",
    "BoxSelectionResult",
    "BoxSelectionState",
    "BoxSelectionTarget",
    "DocumentFacade",
    "DocumentObject",
    "PickResult",
    "PickingFacade",
    "PreviewSession",
    "PreviewSessionManager",
    "LinkedSceneOutputResult",
    "ProjectScenesFacade",
    "projection_cache_signature",
    "SceneBounds",
    "SceneCache",
    "SceneCacheSummary",
    "ScenePoint",
    "SceneSegment",
    "SceneSelectionFacade",
    "SelectionManager",
    "SnapManager",
    "SnapResult",
    "SnapSource",
    "SnapTarget",
    "ScreenRect",
    "ToolActor",
    "ToolServiceError",
    "actors",
    "interaction",
    "selection_box",
    "snap",
]
