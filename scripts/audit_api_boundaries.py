# -*- coding: utf-8 -*-
"""Audit API/layer dependencies without importing the application.

The audit is intentionally static. It gives a package interaction map and guards
migration boundaries that are easy to regress while the old public facades are
kept for compatibility.
"""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "laserprog_studio"
LEGACY_PLAN2D_FACADES = {
    "laserprog_studio.tool_api.planar_drawing",
    "laserprog_studio.tool_api.dimensions",
    "laserprog_studio.tool_api.metrics",
}
APPLICATION_LAYER_PREFIXES = (
    "laserprog_studio.application",
    "laserprog_studio.controllers",
    "laserprog_studio.ui",
    "laserprog_studio.window",
)


@dataclass(frozen=True, slots=True)
class ImportEdge:
    source: str
    target: str
    source_package: str
    target_package: str


@dataclass(frozen=True, slots=True)
class BoundaryIssue:
    severity: str
    path: str
    import_name: str
    message: str


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    return ".".join(rel.parts)


def _package_name(module: str) -> str:
    parts = module.split(".")
    if len(parts) < 2 or parts[0] != "laserprog_studio":
        return "external"
    return parts[1]


def _resolve_from(path: Path, level: int, module: str | None) -> str:
    if level <= 0:
        return module or ""
    current = _module_name(path).split(".")
    # For ``from .x import y`` inside a module, one leading dot refers to the
    # containing package, so remove the module name plus level-1 parents.
    keep = max(0, len(current) - level)
    prefix = current[:keep]
    if module:
        prefix.extend(module.split("."))
    return ".".join(prefix)


def iter_imports(path: Path) -> Iterable[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return ()
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = _resolve_from(path, int(node.level or 0), node.module)
            if name:
                found.append(name)
    return found


def build_edges() -> list[ImportEdge]:
    edges: list[ImportEdge] = []
    for path in sorted(SRC.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = _module_name(path)
        for target in iter_imports(path):
            if not target.startswith("laserprog_studio"):
                continue
            edges.append(ImportEdge(source, target, _package_name(source), _package_name(target)))
    return edges


def audit_boundaries(edges: list[ImportEdge]) -> list[BoundaryIssue]:
    issues: list[BoundaryIssue] = []
    for edge in edges:
        source_path = "src/" + edge.source.replace(".", "/") + ".py"
        if edge.source.startswith("laserprog_studio.tool_core") and edge.target.startswith(APPLICATION_LAYER_PREFIXES):
            if edge.source == "laserprog_studio.tool_core.context" and edge.target == "laserprog_studio.application.projected_drawing_2d":
                issues.append(
                    BoundaryIssue(
                        "warning",
                        source_path,
                        edge.target,
                        "ToolContext keeps a direct live-renderer bootstrap for ToolContext(owner=...) compatibility; runtime adapters should remain the preferred binding path.",
                    )
                )
            else:
                issues.append(
                    BoundaryIssue(
                        "critical",
                        source_path,
                        edge.target,
                        "tool_core must not import application/controller/UI layers; inject callbacks/adapters instead.",
                    )
                )
        if edge.source.startswith("laserprog_studio.tool_core") and edge.target.startswith("laserprog_studio.tool_api"):
            # Diagnostic probes still exercise the public API from inside the lab.
            allowed_diag = edge.source.startswith("laserprog_studio.tool_core.diagnostic")
            allowed_context_actor_bridge = edge.source == "laserprog_studio.tool_core.context" and edge.target == "laserprog_studio.tool_api.actors"
            if not allowed_diag and not allowed_context_actor_bridge:
                issues.append(
                    BoundaryIssue(
                        "warning",
                        source_path,
                        edge.target,
                        "tool_core should remain below tool_api; keep this as a temporary transition only.",
                    )
                )
        if edge.source.startswith(("laserprog_studio.tooling.plan_trace_2d", "laserprog_studio.tooling.vent_generator")) and edge.target in LEGACY_PLAN2D_FACADES:
            issues.append(
                BoundaryIssue(
                    "critical",
                    source_path,
                    edge.target,
                    "Plan 2D tools must import the owned tool_api.plan2d domains, not legacy compatibility facades.",
                )
            )
    return issues


def edge_summary(edges: list[ImportEdge]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in edges:
        if edge.source_package == edge.target_package:
            continue
        key = f"{edge.source_package}->{edge.target_package}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument("--strict", action="store_true", help="Fail on critical boundary issues.")
    args = parser.parse_args(argv)

    edges = build_edges()
    issues = audit_boundaries(edges)
    critical = [issue for issue in issues if issue.severity == "critical"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    payload = {
        "python_files": len([p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]),
        "internal_edges": len(edges),
        "package_edges": edge_summary(edges),
        "critical_issues": [asdict(issue) for issue in critical],
        "warnings": [asdict(issue) for issue in warnings],
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print("LaserProg Studio API boundary audit")
        print("===================================")
        print(f"Python files     : {payload['python_files']}")
        print(f"Internal imports : {payload['internal_edges']}")
        print(f"Critical issues  : {len(critical)}")
        print(f"Warnings         : {len(warnings)}")
        print("\nTop package edges:")
        for key, count in list(payload["package_edges"].items())[:14]:
            print(f"- {count:3d}  {key}")
        if issues:
            print("\nBoundary notes:")
            for issue in issues[:20]:
                print(f"- {issue.severity.upper():8s} {issue.path}: {issue.import_name} — {issue.message}")
    if args.strict and critical:
        raise SystemExit("API boundary gate failed: critical issues remain")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
