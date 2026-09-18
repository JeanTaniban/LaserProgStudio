# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import replace

from laserprog_studio.domain.work_model import WorkMesh

from .texture_projection_decal import (
    _clear_mesh_texture_metadata,
    _copy_material_for_texture,
    _decal_source_name,
    _is_texture_decal,
    _make_anchor_texture_decal,
    _store_texture_border_colors,
    _texture_projection_record,
)
from .texture_projection_faces import (
    _oriented_face_normal,
    _selected_face_ids_for_anchor,
    _stable_planar_axes,
    _store_texture_edit_frame,
    _triangle_centroid,
    _triangle_normal,
)
from .texture_projection_types import TextureProjectionParams
from .texture_projection_uv import compute_projected_uvs
from .texture_projection_vector import _bounds, _dot, _fit_aspect_tile, _image_aspect, _sub, _uv_from_plane_coords


def _copy_domain_metadata(dst: WorkMesh, src: WorkMesh) -> None:
    """Preserve user-facing mesh metadata after topology-only UV splitting."""

    for name in (
        "color",
        "engraving",
        "metadata",
        "object_id",
        "source_id",
        "transform",
        "role",
    ):
        try:
            if hasattr(src, name):
                setattr(dst, name, copy.deepcopy(getattr(src, name)))
        except Exception:
            pass


def _border_uv() -> tuple[float, float]:
    # Non-repeated attached textures are loaded with an opaque neutral padding
    # border.  Do not rely on negative UV + VTK ClampToBorder here: several
    # PyVista/VTK combinations expose that border as transparent alpha, which
    # makes every non-covered face of the mesh look invisible.  Sampling the
    # padded texture's real edge pixel keeps the untextured faces opaque while
    # still avoiding bitmap leakage.
    return (0.0, 0.0)


def _source_uv_inside_padded_texture(uv: tuple[float, float], params: TextureProjectionParams, *, border_px: int = 2) -> tuple[float, float]:
    """Map normal source UVs into the real image area of the padded texture.

    The renderer adds an opaque border around non-repeated attached textures so
    uncovered faces can sample the saved model colour.  Covered faces must then
    be shifted inward; otherwise UV 0/1 also touches the fallback border and a
    texture edge can show the model colour instead of the bitmap.
    """

    try:
        width = max(float(getattr(params, "image_width", None) or 0.0), 1.0)
        height = max(float(getattr(params, "image_height", None) or 0.0), 1.0)
        border = max(float(border_px), 1.0)
        return (
            (border + float(uv[0]) * width) / (width + 2.0 * border),
            (border + float(uv[1]) * height) / (height + 2.0 * border),
        )
    except Exception:
        return uv


