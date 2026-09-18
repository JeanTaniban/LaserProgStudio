from __future__ import annotations

import re
from pathlib import Path

from _path_setup import ROOT  # noqa: F401

SRC = ROOT / "src" / "laserprog_studio"
DOCS = ROOT / "docs"
SCRIPTS = ROOT / "scripts"

_RETIRED_SOURCE_RE = re.compile(r"\b(?:legacy|compat(?:ibility)?|backward(?:-compatible)?|deprecated)\b", re.IGNORECASE)


def _text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md"}:
            continue
        yield path


def test_runtime_source_has_no_retired_transition_wording() -> None:
    offenders: list[tuple[str, int, str]] = []
    for path in _text_files(SRC):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _RETIRED_SOURCE_RE.search(line):
                offenders.append((path.relative_to(ROOT).as_posix(), line_no, line.strip()))
    assert offenders == []


def test_current_docs_have_no_retired_transition_wording() -> None:
    offenders: list[tuple[str, int, str]] = []
    for path in _text_files(DOCS):
        if "archive" in path.parts:
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _RETIRED_SOURCE_RE.search(line):
                offenders.append((path.relative_to(ROOT).as_posix(), line_no, line.strip()))
    assert offenders == []


def test_quality_gate_blocks_transition_wording() -> None:
    gate = (SCRIPTS / "quality_gate.py").read_text(encoding="utf-8")
    assert "--max-transition-hotspots" in gate
