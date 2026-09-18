# -*- coding: utf-8 -*-
"""Verify that a LaserProg release ZIP contains critical runtime source files.

This check intentionally runs *after* archive creation.  It protects against a
packaging cleanup confusing the disposable top-level ``diagnostics`` directory
with ``src/laserprog_studio/diagnostics``, which is imported by the shared
Projected Drawing renderer used by Plan Tracer 2D, Split and Cloth.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


_REQUIRED_SUFFIXES = (
    "src/laserprog_studio/diagnostics/__init__.py",
    "src/laserprog_studio/diagnostics/app_performance_audit.py",
    "src/laserprog_studio/diagnostics/projected_overlay_debug.py",
    "src/laserprog_studio/application/projected_drawing_2d.py",
    "src/laserprog_studio/tooling/plan_trace_2d_tool.py",
    "src/laserprog_studio/tooling/split_tool.py",
    "src/laserprog_studio/tooling/cloth_tool.py",
)
_RUNTIME_DIAGNOSTIC_SUFFIXES = (".json", ".jsonl", ".log")


def verify_archive(archive: Path) -> tuple[str, ...]:
    if not archive.is_file():
        raise SystemExit(f"Release archive not found: {archive}")
    with zipfile.ZipFile(archive, "r") as bundle:
        names = tuple(name.replace("\\", "/") for name in bundle.namelist())
        corrupt = bundle.testzip()
    if corrupt:
        raise SystemExit(f"Corrupt ZIP member: {corrupt}")

    missing = [suffix for suffix in _REQUIRED_SUFFIXES if not any(name.endswith(suffix) for name in names)]
    if missing:
        raise SystemExit("Missing required runtime members: " + ", ".join(missing))

    leaked: list[str] = []
    for name in names:
        parts = name.strip("/").split("/")
        # Release archives normally have one root directory.  The disposable
        # runtime diagnostics directory is therefore the second path segment.
        if len(parts) >= 3 and parts[1] == "diagnostics" and name.lower().endswith(_RUNTIME_DIAGNOSTIC_SUFFIXES):
            leaked.append(name)
    if leaked:
        raise SystemExit("Runtime diagnostic artifacts leaked into release: " + ", ".join(leaked[:10]))
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    names = verify_archive(args.archive.resolve())
    print(f"Release archive OK: {args.archive} ({len(names)} members)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
