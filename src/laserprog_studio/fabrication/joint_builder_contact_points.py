# -*- coding: utf-8 -*-
from __future__ import annotations

from .joint_builder_basis import *  # type: ignore  # noqa: F401,F403

def _closest_boundary_point_on_prism(
    basis: PlankBasis, poly: Polygon, p3: np.ndarray
) -> tuple[np.ndarray, float]:
    """Approximation: closest point on the prism boundary (polygon extruded over [w_min, w_max])."""
    x, y, w = _coords_in_basis(basis, p3)
    pt = Point(x, y)

    w0 = basis.w_min
    w1 = basis.w_max
    w_clamped = _clamp(w, w0, w1)

    # Nearest XY on boundary (works for inside/outside).
    try:
        near_xy = nearest_points(pt, poly.boundary)[1]
    except Exception:
        # Fallback: if boundary fails for some reason, use polygon itself.
        near_xy = nearest_points(pt, poly)[1]

    inside_xy = bool(poly.covers(pt))
    inside_w = (w0 <= w <= w1)

    # Candidate 1: snap XY to boundary, keep/clamp W.
    q1 = np.array(basis.lift_3d(float(near_xy.x), float(near_xy.y), w_clamped), dtype=float)
    d_xy = float(pt.distance(poly.boundary))
    d_w = float(abs(w - w_clamped))
    dist1 = float(math.hypot(d_xy, d_w))

    # Candidate 2: if XY is inside, closest can be top/bottom face.
    if inside_xy:
        if not inside_w:
            # Direct vertical snap to slab boundary.
            q2 = np.array(basis.lift_3d(x, y, w_clamped), dtype=float)
            dist2 = float(abs(w - w_clamped))
        else:
            # Inside slab and footprint -> nearest boundary could be side wall or top/bottom.
            d_to_bottom = w - w0
            d_to_top = w1 - w
            if d_to_bottom <= d_to_top:
                w_face = w0
                dist_face = float(d_to_bottom)
            else:
                w_face = w1
                dist_face = float(d_to_top)
            q_face = np.array(basis.lift_3d(x, y, w_face), dtype=float)
            dist2 = float(dist_face)
            q2 = q_face

        if dist2 <= dist1:
            return q2, dist2

    return q1, dist1

def _closest_sidewall_xy_on_prism(basis: PlankBasis, poly: Polygon, p3: np.ndarray) -> tuple[float, float, float]:
    """Returns (x,y,w_clamped) on the side wall (XY projected to polygon boundary)."""
    x, y, w = _coords_in_basis(basis, p3)
    pt = Point(x, y)
    try:
        near_xy = nearest_points(pt, poly.boundary)[1]
    except Exception:
        near_xy = nearest_points(pt, poly)[1]
    w_clamped = _clamp(w, basis.w_min, basis.w_max)
    return float(near_xy.x), float(near_xy.y), float(w_clamped)

def _orient_axis_for_tab(poly: Polygon, boundary_xy: tuple[float, float], axis_xy: tuple[float, float]) -> tuple[float, float]:
    """For a tab, we want the rectangle to go OUTSIDE the polygon from its boundary point."""
    bx, by = boundary_xy
    ax, ay = axis_xy
    if math.hypot(ax, ay) <= 1e-12:
        return axis_xy
    eps = max(0.5, float(poly.bounds[2] - poly.bounds[0] + poly.bounds[3] - poly.bounds[1]) * 1e-6)
    p_out = Point(bx + ax * eps, by + ay * eps)
    # Use `contains` (strict interior) instead of `covers` here.
    # `covers` returns True for points on the boundary; when numerical noise keeps `p_out` exactly on the edge,
    # we must NOT flip the direction (otherwise the male pin goes opposite the arrow in some scenarios).
    if poly.contains(p_out):
        return (-ax, -ay)
    return (ax, ay)

def _orient_axis_for_slot(poly: Polygon, boundary_xy: tuple[float, float], axis_xy: tuple[float, float]) -> tuple[float, float]:
    """For a slot, we want the rectangle to go INSIDE the polygon from its boundary point."""
    bx, by = boundary_xy
    ax, ay = axis_xy
    if math.hypot(ax, ay) <= 1e-12:
        return axis_xy
    eps = max(0.5, float(poly.bounds[2] - poly.bounds[0] + poly.bounds[3] - poly.bounds[1]) * 1e-6)
    p_in = Point(bx + ax * eps, by + ay * eps)
    if not poly.covers(p_in):
        return (-ax, -ay)
    return (ax, ay)

