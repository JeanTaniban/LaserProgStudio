# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def read_light_transform_source(root: Path) -> str:
    """Return the Light UI overlay source after its package split."""
    ui = root / "src" / "laserprog_studio" / "ui"
    files = [ui / "light_transform_overlay.py", *sorted((ui / "light_transform").glob("*.py"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)
