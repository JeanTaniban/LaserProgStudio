# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderState:
    actors_by_index: dict[int, Any] = field(default_factory=dict)
    polydata_by_index: dict[int, Any] = field(default_factory=dict)
    floor_grid_actor: Any = None
    display_mode: str = "wireframe"
    show_edges_overlay: bool = True
    material_light_intensity: float = 1.4
    material_ambient: float = 0.18
    material_specular: float = 0.55
    material_light_azimuth: float = -45.0
    material_light_elevation: float = 45.0
    material_shadows: bool = False
    material_floor_shadow: bool = False
