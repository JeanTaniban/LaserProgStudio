from __future__ import annotations

import ast
from pathlib import Path

from _path_setup import ROOT  # noqa: F401

SRC = ROOT / "src" / "laserprog_studio"
SCRIPTS = ROOT / "scripts"


def _python_sources(root: Path):
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_runtime_source_has_no_retired_legacy_wording() -> None:
    offenders: list[tuple[str, int, str]] = []
    for path in _python_sources(SRC):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "legacy" in line.lower():
                offenders.append((path.relative_to(ROOT).as_posix(), line_no, line.strip()))
    assert offenders == []


def test_runtime_source_has_no_mixin_import_aliases() -> None:
    aliases: list[tuple[str, str]] = []
    for path in _python_sources(SRC):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.endswith("Mixin"):
                        aliases.append((path.relative_to(ROOT).as_posix(), target.id))
    assert aliases == []


def test_quality_gate_blocks_legacy_wording_and_mixin_aliases() -> None:
    gate = (SCRIPTS / "quality_gate.py").read_text(encoding="utf-8")
    assert "--max-mixin-aliases" in gate
    assert "--max-legacy-hotspots" in gate
    assert "--max-transition-hotspots" in gate
