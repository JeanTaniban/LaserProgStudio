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


def _separate_polygon_point_contacts(geom, *, pixel_size_mm: float):
    """Remove zero-area pinches that cannot form a manifold extrusion.

    A raster can contain strokes that only meet at one pixel corner.  Shapely
    may represent a smoothed version as one polygon whose exterior and an
    interior ring touch at that point.  Extruding that representation produces
    four side faces on the same vertical edge.  The shape looks correct, but it
    is non-manifold and every boolean rightfully rejects it.  Apply an
    imperceptibly small close/open only for that pathological topology.
    """

    from shapely.geometry import GeometryCollection, MultiPolygon, Polygon

    def polygons_of(value):
        if isinstance(value, Polygon):
            return [value] if not value.is_empty else []
        if isinstance(value, MultiPolygon):
            return [poly for poly in value.geoms if isinstance(poly, Polygon) and not poly.is_empty]
        if isinstance(value, GeometryCollection):
            return [poly for poly in value.geoms if isinstance(poly, Polygon) and not poly.is_empty]
        return [poly for poly in getattr(value, "geoms", []) if isinstance(poly, Polygon) and not poly.is_empty]

    def has_ring_point_contact(poly) -> bool:
        seen: set[tuple[int, int]] = set()
        for ring in (poly.exterior, *poly.interiors):
            coords = list(ring.coords)
            if len(coords) > 1:
                coords = coords[:-1]
            for x, y in coords:
                key = (int(round(float(x) * _Q_SCALE)), int(round(float(y) * _Q_SCALE)))
                if key in seen:
                    return True
                seen.add(key)
        return False

    if not any(has_ring_point_contact(poly) for poly in polygons_of(geom)):
        return geom
    epsilon = max(1e-7, min(float(pixel_size_mm) * 1e-4, 1e-4))
    try:
        repaired = geom.buffer(epsilon, quad_segs=1).buffer(-epsilon, quad_segs=1).buffer(0)
        if not getattr(repaired, "is_empty", True) and float(getattr(repaired, "area", 0.0)) > 1e-12:
            return repaired
    except Exception:
        pass
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
    """Create a certified solid from a sub-pixel binary-mask footprint.

    Raster/vector processing is intentionally completed before any 3D mesh is
    built.  The resulting Shapely footprint is then extruded through the same
    planar solid boundary used by Plan Tracer instead of maintaining a private
    cap/wall triangulator here.
    """

    from shapely.geometry import Polygon, MultiPolygon

    from laserprog_studio.planar_tools import make_locked_plane

    from .image_mask_relief_contour import build_binary_mask_footprint
    from .planar_boolean_solid import extrude_planar_regions_boolean_ready

    max_h = float(max_height_mm)
    if not math.isfinite(max_h) or max_h <= 1.0e-9:
        raise ValueError("Mask height must be greater than zero.")

    footprint = build_binary_mask_footprint(
        path,
        pixel_size_mm=float(pixel_size_mm),
        invert=bool(invert),
        binary_threshold=float(binary_threshold),
        levels=levels,
        smooth=float(smooth),
        max_grid_size=int(max_grid_size),
    )
    geometry = footprint.geometry

    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        polygons = [poly for poly in geometry.geoms if not poly.is_empty]
    else:
        polygons = [
            poly
            for poly in getattr(geometry, "geoms", ())
            if isinstance(poly, Polygon) and not poly.is_empty
        ]
    if not polygons:
        raise ValueError("No valid polygon contour was found in the binary mask.")

    regions = []
    for poly in polygons:
        outer = tuple((float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1])
        holes = tuple(
            tuple((float(x), float(y)) for x, y in list(ring.coords)[:-1])
            for ring in poly.interiors
        )
        if len(outer) >= 3:
            regions.append((outer, holes))
    if not regions:
        raise ValueError("The binary mask contains no manufacturable planar region.")

    mesh, solid_report = extrude_planar_regions_boolean_ready(
        regions,
        plane=make_locked_plane("top"),
        depth=max_h,
        name=name,
        color=color,
    )
    metadata = dict(getattr(mesh, "metadata", {}) or {})
    metadata.update(
        {
            "source_tool": "mask_relief",
            "mask_contour_contract": "subpixel_marching_squares_v1",
            "mask_source_width": int(footprint.source_size[0]),
            "mask_source_height": int(footprint.source_size[1]),
            "mask_grid_width": int(footprint.width),
            "mask_grid_height": int(footprint.height),
            "mask_step_x_mm": float(footprint.step_x_mm),
            "mask_step_y_mm": float(footprint.step_y_mm),
            "mask_smooth": float(smooth),
            "mask_threshold": float(footprint.threshold),
            "mask_extrusion_backend": str(solid_report.backend),
        }
    )
    metadata.pop("boolean_skip_merge", None)
    mesh.metadata = metadata
    try:
        if hasattr(mesh, "_lps_skip_boolean_merge"):
            delattr(mesh, "_lps_skip_boolean_merge")
    except Exception:
        pass

    stats = MaskReliefStats(
        source_width=int(footprint.source_size[0]),
        source_height=int(footprint.source_size[1]),
        width=int(footprint.width),
        height=int(footprint.height),
        active_pixels=int(footprint.active_pixels),
        vertices=len(mesh.vertices),
        triangles=len(mesh.triangles),
        max_height_mm=max_h,
        pixel_size_mm=float(pixel_size_mm),
        downsampled=bool(footprint.downsampled),
        binary=True,
        binary_threshold=float(footprint.threshold),
    )
    return MaskReliefResult(mesh=mesh, stats=stats)

