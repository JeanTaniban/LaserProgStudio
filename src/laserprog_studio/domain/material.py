# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

EngravingLayerId = Literal["cut", "engrave", "ignore"]
TextureUsage = Literal["visual", "cut", "engrave", "none"]
ProjectionMode = Literal["planar", "box", "cylindrical", "spherical"]
TexturePlacement = Literal["mesh", "decal"]


@dataclass(slots=True)
class MeshMaterial:
    """Display/manufacturing material attached to a WorkMesh.

    ``WorkMesh.color`` remains as a fast path. New code should prefer
    this material object so visual color, 3MF material data and engraving roles
    do not get mixed together.
    """

    name: str = "Default"
    base_color: str = "#B8B8B8"
    opacity: float = 1.0
    roughness: float = 0.5
    metallic: float = 0.0
    texture_id: str | None = None


@dataclass(slots=True)
class EngravingSettings:
    """Manufacturing metadata for laser export.

    The historical color-based roles are intentionally preserved through
    ``role``. ``layer`` is the future-facing split between cutting and engraving
    outputs.
    """

    role: str = "ignore"  # outline, fill, ignore, future custom roles
    layer: EngravingLayerId = "ignore"
    texture_usage: TextureUsage = "none"
    enabled: bool = True


@dataclass(slots=True)
class TextureProjection:
    """A texture placement on a mesh or a group of nearby faces."""

    texture_id: str
    texture_path: str | None = None
    target_mesh_name: str | None = None
    seed_face_index: int | None = None
    projection_mode: ProjectionMode = "planar"
    coverage_angle_deg: float = 20.0
    scale: float = 1.0
    stretch_u: float = 1.0
    stretch_v: float = 1.0
    rotation_deg: float = 0.0
    offset_u: float = 0.0
    offset_v: float = 0.0
    repeat: bool = False
    engraving_layer: EngravingLayerId = "engrave"
    placement: TexturePlacement = "mesh"


@dataclass(slots=True)
class MeshDomainData:
    """Optional V2 metadata payload for WorkMesh.

    Keeping this payload grouped avoids turning WorkMesh into a giant dataclass
    while still giving tools/textures/exporters one documented place to attach
    future data.
    """

    material: MeshMaterial = field(default_factory=MeshMaterial)
    engraving: EngravingSettings = field(default_factory=EngravingSettings)
    texture_projections: list[TextureProjection] = field(default_factory=list)
