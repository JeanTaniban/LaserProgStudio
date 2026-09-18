# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

try:
    from .._window_deps import QIcon
except Exception:  # pragma: no cover - test environments may not ship Qt
    QIcon = None

_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "toolbar_icons"

_TOOLBAR_ICON_BY_ID = {
    "tool:primitive": "tool_primitive.png",
    "tool:box": "tool_box.png",
    "tool:layflat": "tool_layflat.png",
    "tool:joint": "tool_joint.png",
    "tool:engraving": "tool_engraving.png",
    "tool:material": "tool_material.png",
    "tool:texture_projection": "tool_texture_projection.png",
    "tool:plan_trace": "tool_plan_trace.png",
    "tool:vent_generator": "tool_vent_generator.png",
    "tool:mechanical_motion": "tool_mechanical_motion.png",
    "tool:folding": "tool_folding.png",
    "tool:cloth": "tool_cloth.png",
    "tool:volume_measure": "tool_volume_measure.png",
    "tool:acoustic_diffuser": "tool_acoustic_diffuser.png",
    "modifier:simplify": "modifier_simplify.png",
    "modifier:repair": "modifier_repair.png",
    "modifier:relief": "modifier_relief.png",
    "modifier:split": "modifier_split.png",
    "modifier:extrude_down": "modifier_extrude_down.png",
    "modifier:hollow": "modifier_hollow.png",
    "boolean:subtract": "boolean_subtract.png",
    "boolean:union": "boolean_union.png",
    "boolean:separate": "boolean_separate.png",
}


@lru_cache(maxsize=None)
def toolbar_icon_path(item_id: str | None) -> str | None:
    if not item_id:
        return None
    filename = _TOOLBAR_ICON_BY_ID.get(str(item_id))
    if not filename:
        return None
    path = _ICON_DIR / filename
    return str(path) if path.exists() else None


@lru_cache(maxsize=None)
def toolbar_icon(item_id: str | None):
    path = toolbar_icon_path(item_id)
    if QIcon is None:
        return None
    if path:
        return QIcon(path)
    return QIcon()