def _axis_xy_towards_target_in_plane(
    basis: PlankBasis, boundary_xy: tuple[float, float], boundary_w: float, target3: np.ndarray
) -> tuple[float, float]:
    """2D direction (u/v) from an edge point toward a 3D target, projected onto the board plane."""
    bx, by = boundary_xy
    b3 = np.array(basis.lift_3d(bx, by, boundary_w), dtype=float)
    v3 = target3 - b3
    v3 = v3 - basis.n * float(np.dot(v3, basis.n))
    v3 = _normalize(v3)
    ax = float(np.dot(v3, basis.u))
    ay = float(np.dot(v3, basis.v))
    n = math.hypot(ax, ay)
    if n <= 1e-12:
        return (0.0, 0.0)
    return (ax / n, ay / n)

def _signed_area_ring(coords: list[tuple[float, float]]) -> float:
    if len(coords) < 3:
        return 0.0
    a = 0.0
    for i in range(len(coords)):
        x0, y0 = coords[i]
        x1, y1 = coords[(i + 1) % len(coords)]
        a += (x0 * y1 - x1 * y0)
    return 0.5 * a

def _outward_axis_from_boundary(poly: Polygon, boundary_xy: tuple[float, float]) -> tuple[float, float]:
    """Compute a stable outward direction (2D) at a boundary point on the exterior ring."""
    bx, by = boundary_xy
    coords = list(poly.exterior.coords)
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
    if len(coords) < 3:
        return (0.0, -1.0)

    # Find closest exterior segment.
    best_i = 0
    best_d2 = float("inf")
    n = len(coords)
    for i in range(n):
        x0, y0 = coords[i]
        x1, y1 = coords[(i + 1) % n]
        d2 = _dist2_point_to_segment(bx, by, x0, y0, x1, y1)
        if d2 < best_d2:
            best_d2 = d2
            best_i = i

    x0, y0 = coords[best_i]
    x1, y1 = coords[(best_i + 1) % n]
    tx = x1 - x0
    ty = y1 - y0
    tnorm = math.hypot(tx, ty)
    if tnorm <= 1e-12:
        return (0.0, -1.0)
    tx /= tnorm
    ty /= tnorm

    # Right normal points outward for CCW ring.
    ox = ty
    oy = -tx
    if _signed_area_ring([(float(x), float(y)) for (x, y) in coords]) < 0.0:
        ox, oy = -ox, -oy

    # Verify by probing: if we go "outward" and still are inside, flip.
    eps = max(0.5, float(poly.bounds[2] - poly.bounds[0] + poly.bounds[3] - poly.bounds[1]) * 1e-6)
    if poly.covers(Point(bx + ox * eps, by + oy * eps)):
        ox, oy = -ox, -oy

    on = math.hypot(ox, oy)
    if on <= 1e-12:
        return (0.0, -1.0)
    return (ox / on, oy / on)

def _dist2_point_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-18:
        dx = px - ax
        dy = py - ay
        return dx * dx + dy * dy
    t = (apx * abx + apy * aby) / denom
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    qx = ax + abx * t
    qy = ay + aby * t
    dx = px - qx
    dy = py - qy
    return dx * dx + dy * dy

