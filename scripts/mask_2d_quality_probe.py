# -*- coding: utf-8 -*-
"""Quality probe for the 2D-mask -> vector contour -> 3D solid pipeline."""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology
from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh
from laserprog_studio.geometry_ops.image_mask_relief_loading import _load_binary_mask
from laserprog_studio.geometry_ops.image_mask_relief_vector import _binary_mask_to_smoothed_geometry
from laserprog_studio.geometry_ops.manifold_contract import construct_manifold, manifold_is_valid


def _manifold(mesh) -> dict[str, object]:
    try:
        import manifold3d as m3d
        v = np.asarray(mesh.vertices, dtype=np.float64)
        t = np.asarray(mesh.triangles, dtype=np.int32)
        c = construct_manifold(m3d, vertices=v[:, :3], triangles=t, merge=False, prefer_64bit=True)
        m = c.manifold
        return {
            "valid": bool(manifold_is_valid(m, m3d)),
            "status": str(c.status),
            "volume": float(m.volume()) if callable(getattr(m, "volume", None)) else None,
        }
    except Exception as exc:
        return {"valid": False, "status": f"{type(exc).__name__}: {exc}"}


def _polygon_metrics(geom) -> dict[str, float | int]:
    from shapely.geometry import Polygon, MultiPolygon
    polys = []
    if isinstance(geom, Polygon):
        polys = [geom]
    elif isinstance(geom, MultiPolygon):
        polys = list(geom.geoms)
    else:
        polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    segments = []
    vertices = 0
    perimeter = 0.0
    for poly in polys:
        for ring in (poly.exterior, *poly.interiors):
            coords = list(ring.coords)
            vertices += max(0, len(coords) - 1)
            for a, b in zip(coords, coords[1:]):
                dx = float(b[0] - a[0])
                dy = float(b[1] - a[1])
                length = math.hypot(dx, dy)
                if length <= 1e-12:
                    continue
                perimeter += length
                segments.append((dx, dy, length))
    axis_length = sum(length for dx, dy, length in segments if abs(dx) <= 1e-12 or abs(dy) <= 1e-12)
    return {
        "polygon_count": len(polys),
        "ring_vertices": vertices,
        "perimeter": perimeter,
        "axis_aligned_fraction": axis_length / max(perimeter, 1e-12),
        "area": float(sum(poly.area for poly in polys)),
    }


def _circle_radial_error(geom, *, cx: float, cy: float, radius: float) -> dict[str, float]:
    from shapely.geometry import Polygon, MultiPolygon
    polys = [geom] if isinstance(geom, Polygon) else list(getattr(geom, "geoms", []))
    errors = []
    for poly in polys:
        if not isinstance(poly, Polygon):
            continue
        for x, y in list(poly.exterior.coords)[:-1]:
            rr = math.hypot(float(x)-cx, float(y)-cy)
            errors.append(rr-radius)
    if not errors:
        return {"rms": float("nan"), "max_abs": float("nan")}
    arr = np.asarray(errors, dtype=float)
    return {
        "rms": float(np.sqrt(np.mean(arr*arr))),
        "max_abs": float(np.max(np.abs(arr))),
    }


