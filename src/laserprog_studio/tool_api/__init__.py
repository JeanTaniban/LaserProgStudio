"""Public creator API for LaserProg Studio tools.

External tools should import from this package instead of reaching into Qt,
PyVista or historical controller modules.  The package is intentionally a thin
facade over the existing runtime with stable imports for shipped and external tools
while new tools get a clean entry point.
"""
from __future__ import annotations

from laserprog_studio.parameters import ParameterSpec
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType, ToolModeBase
from laserprog_studio.tool_core.workflow import ToolModeManager, ToolModeSpec, ToolModeState, ToolWorkflowManager, WorkflowState, WorkflowStep
from laserprog_studio.tool_core.box_selection import BoxSelectionActivationModifier, BoxSelectionConfig, BoxSelectionInsidePolicy, BoxSelectionManager, BoxSelectionMode, BoxSelectionResult, BoxSelectionState, BoxSelectionTarget, ScreenRect
from laserprog_studio.tool_core.commands import CommandStack, CompositeCommand, FunctionCommand
from laserprog_studio.tool_core.scene_cache import SceneBounds, SceneCache, SceneCacheSummary, ScenePoint, SceneSegment
from laserprog_studio.tool_core.app_services import (
    DocumentFacade,
    DocumentObject,
    Job,
    JobManager,
    JobState,
    OperationManager,
    OperationResult,
    PickResult,
    PickingFacade,
    PreviewSession,
    PreviewSessionManager,
    LinkedSceneOutputResult,
    ProjectScenesFacade,
    SceneSelectionFacade,
    StatusManager,
    StatusMessage,
    ToolServiceError,
    ViewFacade,
)
from laserprog_studio.tool_core.app_domain_services import (
    AssetManager,
    EngravingManager,
    EngravingRoleSpec,
    MaterialManager,
    MaterialRecord,
    PlanarManager,
    PlanarRegion,
    PlaneSpec,
    TextureAssetRecord,
)
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, SelectionManager, ToolActor
from laserprog_studio.tool_core.inspector import AutoPreview, AutoPreviewConfig
from laserprog_studio.tool_core.snap import SnapManager, SnapResult, SnapSource, SnapTarget
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.tool import StudioTool

from . import actors, application, assets, audit, cleanup, core, diagnostics, document, engraving, gizmos, inspector, interaction, jobs, materials, metrics, operations, picking, planar, planar_drawing, plan2d, projected_drawing, preview_session, project_scenes, scene, selection_box, sketch, snap, status, surface, surface_selection, styles, tracing, ui_catalog, ui_motifs, visual, workflow
from .errors import ToolApiCompatibilityError, ToolApiError, ToolApiUsageError, ToolApiValidationError
from .lifecycle import CreatorTool
from .manifest import ToolManifest
from .diagnostics import ApiDiagnosticCase, ApiDiagnosticReport, run_creator_api_self_test
from .diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabBenchmarkCase, LabBenchmarkReport, LabInteraction, LabLineStyle, LabMovePreset, LabPointStyle, LabSnapshot, LabVisualState
from .cleanup import ApiCleanupFinding, audit_tool_api_surface, cleanup_report_markdown
from .surface import ApiDomain, active_import_paths, supported_import_paths, internal_import_paths, iter_api_domains, public_api_markdown, public_api_summary
from .runtime import CreatorStudioToolAdapter
from .versioning import CREATOR_UI_RUNTIME_CONTRACT, CURRENT_TOOL_API_VERSION, TOOL_API_STABILITY, TOOL_API_VERSION, ToolApiVersion, require_tool_api



def register_tool(*args, **kwargs):
    """Register a Creator tool without importing registry internals during bootstrap."""

    from .registration import register_tool as _register_tool

    return _register_tool(*args, **kwargs)


__all__ = [
    "ActorInteraction",
    "ActorKind",
    "AutoPreview",
    "AutoPreviewConfig",
    "BoxSelectionActivationModifier",
    "BoxSelectionConfig",
    "BoxSelectionInsidePolicy",
    "BoxSelectionManager",
    "BoxSelectionMode",
    "BoxSelectionResult",
    "BoxSelectionState",
    "BoxSelectionTarget",
    "CREATOR_UI_RUNTIME_CONTRACT",
    "CURRENT_TOOL_API_VERSION",
    "CommandStack",
    "CreatorTool",
    "CompositeCommand",
    "CreatorStudioToolAdapter",
    "CreatorApiDiagnosticLab",
    "DocumentFacade",
    "DocumentObject",
    "Job",
    "LabActorKind",
    "LabBenchmarkCase",
    "LabBenchmarkReport",
    "LabInteraction",
    "LabLineStyle",
    "LabMovePreset",
    "LabPointStyle",
    "LabVisualState",
    "LabSnapshot",
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
    "ApiCleanupFinding",
    "ApiDiagnosticCase",
    "ApiDiagnosticReport",
    "ApiDomain",
    "AssetManager",
    "EngravingManager",
    "EngravingRoleSpec",
    "MaterialManager",
    "MaterialRecord",
    "PlanarManager",
    "PlanarRegion",
    "PlaneSpec",
    "TextureAssetRecord",
    "application",
    "cleanup",
    "core",
    "scene",
    "selection_box",
    "sketch",
    "surface",
    "surface_selection",
    "styles",
    "tracing",
    "ui_catalog",
    "ui_motifs",
    "visual",
    "workflow",
    "assets",
    "diagnostics",
    "document",
    "engraving",
    "gizmos",
    "materials",
    "metrics",
    "planar",
    "plan2d",
    "planar_drawing",
    "projected_drawing",
    "jobs",
    "operations",
    "picking",
    "preview_session",
    "project_scenes",
    "status",
    "FunctionCommand",
    "ParameterSpec",
    "ScreenRect",
    "SceneBounds",
    "SceneCache",
    "SceneCacheSummary",
    "ScenePoint",
    "SceneSegment",
    "SelectionManager",
    "SnapManager",
    "SnapResult",
    "SnapSource",
    "SnapTarget",
    "StudioTool",
    "ToolActor",
    "ToolApiCompatibilityError",
    "ToolApiError",
    "ToolApiUsageError",
    "ToolApiValidationError",
    "ToolApiVersion",
    "ToolContext",
    "TOOL_API_STABILITY",
    "TOOL_API_VERSION",
    "ToolEvent",
    "ToolEventType",
    "ToolModeBase",
    "ToolManifest",
    "ToolSpec",
    "ToolWorkflowManager",
    "WorkflowState",
    "WorkflowStep",
    "ToolModeManager",
    "ToolModeSpec",
    "ToolModeState",
    "active_import_paths",
    "audit_tool_api_surface",
    "cleanup_report_markdown",
    "supported_import_paths",
    "internal_import_paths",
    "iter_api_domains",
    "public_api_markdown",
    "public_api_summary",
    "actors",
    "audit",
    "inspector",
    "interaction",
    "register_tool",
    "require_tool_api",
    "run_creator_api_self_test",
    "snap",
]