def _center_boundary_point_on_edge(poly: Polygon, boundary_xy: tuple[float, float]) -> tuple[float, float]:
    """Recenter an edge point on the middle of the closest edge segment (collinear chain).

    Goal: avoid placing the joint on a corner when the contact is on an edge.
    """
    try:
        coords = list(poly.exterior.coords)
        if len(coords) < 4:
            return boundary_xy
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        n = len(coords)
        if n < 3:
            return boundary_xy

        px, py = boundary_xy

        # Find nearest segment on the ring.
        best_i = 0
        best_d2 = float("inf")
        for i in range(n):
            x0, y0 = coords[i]
            x1, y1 = coords[(i + 1) % n]
            d2 = _dist2_point_to_segment(px, py, x0, y0, x1, y1)
            if d2 < best_d2:
                best_d2 = d2
                best_i = i

        # If point is actually closest to a corner, don't "center" on some arbitrary edge.
        # This avoids jumping to a different edge when the contact happens near a corner.
        vx0, vy0 = coords[best_i]
        vx1, vy1 = coords[(best_i + 1) % n]
        corner0 = (px - vx0) * (px - vx0) + (py - vy0) * (py - vy0)
        corner1 = (px - vx1) * (px - vx1) + (py - vy1) * (py - vy1)
        if min(corner0, corner1) <= (max(0.4, math.sqrt(best_d2) + 1e-9) ** 2):
            return boundary_xy

        # Base direction from best segment.
        x0, y0 = coords[best_i]
        x1, y1 = coords[(best_i + 1) % n]
        dx0 = x1 - x0
        dy0 = y1 - y0
        norm0 = math.hypot(dx0, dy0)
        if norm0 <= 1e-12:
            return boundary_xy
        dx0 /= norm0
        dy0 /= norm0

        # Expand chain of near-collinear segments around best_i.
        cos_thr = math.cos(math.radians(8.0))

        def seg_dir(i: int) -> tuple[float, float] | None:
            a = coords[i]
            b = coords[(i + 1) % n]
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            nn = math.hypot(dx, dy)
            if nn <= 1e-12:
                return None
            return (dx / nn, dy / nn)

        start = best_i
        end = best_i

        # Reverse
        for _ in range(n):
            prev = (start - 1) % n
            dprev = seg_dir(prev)
            if dprev is None:
                break
            if abs(dprev[0] * dx0 + dprev[1] * dy0) < cos_thr:
                break
            start = prev
            if start == end:
                break

        # Forward
        for _ in range(n):
            nxt = (end + 1) % n
            dnext = seg_dir(nxt)
            if dnext is None:
                break
            if abs(dnext[0] * dx0 + dnext[1] * dy0) < cos_thr:
                break
            end = nxt
            if end == start:
                break

        # Build chain points from start -> end+1 following ring order.
        chain: list[tuple[float, float]] = []
        i = start
        chain.append((float(coords[i][0]), float(coords[i][1])))
        while i != end:
            i = (i + 1) % n
            chain.append((float(coords[i][0]), float(coords[i][1])))
        # Add end+1
        i = (end + 1) % n
        chain.append((float(coords[i][0]), float(coords[i][1])))

        if len(chain) < 2:
            return boundary_xy

        # Midpoint along chain length.
        lengths: list[float] = [0.0]
        total = 0.0
        for k in range(len(chain) - 1):
            ax, ay = chain[k]
            bx, by = chain[k + 1]
            seg_len = math.hypot(bx - ax, by - ay)
            total += seg_len
            lengths.append(total)

        if total <= 1e-9:
            return boundary_xy

        half = total / 2.0
        # Find segment containing half.
        for k in range(len(chain) - 1):
            if lengths[k + 1] >= half:
                ax, ay = chain[k]
                bx, by = chain[k + 1]
                seg_len = max(1e-12, lengths[k + 1] - lengths[k])
                t = (half - lengths[k]) / seg_len
                cx = ax + (bx - ax) * t
                cy = ay + (by - ay) * t
                return (float(cx), float(cy))

        return (float(chain[-1][0]), float(chain[-1][1]))
    except Exception:
        return boundary_xy

