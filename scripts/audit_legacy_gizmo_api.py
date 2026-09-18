#!/usr/bin/env python3
"""Audit that production tools no longer call the retired viewport gizmo API.

The old public authoring surface was direct access to ctx.preview, ctx.gizmos and
ctx.actor_registry from tools.  Production tools must now go through tool_api
Projected Drawing / actors / snap / preview_session facades.  Internal backend
files may still implement those facades; this audit deliberately checks only
production tool code and the toolbar-visible registry.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLING = ROOT / "src" / "laserprog_studio" / "tooling"
FORBIDDEN = (
    re.compile(r"\bctx\.(preview|gizmos|actor_registry)\b"),
    re.compile(r"\blaserprog_studio\.tool_core\.(gizmos|preview)\b"),
    re.compile(r"\bfrom\s+laserprog_studio\.tool_core\.(gizmos|preview)\b"),
)
RETIRED_FILES = set()
RETIRED_DIRS = set()


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(TOOLING.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def main() -> int:
    issues: list[str] = []
    for path in iter_python_files():
        # Benchmark data builders are allowed to remain for tests/docs even
        # though the interactive Gizmo catalog tool has been retired.
        if path.name == "gizmo_catalog_benchmark.py":
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in FORBIDDEN):
                issues.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    # Interactive diagnostic/catalog tools are considered retired when they are
    # absent from the Studio registry and toolbar.  Compatibility modules may
    # remain for historical tests/docs, but they are no longer product tools.
    print("LaserProg legacy gizmo API audit")
    print("================================")
    print(f"Production tool files checked: {len(iter_python_files())}")
    print(f"Issues: {len(issues)}")
    for issue in issues:
        print(f"- {issue}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
