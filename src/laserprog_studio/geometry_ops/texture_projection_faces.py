# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from laserprog_studio.domain.work_model import WorkMesh

from .texture_projection_types import TextureProjectionParams, Vec3
from .texture_projection_vector import _bounds, _cross, _dot, _fit_aspect_tile, _image_aspect, _length, _sub, _unit

def _triangle_normal(mesh: WorkMesh, face_index: int | None) -> Vec3 | None:
    try:
        if face_index is None:
            return None
        tri = getattr(mesh, "triangles", [])[int(face_index)]
        verts = getattr(mesh, "vertices", [])
        p0 = tuple(float(x) for x in verts[int(tri[0])])  # type: ignore[assignment]
        p1 = tuple(float(x) for x in verts[int(tri[1])])  # type: ignore[assignment]
        p2 = tuple(float(x) for x in verts[int(tri[2])])  # type: ignore[assignment]
        return _unit(_cross(_sub(p1, p0), _sub(p2, p0)), fallback=(0.0, 0.0, 1.0))
    except Exception:
        return None


def _triangle_centroid(mesh: WorkMesh, face_index: int | None) -> Vec3 | None:
    try:
        if face_index is None:
            return None
        tri = getattr(mesh, "triangles", [])[int(face_index)]
        verts = getattr(mesh, "vertices", [])
        pts = [tuple(float(x) for x in verts[int(i)]) for i in tri]
        return (
            (pts[0][0] + pts[1][0] + pts[2][0]) / 3.0,
            (pts[0][1] + pts[1][1] + pts[2][1]) / 3.0,
            (pts[0][2] + pts[1][2] + pts[2][2]) / 3.0,
        )
    except Exception:
        return None


def _face_edge_axis(mesh: WorkMesh, face_index: int | None, normal: Vec3) -> Vec3 | None:
    try:
        if face_index is None:
            return None
        tri = getattr(mesh, "triangles", [])[int(face_index)]
        verts = getattr(mesh, "vertices", [])
        p0 = tuple(float(x) for x in verts[int(tri[0])])
        candidates = []
        for raw in tri[1:]:
            p = tuple(float(x) for x in verts[int(raw)])
            edge = _sub(p, p0)
            # Remove a possible tiny normal component to keep the U axis in plane.
            edge = _sub(edge, (normal[0] * _dot(edge, normal), normal[1] * _dot(edge, normal), normal[2] * _dot(edge, normal)))
            candidates.append(edge)
        candidates.sort(key=_length, reverse=True)
        if candidates and _length(candidates[0]) > 1e-9:
            return _unit(candidates[0])
    except Exception:
        pass
    return None


def _bounds_axis_for_face(mesh: WorkMesh, face_index: int | None, normal: Vec3) -> Vec3 | None:
    """Return a bounds-aligned in-plane axis for the clicked face.

    A triangulated quad often contains a diagonal edge.  Using the longest edge
    of the picked triangle therefore rotates the texture/snap frame by 45° on
    ordinary rectangular faces.  For the texture placement tool we want the first
    practical behaviour requested by the UI: align to the main object bounds.
    Project the global bounds axes into the face plane and keep the one with the
    largest extent on the painted face.
    """

    try:
        if face_index is None:
            return None
        vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
        triangles = list(getattr(mesh, "triangles", []) or [])
        if not vertices or not (0 <= int(face_index) < len(triangles)):
            return None
        n = _unit(normal, fallback=(0.0, 0.0, 1.0))
        seed_center = _triangle_centroid(mesh, face_index)
        if seed_center is None:
            return None
        b = _bounds(vertices)
        scene_size = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0)
        plane_tol = max(scene_size * 1e-5, 1e-5)
        selected_ids: set[int] = set()
        for fid, tri in enumerate(triangles):
            c = _triangle_centroid(mesh, fid)
            fn = _triangle_normal(mesh, fid)
            if c is None or fn is None:
                continue
            if abs(_dot(_sub(c, seed_center), n)) <= plane_tol and abs(_dot(_unit(fn), n)) >= 1.0 - 1e-6:
                selected_ids.update(int(i) for i in tri)
        if not selected_ids:
            selected_ids.update(int(i) for i in triangles[int(face_index)])
        pts = [vertices[i] for i in selected_ids if 0 <= i < len(vertices)]
        if len(pts) < 2:
            return None

        best: tuple[float, int, Vec3] | None = None
        # Deterministic order is important on square faces: X wins ties, then Y,
        # then Z.  This keeps a top cube face from randomly turning diagonally.
        for order, axis in enumerate(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))):
            in_plane = _sub(axis, (n[0] * _dot(axis, n), n[1] * _dot(axis, n), n[2] * _dot(axis, n)))
            length = _length(in_plane)
            if length <= 1e-9:
                continue
            u = _unit(in_plane)
            coords = [_dot(p, u) for p in pts]
            span = max(coords) - min(coords)
            if span <= 1e-9:
                continue
            candidate = (float(span), -int(order), u)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        return best[2] if best is not None else None
    except Exception:
        return None


