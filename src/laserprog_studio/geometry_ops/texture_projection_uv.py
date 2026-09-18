# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from laserprog_studio.domain.work_model import WorkMesh

from .texture_projection_faces import _coplanar_face_vertex_coords, _stable_planar_axes, _triangle_centroid
from .texture_projection_types import Vec3
from .texture_projection_vector import _apply_uv_transform, _bounds, _dot, _fit_aspect_tile, _image_aspect, _norm, _normalize_rotation_deg, _sub, _uv_from_plane_coords

def _uvs_from_projected_coords(
    coords: list[tuple[float, float]],
    *,
    preserve_aspect: bool,
    image_aspect: float | None,
    scale: float,
    rotation_deg: float,
    offset_u: float,
    offset_v: float,
    stretch_u: float = 1.0,
    stretch_v: float = 1.0,
) -> list[tuple[float, float]]:
    if not coords:
        return []
    us = [float(c[0]) for c in coords]
    vs = [float(c[1]) for c in coords]
    lo_u, hi_u = min(us), max(us)
    lo_v, hi_v = min(vs), max(vs)
    span_u = max(hi_u - lo_u, 1e-9)
    span_v = max(hi_v - lo_v, 1e-9)
    center_u = (lo_u + hi_u) * 0.5
    center_v = (lo_v + hi_v) * 0.5
    aspect = float(image_aspect or 0.0)
    out: list[tuple[float, float]] = []
    if bool(preserve_aspect) and aspect > 0.0:
        # Ratio-preserving projection now starts in fit-inside mode. The image
        # never exceeds the clicked face/object bounds until the user scales or
        # stretches it deliberately.
        tile_w, tile_h = _fit_aspect_tile(span_u, span_v, aspect, preserve_aspect=True)
        for u_raw, v_raw in coords:
            out.append(
                _uv_from_plane_coords(
                    float(u_raw) - center_u,
                    float(v_raw) - center_v,
                    tile_w=tile_w,
                    tile_h=tile_h,
                    scale=scale,
                    rotation_deg=rotation_deg,
                    offset_u=offset_u,
                    offset_v=offset_v,
                    stretch_u=stretch_u,
                    stretch_v=stretch_v,
                )
            )
        return out
    for u_raw, v_raw in coords:
        u = _norm(u_raw, lo_u, hi_u)
        v = _norm(v_raw, lo_v, hi_v)
        out.append(_apply_uv_transform(u, v, scale=scale, rotation_deg=rotation_deg, offset_u=offset_u, offset_v=offset_v, stretch_u=stretch_u, stretch_v=stretch_v))
    return out


