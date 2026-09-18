"""Application-facing services exposed through :class:`ToolContext`.

The public API intentionally stays available from ``laserprog_studio.tool_core.app_services``
while the implementation is split by responsibility.
"""
from __future__ import annotations

from .common import ToolServiceError
from .document import DocumentFacade, DocumentObject
from .jobs import Job, JobManager, JobState
from .operations import OperationManager, OperationResult
from .picking import PickResult, PickingFacade
from .preview import PreviewSession, PreviewSessionManager
from .project_scenes import LinkedSceneOutputResult, ProjectScenesFacade
from .selection import SceneSelectionFacade
from .status import StatusManager, StatusMessage
from .view import ViewFacade

__all__ = [
    "DocumentFacade",
    "DocumentObject",
    "Job",
    "JobManager",
    "JobState",
    "OperationManager",
    "OperationResult",
    "PickResult",
    "PickingFacade",
    "PreviewSession",
    "PreviewSessionManager",
    "LinkedSceneOutputResult",
    "ProjectScenesFacade",
    "SceneSelectionFacade",
    "StatusManager",
    "StatusMessage",
    "ToolServiceError",
    "ViewFacade",
]