def compute_anchor_attached_coverage_uvs(
    mesh: WorkMesh,
    params: TextureProjectionParams,
    *,
    projection_origin: tuple[float, float, float] | None = None,
    scale: float | None = None,
    rotation_deg: float | None = None,
    offset_u: float | None = None,
    offset_v: float | None = None,
    stretch_u: float | None = None,
    stretch_v: float | None = None,
) -> list[tuple[float, float]] | None:
    """Compute coverage-masked UVs for an attached face projection.

    This is the live-update equivalent of the topology split done by
    ``_apply_anchor_texture_to_mesh_with_coverage``.  Covered faces receive real
    UVs; faces outside Coverage are sent to the padded border so the bitmap does
    not leak onto the rest of the object.
    """

    if params.seed_face_index is None:
        return None
    vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
    triangles = [tuple(int(i) for i in tri) for tri in (getattr(mesh, "triangles", []) or [])]
    if not vertices or not triangles:
        return None

    raw_normal = params.projection_normal or _triangle_normal(mesh, params.seed_face_index) or (0.0, 0.0, 1.0)
    normal = _oriented_face_normal(mesh, params.seed_face_index, raw_normal)
    normal, u_axis, v_axis = _stable_planar_axes(mesh, face_index=params.seed_face_index, normal=normal)
    normal = _oriented_face_normal(mesh, params.seed_face_index, normal)
    origin = tuple(
        float(x)
        for x in (
            projection_origin
            or params.projection_origin
            or _triangle_centroid(mesh, params.seed_face_index)
            or (0.0, 0.0, 0.0)
        )
    )
    covered_faces = set(
        _selected_face_ids_for_anchor(
            mesh,
            seed_face_index=params.seed_face_index,
            normal=normal,
            coverage_angle_deg=params.coverage_angle_deg,
        )
    )
    if not covered_faces:
        covered_faces = {int(params.seed_face_index)}

    all_coords: list[tuple[float, float]] = []
    for face_id in sorted(covered_faces):
        if 0 <= int(face_id) < len(triangles):
            for src_i in triangles[int(face_id)]:
                rel = _sub(vertices[int(src_i)], origin)
                all_coords.append((_dot(rel, u_axis), _dot(rel, v_axis)))
    if not all_coords:
        return None
    us = [c[0] for c in all_coords]
    vs = [c[1] for c in all_coords]
    span_u = max(max(us) - min(us), 1e-9)
    span_v = max(max(vs) - min(vs), 1e-9)
    aspect = _image_aspect(params.image_width, params.image_height)
    if bool(params.preserve_aspect) and aspect:
        tile_w, tile_h = _fit_aspect_tile(span_u, span_v, float(aspect), preserve_aspect=True)
    else:
        tile_w, tile_h = span_u, span_v

    real_scale = float(scale if scale is not None else params.scale)
    real_rotation = float(rotation_deg if rotation_deg is not None else params.rotation_deg)
    real_offset_u = float(offset_u if offset_u is not None else params.offset_u)
    real_offset_v = float(offset_v if offset_v is not None else params.offset_v)
    real_stretch_u = float(stretch_u if stretch_u is not None else getattr(params, "stretch_u", 1.0))
    real_stretch_v = float(stretch_v if stretch_v is not None else getattr(params, "stretch_v", 1.0))

    uvs = [_border_uv() for _ in vertices]
    for face_id, tri in enumerate(triangles):
        if int(face_id) not in covered_faces:
            continue
        for src_i in tri:
            p = vertices[int(src_i)]
            rel = _sub(p, origin)
            uv = _uv_from_plane_coords(
                _dot(rel, u_axis),
                _dot(rel, v_axis),
                tile_w=tile_w,
                tile_h=tile_h,
                scale=real_scale,
                rotation_deg=real_rotation,
                offset_u=real_offset_u,
                offset_v=real_offset_v,
                stretch_u=real_stretch_u,
                stretch_v=real_stretch_v,
            )
            uvs[int(src_i)] = _source_uv_inside_padded_texture(uv, params)
    return uvs


