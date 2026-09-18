# -*- coding: utf-8 -*-
"""Small AST helpers for static architecture checks."""

from __future__ import annotations

import ast
from pathlib import Path


def class_methods(path: Path) -> list[str]:
    """Return top-level class method names declared in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    out.append(item.name)
    return out
