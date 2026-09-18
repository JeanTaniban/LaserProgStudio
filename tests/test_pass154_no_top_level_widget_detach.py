from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "laserprog_studio"


def _iter_python_sources():
    for path in SRC.rglob("*.py"):
        if "__pycache__" not in path.parts:
            yield path


def _set_parent_none_calls(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "setParent":
            continue
        if not node.args:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and arg.value is None:
            hits.append((node.lineno, ast.get_source_segment(path.read_text(encoding="utf-8"), node) or "setParent(None)"))
    return hits


def test_runtime_code_never_detaches_qwidgets_to_none() -> None:
    """Visible Qt widgets must not be detached to None during UI rebuilds.

    Detaching a QWidget to None makes it a top-level window.  The Creator tool
    panel and the dynamic toolbar rebuild while tools open, so this regression
    guard prevents the tiny-window flash from coming back in another area.
    """

    failures: list[str] = []
    for path in _iter_python_sources():
        for lineno, call in _set_parent_none_calls(path):
            failures.append(f"{path.relative_to(ROOT)}:{lineno}: {call}")
    assert failures == []
