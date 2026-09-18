# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def read_scene_tabs_source(root: Path | None = None) -> str:
    """Return the Scene Tabs controller source after its package split."""
    base = (root or Path.cwd()) / "src" / "laserprog_studio" / "controllers"
    files = [
        base / "scene_tabs.py",
        base / "scene_tabs_frame.py",
        base / "scene_tabs_sync.py",
        base / "scene_tabs_actions.py",
        base / "scene_tabs_drag.py",
    ]
    return "\n".join(path.read_text(encoding="utf-8") for path in files)
