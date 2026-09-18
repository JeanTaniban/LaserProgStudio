# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import WorkMesh

from .image_mask_relief_loading import _clamp_float, _load_binary_mask
from .image_mask_relief_types import MaskReliefResult, MaskReliefStats

_Q_SCALE = 1_000_000.0


def _binary_mask_to_smoothed_geometry(mask: list[list[bool]], *, pixel_size_mm: float, smooth: float):
    """Convert a binary mask grid to the same smoothed footprint used by the mesh."""

    from shapely.geometry import box
    from shapely.ops import unary_union

    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    if rows <= 0 or cols <= 0:
        return None, 0

    pixel = max(1e-6, float(pixel_size_mm))
    rects = []
    active_pixels = 0
    for r in range(rows):
        c = 0
        while c < cols:
            if not bool(mask[r][c]):
                c += 1
                continue
            start = c
            while c < cols and bool(mask[r][c]):
                c += 1
            end = c
            active_pixels += end - start
            rects.append(box(float(start) * pixel, float(r) * pixel, float(end) * pixel, float(r + 1) * pixel))

    if not rects:
        return None, 0
    geom = unary_union(rects)
    geom = _smooth_binary_geometry(geom, pixel_size_mm=pixel, smooth=float(smooth))
    return geom, int(active_pixels)


def _smooth_binary_geometry(geom, *, pixel_size_mm: float, smooth: float):
    """Round and simplify a binary footprint without pre-threshold blur.

    The mask is thresholded first, exactly from the source pixels, then only the
    vector outline is simplified/rounded.  This preserves thin strokes and edge
    information that a Gaussian blur would otherwise erase before binarization.
    """

    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
    from shapely.ops import unary_union

    smooth_level = _clamp_float(float(smooth), 0.0, 100.0)
    try:
        geom = geom.buffer(0)
    except Exception:
        pass
    if smooth_level <= 0.0 or getattr(geom, "is_empty", False):
        return geom

    pixel = max(1e-6, float(pixel_size_mm))
    minx, miny, maxx, maxy = geom.bounds
    span = max(0.0, min(float(maxx - minx), float(maxy - miny)))
    if span <= 0.0:
        return geom

    # Stay below half a pixel so Smooth improves jagged contours without turning
    # into a morphological filter.  The previous blur/opening pass could delete
    # narrow borders; this one is intentionally contour-only and conservative.
    # The simplification tolerance can exceed one raw pixel on broad shapes so
    # ellipses and logos do not keep every stair-step vertex.  The span and area
    # guards below reject destructive candidates, which protects very thin parts.
    tolerance = min(pixel * 1.15, pixel * (0.08 + 1.55 * smooth_level / 100.0), span * 0.08)
    radius = min(pixel * 0.38, pixel * (0.03 + 0.32 * smooth_level / 100.0), span * 0.05)
    if tolerance <= 1e-9 and radius <= 1e-9:
        return geom

    def polygons_of(value):
        if isinstance(value, Polygon):
            return [value] if not value.is_empty else []
        if isinstance(value, MultiPolygon):
            return [poly for poly in value.geoms if isinstance(poly, Polygon) and not poly.is_empty]
        if isinstance(value, GeometryCollection):
            return [poly for poly in value.geoms if isinstance(poly, Polygon) and not poly.is_empty]
        return [poly for poly in getattr(value, "geoms", []) if isinstance(poly, Polygon) and not poly.is_empty]

    def valid_candidate(candidate, reference) -> bool:
        try:
            if getattr(candidate, "is_empty", True):
                return False
            ref_area = max(float(reference.area), 1e-9)
            cand_area = float(candidate.area)
            if cand_area < ref_area * 0.72:
                return False
            if cand_area > ref_area * 1.45 + pixel * pixel * 8.0:
                return False
            # Prevent the smoothing pass from collapsing tiny strokes into a
            # different object.  The moved area may grow with smoothing, but not
            # enough to dominate the original shape.
            try:
                changed_area = float(candidate.symmetric_difference(reference).area)
                if changed_area > max(ref_area * 0.55, pixel * pixel * 12.0):
                    return False
            except Exception:
                pass
            return True
        except Exception:
            return False

    smoothed_parts = []
    for part in polygons_of(geom):
        reference = part
        candidate = reference
        if tolerance > 1e-9:
            simplified = candidate.simplify(float(tolerance), preserve_topology=True)
            if valid_candidate(simplified, reference):
                candidate = simplified
        if radius > 1e-9:
            # Closing rounds outward corners but does not perform the destructive
            # erode/open pass that was removing fine details.  Each component is
            # processed separately to avoid merging nearby independent islands.
            rounded = candidate.buffer(float(radius), quad_segs=5, join_style=1).buffer(
                -float(radius), quad_segs=5, join_style=1
            )
            if valid_candidate(rounded, reference):
                candidate = rounded
        try:
            candidate = candidate.buffer(0)
        except Exception:
            pass
        smoothed_parts.extend(polygons_of(candidate) or [reference])

    if not smoothed_parts:
        return geom
    try:
        merged = unary_union(smoothed_parts).buffer(0)
        if valid_candidate(merged, geom):
            return merged
    except Exception:
        pass
    try:
        return MultiPolygon(smoothed_parts).buffer(0)
    except Exception:
        return geom


