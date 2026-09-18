# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any

from .studio_log import log


def apply_pyvista_safe_theme() -> None:
    import pyvista as pv

    pv.global_theme.smooth_shading = False
    try:
        pv.global_theme.multi_samples = 0
    except Exception:
        pass
    try:
        pv.global_theme.depth_peeling.enabled = False
    except Exception:
        pass
    try:
        pv.global_theme.allow_empty_mesh = True
    except Exception:
        pass
    log("[PYVISTA] Safe theme applied: smooth_shading=False, multi_samples=0, depth_peeling=False")


def parse_hex_color(value: str) -> tuple[float, float, float]:
    v = (value or "#B8B8B8").strip()
    if v.startswith("#"):
        v = v[1:]
    if len(v) == 8:
        v = v[:6]
    if len(v) != 6:
        return (0.72, 0.72, 0.72)
    try:
        return tuple(int(v[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]
    except Exception:
        return (0.72, 0.72, 0.72)


def workmesh_to_polydata(work_mesh: Any):
    import numpy as np
    import pyvista as pv

    vertices = np.asarray(work_mesh.vertices, dtype=float)
    tris = np.asarray(work_mesh.triangles, dtype=int)
    if tris.size == 0:
        faces = np.empty((0,), dtype=int)
    else:
        faces = np.empty((tris.shape[0], 4), dtype=int)
        faces[:, 0] = 3
        faces[:, 1:] = tris
        faces = faces.ravel()
    poly = pv.PolyData(vertices, faces)
    # Optional point UVs are used by the projected-texture tool.  Always write
    # VTK's native TCoords explicitly: relying only on PyVista's point_data name
    # works on some versions but can make a texture appear for one frame and then
    # vanish after a display/style refresh.
    uvs = getattr(work_mesh, "uvs", None)
    if uvs is not None:
        try:
            uv_arr = np.asarray(uvs, dtype=float)
            if uv_arr.shape == (len(vertices), 2):
                try:
                    poly.active_texture_coordinates = uv_arr
                except Exception:
                    pass
                try:
                    poly.point_data["Texture Coordinates"] = uv_arr
                    if hasattr(poly.point_data, "active_texture_coordinates_name"):
                        poly.point_data.active_texture_coordinates_name = "Texture Coordinates"
                except Exception:
                    pass

                from vtkmodules.vtkCommonCore import vtkFloatArray

                tcoords = vtkFloatArray()
                tcoords.SetName("Texture Coordinates")
                tcoords.SetNumberOfComponents(2)
                tcoords.SetNumberOfTuples(int(len(vertices)))
                for i, (u, v) in enumerate(uv_arr):
                    tcoords.SetTuple2(int(i), float(u), float(v))
                poly.GetPointData().SetTCoords(tcoords)
        except Exception as exc:
            try:
                log(f"[TEXTURE][WARN] could not attach UV TCoords to polydata: {exc}")
            except Exception:
                pass
    return poly


def mesh_bounds(mesh: Any) -> tuple[float, float, float, float, float, float]:
    if not mesh.vertices:
        return (0, 0, 0, 0, 0, 0)
    xs = [v[0] for v in mesh.vertices]
    ys = [v[1] for v in mesh.vertices]
    zs = [v[2] for v in mesh.vertices]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def mesh_center(mesh: Any) -> tuple[float, float, float]:
    b = mesh_bounds(mesh)
    return ((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, (b[4] + b[5]) / 2.0)


def scene_bounds(meshes: list[Any]) -> tuple[float, float, float, float, float, float]:
    if not meshes:
        return (-1, 1, -1, 1, -1, 1)
    bs = [mesh_bounds(m) for m in meshes if getattr(m, "vertices", None)]
    if not bs:
        return (-1, 1, -1, 1, -1, 1)
    return (
        min(b[0] for b in bs),
        max(b[1] for b in bs),
        min(b[2] for b in bs),
        max(b[3] for b in bs),
        min(b[4] for b in bs),
        max(b[5] for b in bs),
    )


def bounds_size(bounds: tuple[float, float, float, float, float, float]) -> float:
    return max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4], 1.0)


def transform_vertices(
    vertices: list[tuple[float, float, float]],
    *,
    dx: float,
    dy: float,
    dz: float,
    rx: float,
    ry: float,
    rz: float,
    sx: float,
    sy: float,
    sz: float,
    center: tuple[float, float, float],
) -> list[tuple[float, float, float]]:
    cx, cy, cz = center
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    sinx, cosx = math.sin(ax), math.cos(ax)
    siny, cosy = math.sin(ay), math.cos(ay)
    sinz, cosz = math.sin(az), math.cos(az)
    out: list[tuple[float, float, float]] = []
    for x, y, z in vertices:
        x = (x - cx) * sx
        y = (y - cy) * sy
        z = (z - cz) * sz
        y, z = y * cosx - z * sinx, y * sinx + z * cosx
        x, z = x * cosy + z * siny, -x * siny + z * cosy
        x, y = x * cosz - y * sinz, x * sinz + y * cosz
        out.append((x + cx + dx, y + cy + dy, z + cz + dz))
    return out


def translate_mesh(mesh: Any, dx: float, dy: float, dz: float) -> None:
    mesh.vertices = [(x + dx, y + dy, z + dz) for x, y, z in mesh.vertices]


def create_box_panel_meshes(width: float, depth: float, height: float, thickness: float):
    """Very small generator returning 6 panels.

    This is a first preview-only wiring, not the full production generator yet.
    """
    from laserprog_studio.domain.work_model import WorkMesh

    def panel(name: str, cx: float, cy: float, cz: float, lx: float, ly: float, lz: float, color: str):
        x0, x1 = cx - lx / 2, cx + lx / 2
        y0, y1 = cy - ly / 2, cy + ly / 2
        z0, z1 = cz - lz / 2, cz + lz / 2
        v = [
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
        ]
        t = [
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
            (1, 5, 6),
            (1, 6, 2),
            (2, 6, 7),
            (2, 7, 3),
            (3, 7, 4),
            (3, 4, 0),
        ]
        return WorkMesh(name=name, vertices=v, triangles=t, color=color)

    return [
        panel("fond", 0, 0, 0, width, depth, thickness, "#d6d6d6"),
        panel("couvercle", 0, 0, height, width, depth, thickness, "#cfcfcf"),
        panel("avant", 0, -depth / 2, height / 2, width, thickness, height, "#b8c7e0"),
        panel("arriere", 0, depth / 2, height / 2, width, thickness, height, "#b8c7e0"),
        panel("left", -width / 2, 0, height / 2, thickness, depth, height, "#e0c7b8"),
        panel("right", width / 2, 0, height / 2, thickness, depth, height, "#e0c7b8"),
    ]


__all__ = [
    "apply_pyvista_safe_theme",
    "bounds_size",
    "create_box_panel_meshes",
    "mesh_bounds",
    "mesh_center",
    "parse_hex_color",
    "scene_bounds",
    "transform_vertices",
    "translate_mesh",
    "workmesh_to_polydata",
]
