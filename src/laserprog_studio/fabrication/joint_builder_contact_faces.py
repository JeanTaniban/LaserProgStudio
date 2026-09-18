# -*- coding: utf-8 -*-
from __future__ import annotations

from .joint_builder_contact_points import *  # type: ignore  # noqa: F401,F403

def _face_polygon_on_plane(
    mesh: WorkMesh,
    *,
    normal: np.ndarray,
    d_plane: float,
    plane_tol: float,
    normal_cos_tol: float = 0.97,
) -> Polygon | None:
    """Reconstruct a face (2D polygon) from triangles located on one plane.

    Backne la plus grande composante Polygon de l'union.
    """
    n = _normalize(np.array(normal, dtype=float))
    if float(np.linalg.norm(n)) <= 1e-12:
        return None
    s, t = _plane_basis_from_normal(n)

    polys: list[Polygon] = []
    v = np.array(mesh.vertices, dtype=float)

    for ia, ib, ic in mesh.triangles:
        p0 = v[ia]
        p1 = v[ib]
        p2 = v[ic]

        # Close to the plane?
        d0 = float(abs(float(p0 @ n) - d_plane))
        d1 = float(abs(float(p1 @ n) - d_plane))
        d2 = float(abs(float(p2 @ n) - d_plane))
        if max(d0, d1, d2) > plane_tol:
            continue

        # Face triangles: normal approximately collinear with n.
        nt = np.cross(p1 - p0, p2 - p0)
        nt = _normalize(nt.astype(float))
        if float(np.linalg.norm(nt)) <= 1e-12:
            continue
        if abs(float(nt @ n)) < float(normal_cos_tol):
            continue

        tri2d = Polygon([(float(p0 @ s), float(p0 @ t)), (float(p1 @ s), float(p1 @ t)), (float(p2 @ s), float(p2 @ t))])
        if tri2d.is_empty or tri2d.area <= 1e-9:
            continue
        polys.append(tri2d)

    if not polys:
        return None

    geom = unary_union(polys)
    if geom is None or getattr(geom, "is_empty", True):
        return None

    gt = getattr(geom, "geom_type", "")
    if gt == "Polygon":
        return geom
    if gt == "MultiPolygon":
        parts = [g for g in getattr(geom, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and getattr(g, "area", 0.0) > 1e-9]
        if parts:
            return max(parts, key=lambda p: getattr(p, "area", 0.0))
        return None

    if gt == "GeometryCollection":
        parts = [g for g in getattr(geom, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and getattr(g, "area", 0.0) > 1e-9]
        if parts:
            return max(parts, key=lambda p: getattr(p, "area", 0.0))

    return None

@dataclass(frozen=True)
class PlanarFace:
    normal: np.ndarray  # unit (3,)
    d: float  # plane offset: dot(normal, p) = d
    s: np.ndarray  # plane axis (3,)
    t: np.ndarray  # plane axis (3,)
    poly2d: Polygon  # in (s,t) coordinates: (dot(p,s), dot(p,t))
    triangles: tuple[int, ...]  # indices of triangles in original mesh

    @property
    def area(self) -> float:
        return float(getattr(self.poly2d, "area", 0.0))

def _triangle_normal_and_d(verts: np.ndarray, tri: tuple[int, int, int]) -> tuple[np.ndarray | None, float]:
    ia, ib, ic = tri
    p0 = verts[ia]
    p1 = verts[ib]
    p2 = verts[ic]
    n = np.cross(p1 - p0, p2 - p0)
    n = n.astype(float)
    nn = float(np.linalg.norm(n))
    if nn <= 1e-12:
        return None, 0.0
    n = n / nn
    d = float(np.dot(n, p0))
    return n, d

def _triangle_adjacency(tris: list[tuple[int, int, int]]) -> list[list[int]]:
    """Build per-triangle adjacency based on shared edges (2 common vertex indices)."""
    edge_to_tris: dict[tuple[int, int], list[int]] = {}
    for ti, (a, b, c) in enumerate(tris):
        for i, j in ((a, b), (b, c), (c, a)):
            if i < j:
                key = (i, j)
            else:
                key = (j, i)
            edge_to_tris.setdefault(key, []).append(ti)

    adj: list[set[int]] = [set() for _ in range(len(tris))]
    for ids in edge_to_tris.values():
        if len(ids) < 2:
            continue
        # Usually 2 for manifold meshes; support >2 defensively.
        for i in range(len(ids)):
            ti = ids[i]
            for j in range(i + 1, len(ids)):
                tj = ids[j]
                adj[ti].add(tj)
                adj[tj].add(ti)

    return [sorted(list(s)) for s in adj]

def _extract_planar_faces(
    mesh: WorkMesh,
    *,
    angle_deg: float = 1.0,
    plane_tol: float = 0.02,
    min_area: float = 1e-6,
) -> list[PlanarFace]:
    """Group coplanar triangles into planar faces (2D polygons).

    Criteria:
    - neighboring triangles (shared edge)
    - almost identical normals (tolerance angulaire)
    - same plane (plane_tol tolerance on d = dot(n,p))

    Return a list of PlanarFace objects with a reconstructed 2D polygon.
    """
    verts = np.array(mesh.vertices, dtype=float)
    tris = list(mesh.triangles)
    if not len(tris) or len(verts) < 3:
        return []

    cos_tol = float(math.cos(math.radians(float(angle_deg))))
    plane_tol = float(abs(plane_tol))
    if plane_tol <= 0:
        plane_tol = 0.02

    tri_n: list[np.ndarray | None] = [None] * len(tris)
    tri_d: list[float] = [0.0] * len(tris)
    valid = [True] * len(tris)
    for i, tri in enumerate(tris):
        n, d = _triangle_normal_and_d(verts, tri)
        if n is None:
            valid[i] = False
            continue
        tri_n[i] = n
        tri_d[i] = float(d)

    adj = _triangle_adjacency(tris)
    visited = [False] * len(tris)

    faces: list[PlanarFace] = []

    for seed in range(len(tris)):
        if not valid[seed] or visited[seed]:
            continue

        n0 = tri_n[seed]
        if n0 is None:
            continue
        n0 = n0.astype(float)
        d0 = float(tri_d[seed])

        # Flood fill on adjacency with coplanar constraint.
        stack = [seed]
        group: list[int] = []
        visited[seed] = True

        while stack:
            ti = stack.pop()
            group.append(ti)
            for tj in adj[ti]:
                if visited[tj] or (not valid[tj]):
                    continue
                nj = tri_n[tj]
                if nj is None:
                    continue
                dj = float(tri_d[tj])

                # Orient neighbor normal to seed.
                if float(np.dot(n0, nj)) < 0.0:
                    nj = -nj
                    dj = -dj

                if float(np.dot(n0, nj)) < cos_tol:
                    continue
                if abs(dj - d0) > plane_tol:
                    continue

                visited[tj] = True
                stack.append(tj)

        if not group:
            continue

        # Build 2D polygon via union of projected triangles in this plane.
        try:
            s, t = _plane_basis_from_normal(n0)
        except Exception:
            continue

        polys: list[Polygon] = []
        for ti in group:
            ia, ib, ic = tris[ti]
            p0 = verts[ia]
            p1 = verts[ib]
            p2 = verts[ic]
            tri2d = Polygon([(float(p0 @ s), float(p0 @ t)), (float(p1 @ s), float(p1 @ t)), (float(p2 @ s), float(p2 @ t))])
            if tri2d.is_empty or tri2d.area <= 1e-12:
                continue
            polys.append(tri2d)

        if not polys:
            continue

        geom = unary_union(polys)
        try:
            geom = geom.buffer(0)
        except Exception:
            pass

        poly = None
        gt = getattr(geom, "geom_type", "")
        if gt == "Polygon":
            poly = geom
        elif gt == "MultiPolygon":
            parts = [g for g in getattr(geom, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and getattr(g, "area", 0.0) > 1e-12]
            if parts:
                poly = max(parts, key=lambda p: getattr(p, "area", 0.0))
        elif gt == "GeometryCollection":
            parts = [g for g in getattr(geom, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and getattr(g, "area", 0.0) > 1e-12]
            if parts:
                poly = max(parts, key=lambda p: getattr(p, "area", 0.0))

        if poly is None or poly.is_empty or float(poly.area) < float(min_area):
            continue

        faces.append(PlanarFace(normal=n0, d=d0, s=s, t=t, poly2d=poly, triangles=tuple(group)))

    # Keep only meaningful faces, largest first (helps contact picking).
    faces.sort(key=lambda f: f.area, reverse=True)
    return faces

def _face_plane_offset_in_normal(mesh: WorkMesh, face: PlanarFace, normal: np.ndarray) -> float:
    """Estimate face plane offset in the given normal coordinates using median(dot(n, p))."""
    n = _normalize(np.array(normal, dtype=float))
    verts = np.array(mesh.vertices, dtype=float)
    tris = list(mesh.triangles)

    # Sample up to ~600 triangles to stay fast even on dense meshes.
    tri_ids = list(face.triangles)
    if not tri_ids:
        return float(np.median(verts @ n)) if len(verts) else 0.0

    step = max(1, int(len(tri_ids) // 600))
    dots: list[float] = []
    for ti in tri_ids[::step]:
        if ti < 0 or ti >= len(tris):
            continue
        a, b, c = tris[ti]
        dots.append(float(np.dot(n, verts[a])))
        dots.append(float(np.dot(n, verts[b])))
        dots.append(float(np.dot(n, verts[c])))

    if not dots:
        return float(np.median(verts @ n)) if len(verts) else 0.0
    return float(np.median(np.array(dots, dtype=float)))

def _poly_to_other_basis(poly: Polygon, *, src: PlanarFace, dst_s: np.ndarray, dst_t: np.ndarray) -> Polygon:
    """Transform a src poly2d (in src.s/src.t) into coordinates of (dst_s, dst_t)."""
    def ring_to_xy(ring) -> list[tuple[float, float]]:
        coords = list(ring.coords)
        if len(coords) >= 2 and coords[0] == coords[-1]:
            coords = coords[:-1]
        pts2: list[tuple[float, float]] = []
        for u, v in coords:
            p3 = (src.s * float(u)) + (src.t * float(v)) + (src.normal * float(src.d))
            pts2.append((float(p3 @ dst_s), float(p3 @ dst_t)))
        return pts2

    shell = ring_to_xy(poly.exterior)
    holes = [ring_to_xy(r) for r in poly.interiors]
    return Polygon(shell, holes)

def _contact_patch_center(
    mesh_a: WorkMesh,
    mesh_b: WorkMesh,
    *,
    contact_normal: np.ndarray,
    touch_tolerance: float,
) -> tuple[np.ndarray, float, float, np.ndarray, np.ndarray, object]:
    """Find a contact area between two planar faces of two meshes (tolerance ).

    Implements the robust pipeline:
    1) Group coplanar triangles -> planar faces (polygons)
    2) Test face pairs (opposite normals + close planes)
    3) Project to 2D in face A coordinates
    4) Compute the 2D intersection to get the shared area
    5) Return to 3D through (s,t,n)

    Returns: (center3, dA, dB, s, t, patch2d), where dot(n,p)=dA for face A and
    dot(n,p)=dB for face B after normal alignment. The joint plane is
    dot(n,p)=(dA+dB)/2.
    """
    eps = float(abs(touch_tolerance))
    if eps <= 0:
        eps = 0.05

    n_hint = _normalize(np.array(contact_normal, dtype=float))
    if float(np.linalg.norm(n_hint)) <= 1e-12:
        # Hint absent: fallback to centroid direction.
        va = np.array(mesh_a.vertices, dtype=float)
        vb = np.array(mesh_b.vertices, dtype=float)
        n_hint = _normalize((vb.mean(axis=0) - va.mean(axis=0)).astype(float))

    # 1) Extract planar faces for each mesh.
    plane_tol = max(0.02, eps * 0.25)  # face reconstruction should be tighter than contact epsilon.
    faces_a = _extract_planar_faces(mesh_a, angle_deg=1.0, plane_tol=plane_tol)
    faces_b = _extract_planar_faces(mesh_b, angle_deg=1.0, plane_tol=plane_tol)
    if not faces_a or not faces_b:
        raise ValueError("Cannot identify planar faces on the selected parts.")

    cos_parallel = float(math.cos(math.radians(1.0)))

    # best = (score, faceA, faceB, dA_in_nA, dB_in_nA, patch2d_in_A)
    best = None

    for fa in faces_a:
        nA = fa.normal
        dA = _face_plane_offset_in_normal(mesh_a, fa, nA)
        sA = fa.s
        tA = fa.t

        # Optional: bias to faces whose normal points roughly toward the other part.
        biasA = float(np.dot(nA, n_hint))
        if biasA < 0.0:
            # This face points away from the hint direction; still possible but less likely.
            bias_penalty = -biasA
        else:
            bias_penalty = 0.0

        for fb in faces_b:
            nB = fb.normal
            dotAB = float(np.dot(nA, nB))
            # Meshes may have inconsistent triangle winding, so we accept both same and opposite normals
            # as long as the planes are (almost) parallel.
            if abs(dotAB) < cos_parallel:
                continue

            # Align B plane to A normal (robust): estimate dB in nA coordinates.
            dB_aligned = _face_plane_offset_in_normal(mesh_b, fb, nA)
            gap = abs(dA - dB_aligned)
            if gap > eps:
                continue

            # Project B face polygon into A basis and intersect in 2D.
            try:
                polyB_in_A = _poly_to_other_basis(fb.poly2d, src=fb, dst_s=sA, dst_t=tA)
            except Exception:
                continue

            patch = fa.poly2d.intersection(polyB_in_A)
            if patch is None or getattr(patch, "is_empty", True):
                continue

            # Normalize to polygon.
            gt = getattr(patch, "geom_type", "")
            if gt == "MultiPolygon":
                polys = [g for g in getattr(patch, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and getattr(g, "area", 0.0) > 1e-12]
                if polys:
                    patch = max(polys, key=lambda p: getattr(p, "area", 0.0))
                    gt = "Polygon"
            elif gt == "GeometryCollection":
                polys = [g for g in getattr(patch, "geoms", []) if getattr(g, "geom_type", "") == "Polygon" and getattr(g, "area", 0.0) > 1e-12]
                if polys:
                    patch = max(polys, key=lambda p: getattr(p, "area", 0.0))
                    gt = "Polygon"

            if gt != "Polygon":
                continue

            area = float(getattr(patch, "area", 0.0))
            if area <= 1e-9:
                continue

            score = area - (bias_penalty * 1e-3)  # tiny tie-breaker
            if best is None or score > best[0] + 1e-12:
                best = (score, fa, fb, float(dA), float(dB_aligned), patch)

    if best is None:
        # Diagnostics: help tune tolerances when contact exists but face pairing fails.
        best_abs_dot = 0.0
        min_gap_any = float("inf")
        min_gap_parallel = float("inf")
        for fa in faces_a[:20]:
            nA = fa.normal
            dA = _face_plane_offset_in_normal(mesh_a, fa, nA)
            for fb in faces_b[:20]:
                nB = fb.normal
                abs_dot = abs(float(np.dot(nA, nB)))
                if abs_dot > best_abs_dot:
                    best_abs_dot = abs_dot
                dB_aligned = _face_plane_offset_in_normal(mesh_b, fb, nA)
                gap = abs(float(dA) - float(dB_aligned))
                if gap < min_gap_any:
                    min_gap_any = gap
                if abs_dot >= cos_parallel and gap < min_gap_parallel:
                    min_gap_parallel = gap

        msg = "Cannot find a stable contact area (tolerance too low?)."
        if math.isfinite(min_gap_any) and math.isfinite(min_gap_parallel):
            msg += f" (diag: facesA={len(faces_a)} facesB={len(faces_b)} best|dot|={best_abs_dot:.4f} min_gap_parallel={min_gap_parallel:.3f} min_gap_any={min_gap_any:.3f} eps={eps:.3f})"
        raise ValueError(msg)

    _score, fa, _fb, dA, dB_aligned, patch2d = best
    n = np.array(fa.normal, dtype=float)
    s = np.array(fa.s, dtype=float)
    t = np.array(fa.t, dtype=float)

    # Orient the returned (s, t, n) frame so that the patch normal points from A toward B.
    # IMPORTANT: keep patch2d consistent with the returned axes.
    #
    # Using centroids (vb.mean - va.mean) is unstable once you start boolean ops on parts.
    # A more robust sign comes from the plane offsets along nA:
    # - dA = dot(nA, p) for face A
    # - dB_aligned = dot(nA, p) for face B (measured in nA coordinates)
    # If dB_aligned > dA, then +nA points from A to B, else we flip.
    flip = False
    try:
        diff = float(dB_aligned) - float(dA)
        if abs(diff) > 1e-6:
            flip = diff < 0.0
        else:
            # Coplanar/near-coplanar faces: use the contact normal hint.
            nh = _normalize(np.array(contact_normal, dtype=float))
            if float(np.linalg.norm(nh)) > 1e-12:
                flip = float(np.dot(n, nh)) < 0.0
    except Exception:
        flip = False

    if flip:
        n = -n
        s = -s  # keep (s,t,n) right-handed so cross(s,t) matches the new normal direction
        dA = -float(dA)
        dB_aligned = -float(dB_aligned)
        try:
            from shapely import affinity

            patch2d = affinity.scale(patch2d, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0))
        except Exception:
            # If affinity is unavailable for some reason, we still return the flipped frame;
            # worst case: caller visualization may be mirrored.
            pass

    cx, cy = _geom_center_2d(patch2d)
    d_plane = (float(dA) + float(dB_aligned)) / 2.0
    center3 = (s * cx) + (t * cy) + (n * d_plane)

    return center3.astype(float), float(dA), float(dB_aligned), s.astype(float), t.astype(float), patch2d

def _major_axis_dir_2d(geom) -> tuple[float, float]:
    """Return a unit 2D direction following the longest axis of geom (in its own 2D coords)."""
    if geom is None or getattr(geom, "is_empty", True):
        return (1.0, 0.0)

    g = geom
    if getattr(g, "geom_type", "") == "MultiPolygon":
        polys = [p for p in getattr(g, "geoms", []) if getattr(p, "geom_type", "") == "Polygon" and p.area > 1e-9]
        if polys:
            g = max(polys, key=lambda p: p.area)

    mrr = getattr(g, "minimum_rotated_rectangle", None)
    if mrr is None:
        return (1.0, 0.0)
    mrr = g.minimum_rotated_rectangle

    gt = getattr(mrr, "geom_type", "")
    if gt == "LineString":
        coords = list(mrr.coords)
        if len(coords) >= 2:
            dx = float(coords[-1][0] - coords[0][0])
            dy = float(coords[-1][1] - coords[0][1])
            n = math.hypot(dx, dy)
            if n > 1e-12:
                return (dx / n, dy / n)
        return (1.0, 0.0)

    if gt == "Polygon":
        coords = list(mrr.exterior.coords)
        if len(coords) >= 2 and coords[0] == coords[-1]:
            coords = coords[:-1]
        if len(coords) < 4:
            return (1.0, 0.0)
        # Find longest edge.
        best = (1.0, 0.0)
        best_len = -1.0
        for i in range(len(coords)):
            x0, y0 = coords[i]
            x1, y1 = coords[(i + 1) % len(coords)]
            dx = float(x1 - x0)
            dy = float(y1 - y0)
            l = math.hypot(dx, dy)
            if l > best_len + 1e-12:
                best_len = l
                if l > 1e-12:
                    best = (dx / l, dy / l)
        return best

    return (1.0, 0.0)

def _projected_range_2d(geom, axis: tuple[float, float]) -> tuple[float, float]:
    ax, ay = axis
    n = math.hypot(ax, ay)
    if n <= 1e-12:
        return (0.0, 0.0)
    ax /= n
    ay /= n

    def add_coords(coords: list[tuple[float, float]], out: list[float]) -> None:
        for x, y in coords:
            out.append(float(x) * ax + float(y) * ay)

    vals: list[float] = []
    if geom is None or getattr(geom, "is_empty", True):
        return (0.0, 0.0)

    gt = getattr(geom, "geom_type", "")
    if gt == "Polygon":
        add_coords(list(geom.exterior.coords), vals)
    elif gt == "MultiPolygon":
        for g in getattr(geom, "geoms", []):
            if getattr(g, "geom_type", "") == "Polygon":
                add_coords(list(g.exterior.coords), vals)
    elif gt == "LineString":
        add_coords(list(geom.coords), vals)
    elif gt == "MultiLineString":
        for g in getattr(geom, "geoms", []):
            if getattr(g, "geom_type", "") == "LineString":
                add_coords(list(g.coords), vals)
    elif gt == "Point":
        x = float(geom.x)
        y = float(geom.y)
        vals.append(x * ax + y * ay)
    else:
        # Fallback: use centroid.
        c = geom.centroid
        vals.append(float(c.x) * ax + float(c.y) * ay)

    if not vals:
        return (0.0, 0.0)
    return (min(vals), max(vals))

def _contact_patch_short_side_mm(geom) -> float:
    """Smallest useful dimension of the joint face.

    Use the minimum oriented rectangle of the contact patch:
    - length = long side of the joint face
    - width = short side of the joint face

    This width controls the requested boolean cube X/Y/Z size.
    """
    if geom is None or getattr(geom, "is_empty", True):
        return 3.0

    g = geom
    if getattr(g, "geom_type", "") == "MultiPolygon":
        polys = [p for p in getattr(g, "geoms", []) if getattr(p, "geom_type", "") == "Polygon" and p.area > 1e-9]
        if polys:
            g = max(polys, key=lambda p: p.area)

    try:
        rect = g.minimum_rotated_rectangle
        gt = getattr(rect, "geom_type", "")
        if gt == "Polygon":
            coords = list(rect.exterior.coords)
            if len(coords) >= 2 and coords[0] == coords[-1]:
                coords = coords[:-1]
            lengths = []
            for i in range(len(coords)):
                x0, y0 = coords[i]
                x1, y1 = coords[(i + 1) % len(coords)]
                l = math.hypot(float(x1) - float(x0), float(y1) - float(y0))
                if l > 1e-6:
                    lengths.append(float(l))
            if lengths:
                return float(max(0.2, min(lengths)))
        elif gt == "LineString":
            # Patch reduced to a line: keep a small safety size.
            return float(max(0.2, min(3.0, getattr(rect, "length", 3.0))))
    except Exception:
        pass

    try:
        minx, miny, maxx, maxy = g.bounds
        return float(max(0.2, min(abs(maxx - minx), abs(maxy - miny))))
    except Exception:
        return 3.0

def _orthonormal_basis_from_forward(forward: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build a right-handed basis where local +Z (= forward) follows the arrow normal."""
    f = _normalize(np.array(forward, dtype=float))
    if float(np.linalg.norm(f)) <= 1e-12:
        raise ValueError("Arrow normal is zero: cannot orient the boolean cube.")

    # Choose a reference axis that is not parallel to forward.
    if abs(float(f[2])) < 0.9:
        ref = np.array([0.0, 0.0, 1.0], dtype=float)
    else:
        ref = np.array([0.0, 1.0, 0.0], dtype=float)

    x_axis = _normalize(np.cross(ref, f))
    if float(np.linalg.norm(x_axis)) <= 1e-12:
        ref = np.array([1.0, 0.0, 0.0], dtype=float)
        x_axis = _normalize(np.cross(ref, f))
    y_axis = _normalize(np.cross(f, x_axis))
    return x_axis.astype(float), y_axis.astype(float), f.astype(float)

def _make_oriented_boolean_box(
    *,
    name: str,
    center: np.ndarray,
    forward: np.ndarray,
    x_axis_hint: np.ndarray,
    size_x_mm: float,
    size_y_mm: float,
    size_z_mm: float,
    color: str = "#FF7F7F",
) -> WorkMesh:
    """Create a closed centered 3D box for joint booleans.

    Local convention used by the tool:
    - X = pin length on the joint face ;
    - Y = depth, aligned with the joint normal/arrow ;
    - Z = short width of the joint face.
    """
    sx = float(size_x_mm)
    sy = float(size_y_mm)
    sz = float(size_z_mm)
    if sx <= 0.0 or sy <= 0.0 or sz <= 0.0:
        raise ValueError("Invalid boolean box dimensions.")

    y_axis = _normalize(np.array(forward, dtype=float))
    if float(np.linalg.norm(y_axis)) <= 1e-12:
        raise ValueError("Arrow normal is zero: cannot orient the boolean box.")

    # X must stay in the face plane. Remove any component parallel to Y.
    x_axis = np.array(x_axis_hint, dtype=float)
    x_axis = x_axis - y_axis * float(np.dot(x_axis, y_axis))
    x_axis = _normalize(x_axis)
    if float(np.linalg.norm(x_axis)) <= 1e-12:
        # Fallback: build an axis that is not parallel to Y.
        ref = np.array([0.0, 0.0, 1.0], dtype=float) if abs(float(y_axis[2])) < 0.9 else np.array([1.0, 0.0, 0.0], dtype=float)
        x_axis = _normalize(np.cross(ref, y_axis))
    z_axis = _normalize(np.cross(x_axis, y_axis))
    if float(np.linalg.norm(z_axis)) <= 1e-12:
        raise ValueError("Cannot build the boolean box width axis.")
    # Re-align to guarantee a right-handed orthonormal basis.
    x_axis = _normalize(np.cross(y_axis, z_axis))

    c = np.array(center, dtype=float)
    hx = sx / 2.0
    hy = sy / 2.0
    hz = sz / 2.0

    local_vertices = [
        (-hx, -hy, -hz),
        ( hx, -hy, -hz),
        ( hx,  hy, -hz),
        (-hx,  hy, -hz),
        (-hx, -hy,  hz),
        ( hx, -hy,  hz),
        ( hx,  hy,  hz),
        (-hx,  hy,  hz),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]

    vertices: list[tuple[float, float, float]] = []
    for x, y, z in local_vertices:
        p = c + x_axis * float(x) + y_axis * float(y) + z_axis * float(z)
        vertices.append((float(p[0]), float(p[1]), float(p[2])))
    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)

def _make_oriented_boolean_cube(
    *,
    name: str,
    center: np.ndarray,
    forward: np.ndarray,
    size_mm: float,
    color: str = "#FF7F7F",
) -> WorkMesh:
    """Create a cube with X=Y=Z=size_mm."""
    x_axis, _, _ = _orthonormal_basis_from_forward(np.array(forward, dtype=float))
    return _make_oriented_boolean_box(
        name=name,
        center=center,
        forward=forward,
        x_axis_hint=x_axis,
        size_x_mm=size_mm,
        size_y_mm=size_mm,
        size_z_mm=size_mm,
        color=color,
    )

__all__ = [name for name in globals() if not name.startswith("__")]
