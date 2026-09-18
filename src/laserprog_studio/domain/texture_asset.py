# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

TextureAssetUsage = Literal["visual", "cut", "engrave"]


@dataclass(slots=True, frozen=True)
class TextureAsset:
    """Texture resource known by the Studio.

    The texture projection tool will store only stable ids/references on meshes;
    the asset manager owns the path and recent-file history.
    """

    id: str
    path: Path
    usage: TextureAssetUsage = "visual"
    width: int | None = None
    height: int | None = None

    @property
    def filename(self) -> str:
        return self.path.name
