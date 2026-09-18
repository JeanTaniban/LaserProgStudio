# -*- coding: utf-8 -*-
"""Inventory runtime geometry writes that can bypass a future mutation gateway.

Diagnostic only for now. The script intentionally does not fail: its output is
used to define the migration allowlist before the audit becomes a quality gate.
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "laserprog_studio"

MUTATING_METHODS = {
    "set_meshes",
    "push_meshes",
    "set_preview_meshes",
    "commit_preview",
    "clear_preview",
    "replace_meshes",
}

LOW_LEVEL_ALLOWED_PREFIXES = (
    "domain/work_model.py",
    "io/project_file.py",
    "project/",
)


def main() -> int:
    records: list[tuple[str, int, str, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            method = str(func.attr)
            if method not in MUTATING_METHODS:
                continue
            owner = ast.unparse(func.value) if hasattr(ast, "unparse") else "?"
            classification = "low_level_allowed" if rel.startswith(LOW_LEVEL_ALLOWED_PREFIXES) else "runtime_bypass_candidate"
            records.append((rel, int(getattr(node, "lineno", 0)), method, classification + ":" + owner))

    counts = Counter(record[2] for record in records)
    candidates = [r for r in records if r[3].startswith("runtime_bypass_candidate")]

    print("Geometry mutation write inventory")
    print(f"total_calls={len(records)}")
    print(f"runtime_bypass_candidates={len(candidates)}")
    print("methods=" + ", ".join(f"{key}:{counts[key]}" for key in sorted(counts)))
    print()
    for rel, line, method, detail in records:
        print(f"{rel}:{line}: {method}: {detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
