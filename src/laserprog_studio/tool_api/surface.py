"""Public surface map for the Creator API.

This module is the single source of truth for public imports.  It separates the
recommended domains from older supported aliases and internal implementation
modules, so diagnostics and documentation can stay generated from code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ApiSurfaceStatus = Literal["active", "supported", "internal"]


@dataclass(frozen=True, slots=True)
class ApiDomain:
    """One documented public API domain."""

    name: str
    import_path: str
    purpose: str
    status: ApiSurfaceStatus = "active"
    symbols: tuple[str, ...] = ()


_ACTIVE_DOMAINS: tuple[ApiDomain, ...] = (
    ApiDomain(
        "Core",
        "laserprog_studio.tool_api.core",
        "Tool identity, lifecycle, registration, runtime adapter, versioning and command contracts.",
        symbols=("CreatorTool", "ToolManifest", "ToolContext", "register_tool", "require_tool_api"),
    ),
    ApiDomain(
        "Scene",
        "laserprog_studio.tool_api.scene",
        "Document access, scene selection, picking, actors, snap, scene cache and preview sessions.",
        symbols=("DocumentFacade", "SceneSelectionFacade", "PickingFacade", "SceneCache", "BoxSelectionManager", "actors", "snap"),
    ),
    ApiDomain(
        "Visual",
        "laserprog_studio.tool_api.visual",
        "Inspector panels, viewport previews, gizmos, projected 2D drawings, native styles, status output and render adapter contracts.",
        symbols=("inspector", "AutoPreview", "gizmos", "projected_drawing", "styles", "ui_catalog", "PreviewManager", "ViewportAdapter", "StatusManager"),
    ),
    ApiDomain(
        "Application",
        "laserprog_studio.tool_api.application",
        "Operations, jobs, materials, assets, engraving metadata and planar SDK services.",
        symbols=("OperationManager", "JobManager", "MaterialManager", "AssetManager", "PlanarManager"),
    ),
    ApiDomain(
        "Workflow",
        "laserprog_studio.tool_api.workflow",
        "Multi-step tool workflows and Add/Edit/Delete-style mode state for complex interactive tools.",
        symbols=("ToolWorkflowManager", "WorkflowStep", "ToolModeManager", "ToolModeSpec"),
    ),
    ApiDomain(
        "Plan 2D",
        "laserprog_studio.tool_api.plan2d",
        "Focused locked-plane drawing API: plane anchoring, coordinate mapping, plan actors, snap, sketch topology, dimensions, metrics and curve intent.",
        symbols=("Plan2DCoordinateMapper", "PlanSketch", "ArcIntent", "register_plan_line", "smart_snap_on_plan", "MetricEditSession", "DimensionSpec"),
    ),
    ApiDomain(
        "Surface selection",
        "laserprog_studio.tool_api.surface_selection",
        "Headless logical mesh-surface recognition with manual continuity, automatic stable-region detection and include/exclude constraints.",
        symbols=("SurfaceMeshSnapshot", "SurfaceSelectionSession", "SurfaceSelectionPointerMachine", "SurfaceRegionResult", "auto_surface_region", "select_surface_region"),
    ),
    ApiDomain(
        "Diagnostics",
        "laserprog_studio.tool_api.diagnostics",
        "Headless self-tests used by the Tool Core Diagnostic panel and CI-style checks.",
        symbols=("run_creator_api_self_test", "ApiDiagnosticReport"),
    ),
)

_SUPPORTED_ALIASES: tuple[ApiDomain, ...] = (
    ApiDomain("Root facade", "laserprog_studio.tool_api", "Convenient one-stop import path for examples and small tools.", "supported"),
    ApiDomain("Actors helper", "laserprog_studio.tool_api.actors", "Low-level actor factory helpers documented through the Scene domain.", "supported"),
    ApiDomain("Inspector helper", "laserprog_studio.tool_api.inspector", "Low-level inspector DSL documented through the Visual domain.", "supported"),
    ApiDomain("Snap helper", "laserprog_studio.tool_api.snap", "Low-level snap-target helpers documented through the Scene domain.", "supported"),
    ApiDomain("Plan drawing alias", "laserprog_studio.tool_api.planar_drawing", "Transitional import that forwards to tool_api.plan2d.plane / actors / snap.", "supported"),
    ApiDomain("Dimensions alias", "laserprog_studio.tool_api.dimensions", "Transitional import that forwards to tool_api.plan2d.dimensions.", "supported"),
    ApiDomain("Metrics alias", "laserprog_studio.tool_api.metrics", "Transitional import that forwards to tool_api.plan2d.metrics.", "supported"),
    ApiDomain("Sketch helper", "laserprog_studio.tool_api.sketch", "Neutral sketch document and face-compilation contracts used by Plan 2D creator tools.", "supported"),
    ApiDomain("Tracing helper", "laserprog_studio.tool_api.tracing", "Neutral drawing modes, click drafts and 3D curve helpers shared by Plan Tracer and Cloth.", "supported"),
    ApiDomain("Thin service shims", "laserprog_studio.tool_api.{document,picking,operations,jobs,status,materials,assets,engraving,planar}", "Small service re-export modules for concise tool code.", "supported"),
)

_INTERNAL_DOMAINS: tuple[ApiDomain, ...] = (
    ApiDomain("Tool core internals", "laserprog_studio.tool_core", "Shared runtime implementation; creator tools should not import this directly.", "internal"),
    ApiDomain("Qt UI internals", "laserprog_studio.ui", "Qt widgets/factories; creator tools use the declarative inspector instead.", "internal"),
    ApiDomain("Rendering internals", "pyvista/vtk/PySide6", "Backend technologies are hidden behind the creator API.", "internal"),
)


def iter_api_domains(*, include_supported: bool = True, include_internal: bool = False) -> tuple[ApiDomain, ...]:
    """Return the documented Creator API domains in display order."""

    domains: list[ApiDomain] = [*_ACTIVE_DOMAINS]
    if include_supported:
        domains.extend(_SUPPORTED_ALIASES)
    if include_internal:
        domains.extend(_INTERNAL_DOMAINS)
    return tuple(domains)


def active_import_paths() -> tuple[str, ...]:
    """Recommended imports for new tools."""

    return tuple(domain.import_path for domain in _ACTIVE_DOMAINS)


def supported_import_paths() -> tuple[str, ...]:
    """Supported aliases that still work but are not the preferred starting point."""

    return tuple(domain.import_path for domain in _SUPPORTED_ALIASES)


def internal_import_paths() -> tuple[str, ...]:
    """Imports a creator tool should not use directly."""

    return tuple(domain.import_path for domain in _INTERNAL_DOMAINS)


def public_api_summary() -> dict[str, object]:
    """Compact serialisable summary used by diagnostics and tests."""

    active = iter_api_domains(include_supported=False)
    supported = _SUPPORTED_ALIASES
    return {
        "active_domains": len(active),
        "supported_domains": len(supported),
        "active_import_paths": active_import_paths(),
        "supported_import_paths": supported_import_paths(),
        "domains": [
            {
                "name": domain.name,
                "import_path": domain.import_path,
                "status": domain.status,
                "purpose": domain.purpose,
                "symbols": list(domain.symbols),
            }
            for domain in iter_api_domains(include_supported=True)
        ],
    }


def public_api_markdown() -> str:
    """Human-readable map suitable for diagnostic reports."""

    lines = [
        "# Creator API public surface",
        "",
        "## Recommended domains",
        "",
        "| Domain | Import path | Purpose |",
        "|---|---|---|",
    ]
    for domain in _ACTIVE_DOMAINS:
        lines.append(f"| {domain.name} | `{domain.import_path}` | {domain.purpose} |")
    lines.extend(["", "## Supported aliases", "", "These imports remain supported; new tools should prefer the domains above.", "", "| Import path | Note |", "|---|---|"])
    for domain in _SUPPORTED_ALIASES:
        lines.append(f"| `{domain.import_path}` | {domain.purpose} |")
    lines.extend(["", "## Do not import directly", "", "| Import path | Reason |", "|---|---|"])
    for domain in _INTERNAL_DOMAINS:
        lines.append(f"| `{domain.import_path}` | {domain.purpose} |")
    return "\n".join(lines)


__all__ = [
    "ApiDomain",
    "ApiSurfaceStatus",
    "active_import_paths",
    "internal_import_paths",
    "iter_api_domains",
    "public_api_markdown",
    "public_api_summary",
    "supported_import_paths",
]