def _boundary_point_from_seam(
    poly: Polygon,
    seam_origin_xy: tuple[float, float],
    seam_dir_xy: tuple[float, float],
    *,
    preferred_dir_xy: tuple[float, float] | None = None,
) -> tuple[float, float] | None:
    """Returns a boundary point by intersecting the polygon boundary with an infinite seam line.

    This helps keep A/B aligned by using the same seam parameter instead of a nearest-point snap.
    """
    try:
        ox, oy = seam_origin_xy
        dx, dy = seam_dir_xy
        n = math.hypot(dx, dy)
        if n <= 1e-12:
            return None
        dx /= n
        dy /= n
        minx, miny, maxx, maxy = poly.bounds
        scale = max(maxx - minx, maxy - miny, 1.0) * 5.0 + 100.0
        a = (ox - dx * scale, oy - dy * scale)
        b = (ox + dx * scale, oy + dy * scale)
        line = LineString([a, b])
        inter = poly.boundary.intersection(line)
        pts: list[tuple[float, float]] = []
        if inter.is_empty:
            return None
        gt = inter.geom_type
        if gt == "Point":
            pts = [(float(inter.x), float(inter.y))]
        elif gt == "MultiPoint":
            pts = [(float(p.x), float(p.y)) for p in getattr(inter, "geoms", []) if p.geom_type == "Point"]
        elif gt == "LineString":
            # Overlap: pick midpoint along the overlapping segment (more centered).
            m = inter.interpolate(inter.length / 2.0) if inter.length > 1e-9 else nearest_points(Point(ox, oy), inter)[1]
            return (float(m.x), float(m.y))
        elif gt == "MultiLineString":
            # Overlap pieces: pick midpoint of the longest piece.
            segs = [g for g in getattr(inter, "geoms", []) if g.geom_type == "LineString" and g.length > 1e-9]
            if not segs:
                p = nearest_points(Point(ox, oy), inter)[1]
                return (float(p.x), float(p.y))
            longest = max(segs, key=lambda g: g.length)
            m = longest.interpolate(longest.length / 2.0)
            return (float(m.x), float(m.y))
        else:
            # GeometryCollection etc. -> pick points if any.
            for g in getattr(inter, "geoms", []):
                if g.geom_type == "Point":
                    pts.append((float(g.x), float(g.y)))

        if not pts:
            return None
        # Choose intersection on the expected side if possible, else closest to origin.
        if preferred_dir_xy is not None:
            best = _select_intersection_point_in_direction(poly, (ox, oy), preferred_dir_xy, pts)
        else:
            best = min(pts, key=lambda p: (p[0] - ox) * (p[0] - ox) + (p[1] - oy) * (p[1] - oy))
        return (float(best[0]), float(best[1]))
    except Exception:
        return None

def _select_intersection_point_in_direction(
    poly: Polygon,
    origin_xy: tuple[float, float],
    dir_xy: tuple[float, float],
    candidates: list[tuple[float, float]],
) -> tuple[float, float] | None:
    """Pick candidate in +dir from origin if possible, else closest."""
    ox, oy = origin_xy
    dx, dy = dir_xy
    n = math.hypot(dx, dy)
    if n <= 1e-12:
        return min(candidates, key=lambda p: (p[0] - ox) * (p[0] - ox) + (p[1] - oy) * (p[1] - oy))
    dx /= n
    dy /= n
    forward: list[tuple[float, float]] = []
    for px, py in candidates:
        vx = px - ox
        vy = py - oy
        if (vx * dx + vy * dy) >= 0.0:
            forward.append((px, py))
    if forward:
        return min(forward, key=lambda p: (p[0] - ox) * (p[0] - ox) + (p[1] - oy) * (p[1] - oy))
    return min(candidates, key=lambda p: (p[0] - ox) * (p[0] - ox) + (p[1] - oy) * (p[1] - oy))

