# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

RUNTIME_METADATA_ATTRS: tuple[str, ...] = (
    "material",
    "engraving",
    "uvs",
    "texture_projections",
    "domain",
)


def copy_runtime_mesh_metadata(src: Any, dst: Any) -> None:
    """Copy optional UI/export metadata between WorkMesh-like objects.

    Geometry operations often rebuild vertices and triangles but must not lose
    material, engraving or texture metadata attached by higher-level tools. The
    helper is intentionally defensive because older WorkMesh instances do not
    necessarily expose all attributes.
    """

    for name in RUNTIME_METADATA_ATTRS:
        if not hasattr(src, name):
            continue
        try:
            setattr(dst, name, copy.deepcopy(getattr(src, name)))
        except Exception:
            # Metadata must never make a geometry operation fail.
            continue
