"""Application-service contracts for generated tools and modifiers."""
from __future__ import annotations

from laserprog_studio.tool_core.app_services import Job, JobManager, JobState, OperationManager, OperationResult, StatusManager, StatusMessage, ViewFacade
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

from . import assets, engraving, jobs, materials, operations, planar, status, workflow

__all__ = [
    "AssetManager",
    "EngravingManager",
    "EngravingRoleSpec",
    "Job",
    "JobManager",
    "JobState",
    "MaterialManager",
    "MaterialRecord",
    "OperationManager",
    "OperationResult",
    "PlanarManager",
    "PlanarRegion",
    "PlaneSpec",
    "StatusManager",
    "StatusMessage",
    "TextureAssetRecord",
    "ViewFacade",
    "assets",
    "engraving",
    "jobs",
    "materials",
    "operations",
    "planar",
    "status",
    "workflow",
]
