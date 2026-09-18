"""Lightweight static checks for external creator-tool examples."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_FORBIDDEN_IMPORT_PREFIXES = (
    "PySide6",
    "pyvista",
    "vtk",
    "laserprog_studio.ui",
    "laserprog_studio.window",
    "laserprog_studio.controllers",
    "laserprog_studio.tool_core",
)


@dataclass(frozen=True, slots=True)
class ImportAuditIssue:
    path: str
    module: str
    lineno: int
    message: str


def audit_imports(path: str | Path, *, forbidden_prefixes: Iterable[str] = DEFAULT_FORBIDDEN_IMPORT_PREFIXES) -> tuple[ImportAuditIssue, ...]:
    """Return forbidden imports found in one Python file.

    The audit intentionally targets creator examples/plugins. Internal Studio
    code may import Qt/PyVista/tool_core directly; external tools should not.
    """

    file_path = Path(path)
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    prefixes = tuple(str(prefix) for prefix in forbidden_prefixes)
    issues: list[ImportAuditIssue] = []
    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * int(node.level or 0) + str(node.module or "")
            modules.append(module)
        for module in modules:
            if _is_forbidden(module, prefixes):
                issues.append(
                    ImportAuditIssue(
                        path=str(file_path),
                        module=module,
                        lineno=getattr(node, "lineno", 0),
                        message=f"External creator tools should not import {module!r}; use laserprog_studio.tool_api instead.",
                    )
                )
    return tuple(issues)


def assert_no_forbidden_imports(path: str | Path, *, forbidden_prefixes: Iterable[str] = DEFAULT_FORBIDDEN_IMPORT_PREFIXES) -> None:
    issues = audit_imports(path, forbidden_prefixes=forbidden_prefixes)
    if issues:
        details = "\n".join(f"{issue.path}:{issue.lineno}: {issue.message}" for issue in issues)
        raise AssertionError(details)


def _is_forbidden(module: str, prefixes: tuple[str, ...]) -> bool:
    normalized = module.lstrip(".")
    return any(normalized == prefix or normalized.startswith(f"{prefix}.") for prefix in prefixes)


__all__ = [
    "DEFAULT_FORBIDDEN_IMPORT_PREFIXES",
    "ImportAuditIssue",
    "assert_no_forbidden_imports",
    "audit_imports",
]
