# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any


@dataclass(frozen=True, slots=True)
class DisplayLodInfo:
    enabled: bool
    original_triangles: int
    displayed_triangles: int
    stride: int


def _triangle_stride(count: int, *, threshold: int = 80_000, target: int = 55_000) -> int:
    count = int(max(0, count))
    if count <= int(threshold):
        return 1
    return max(2, int(round(count / max(1, int(target)))))


def make_display_lod_mesh(mesh: Any, *, threshold: int = 80_000, target: int = 55_000) -> tuple[Any, DisplayLodInfo]:
    """Return a display-only LOD proxy for large meshes.

    The proxy keeps the original point array and only thins rendered triangles.
    Keeping all points is intentional: live transform code can still replace
    ``polydata.points`` with the authoritative WorkMesh vertices without
    corrupting triangle indices.
    """
    triangles = list(getattr(mesh, "triangles", []) or [])
    original = len(triangles)
    stride = _triangle_stride(original, threshold=threshold, target=target)
    if stride <= 1:
        return mesh, DisplayLodInfo(False, original, original, 1)
    # Deterministic triangle thinning.  Always keep a small prefix so tiny
    # separate components remain visible even with a very coarse stride.
    kept = triangles[: min(64, original)]
    kept.extend(triangles[i] for i in range(64, original, stride))
    proxy = SimpleNamespace(
        name=getattr(mesh, "name", "part"),
        vertices=getattr(mesh, "vertices", []) or [],
        triangles=kept,
        color=getattr(mesh, "color", "#B8B8B8") or "#B8B8B8",
        material=getattr(mesh, "material", None),
        engraving=getattr(mesh, "engraving", None),
        uvs=getattr(mesh, "uvs", None),
        texture_projections=getattr(mesh, "texture_projections", []),
        mesh_id=getattr(mesh, "mesh_id", None),
    )
    return proxy, DisplayLodInfo(True, original, len(kept), stride)


__all__ = ["DisplayLodInfo", "make_display_lod_mesh"]