def _apply_anchor_texture_to_mesh_with_coverage(mesh: WorkMesh, params: TextureProjectionParams) -> WorkMesh:
    """Attach a face-anchored texture to the real mesh, not as a decal.

    VTK stores UVs per point.  A cube/box shares vertices between the clicked
    face and neighbouring faces, so a face-limited UV assignment cannot be stable
    unless those points are split per triangle.  This helper keeps one mesh actor
    (the user's requested *Attach to mesh* behaviour), duplicates only the point
    records needed for independent UVs, and sends non-covered faces to the neutral
    border colour.  The unchecked mode still creates a lifted decal patch.
    """

    if params.seed_face_index is None:
        return apply_texture_projection_to_mesh(mesh, params)
    vertices = [tuple(float(x) for x in v) for v in getattr(mesh, "vertices", [])]
    triangles = [tuple(int(i) for i in tri) for tri in (getattr(mesh, "triangles", []) or [])]
    if not vertices or not triangles:
        return apply_texture_projection_to_mesh(mesh, params)

    raw_normal = params.projection_normal or _triangle_normal(mesh, params.seed_face_index) or (0.0, 0.0, 1.0)
    normal = _oriented_face_normal(mesh, params.seed_face_index, raw_normal)
    normal, u_axis, v_axis = _stable_planar_axes(mesh, face_index=params.seed_face_index, normal=normal)
    normal = _oriented_face_normal(mesh, params.seed_face_index, normal)
    origin = tuple(float(x) for x in (params.projection_origin or _triangle_centroid(mesh, params.seed_face_index) or (0.0, 0.0, 0.0)))
    covered_faces = set(
        _selected_face_ids_for_anchor(
            mesh,
            seed_face_index=params.seed_face_index,
            normal=normal,
            coverage_angle_deg=params.coverage_angle_deg,
        )
    )
    if not covered_faces:
        covered_faces = {int(params.seed_face_index)}
    has_uncovered_faces = len(covered_faces) < len(triangles)
    effective_params = replace(params, repeat=False) if has_uncovered_faces and bool(params.repeat) else params

    all_coords: list[tuple[float, float]] = []
    for face_id in sorted(covered_faces):
        if 0 <= int(face_id) < len(triangles):
            for src_i in triangles[int(face_id)]:
                rel = _sub(vertices[int(src_i)], origin)
                all_coords.append((_dot(rel, u_axis), _dot(rel, v_axis)))
    if not all_coords:
        return apply_texture_projection_to_mesh(mesh, params)
    us = [c[0] for c in all_coords]
    vs = [c[1] for c in all_coords]
    span_u = max(max(us) - min(us), 1e-9)
    span_v = max(max(vs) - min(vs), 1e-9)
    aspect = _image_aspect(params.image_width, params.image_height)
    if bool(params.preserve_aspect) and aspect:
        tile_w, tile_h = _fit_aspect_tile(span_u, span_v, float(aspect), preserve_aspect=True)
    else:
        tile_w, tile_h = span_u, span_v

    out_vertices: list[tuple[float, float, float]] = []
    out_uvs: list[tuple[float, float]] = []
    out_tris: list[tuple[int, int, int]] = []
    # Keep shared vertices on the same UV only when the covered/uncovered state is
    # identical.  This prevents texture interpolation from bleeding over an edge
    # but still avoids needless duplication inside the covered patch.
    point_key_to_index: dict[tuple[int, bool], int] = {}
    for face_id, tri in enumerate(triangles):
        covered = int(face_id) in covered_faces
        new_tri: list[int] = []
        for src_i in tri:
            key = (int(src_i), bool(covered))
            dst_i = point_key_to_index.get(key)
            if dst_i is None:
                p = vertices[int(src_i)]
                if covered:
                    rel = _sub(p, origin)
                    uv = _uv_from_plane_coords(
                        _dot(rel, u_axis),
                        _dot(rel, v_axis),
                        tile_w=tile_w,
                        tile_h=tile_h,
                        scale=float(params.scale),
                        rotation_deg=float(params.rotation_deg),
                        offset_u=float(params.offset_u),
                        offset_v=float(params.offset_v),
                        stretch_u=float(getattr(params, "stretch_u", 1.0)),
                        stretch_v=float(getattr(params, "stretch_v", 1.0)),
                    )
                    uv = _source_uv_inside_padded_texture(uv, effective_params)
                else:
                    uv = _border_uv()
                dst_i = len(out_vertices)
                point_key_to_index[key] = dst_i
                out_vertices.append(p)
                out_uvs.append(uv)
            new_tri.append(dst_i)
        if len(new_tri) == 3:
            out_tris.append((new_tri[0], new_tri[1], new_tri[2]))

    out = WorkMesh(
        name=str(getattr(mesh, "name", "mesh") or "mesh"),
        vertices=out_vertices,
        triangles=out_tris,
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
    )
    _copy_domain_metadata(out, mesh)
    out.uvs = out_uvs
    out.texture_projections = [_texture_projection_record(out, effective_params)]
    out.material = _copy_material_for_texture(mesh, effective_params)
    _store_texture_border_colors(out, mesh)
    _store_texture_edit_frame(out, effective_params)
    return out