def _build_binary_vector_mesh(
    path: str | Path,
    *,
    max_height_mm: float,
    pixel_size_mm: float,
    invert: bool,
    binary_threshold: float,
    max_grid_size: int,
    name: str,
    color: str,
    levels: float | None = None,
    smooth: float = 0.0,
) -> MaskReliefResult:
    """Vectorise a binary mask, triangulate it, then extrude it.

    This replaces the old per-pixel 3D column generation for binary imports.
    The raster is still sampled on a grid, but the resulting mesh is built from
    the merged mask contours, which drastically reduces triangle counts for
    large masks while staying faithful to the bitmap silhouette.
    """

    from shapely.geometry import Polygon, MultiPolygon, box
    from shapely.geometry.polygon import orient
    from shapely.ops import triangulate, unary_union

    pixel = max(1e-6, float(pixel_size_mm))
    max_h = max(0.0, float(max_height_mm))
    mask, source_size, downsampled, threshold = _load_binary_mask(
        path,
        invert=bool(invert),
        binary_threshold=float(binary_threshold),
        levels=levels,
        smooth=float(smooth),
        max_grid_size=int(max_grid_size),
    )
    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    if rows <= 0 or cols <= 0:
        raise ValueError("Empty or unreadable image.")

    active = {(r, c) for r in range(rows) for c in range(cols) if bool(mask[r][c])}
    if not active:
        raise ValueError("The binary mask contains no material. Adjust Levels, enable Invert, or use a higher-contrast image.")

    total_w = cols * pixel
    total_h = rows * pixel
    x_origin = -total_w / 2.0
    y_origin = -total_h / 2.0

    def cell_bounds(r: int, c0: int, c1: int) -> tuple[float, float, float, float]:
        x0 = x_origin + float(c0) * pixel
        x1 = x_origin + float(c1) * pixel
        y_top = y_origin + float(rows - r) * pixel
        y_bottom = y_top - pixel
        return x0, y_bottom, x1, y_top

    # Step 1: raster -> vector-ready rectangles (merged horizontal runs).
    rects = []
    active_pixels = 0
    for r in range(rows):
        c = 0
        while c < cols:
            if not bool(mask[r][c]):
                c += 1
                continue
            start = c
            while c < cols and bool(mask[r][c]):
                c += 1
            end = c
            active_pixels += end - start
            x0, y0, x1, y1 = cell_bounds(r, start, end)
            rects.append(box(x0, y0, x1, y1))

    merged = unary_union(rects)
    merged = _smooth_binary_geometry(merged, pixel_size_mm=pixel, smooth=float(smooth))
    if merged.is_empty:
        raise ValueError(
            "Binary mask vectorization failed. Try another threshold or a higher-contrast image."
        )

    if isinstance(merged, Polygon):
        polygons = [orient(merged, sign=1.0)]
    elif isinstance(merged, MultiPolygon):
        polygons = [orient(poly, sign=1.0) for poly in merged.geoms if not poly.is_empty]
    else:  # pragma: no cover - defensive fallback for rare degenerate outputs
        polygons = [orient(poly, sign=1.0) for poly in getattr(merged, "geoms", []) if isinstance(poly, Polygon) and not poly.is_empty]

    if not polygons:
        raise ValueError("No valid polygon contour was found in the binary mask.")

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    vertex_index: dict[tuple[int, int, int, int], int] = {}
    vertex_scope = [0]

    def _q(value: float) -> int:
        return int(round(float(value) * _Q_SCALE))

    def vertex(x: float, y: float, z: float) -> int:
        key = (int(vertex_scope[0]), _q(x), _q(y), _q(z))
        idx = vertex_index.get(key)
        if idx is not None:
            return idx
        idx = len(vertices)
        vertex_index[key] = idx
        vertices.append((float(x), float(y), float(z)))
        return idx

    def add_tri(a: int, b: int, c: int) -> None:
        if len({int(a), int(b), int(c)}) == 3:
            triangles.append((int(a), int(b), int(c)))

    def add_side_ring(coords: list[tuple[float, float]], *, reverse: bool = False) -> None:
        if len(coords) < 2:
            return
        pts = list(coords)
        if reverse:
            pts = list(reversed(pts))
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(x1 - x0) <= 1e-12 and abs(y1 - y0) <= 1e-12:
                continue
            b0 = vertex(x0, y0, 0.0)
            b1 = vertex(x1, y1, 0.0)
            t0 = vertex(x0, y0, max_h)
            t1 = vertex(x1, y1, max_h)
            add_tri(b0, b1, t1)
            add_tri(b0, t1, t0)

    # Step 2: polygon triangulation for top/bottom caps + side walls.
    for poly_index, poly in enumerate(polygons, start=1):
        vertex_scope[0] = int(poly_index)
        for tri in triangulate(poly):
            if tri.is_empty or tri.area <= 1e-12:
                continue
            rp = tri.representative_point()
            if not poly.covers(rp):
                continue
            coords = [(float(x), float(y)) for x, y in list(tri.exterior.coords)[:-1]]
            if len(coords) != 3:
                continue
            top_ids = [vertex(x, y, max_h) for x, y in coords]
            bot_ids = [vertex(x, y, 0.0) for x, y in coords]
            add_tri(top_ids[0], top_ids[1], top_ids[2])
            add_tri(bot_ids[2], bot_ids[1], bot_ids[0])

        ext = [(float(x), float(y)) for x, y in list(poly.exterior.coords)]
        add_side_ring(ext, reverse=False)
        for ring in poly.interiors:
            # Reverse hole ring to keep the wall facing the cavity.
            inner = [(float(x), float(y)) for x, y in list(ring.coords)]
            add_side_ring(inner, reverse=True)

    mesh = WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)
    try:
        setattr(mesh, "_lps_skip_boolean_merge", True)
    except Exception:
        pass
    stats = MaskReliefStats(
        source_width=int(source_size[0]),
        source_height=int(source_size[1]),
        width=cols,
        height=rows,
        active_pixels=int(active_pixels),
        vertices=len(vertices),
        triangles=len(triangles),
        max_height_mm=max_h,
        pixel_size_mm=pixel,
        downsampled=bool(downsampled),
        binary=True,
        binary_threshold=threshold,
    )
    return MaskReliefResult(mesh=mesh, stats=stats)
