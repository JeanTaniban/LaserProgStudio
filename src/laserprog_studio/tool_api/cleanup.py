"""Cleanliness checks for the creator API source tree.

This is intentionally lightweight: it does not enforce style preferences, it
only catches things that make the SDK confusing for external tool authors.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Literal

from .surface import active_import_paths, supported_import_paths, public_api_summary

ApiCleanupSeverity = Literal["ok", "warning", "blocker"]


@dataclass(frozen=True, slots=True)
class ApiCleanupFinding:
    code: str
    severity: ApiCleanupSeverity
    message: str

    @property
    def ok(self) -> bool:
        return self.severity == "ok"


def audit_tool_api_surface(*, project_root: str | Path | None = None) -> tuple[ApiCleanupFinding, ...]:
    """Return cleanup findings for public creator API packaging."""

    findings: list[ApiCleanupFinding] = []
    summary = public_api_summary()
    active_paths = set(active_import_paths())
    required_paths = {
        "laserprog_studio.tool_api.core",
        "laserprog_studio.tool_api.scene",
        "laserprog_studio.tool_api.visual",
        "laserprog_studio.tool_api.application",
        "laserprog_studio.tool_api.workflow",
        "laserprog_studio.tool_api.plan2d",
        "laserprog_studio.tool_api.diagnostics",
    }
    missing = sorted(required_paths - active_paths)
    alias_active = sorted(
        path
        for path in active_paths
        if path in {
            "laserprog_studio.tool_api.planar_drawing",
            "laserprog_studio.tool_api.dimensions",
            "laserprog_studio.tool_api.metrics",
        }
    )
    if missing or alias_active:
        details = []
        if missing:
            details.append(f"missing={missing}")
        if alias_active:
            details.append(f"alias_active={alias_active}")
        findings.append(ApiCleanupFinding("ACTIVE_DOMAIN_COUNT", "blocker", "Unexpected recommended creator API domains: " + ", ".join(details)))
    else:
        findings.append(ApiCleanupFinding("ACTIVE_DOMAIN_COUNT", "ok", f"Recommended creator API domains are grouped ({summary['active_domains']} active domains)."))

    for path in active_import_paths() + supported_import_paths():
        if "{" in path:
            continue
        try:
            import_module(path)
        except Exception as exc:  # pragma: no cover - only triggered on broken packaging
            findings.append(ApiCleanupFinding("IMPORT_BROKEN", "blocker", f"Cannot import {path}: {exc}"))
        else:
            findings.append(ApiCleanupFinding("IMPORT_OK", "ok", f"{path} imports cleanly."))

    if project_root is not None:
        root = Path(project_root)
        pycache = sorted(root.rglob("__pycache__"))
        pyc = sorted(root.rglob("*.pyc"))
        pytest_cache = root / ".pytest_cache"
        if pycache or pyc or pytest_cache.exists():
            findings.append(
                ApiCleanupFinding(
                    "GENERATED_CACHE_FILES",
                    "warning",
                    f"Generated caches should not be shipped: {len(pycache)} __pycache__ dirs, {len(pyc)} .pyc files, pytest_cache={pytest_cache.exists()}.",
                )
            )
        else:
            findings.append(ApiCleanupFinding("GENERATED_CACHE_FILES", "ok", "No generated Python/test caches in the source tree."))

    return tuple(findings)


def cleanup_report_markdown(*, project_root: str | Path | None = None) -> str:
    findings = audit_tool_api_surface(project_root=project_root)
    lines = [
        "# Creator API cleanup audit",
        "",
        "| Severity | Code | Message |",
        "|---|---|---|",
    ]
    for finding in findings:
        lines.append(f"| {finding.severity.upper()} | {finding.code} | {finding.message} |")
    return "\n".join(lines)


__all__ = ["ApiCleanupFinding", "ApiCleanupSeverity", "audit_tool_api_surface", "cleanup_report_markdown"]