def _estimate_contact_points(
    mesh_a: WorkMesh,
    basis_a: PlankBasis,
    poly_a: Polygon,
    mesh_b: WorkMesh,
    basis_b: PlankBasis,
    poly_b: Polygon,
    *,
    touch_tolerance: float,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Backne (pA, pB, dist) ~ points les plus proches entre les 2 prismes."""
    verts_a = np.array(mesh_a.vertices, dtype=float)
    verts_b = np.array(mesh_b.vertices, dtype=float)

    best_dist = float("inf")
    best_pa = None
    best_pb = None

    # A vertices to B boundary
    for p in verts_a:
        q, d = _closest_boundary_point_on_prism(basis_b, poly_b, p)
        if d < best_dist:
            best_dist = d
            best_pa = p.copy()
            best_pb = q.copy()

    # B vertices to A boundary
    for p in verts_b:
        q, d = _closest_boundary_point_on_prism(basis_a, poly_a, p)
        if d < best_dist:
            best_dist = d
            best_pa = q.copy()
            best_pb = p.copy()

    if best_pa is None or best_pb is None or not math.isfinite(best_dist):
        raise ValueError("Cannot estimate contact between the 2 boards.")

    if best_dist > touch_tolerance:
        raise ValueError(
            f"The 2 boards do not touch (distance {best_dist:.3f} mm > tol {touch_tolerance:.3f} mm)."
        )

    return best_pa, best_pb, float(best_dist)

def _project_vec_to_basis_2d(basis: PlankBasis, v3: np.ndarray) -> tuple[float, float]:
    x = float(np.dot(v3, basis.u))
    y = float(np.dot(v3, basis.v))
    n = math.hypot(x, y)
    if n <= 1e-12:
        return (0.0, 0.0)
    return (x / n, y / n)

def _plane_basis_from_normal(n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = _normalize(n)
    if float(np.linalg.norm(n)) <= 1e-12:
        raise ValueError("Zero normal for plane basis.")
    if abs(float(n[2])) < 0.9:
        a = np.array([0.0, 0.0, 1.0], dtype=float)
    else:
        a = np.array([0.0, 1.0, 0.0], dtype=float)
    s = _normalize(np.cross(a, n))
    if float(np.linalg.norm(s)) <= 1e-12:
        a = np.array([1.0, 0.0, 0.0], dtype=float)
        s = _normalize(np.cross(a, n))
    t = _normalize(np.cross(n, s))
    return s, t

def _geom_center_2d(geom) -> tuple[float, float]:
    if geom is None or getattr(geom, "is_empty", True):
        raise ValueError("Empty geometry.")

    gt = getattr(geom, "geom_type", "")
    if gt == "Polygon":
        c = geom.centroid
        return (float(c.x), float(c.y))
    if gt == "MultiPolygon":
        polys = [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon" and g.area > 1e-9]
        if polys:
            g = max(polys, key=lambda p: p.area)
            c = g.centroid
            return (float(c.x), float(c.y))
    if gt == "LineString":
        p = geom.interpolate(geom.length / 2.0) if geom.length > 1e-9 else geom.centroid
        return (float(p.x), float(p.y))
    if gt == "MultiLineString":
        lines = [g for g in getattr(geom, "geoms", []) if g.geom_type == "LineString" and g.length > 1e-9]
        if lines:
            g = max(lines, key=lambda l: l.length)
            p = g.interpolate(g.length / 2.0)
            return (float(p.x), float(p.y))
    if gt == "Point":
        return (float(geom.x), float(geom.y))
    if gt == "MultiPoint":
        c = geom.centroid
        return (float(c.x), float(c.y))

    c = geom.centroid
    return (float(c.x), float(c.y))

def _fit_plane_normal(points: np.ndarray) -> np.ndarray:
    """Return a unit normal for the best plane through `points` (PCA)."""
    if points is None or len(points) < 3:
        raise ValueError("Not enough points to estimate a plane.")
    ctr = points.mean(axis=0)
    x = points - ctr
    cov = (x.T @ x) / max(1, len(points))
    _w, vecs = np.linalg.eigh(cov)  # ascending
    n = vecs[:, 0]
    n = _normalize(n.astype(float))
    if float(np.linalg.norm(n)) <= 1e-12:
        raise ValueError("Undefined plane normal.")
    return n

def _sample_near_contact_points(
    mesh_a: WorkMesh,
    basis_a: PlankBasis,
    poly_a: Polygon,
    mesh_b: WorkMesh,
    basis_b: PlankBasis,
    poly_b: Polygon,
    *,
    sample_tol: float,
    max_samples: int = 2500,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Backne (a_contact_pts, b_contact_pts, mid_pts) sous forme de numpy arrays.

    Mathematical point->prism boundary measure (no raycasts). Subsample
    to keep the UI responsive.
    """
    va = np.array(mesh_a.vertices, dtype=float)
    vb = np.array(mesh_b.vertices, dtype=float)

    step_a = max(1, int(len(va) // max_samples)) if len(va) else 1
    step_b = max(1, int(len(vb) // max_samples)) if len(vb) else 1

    a_pts: list[np.ndarray] = []
    b_pts: list[np.ndarray] = []
    mids: list[np.ndarray] = []

    for p in va[::step_a]:
        q, d = _closest_boundary_point_on_prism(basis_b, poly_b, p)
        if d <= sample_tol:
            a_pts.append(p.copy())
            mids.append((p + q) * 0.5)

    for p in vb[::step_b]:
        q, d = _closest_boundary_point_on_prism(basis_a, poly_a, p)
        if d <= sample_tol:
            b_pts.append(p.copy())
            mids.append((p + q) * 0.5)

    a_arr = np.array(a_pts, dtype=float) if a_pts else np.empty((0, 3), dtype=float)
    b_arr = np.array(b_pts, dtype=float) if b_pts else np.empty((0, 3), dtype=float)
    m_arr = np.array(mids, dtype=float) if mids else np.empty((0, 3), dtype=float)
    return a_arr, b_arr, m_arr

__all__ = [name for name in globals() if not name.startswith("__")]