def _oriented_face_normal(mesh: WorkMesh, face_index: int | None, normal: Vec3) -> Vec3:
    """Prefer an outward normal for decal lifting.

    Imported/generated meshes can have inconsistent triangle winding.  For visual
    texture decals, a wrong normal can put the decal just inside the solid, where
    z-buffering hides it.  Compare the face center with the mesh center and flip
    the normal when it points inward.
    """

    try:
        center = _triangle_centroid(mesh, face_index)
        if center is None:
            return _unit(normal, fallback=(0.0, 0.0, 1.0))
        vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
        b = _bounds(vertices)
        mesh_center = ((b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, (b[4] + b[5]) * 0.5)
        n = _unit(normal, fallback=(0.0, 0.0, 1.0))
        outward_hint = _sub(center, mesh_center)
        if _length(outward_hint) > 1e-9 and _dot(n, outward_hint) < 0.0:
            return (-n[0], -n[1], -n[2])
        return n
    except Exception:
        return _unit(normal, fallback=(0.0, 0.0, 1.0))


def _stable_planar_axes(mesh: WorkMesh, *, face_index: int | None = None, normal: Vec3 | None = None) -> tuple[Vec3, Vec3, Vec3]:
    """Return normal, U axis, V axis for face-aware planar mapping.

    If a face was clicked, the U axis follows the longest edge of that triangle.
    This makes the image placement much more predictable than a global XY-only
    projection.  If no face is available, we keep the old XY behaviour.
    """

    n = _unit(normal or _triangle_normal(mesh, face_index) or (0.0, 0.0, 1.0), fallback=(0.0, 0.0, 1.0))
    bounds_axis = _bounds_axis_for_face(mesh, face_index, n)
    if bounds_axis is not None:
        u = bounds_axis
        v = _unit(_cross(n, u), fallback=(0.0, 1.0, 0.0))
        return n, u, v
    edge_axis = _face_edge_axis(mesh, face_index, n)
    if edge_axis is not None:
        u = edge_axis
        v = _unit(_cross(n, u), fallback=(0.0, 1.0, 0.0))
        return n, u, v
    # Old default: global XY plane, which is useful for top-down texture work.
    if abs(n[2]) > 0.80:
        u = (1.0, 0.0, 0.0)
    elif abs(n[1]) > 0.80:
        u = (1.0, 0.0, 0.0)
    else:
        u = (0.0, 1.0, 0.0)
    # Keep U exactly inside the plane.
    u = _sub(u, (n[0] * _dot(u, n), n[1] * _dot(u, n), n[2] * _dot(u, n)))
    u = _unit(u, fallback=(1.0, 0.0, 0.0))
    v = _unit(_cross(n, u), fallback=(0.0, 1.0, 0.0))
    return n, u, v


def _coplanar_face_vertex_coords(mesh: WorkMesh, *, seed_face_index: int | None, normal: Vec3, u_axis: Vec3, v_axis: Vec3, origin: Vec3, coverage_angle_deg: float) -> list[tuple[float, float]]:
    """Return projection coords for the flat face group around a clicked triangle.

    This gives the aspect-ratio fitter the target face size instead of the full
    object bounds.  If anything looks invalid, callers fall back to all vertices.
    """

    if seed_face_index is None:
        return []
    try:
        vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
        triangles = list(getattr(mesh, "triangles", []) or [])
        if not (0 <= int(seed_face_index) < len(triangles)):
            return []
        seed_center = _triangle_centroid(mesh, seed_face_index)
        if seed_center is None:
            return []
        cos_limit = math.cos(math.radians(max(0.0, min(180.0, float(coverage_angle_deg)))))
        # Plane tolerance follows the object size; this catches the second
        # triangle of a quad while avoiding the opposite face of a thin box.
        b = _bounds(vertices)
        scene_size = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0)
        plane_tol = max(scene_size * 1e-5, 1e-5)
        selected_vertex_ids: set[int] = set()
        for face_id, tri in enumerate(triangles):
            n = _triangle_normal(mesh, face_id)
            c = _triangle_centroid(mesh, face_id)
            if n is None or c is None:
                continue
            same_direction = abs(_dot(n, normal)) >= cos_limit
            same_plane = abs(_dot(_sub(c, seed_center), normal)) <= plane_tol
            if same_direction and same_plane:
                selected_vertex_ids.update(int(i) for i in tri)
        if not selected_vertex_ids:
            return []
        return [(_dot(_sub(vertices[i], origin), u_axis), _dot(_sub(vertices[i], origin), v_axis)) for i in sorted(selected_vertex_ids)]
    except Exception:
        return []


