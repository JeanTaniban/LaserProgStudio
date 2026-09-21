# -*- coding: utf-8 -*-
"""Quality probe for the 2D-mask -> vector contour -> 3D solid pipeline."""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import time

import numpy as np
from PIL import Image, ImageDraw

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology
from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh
from laserprog_studio.geometry_ops.image_mask_relief_contour import build_binary_mask_footprint, clear_mask_contour_caches
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


def _marching_squares_geometry(path: Path, *, threshold: float = 127.5):
    """Prototype sub-pixel contour extraction from grayscale activity.

    Diagnostic only: this validates the replacement architecture before
    production code is changed.
    """
    from shapely.geometry import LineString
    from shapely.ops import polygonize, unary_union

    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255,255,255,255))
        gray = Image.alpha_composite(white, rgba).convert("L")
        arr = 255.0 - np.asarray(gray, dtype=np.float64)

    h, w = arr.shape
    # Pad with empty samples. Original samples live at pixel centers.
    a = np.zeros((h+2,w+2), dtype=np.float64)
    a[1:-1,1:-1] = arr

    def value(r:int,c:int)->float:
        return float(a[r,c])

    def point(r:int,c:int)->tuple[float,float]:
        # padded sample (1,1) == original pixel center (0.5,0.5)
        return (float(c)-0.5, float(r)-0.5)

    def interp(p0,p1,v0,v1):
        dv=float(v1-v0)
        if abs(dv) <= 1e-12:
            t=0.5
        else:
            t=(float(threshold)-float(v0))/dv
        t=max(0.0,min(1.0,t))
        return (p0[0]+(p1[0]-p0[0])*t, p0[1]+(p1[1]-p0[1])*t)

    segments=[]
    # edge ids: 0 top, 1 right, 2 bottom, 3 left.
    base_cases={
        0:(), 1:((3,2),), 2:((2,1),), 3:((3,1),),
        4:((0,1),), 6:((0,2),), 7:((0,3),),
        8:((3,0),), 9:((0,2),), 11:((0,1),),
        12:((3,1),), 13:((2,1),), 14:((3,2),), 15:(),
    }
    for rr in range(h+1):
        for cc in range(w+1):
            # corners TL,TR,BR,BL
            vals=[value(rr,cc),value(rr,cc+1),value(rr+1,cc+1),value(rr+1,cc)]
            pts=[point(rr,cc),point(rr,cc+1),point(rr+1,cc+1),point(rr+1,cc)]
            bits=[v>=threshold for v in vals]
            case=(8 if bits[0] else 0)|(4 if bits[1] else 0)|(2 if bits[2] else 0)|(1 if bits[3] else 0)
            if case in (0,15):
                continue
            edges={
                0:interp(pts[0],pts[1],vals[0],vals[1]),
                1:interp(pts[1],pts[2],vals[1],vals[2]),
                2:interp(pts[3],pts[2],vals[3],vals[2]),
                3:interp(pts[0],pts[3],vals[0],vals[3]),
            }
            if case in (5,10):
                center=sum(vals)/4.0
                # Choose topology using the scalar center (simple asymptotic-style decider).
                if case==5:
                    pairs=((0,3),(1,2)) if center>=threshold else ((0,1),(3,2))
                else:
                    pairs=((0,1),(3,2)) if center>=threshold else ((0,3),(1,2))
            else:
                pairs=base_cases.get(case,())
            for e0,e1 in pairs:
                p0,p1=edges[e0],edges[e1]
                if math.hypot(p1[0]-p0[0],p1[1]-p0[1])>1e-10:
                    segments.append(LineString([p0,p1]))
    if not segments:
        return None
    polys=list(polygonize(segments))
    if not polys:
        return None
    return unary_union(polys)


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
    holes = 0
    perimeter = 0.0
    for poly in polys:
        holes += len(poly.interiors)
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
        "hole_count": holes,
        "euler_characteristic": len(polys) - holes,
        "ring_vertices": vertices,
        "perimeter": perimeter,
        "axis_aligned_fraction": axis_length / max(perimeter, 1e-12),
        "area": float(sum(poly.area for poly in polys)),
        "is_valid": bool(getattr(geom, "is_valid", False)),
        "minimum_clearance": float(getattr(geom, "minimum_clearance", 0.0) or 0.0),
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
    try:
        footprint = build_binary_mask_footprint(
            path,
            pixel_size_mm=1.0,
            invert=False,
            binary_threshold=0.5,
            levels=50,
            smooth=smooth,
            max_grid_size=0,
        )
        geom = footprint.geometry
        active = int(footprint.active_pixels)
        result = build_mask_relief_mesh(
            path, max_height_mm=10.0, pixel_size_mm=1.0, binary=True,
            levels=50, smooth=smooth, max_grid_size=0
        )
        closed = is_closed_triangle_mesh(result.mesh.vertices, result.mesh.triangles)
        topo = analyze_work_mesh_boolean_topology(result.mesh)
        return {
            "ok": True,
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
                "collapsed_triangles": int(topo.collapsed_triangles_after_weld),
                "duplicate_triangles": int(topo.duplicate_triangles_after_weld),
                "manifold": _manifold(result.mesh),
            }
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
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
            footprint = build_binary_mask_footprint(
                path,
                pixel_size_mm=1.0,
                invert=False,
                binary_threshold=0.5,
                levels=50,
                smooth=smooth,
                max_grid_size=0,
            )
            geom = footprint.geometry
            circle_rows[str(int(smooth))] = {
                **_polygon_metrics(geom),
                "radial_error": _circle_radial_error(geom,cx=0.0,cy=0.0,radius=60.0),
            }
        report["circle_quality"] = circle_rows

        # Prototype comparison: current pixel-box vectorization versus sub-pixel
        # marching-squares contouring on the same antialiased circle source.
        try:
            proto = _marching_squares_geometry(shapes["circle_aa"], threshold=127.5)
            report["circle_subpixel_prototype"] = {
                **_polygon_metrics(proto),
                "radial_error": _circle_radial_error(proto,cx=80.0,cy=80.0,radius=60.0),
            }
        except Exception as exc:
            report["circle_subpixel_prototype"] = {"error": f"{type(exc).__name__}: {exc}"}

        # Downsampling contract: verify whether max_grid_size changes the physical
        # size when pixel_size_mm is kept constant.
        hi = Image.new("L", (2048, 1024), 255)
        hd = ImageDraw.Draw(hi)
        hd.ellipse((256, 128, 1792, 896), fill=0)
        hi_path = root / "highres_2048.png"
        hi.save(hi_path)
        hi_result = build_mask_relief_mesh(
            hi_path,
            max_height_mm=10.0,
            pixel_size_mm=1.0,
            binary=True,
            levels=50,
            smooth=35,
            max_grid_size=512,
        )
        xs=[float(v[0]) for v in hi_result.mesh.vertices]
        ys=[float(v[1]) for v in hi_result.mesh.vertices]
        report["downsample_physical_scale"] = {
            "source_size": [2048,1024],
            "grid_size": [hi_result.stats.width, hi_result.stats.height],
            "downsampled": bool(hi_result.stats.downsampled),
            "mesh_bounds_xy": [
                min(xs) if xs else None,
                min(ys) if ys else None,
                max(xs) if xs else None,
                max(ys) if ys else None,
            ],
            "expected_full_image_width_if_1mm_per_source_pixel": 2048.0,
            "effective_full_grid_width_mm": float(hi_result.stats.width)*float(hi_result.stats.pixel_size_mm),
        }

        resolution_rows = {}
        for grid_limit in (256, 512, 1024):
            clear_mask_contour_caches()
            started = time.perf_counter()
            fp = build_binary_mask_footprint(
                hi_path,
                pixel_size_mm=1.0,
                invert=False,
                binary_threshold=0.5,
                levels=50,
                smooth=35,
                max_grid_size=grid_limit,
            )
            cold_footprint_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            warm_fp = build_binary_mask_footprint(
                hi_path,
                pixel_size_mm=1.0,
                invert=False,
                binary_threshold=0.5,
                levels=50,
                smooth=75,
                max_grid_size=grid_limit,
            )
            warm_smooth_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            result = build_mask_relief_mesh(
                hi_path,
                max_height_mm=10.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=35,
                max_grid_size=grid_limit,
            )
            warm_solid_ms = (time.perf_counter() - started) * 1000.0
            resolution_rows[str(grid_limit)] = {
                "cold_footprint_ms": cold_footprint_ms,
                "warm_smooth_ms": warm_smooth_ms,
                "warm_solid_ms": warm_solid_ms,
                "grid": [fp.width, fp.height],
                "ring_vertices": _polygon_metrics(fp.geometry)["ring_vertices"],
                "warm_ring_vertices": _polygon_metrics(warm_fp.geometry)["ring_vertices"],
                "mesh_vertices": len(result.mesh.vertices),
                "mesh_triangles": len(result.mesh.triangles),
            }
        report["resolution_performance"] = resolution_rows

        # More representative performance fixture: many holes and islands.
        complex_img = Image.new("L", (2048, 1024), 255)
        cd = ImageDraw.Draw(complex_img)
        cd.rounded_rectangle((96, 96, 1952, 928), radius=120, fill=0)
        for row in range(6):
            for col in range(12):
                cx = 210 + col * 145
                cy = 205 + row * 125
                radius = 24 + ((row + col) % 3) * 7
                cd.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=255)
        for col in range(14):
            x = 125 + col * 135
            cd.rectangle((x, 455, x + 34, 570), fill=255)
        complex_path = root / "complex_logo.png"
        complex_img.save(complex_path)

        complex_rows = {}
        for grid_limit in (512, 1024):
            clear_mask_contour_caches()
            started = time.perf_counter()
            fp = build_binary_mask_footprint(
                complex_path,
                pixel_size_mm=1.0,
                invert=False,
                binary_threshold=0.5,
                levels=50,
                smooth=35,
                max_grid_size=grid_limit,
            )
            cold_footprint_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            warm_fp = build_binary_mask_footprint(
                complex_path,
                pixel_size_mm=1.0,
                invert=False,
                binary_threshold=0.5,
                levels=50,
                smooth=75,
                max_grid_size=grid_limit,
            )
            warm_smooth_ms = (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            result = build_mask_relief_mesh(
                complex_path,
                max_height_mm=10.0,
                pixel_size_mm=1.0,
                binary=True,
                levels=50,
                smooth=35,
                max_grid_size=grid_limit,
            )
            warm_solid_ms = (time.perf_counter() - started) * 1000.0
            metrics = _polygon_metrics(fp.geometry)
            complex_rows[str(grid_limit)] = {
                "cold_footprint_ms": cold_footprint_ms,
                "warm_smooth_ms": warm_smooth_ms,
                "warm_solid_ms": warm_solid_ms,
                "grid": [fp.width, fp.height],
                "polygon_count": metrics["polygon_count"],
                "hole_count": metrics["hole_count"],
                "ring_vertices": metrics["ring_vertices"],
                "warm_ring_vertices": _polygon_metrics(warm_fp.geometry)["ring_vertices"],
                "mesh_vertices": len(result.mesh.vertices),
                "mesh_triangles": len(result.mesh.triangles),
                "manifold": _manifold(result.mesh),
            }
        report["complex_logo_performance"] = complex_rows

        # JPEG noise fixture. Keep the noise deterministic and moderate so the
        # probe measures realistic compression artifacts without becoming an
        # unbounded pathological stress test.
        rng = np.random.default_rng(20260921)
        noisy = np.full((512, 1024), 230, dtype=np.int16)
        yy, xx = np.ogrid[:512, :1024]
        mask_shape = ((xx - 512.0) / 390.0) ** 2 + ((yy - 256.0) / 175.0) ** 2 <= 1.0
        noisy[mask_shape] = 145
        noise = rng.normal(0.0, 5.0, size=noisy.shape)
        noisy = np.clip(noisy + noise, 0, 255).astype(np.uint8)
        noisy_path = root / "noisy_mask.jpg"
        Image.fromarray(noisy, mode="L").save(noisy_path, quality=55)

        noisy_rows = {}
        for grid_limit in (512, 1024):
            started = time.perf_counter()
            fp = build_binary_mask_footprint(
                noisy_path,
                pixel_size_mm=1.0,
                invert=False,
                binary_threshold=0.5,
                levels=50,
                smooth=35,
                max_grid_size=grid_limit,
            )
            elapsed = (time.perf_counter() - started) * 1000.0
            metrics = _polygon_metrics(fp.geometry)
            noisy_rows[str(grid_limit)] = {
                "footprint_ms": elapsed,
                "grid": [fp.width, fp.height],
                "polygon_count": metrics["polygon_count"],
                "hole_count": metrics["hole_count"],
                "ring_vertices": metrics["ring_vertices"],
                "minimum_clearance": metrics["minimum_clearance"],
            }
        report["noisy_jpeg_performance"] = noisy_rows

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
