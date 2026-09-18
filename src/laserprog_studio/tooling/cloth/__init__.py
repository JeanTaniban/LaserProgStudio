"""Cloth domain and UX services.

The package stays independent from the Studio window: geometry, topology,
flattening, validation, drawing drafts and overlays are separate services.  The
thin Creator adapter lives in :mod:`laserprog_studio.tooling.cloth_tool`.
"""
from .flattening import ClothFlatteningResult, PatchPlacement, flatten_cloth_document
from .mesh_builder import ClothMeshBuildResult, build_cloth_surface_mesh
from .models import (
    ClothCurve,
    ClothCurveKind,
    ClothCurveRole,
    ClothDocument,
    ClothEditMode,
    ClothFold,
    ClothFoldKind,
    ClothLayer,
    ClothPatch,
    ClothPatchFunction,
    ClothPoint,
    ClothSeam,
    ClothSession,
    ClothWorkflowPhase,
)
from .output import ClothApplyPlan, build_cloth_apply_plan
from .serialization import CLOTH_SCHEMA_VERSION, CLOTH_SOURCE_KEY, cloth_output_kind, restore_cloth_source
from .state_machine import ClothFoldDraftMachine, ClothTransitionError, ClothWorkflowMachine
from .validation import ClothValidationCache, ClothValidationReport, validate_cloth_document

__all__ = [
    "CLOTH_SCHEMA_VERSION",
    "CLOTH_SOURCE_KEY",
    "ClothApplyPlan",
    "ClothCurve",
    "ClothCurveKind",
    "ClothCurveRole",
    "ClothDocument",
    "ClothEditMode",
    "ClothFlatteningResult",
    "ClothFold",
    "ClothFoldDraftMachine",
    "ClothFoldKind",
    "ClothLayer",
    "ClothMeshBuildResult",
    "ClothPatch",
    "ClothPatchFunction",
    "ClothPoint",
    "ClothSeam",
    "ClothSession",
    "ClothTransitionError",
    "ClothValidationCache",
    "ClothValidationReport",
    "ClothWorkflowMachine",
    "ClothWorkflowPhase",
    "PatchPlacement",
    "build_cloth_apply_plan",
    "build_cloth_surface_mesh",
    "cloth_output_kind",
    "flatten_cloth_document",
    "restore_cloth_source",
    "validate_cloth_document",
]
