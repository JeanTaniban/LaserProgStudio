# -*- coding: utf-8 -*-
from __future__ import annotations

from .joint_builder_rays import *  # type: ignore  # noqa: F401,F403

def _line_segment_along_axis_in_geom(
    geom, *, center_xy: tuple[float, float], axis_xy: tuple[float, float]
) -> tuple[float, float, object] | None:
    """Intersect geom with a long line through center in axis direction; return (dmin, dmax, inter_geom).

    d is the signed coordinate along axis, relative to center (dot(axis, (p-center))).
    """
    if geom is None or getattr(geom, "is_empty", True):
        return None
    ax, ay = axis_xy
    n = math.hypot(ax, ay)
    if n <= 1e-12:
        return None
    ax /= n
    ay /= n
    cx, cy = center_xy
    minx, miny, maxx, maxy = geom.bounds
    scale = max(maxx - minx, maxy - miny, 1.0) * 5.0 + 100.0
    p0 = (cx - ax * scale, cy - ay * scale)
    p1 = (cx + ax * scale, cy + ay * scale)
    line = LineString([p0, p1])
    inter = geom.intersection(line)
    if getattr(inter, "is_empty", True):
        return None

    def add_coords(coords: list[tuple[float, float]], out: list[float]) -> None:
        for x, y in coords:
            out.append((float(x) - cx) * ax + (float(y) - cy) * ay)

    vals: list[float] = []
    gt = getattr(inter, "geom_type", "")
    if gt == "LineString":
        add_coords(list(inter.coords), vals)
    elif gt == "MultiLineString":
        for g in getattr(inter, "geoms", []):
            if getattr(g, "geom_type", "") == "LineString":
                add_coords(list(g.coords), vals)
    elif gt == "Point":
        vals.append((float(inter.x) - cx) * ax + (float(inter.y) - cy) * ay)
    elif gt == "MultiPoint":
        for g in getattr(inter, "geoms", []):
            if getattr(g, "geom_type", "") == "Point":
                vals.append((float(g.x) - cx) * ax + (float(g.y) - cy) * ay)
    else:
        # fallback: sample centroid
        c = inter.centroid
        vals.append((float(c.x) - cx) * ax + (float(c.y) - cy) * ay)

    if not vals:
        return None
    return (min(vals), max(vals), inter)

def _boundary_point_along_axis(
    poly: Polygon, origin_xy: tuple[float, float], axis_xy: tuple[float, float]
) -> tuple[float, float] | None:
    """Boundary selection in 2D along a given axis.

    We intersect a long line through `origin_xy` with the polygon boundary and select the closest hit along that
    axis line (smallest |t|). This is robust when `origin_xy` is already on (or extremely close to) the boundary,
    which is common when placing pins from a contact patch.
    """
    ox, oy = origin_xy
    ax, ay = axis_xy
    n = math.hypot(ax, ay)
    if n <= 1e-12 or poly.is_empty:
        return None
    ax /= n
    ay /= n

    minx, miny, maxx, maxy = poly.bounds
    scale = max(maxx - minx, maxy - miny, 1.0) * 10.0 + 100.0
    p0 = (ox - ax * scale, oy - ay * scale)
    p1 = (ox + ax * scale, oy + ay * scale)
    line = LineString([p0, p1])
    inter = poly.boundary.intersection(line)
    if getattr(inter, "is_empty", True):
        return None

    pts: list[Point] = []
    gt = getattr(inter, "geom_type", "")
    if gt == "Point":
        pts = [inter]
    elif gt == "MultiPoint":
        pts = [g for g in getattr(inter, "geoms", []) if getattr(g, "geom_type", "") == "Point"]
    elif gt == "LineString":
        coords = list(inter.coords)
        if coords:
            pts = [Point(coords[0]), Point(coords[-1])]
    elif gt == "MultiLineString":
        for g in getattr(inter, "geoms", []):
            if getattr(g, "geom_type", "") == "LineString":
                coords = list(g.coords)
                if coords:
                    pts.append(Point(coords[0]))
                    pts.append(Point(coords[-1]))
    elif gt == "GeometryCollection":
        for g in getattr(inter, "geoms", []):
            if getattr(g, "geom_type", "") == "Point":
                pts.append(g)
            elif getattr(g, "geom_type", "") == "LineString":
                coords = list(g.coords)
                if coords:
                    pts.append(Point(coords[0]))
                    pts.append(Point(coords[-1]))

    if not pts:
        c = inter.centroid
        return (float(c.x), float(c.y))

    # NOTE: In our joint workflow, `origin_xy` is the projection of a point lying on the *contact patch plane*.
    # Numerically, this point is often already on the polygon boundary (t ~= 0 along the axis line).
    #
    # The previous "+axis only" selection was skipping t==0 and could pick the *opposite* boundary, which shifts
    # pins away from the blue-arrow guides. To make placement deterministic and sign-invariant, we select the
    # intersection with the smallest |t| (closest along the axis line).
    best_abs_t = float("inf")
    best_pt: Point | None = None
    for p in pts:
        dx = float(p.x) - ox
        dy = float(p.y) - oy
        t = dx * ax + dy * ay
        at = abs(t)
        if at < best_abs_t:
            best_abs_t = at
            best_pt = p

    if best_pt is None:
        return None
    return (float(best_pt.x), float(best_pt.y))

def _plane_point(basis: PlankBasis) -> np.ndarray:
    # Approximate mid-plane point.
    return basis.origin + basis.n * ((basis.w_min + basis.w_max) / 2.0)