def apply_texture_projection_to_mesh(mesh: WorkMesh, params: TextureProjectionParams) -> WorkMesh:
    """Return a copy of ``mesh`` with UVs + texture metadata attached."""

    out = copy.deepcopy(mesh)
    out.uvs = compute_projected_uvs(
        out,
        projection_mode=params.projection_mode,
        scale=params.scale,
        stretch_u=float(getattr(params, "stretch_u", 1.0)),
        stretch_v=float(getattr(params, "stretch_v", 1.0)),
        rotation_deg=params.rotation_deg,
        offset_u=params.offset_u,
        offset_v=params.offset_v,
        preserve_aspect=bool(params.preserve_aspect),
        image_width=params.image_width,
        image_height=params.image_height,
        seed_face_index=params.seed_face_index,
        projection_origin=params.projection_origin,
        projection_normal=params.projection_normal,
        coverage_angle_deg=params.coverage_angle_deg,
    )
    projection = _texture_projection_record(out, params)
    out.texture_projections = [projection]
    _store_texture_border_colors(out, mesh)
    out.material = _copy_material_for_texture(out, params)
    _store_texture_edit_frame(out, params)
    try:
        engraving = getattr(out, "engraving", None)
        if engraving is not None:
            engraving.texture_usage = params.usage if params.usage in {"visual", "cut", "engrave", "none"} else "visual"
            engraving.layer = "cut" if params.usage == "cut" else ("engrave" if params.usage == "engrave" else "ignore")
    except Exception:
        pass
    return out


def apply_texture_projection(
    meshes: list[WorkMesh],
    indices: list[int],
    params: TextureProjectionParams,
) -> list[WorkMesh]:
    out = [copy.deepcopy(m) for m in meshes]
    selected = sorted({int(i) for i in indices})
    attach_to_mesh = bool(getattr(params, "attach_to_mesh", False))

    # Resolve selected real source names before removing old decal actors.  This
    # makes the placement mode switch deterministic:
    #   mesh -> decal: source mesh is cleaned, then a fresh decal is created.
    #   decal -> mesh: old decal is removed, source mesh receives the texture.
    source_names = {
        str(getattr(out[i], "name", ""))
        for i in selected
        if 0 <= i < len(out) and not _is_texture_decal(out[i])
    }
    if source_names:
        out = [m for m in out if not (_is_texture_decal(m) and _decal_source_name(m) in source_names)]

    if params.seed_face_index is not None and not attach_to_mesh:
        decals: list[WorkMesh] = []
        for idx in selected:
            if 0 <= idx < len(out):
                base_mesh = out[idx]
                if _is_texture_decal(base_mesh):
                    continue
                clean_base = _clear_mesh_texture_metadata(base_mesh)
                out[idx] = clean_base
                decal = _make_anchor_texture_decal(clean_base, params)
                if decal is not None:
                    decals.append(decal)
        if decals:
            out.extend(decals)
            return out

    for idx in selected:
        if 0 <= idx < len(out):
            if _is_texture_decal(out[idx]):
                continue
            clean_base = _clear_mesh_texture_metadata(out[idx])
            if params.seed_face_index is not None and attach_to_mesh:
                out[idx] = _apply_anchor_texture_to_mesh_with_coverage(clean_base, params)
            else:
                out[idx] = apply_texture_projection_to_mesh(clean_base, params)
    return out


def clear_texture_projection(meshes: list[WorkMesh], indices: list[int]) -> list[WorkMesh]:
    out = [copy.deepcopy(m) for m in meshes]
    selected = sorted({int(i) for i in indices})
    source_names: set[str] = set()
    selected_decal_indices: set[int] = set()
    for idx in selected:
        if 0 <= idx < len(out):
            if _is_texture_decal(out[idx]):
                selected_decal_indices.add(idx)
                src = _decal_source_name(out[idx])
                if src:
                    source_names.add(src)
            else:
                source_names.add(str(getattr(out[idx], "name", "")))
                out[idx] = _clear_mesh_texture_metadata(out[idx])
    cleaned: list[WorkMesh] = []
    for idx, mesh in enumerate(out):
        remove = idx in selected_decal_indices
        if _is_texture_decal(mesh):
            src = _decal_source_name(mesh)
            if src and src in source_names:
                remove = True
        if not remove:
            cleaned.append(mesh)
    return cleaned