def _write_shapes(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}

    # Antialiased source circle: source contains sub-pixel edge information.
    scale = 4
    big = Image.new("L", (160*scale, 160*scale), 255)
    draw = ImageDraw.Draw(big)
    draw.ellipse((20*scale, 20*scale, 140*scale, 140*scale), fill=0)
    circle = big.resize((160, 160), Image.Resampling.LANCZOS)
    p = root / "circle_aa.png"; circle.save(p); out["circle_aa"] = p

    ring = Image.new("L", (160,160), 255)
    d = ImageDraw.Draw(ring)
    d.ellipse((18,18,142,142), fill=0)
    d.ellipse((54,54,106,106), fill=255)
    p = root / "ring.png"; ring.save(p); out["ring"] = p

    star = Image.new("L", (160,160), 255)
    d = ImageDraw.Draw(star)
    pts=[]
    for i in range(20):
        a=-math.pi/2+i*math.pi/10
        r=62 if i%2==0 else 26
        pts.append((80+r*math.cos(a),80+r*math.sin(a)))
    d.polygon(pts, fill=0)
    p = root / "star.png"; star.save(p); out["star"] = p

    thin = Image.new("L", (160,160), 255)
    d=ImageDraw.Draw(thin)
    d.line((12,80,148,80), fill=0, width=2)
    d.line((80,12,80,148), fill=0, width=2)
    d.ellipse((55,55,105,105), outline=0, width=2)
    p=root/"thin.png"; thin.save(p); out["thin"] = p

    holes = Image.new("L", (160,160), 255)
    d=ImageDraw.Draw(holes)
    d.rounded_rectangle((15,15,145,145), radius=24, fill=0)
    for x,y in ((45,45),(115,45),(45,115),(115,115),(80,80)):
        d.ellipse((x-9,y-9,x+9,y+9), fill=255)
    p=root/"holes.png"; holes.save(p); out["holes"] = p

    diagonal = Image.new("L", (160,160), 255)
    d=ImageDraw.Draw(diagonal)
    d.polygon([(18,135),(65,18),(142,50),(96,143)], fill=0)
    p=root/"diagonal.png"; diagonal.save(p); out["diagonal"] = p
    return out


def _case(path: Path, smooth: float) -> dict[str, object]:
    mask, _src, _down, _thr = _load_binary_mask(
        path, invert=False, binary_threshold=0.5, levels=50,
        smooth=smooth, max_grid_size=0
    )
    geom, active = _binary_mask_to_smoothed_geometry(mask, pixel_size_mm=1.0, smooth=smooth)
    result = build_mask_relief_mesh(
        path, max_height_mm=10.0, pixel_size_mm=1.0, binary=True,
        levels=50, smooth=smooth, max_grid_size=0
    )
    closed = is_closed_triangle_mesh(result.mesh.vertices, result.mesh.triangles)
    topo = analyze_work_mesh_boolean_topology(result.mesh)
    return {
        "active_pixels": active,
        "polygon": _polygon_metrics(geom),
        "mesh": {
            "vertices": len(result.mesh.vertices),
            "triangles": len(result.mesh.triangles),
            "closed": bool(closed[0]),
            "boundary_edges": int(closed[1]),
            "indexed_nonmanifold_edges": int(closed[2]),
            "geometrically_manifold": bool(topo.geometrically_manifold),
            "welded_boundary_edges": int(topo.welded_boundary_edges),
            "welded_nonmanifold_edges": int(topo.welded_nonmanifold_edges),
            "collapsed_triangles": int(topo.collapsed_triangles),
            "duplicate_triangles": int(topo.duplicate_triangles),
            "manifold": _manifold(result.mesh),
        }
    }


def main() -> int:
    report: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shapes = _write_shapes(root)
        for name, path in shapes.items():
            rows={}
            for smooth in (0.0, 15.0, 35.0, 50.0, 75.0, 100.0):
                rows[str(int(smooth))] = _case(path, smooth)
            report[name] = rows

        # Circle quality relative to ideal raster-space circle center/radius.
        circle_rows={}
        path=shapes["circle_aa"]
        for smooth in (0.0,15.0,35.0,50.0,75.0,100.0):
            mask,*_ = _load_binary_mask(path, invert=False, binary_threshold=0.5, levels=50, smooth=smooth, max_grid_size=0)
            geom,_ = _binary_mask_to_smoothed_geometry(mask,pixel_size_mm=1.0,smooth=smooth)
            circle_rows[str(int(smooth))] = {
                **_polygon_metrics(geom),
                "radial_error": _circle_radial_error(geom,cx=80.0,cy=80.0,radius=60.0),
            }
        report["circle_quality"] = circle_rows

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
