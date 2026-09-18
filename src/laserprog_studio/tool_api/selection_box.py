"""Public rectangle-selection API for creator tools."""
from __future__ import annotations

from laserprog_studio.tool_core.box_selection import (
    BoxSelectionActivationModifier,
    BoxSelectionConfig,
    BoxSelectionInsidePolicy,
    BoxSelectionManager,
    BoxSelectionMode,
    BoxSelectionResult,
    BoxSelectionState,
    BoxSelectionTarget,
    SceneEdgeRef,
    SceneFaceRef,
    SceneVertexRef,
    ScreenRect,
)

__all__ = [
    "BoxSelectionActivationModifier",
    "BoxSelectionConfig",
    "BoxSelectionInsidePolicy",
    "BoxSelectionManager",
    "BoxSelectionMode",
    "BoxSelectionResult",
    "BoxSelectionState",
    "BoxSelectionTarget",
    "SceneEdgeRef",
    "SceneFaceRef",
    "SceneVertexRef",
    "ScreenRect",
]
