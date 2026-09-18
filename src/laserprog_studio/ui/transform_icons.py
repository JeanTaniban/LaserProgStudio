# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

try:
    from .._window_deps import QIcon
except Exception:  # pragma: no cover
    QIcon = None

_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "toolbar_icons"
_TRANSFORM_ICON_BY_NAME = {
    "none": "transform_none.png",
    "translate": "transform_translate.png",
    "rotate": "transform_rotate.png",
    "scale": "transform_scale.png",
}


@lru_cache(maxsize=None)
def transform_icon_path(name: str | None) -> str | None:
    if not name:
        return None
    filename = _TRANSFORM_ICON_BY_NAME.get(str(name))
    if not filename:
        return None
    path = _ICON_DIR / filename
    return str(path) if path.exists() else None


@lru_cache(maxsize=None)
def transform_icon(name: str | None):
    path = transform_icon_path(name)
    if QIcon is None:
        return None
    if path:
        return QIcon(path)
    return QIcon()