def _selected_face_ids_for_anchor(
    mesh: WorkMesh,
    *,
    seed_face_index: int | None,
    normal: Vec3,
    coverage_angle_deg: float,
) -> list[int]:
    """Return triangle ids covered by a face-anchored projection.

    A VTK texture is actor-wide: if we attach it to the whole mesh, even vertices
    outside the intended area still receive sampled/clamped texels.  For an
    anchored TEX click we therefore build a small decal mesh containing only the
    coplanar face group around the picked triangle.  Coverage is used as an
    angular filter inside that plane; the opposite face of a box is never selected.
    """

    if seed_face_index is None:
        return []
    try:
        vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
        triangles = list(getattr(mesh, "triangles", []) or [])
        seed_id = int(seed_face_index)
        if not (0 <= seed_id < len(triangles)):
            return []
        seed_center = _triangle_centroid(mesh, seed_id)
        if seed_center is None:
            return []
        n0 = _unit(normal, fallback=_triangle_normal(mesh, seed_id) or (0.0, 0.0, 1.0))
        # Coverage=0 should still catch the other triangle of the same quad even
        # with tiny floating point noise.  The tolerance is intentionally strict:
        # a cube side at 90° or the rear face at 180° must not leak into the decal.
        coverage = max(0.0, min(180.0, float(coverage_angle_deg)))
        cos_limit = math.cos(math.radians(coverage)) - 1e-9
        b = _bounds(vertices)
        scene_size = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0)
        plane_tol = max(scene_size * 1e-5, 1e-5)
        face_ids: list[int] = []
        for face_id, _tri in enumerate(triangles):
            n = _triangle_normal(mesh, face_id)
            c = _triangle_centroid(mesh, face_id)
            if n is None or c is None:
                continue
            n_oriented = _oriented_face_normal(mesh, face_id, n)
            same_direction = _dot(n_oriented, n0) >= cos_limit
            same_plane = abs(_dot(_sub(c, seed_center), n0)) <= plane_tol
            if same_direction and same_plane:
                face_ids.append(int(face_id))
        if seed_id not in face_ids:
            face_ids.append(seed_id)
        return sorted(set(face_ids))
    except Exception:
        return []


