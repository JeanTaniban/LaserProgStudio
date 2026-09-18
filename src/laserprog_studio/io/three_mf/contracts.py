# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True, frozen=True)
class TextureExportRecord:
    texture_id: str
    source_path: Path
    package_path: str


@dataclass(slots=True, frozen=True)
class MaterialExportRecord:
    material_id: str
    base_color: str
    texture_id: str | None = None


@dataclass(slots=True)
class ThreeMfExportPlan:
    """Future-facing 3MF export contract.

    The current exporter can keep writing simple mesh/color resources. Texture
    and material-aware exporters should first build this plan, then serialize it
    into the 3MF package. Keeping the plan separate prevents UI/tool code from
    knowing the internal 3MF zip/resource layout.
    """

    materials: list[MaterialExportRecord] = field(default_factory=list)
    textures: list[TextureExportRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_textures(self) -> bool:
        return bool(self.textures)