def compute_projected_uvs(
    mesh: WorkMesh,
    *,
    projection_mode: str = "planar",
    scale: float = 1.0,
    stretch_u: float = 1.0,
    stretch_v: float = 1.0,
    rotation_deg: float = 0.0,
    offset_u: float = 0.0,
    offset_v: float = 0.0,
    preserve_aspect: bool = False,
    image_width: int | None = None,
    image_height: int | None = None,
    seed_face_index: int | None = None,
    projection_origin: Vec3 | None = None,
    projection_normal: Vec3 | None = None,
    coverage_angle_deg: float = 20.0,
) -> list[tuple[float, float]]:
    """Compute point UVs for a mesh.

    The first implementation normalized U/V independently, which stretched a
    texture to the exact face/object shape.  When image dimensions are provided
    and ``preserve_aspect`` is true, U/V now use the image ratio in model space.
    """

    vertices = [(float(x), float(y), float(z)) for x, y, z in getattr(mesh, "vertices", [])]
    b = _bounds(vertices)
    cx = (b[0] + b[1]) * 0.5
    cy = (b[2] + b[3]) * 0.5
    cz = (b[4] + b[5]) * 0.5
    mode = str(projection_mode or "planar").lower()
    aspect = _image_aspect(image_width, image_height)
    rotation_deg = _normalize_rotation_deg(rotation_deg)
    coords: list[tuple[float, float]] = []

    if mode == "planar":
        normal, u_axis, v_axis = _stable_planar_axes(mesh, face_index=seed_face_index, normal=projection_normal)
        if projection_origin is not None:
            origin = tuple(float(x) for x in projection_origin)
        else:
            origin = _triangle_centroid(mesh, seed_face_index) or (cx, cy, cz)
        # First compute target coords for the picked coplanar face group so the
        # ratio fitter sizes the image against the face actually aimed at.
        target_coords = _coplanar_face_vertex_coords(
            mesh,
            seed_face_index=seed_face_index,
            normal=normal,
            u_axis=u_axis,
            v_axis=v_axis,
            origin=origin,
            coverage_angle_deg=coverage_angle_deg,
        )
        coords = [(_dot(_sub(p, origin), u_axis), _dot(_sub(p, origin), v_axis)) for p in vertices]
        if target_coords and bool(preserve_aspect) and aspect:
            # Compute UVs from the target face bounds, then map all vertices with
            # the same center/tile dimensions.  This avoids full-object stretching.
            tu = [c[0] for c in target_coords]
            tv = [c[1] for c in target_coords]
            ctu, ctv = (min(tu) + max(tu)) * 0.5, (min(tv) + max(tv)) * 0.5
            span_u = max(max(tu) - min(tu), 1e-9)
            span_v = max(max(tv) - min(tv), 1e-9)
            tile_w, tile_h = _fit_aspect_tile(span_u, span_v, float(aspect), preserve_aspect=True)
            # If the user clicked/dragged a specific projection origin, that
            # point is the texture centre.  The previous code always subtracted
            # the target-face bounding-box centre (ctu/ctv). That silently
            # cancelled any origin movement in attached-to-mesh mode: dragging
            # the blue centre point changed ``projection_origin`` but the UVs
            # were immediately re-centred on the face bounds, so the texture did
            # not move.  When no explicit origin exists, keep the old auto-center
            # behaviour for saved projects without explicit origins.
            center_u = 0.0 if projection_origin is not None else ctu
            center_v = 0.0 if projection_origin is not None else ctv
            out: list[tuple[float, float]] = []
            for u_raw, v_raw in coords:
                out.append(
                    _uv_from_plane_coords(
                        float(u_raw) - center_u,
                        float(v_raw) - center_v,
                        tile_w=tile_w,
                        tile_h=tile_h,
                        scale=scale,
                        rotation_deg=rotation_deg,
                        offset_u=offset_u,
                        offset_v=offset_v,
                        stretch_u=stretch_u,
                        stretch_v=stretch_v,
                    )
                )
            return out
    elif mode == "cylindrical":
        for x, y, z in vertices:
            coords.append(((math.atan2(y - cy, x - cx) + math.pi) / (2.0 * math.pi), _norm(z, b[4], b[5])))
        # Cylindrical/spherical UVs are already dimensionless angular mappings;
        # only the vertical image ratio can be respected in a useful way, so keep
        # old behaviour unless the user deliberately uses scale/rotation/offset.
        return [_apply_uv_transform(u, v, scale=scale, rotation_deg=rotation_deg, offset_u=offset_u, offset_v=offset_v, stretch_u=stretch_u, stretch_v=stretch_v) for u, v in coords]
    elif mode == "spherical":
        for x, y, z in vertices:
            dx, dy, dz = x - cx, y - cy, z - cz
            radius = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            u = (math.atan2(dy, dx) + math.pi) / (2.0 * math.pi)
            v = 0.5 - math.asin(max(-1.0, min(1.0, dz / radius))) / math.pi
            coords.append((u, v))
        return [_apply_uv_transform(u, v, scale=scale, rotation_deg=rotation_deg, offset_u=offset_u, offset_v=offset_v, stretch_u=stretch_u, stretch_v=stretch_v) for u, v in coords]
    elif mode == "box":
        # Point-based box fallback: choose the two largest object dimensions.
        sx, sy, sz = b[1] - b[0], b[3] - b[2], b[5] - b[4]
        dims = sorted(((sx, "x"), (sy, "y"), (sz, "z")), reverse=True)
        axes = {dims[0][1], dims[1][1]}
        for x, y, z in vertices:
            if axes == {"x", "z"}:
                coords.append((float(x), float(z)))
            elif axes == {"y", "z"}:
                coords.append((float(y), float(z)))
            else:
                coords.append((float(x), float(y)))
    else:  # historical Planar XY fallback.
        coords = [(float(x), float(y)) for x, y, _z in vertices]

    return _uvs_from_projected_coords(
        coords,
        preserve_aspect=bool(preserve_aspect),
        image_aspect=aspect,
        scale=scale,
        rotation_deg=rotation_deg,
        offset_u=offset_u,
        offset_v=offset_v,
        stretch_u=stretch_u,
        stretch_v=stretch_v,
    )