def _texture_anchor_frame_for_mesh(mesh: WorkMesh, params: TextureProjectionParams) -> tuple[Vec3, Vec3, Vec3, Vec3, float, float] | None:
    """Return the editable TEX frame for a face-anchored projection.

    Decal placement and attached-to-mesh placement must expose the same gizmo
    frame.  Otherwise the TEX handles disappear as soon as the texture is merged
    into the source mesh.  The frame is stored as dynamic metadata on the mesh so
    the controller can draw and drag the same rotation/scale/move gizmo for both
    modes.
    """

    if params.seed_face_index is None:
        return None
    try:
        vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
        triangles = list(getattr(mesh, "triangles", []) or [])
        if not vertices or not triangles:
            return None
        raw_normal = params.projection_normal or _triangle_normal(mesh, params.seed_face_index) or (0.0, 0.0, 1.0)
        normal = _oriented_face_normal(mesh, params.seed_face_index, raw_normal)
        normal, u_axis, v_axis = _stable_planar_axes(mesh, face_index=params.seed_face_index, normal=normal)
        normal = _oriented_face_normal(mesh, params.seed_face_index, normal)
        origin = tuple(float(x) for x in (params.projection_origin or _triangle_centroid(mesh, params.seed_face_index) or (0.0, 0.0, 0.0)))
        face_ids = _selected_face_ids_for_anchor(
            mesh,
            seed_face_index=params.seed_face_index,
            normal=normal,
            coverage_angle_deg=params.coverage_angle_deg,
        )
        all_coords: list[tuple[float, float]] = []
        for face_id in face_ids or [int(params.seed_face_index)]:
            if not (0 <= int(face_id) < len(triangles)):
                continue
            for raw_i in triangles[int(face_id)]:
                p = vertices[int(raw_i)]
                rel = _sub(p, origin)
                all_coords.append((_dot(rel, u_axis), _dot(rel, v_axis)))
        if not all_coords:
            return (origin, normal, u_axis, v_axis, 1.0, 1.0)
        us = [c[0] for c in all_coords]
        vs = [c[1] for c in all_coords]
        span_u = max(max(us) - min(us), 1e-9)
        span_v = max(max(vs) - min(vs), 1e-9)
        aspect = _image_aspect(params.image_width, params.image_height)
        if bool(params.preserve_aspect) and aspect:
            tile_w, tile_h = _fit_aspect_tile(span_u, span_v, float(aspect), preserve_aspect=True)
        else:
            tile_w = span_u
            tile_h = span_v
        return (origin, normal, u_axis, v_axis, float(tile_w), float(tile_h))
    except Exception:
        return None


def _store_texture_edit_frame(out: WorkMesh, params: TextureProjectionParams) -> None:
    frame = _texture_anchor_frame_for_mesh(out, params)
    if frame is None:
        return
    origin, normal, u_axis, v_axis, tile_w, tile_h = frame
    # Historical names are intentionally reused: the TEX gizmo controller already
    # knows how to read them from decal meshes.  Attached textures now expose the
    # same contract, but without setting ``is_texture_decal``.
    try:
        setattr(out, "texture_decal_origin", origin)
        setattr(out, "texture_decal_normal", normal)
        setattr(out, "texture_decal_u_axis", u_axis)
        setattr(out, "texture_decal_v_axis", v_axis)
        setattr(out, "texture_decal_tile_width", float(tile_w))
        setattr(out, "texture_decal_tile_height", float(tile_h))
        setattr(out, "texture_decal_stretch_u", float(getattr(params, "stretch_u", 1.0)))
        setattr(out, "texture_decal_stretch_v", float(getattr(params, "stretch_v", 1.0)))
        setattr(out, "texture_attached_to_mesh", True)
        setattr(out, "texture_attached_source_face", int(params.seed_face_index))
    except Exception:
        pass