def _line_of_intersection(p1: np.ndarray, n1: np.ndarray, p2: np.ndarray, n2: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Returns (point_on_line, direction) for intersection of 2 planes, or None if parallel."""
    d = np.cross(n1, n2)
    denom = float(np.dot(d, d))
    if denom <= 1e-18:
        return None

    # Solve for a point on the line using formula from plane intersection.
    # p = ( (c1*n2 - c2*n1) x d ) / |d|^2, with ci = nipi.
    c1 = float(np.dot(n1, p1))
    c2 = float(np.dot(n2, p2))
    num = np.cross((c1 * n2 - c2 * n1), d)
    p = num / denom
    return p, _normalize(d)

def _is_inside_prism(basis: PlankBasis, poly: Polygon, p3: np.ndarray, tol: float) -> bool:
    x, y, w = _coords_in_basis(basis, p3)
    if w < (basis.w_min - tol) or w > (basis.w_max + tol):
        return False
    return bool(poly.covers(Point(x, y)))

def _seam_interval(
    p0: np.ndarray,
    d: np.ndarray,
    basis_a: PlankBasis,
    poly_a: Polygon,
    mesh_a: WorkMesh,
    basis_b: PlankBasis,
    poly_b: Polygon,
    mesh_b: WorkMesh,
    *,
    touch_tolerance: float,
) -> tuple[float, float]:
    """Compute [tmin, tmax] along seam line where p0 + d*t is close to both prisms (approx).

    On vise le cas "les planches se touchent" (volumes non forcement en intersection).
    Perform a 1D scan and keep the area where the distance to each prism <= tol.
    """
    verts_a = np.array(mesh_a.vertices, dtype=float)
    verts_b = np.array(mesh_b.vertices, dtype=float)

    proj_a = (verts_a - p0) @ d
    proj_b = (verts_b - p0) @ d
    t_lo = float(max(proj_a.min(), proj_b.min()))
    t_hi = float(min(proj_a.max(), proj_b.max()))
    if not (t_hi > t_lo):
        raise ValueError("Boards do not seem to overlap along the contact line.")

    # Shrink via sampling where both distances are small.
    span = t_hi - t_lo
    # Prefer finer sampling to avoid missing a thin contact zone.
    # The previous fixed step could miss the contact entirely when touch_tolerance is small.
    target_step = max(0.02, float(touch_tolerance) / 3.0)
    max_samples = 8000
    min_samples = 400
    samples = int(math.ceil(span / target_step) + 1)
    if samples < min_samples:
        samples = min_samples
    if samples > max_samples:
        samples = max_samples
    step = float(span / max(1, samples - 1))

    def ok(t: float) -> bool:
        p = p0 + d * t
        _qa, da = _closest_boundary_point_on_prism(basis_a, poly_a, p)
        _qb, db = _closest_boundary_point_on_prism(basis_b, poly_b, p)
        return (da <= touch_tolerance) and (db <= touch_tolerance)

    # Sample and keep the OK band.
    ts = np.linspace(t_lo, t_hi, samples, dtype=float)
    ok_mask = np.zeros(samples, dtype=bool)
    for i in range(samples):
        ok_mask[i] = bool(ok(float(ts[i])))

    if not bool(ok_mask.any()):
        raise ValueError("Cannot find a stable contact area (tolerance too small?).")

    first_idx = int(np.argmax(ok_mask))
    last_idx = int(len(ok_mask) - 1 - np.argmax(ok_mask[::-1]))
    found_lo = float(ts[first_idx])
    found_hi = float(ts[last_idx])
    if not (found_hi >= found_lo):
        raise ValueError("Cannot determine contact length.")

    # Refine edges a bit (binary search).
    def refine_edge(lo: float, hi: float, want_ok_at_hi: bool) -> float:
        for _ in range(18):
            mid = (lo + hi) / 2.0
            if ok(mid) == want_ok_at_hi:
                hi = mid
            else:
                lo = mid
        return hi

    # left edge: transition from !ok to ok around found_lo
    left_lo = float(ts[max(0, first_idx - 1)])
    left_hi = found_lo
    if ok(left_hi) and (left_lo < left_hi):
        found_lo = refine_edge(left_lo, left_hi, True)

    # right edge: transition from ok to !ok around found_hi
    right_lo = found_hi
    right_hi = float(ts[min(samples - 1, last_idx + 1)])
    if ok(right_lo) and (right_lo < right_hi):
        # want first !ok after ok -> refine where ok becomes False, so find boundary of ok region
        for _ in range(18):
            mid = (right_lo + right_hi) / 2.0
            if ok(mid):
                right_lo = mid
            else:
                right_hi = mid
        found_hi = right_lo

    return float(found_lo), float(found_hi)

def _centers_along_seam(
    p0: np.ndarray, d: np.ndarray, tmin: float, tmax: float, *, count: int, margin: float
) -> list[np.ndarray]:
    if count <= 0:
        return []
    if count == 1:
        return [p0 + d * ((tmin + tmax) / 2.0)]
    usable_min = tmin + margin
    usable_max = tmax - margin
    if usable_max <= usable_min:
        raise ValueError(
            f"Contact surface too small for {count} pins (margin {margin:.2f} mm, length {max(0.0, tmax - tmin):.2f} mm). "
            f"Reduce N, reduce pin size, or increase contact tolerance."
        )

    step = (usable_max - usable_min) / (count - 1)
    return [p0 + d * (usable_min + step * i) for i in range(count)]

__all__ = [name for name in globals() if not name.startswith("__")]
