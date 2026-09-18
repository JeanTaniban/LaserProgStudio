# -*- coding: utf-8 -*-
"""Shared low-level contract for LaserProg's Manifold boolean kernel.

Keep conversion and status checks in one place so geometry generators validate
against the exact same rules as the boolean operation runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ManifoldConstruction:
    manifold: Any
    status: str
    merge_changed: bool


def manifold_status_text(value: Any) -> str:
    try:
        status = value.status()
        return str(getattr(status, "name", status))
    except Exception as exc:
        return f"status_error:{type(exc).__name__}"


def manifold_is_valid(value: Any, module: Any) -> bool:
    try:
        status = value.status()
        no_error = getattr(getattr(module, "Error", None), "NoError", None)
        if no_error is not None and status != no_error:
            return False
        if no_error is None and str(getattr(status, "name", status)).lower() not in {
            "noerror",
            "error.noerror",
        }:
            return False
        return not bool(value.is_empty())
    except Exception:
        return False


def construct_manifold(
    module: Any,
    *,
    vertices: Any,
    triangles: Any,
    merge: bool = True,
    prefer_64bit: bool = False,
) -> ManifoldConstruction:
    """Build one Manifold using the production mesh conversion contract.

    ``Mesh64`` is preferred for generator-side validation when available so a
    world-space solid is not degraded to float32 merely to prove that it is
    manifold.  Boolean operations may continue to request the historical Mesh
    path by leaving ``prefer_64bit`` disabled.
    """

    mesh_type = getattr(module, "Mesh64", None) if bool(prefer_64bit) else None
    if mesh_type is None:
        mesh_type = module.Mesh
    mesh = mesh_type(tri_verts=triangles, vert_properties=vertices)
    merge_changed = False
    if bool(merge):
        try:
            merge_changed = bool(mesh.merge())
        except Exception:
            merge_changed = False
    manifold = module.Manifold(mesh)
    return ManifoldConstruction(
        manifold=manifold,
        status=manifold_status_text(manifold),
        merge_changed=bool(merge_changed),
    )


__all__ = [
    "ManifoldConstruction",
    "construct_manifold",
    "manifold_is_valid",
    "manifold_status_text",
]
