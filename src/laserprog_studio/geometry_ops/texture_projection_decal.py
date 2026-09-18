# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from pathlib import Path

from laserprog_studio.domain.work_model import WorkMesh

from ..domain.material import MeshMaterial, TextureProjection
from .texture_projection_faces import _oriented_face_normal, _selected_face_ids_for_anchor, _stable_planar_axes, _triangle_centroid, _triangle_normal
from .texture_projection_types import TextureProjectionParams
from .texture_projection_vector import _bounds, _dot, _fit_aspect_tile, _image_aspect, _normalize_rotation_deg, _sub, _uv_from_plane_coords

def _texture_projection_record(out: WorkMesh, params: TextureProjectionParams) -> TextureProjection:
    return TextureProjection(
        texture_id=str(params.texture_id),
        texture_path=str(Path(params.texture_path).expanduser()),
        target_mesh_name=str(getattr(out, "name", "")) or None,
        seed_face_index=params.seed_face_index,
        projection_mode=params.projection_mode if params.projection_mode in {"planar", "box", "cylindrical", "spherical"} else "planar",
        coverage_angle_deg=float(params.coverage_angle_deg),
        scale=max(float(params.scale), 1e-6),
        stretch_u=max(float(getattr(params, "stretch_u", 1.0)), 1e-6),
        stretch_v=max(float(getattr(params, "stretch_v", 1.0)), 1e-6),
        rotation_deg=_normalize_rotation_deg(float(params.rotation_deg)),
        offset_u=float(params.offset_u),
        offset_v=float(params.offset_v),
        repeat=bool(params.repeat),
        engraving_layer="cut" if params.usage == "cut" else ("engrave" if params.usage == "engrave" else "ignore"),
        placement="mesh" if bool(getattr(params, "attach_to_mesh", False)) else "decal",
    )


def _copy_material_for_texture(mesh: WorkMesh, params: TextureProjectionParams) -> MeshMaterial:
    material = getattr(mesh, "material", None)
    if material is None or isinstance(material, dict):
        material = MeshMaterial(name="Projected texture", base_color="#FFFFFF")
    else:
        material = copy.deepcopy(material)
        try:
            material.base_color = "#FFFFFF"
        except Exception:
            pass
    material.texture_id = str(params.texture_id)
    return material




def _texture_border_colors_for_source(mesh: WorkMesh) -> tuple[str, str]:
    """Return the colour that existed before a texture was attached.

    Face-attached textures are rendered through one VTK actor texture.  Faces that
    are not covered by the picked projection therefore sample an opaque fallback
    texel.  That fallback must be the model colour captured *before* the texture
    material turns the actor white; otherwise a second preview/apply can make the
    untouched faces white or transparent.
    """

    saved_solid = (
        getattr(mesh, "texture_pre_projection_role_color", None)
        or getattr(mesh, "texture_saved_role_color", None)
        or getattr(mesh, "texture_border_role_color", None)
    )
    solid = str(saved_solid or getattr(mesh, "color", "#B8B8B8") or "#B8B8B8")
    saved_material = (
        getattr(mesh, "texture_pre_projection_material_color", None)
        or getattr(mesh, "texture_saved_material_color", None)
        or getattr(mesh, "texture_border_material_color", None)
    )
    if saved_material:
        mat = str(saved_material)
    else:
        material = getattr(mesh, "material", None)
        if isinstance(material, dict):
            mat = str(material.get("base_color") or solid or "#B8B8B8")
        else:
            mat = str(getattr(material, "base_color", solid) or solid or "#B8B8B8")
    return solid, mat


def _store_texture_border_colors(mesh: WorkMesh, source: WorkMesh) -> None:
    """Persist the pre-texture colours used by uncovered attached faces."""

    try:
        solid, material = _texture_border_colors_for_source(source)
        # Historical names used by the renderer.
        setattr(mesh, "texture_border_color", solid)
        setattr(mesh, "texture_border_role_color", solid)
        setattr(mesh, "texture_border_material_color", material)
        # Explicit contract: this is the colour captured before texture material
        # styling.  Keep both names for old project compatibility and readability.
        setattr(mesh, "texture_pre_projection_color", solid)
        setattr(mesh, "texture_pre_projection_role_color", solid)
        setattr(mesh, "texture_pre_projection_material_color", material)
        setattr(mesh, "texture_saved_color", solid)
        setattr(mesh, "texture_saved_role_color", solid)
        setattr(mesh, "texture_saved_material_color", material)
    except Exception:
        pass


def _make_anchor_texture_decal(mesh: WorkMesh, params: TextureProjectionParams) -> WorkMesh | None:
    """Build a separate textured face decal for a clicked face.

    This fixes two important behaviours at once:
    - coverage now really limits the affected faces, because the actor contains
      only those triangles;
    - the rear/opposite side of a cube cannot receive the same texture by UV
      clamping, because it is not part of the decal mesh.
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
        if not face_ids:
            return None

        # Size the texture tile from the selected face group, but center it on the
        # exact click point/projection origin.  That gives the expected “click here
        # = texture center here” behaviour while preserving the original ratio.
        all_coords: list[tuple[float, float]] = []
        for face_id in face_ids:
            for raw_i in triangles[int(face_id)]:
                p = vertices[int(raw_i)]
                rel = _sub(p, origin)
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
            tile_w = span_u
            tile_h = span_v

        b = _bounds(vertices)
        scene_size = max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0)
        # A small visual-only lift prevents z-fighting between the decal panel and
        # the source mesh.  The previous 1e-5 lift was still too close on many
        # VTK/OpenGL depth buffers, especially when the camera is oblique.
        lift = max(scene_size * 1e-4, 0.01)
        decal_vertices: list[tuple[float, float, float]] = []
        decal_uvs: list[tuple[float, float]] = []
        decal_tris: list[tuple[int, int, int]] = []
        index_map: dict[int, int] = {}

        for face_id in face_ids:
            new_tri: list[int] = []
            for raw_i in triangles[int(face_id)]:
                src_i = int(raw_i)
                dst_i = index_map.get(src_i)
                if dst_i is None:
                    p = vertices[src_i]
                    p_lift = (
                        float(p[0]) + normal[0] * lift,
                        float(p[1]) + normal[1] * lift,
                        float(p[2]) + normal[2] * lift,
                    )
                    rel = _sub(p, origin)
                    uv = _uv_from_plane_coords(
                        _dot(rel, u_axis),
                        _dot(rel, v_axis),
                        tile_w=tile_w,
                        tile_h=tile_h,
                        scale=params.scale,
                        rotation_deg=params.rotation_deg,
                        offset_u=params.offset_u,
                        offset_v=params.offset_v,
                        stretch_u=float(getattr(params, "stretch_u", 1.0)),
                        stretch_v=float(getattr(params, "stretch_v", 1.0)),
                    )
                    dst_i = len(decal_vertices)
                    index_map[src_i] = dst_i
                    decal_vertices.append(p_lift)
                    decal_uvs.append(uv)
                new_tri.append(dst_i)
            if len(new_tri) == 3:
                decal_tris.append((new_tri[0], new_tri[1], new_tri[2]))

        if not decal_vertices or not decal_tris:
            return None
        source_name = str(getattr(mesh, "name", "mesh") or "mesh")
        decal = WorkMesh(
            name=f"{source_name}_texture_decal",
            vertices=decal_vertices,
            triangles=decal_tris,
            color="#FFFFFF",
        )
        decal.uvs = decal_uvs
        decal.texture_projections = [_texture_projection_record(decal, params)]
        decal.material = _copy_material_for_texture(mesh, params)
        _store_texture_border_colors(decal, mesh)
        try:
            from ..domain.material import EngravingSettings

            decal.engraving = EngravingSettings(role="ignore", layer=("cut" if params.usage == "cut" else ("engrave" if params.usage == "engrave" else "ignore")), texture_usage=(params.usage if params.usage in {"visual", "cut", "engrave"} else "visual"), enabled=True)
        except Exception:
            pass
        # Dynamic metadata keeps the decal payload readable for
        # project files created before the WorkMesh domain model was expanded.
        setattr(decal, "is_texture_decal", True)
        setattr(decal, "texture_decal_for", source_name)
        setattr(decal, "texture_decal_source_face", int(params.seed_face_index))
        setattr(decal, "texture_decal_origin", origin)
        setattr(decal, "texture_decal_normal", normal)
        setattr(decal, "texture_decal_u_axis", u_axis)
        setattr(decal, "texture_decal_v_axis", v_axis)
        setattr(decal, "texture_decal_tile_width", float(tile_w))
        setattr(decal, "texture_decal_tile_height", float(tile_h))
        setattr(decal, "texture_decal_stretch_u", float(getattr(params, "stretch_u", 1.0)))
        setattr(decal, "texture_decal_stretch_v", float(getattr(params, "stretch_v", 1.0)))
        return decal
    except Exception:
        return None


def _is_texture_decal(mesh: WorkMesh) -> bool:
    return bool(getattr(mesh, "is_texture_decal", False))


def _decal_source_name(mesh: WorkMesh) -> str | None:
    try:
        value = getattr(mesh, "texture_decal_for", None)
        return str(value) if value else None
    except Exception:
        return None


def _clear_mesh_texture_metadata(mesh: WorkMesh) -> WorkMesh:
    """Return a copy of a real mesh with TEX material/UV metadata removed.

    This is intentionally used when switching between *attached* and *decal*
    placement modes. Without it, changing mode can leave an old attached texture
    on the source mesh while also adding a new decal, or keep an obsolete decal
    next to a newly attached texture.
    """

    out = copy.deepcopy(mesh)
    try:
        out.uvs = None
    except Exception:
        pass
    try:
        out.texture_projections = []
    except Exception:
        pass
    for _name in (
        "texture_decal_origin",
        "texture_decal_normal",
        "texture_decal_u_axis",
        "texture_decal_v_axis",
        "texture_decal_tile_width",
        "texture_decal_tile_height",
        "texture_decal_stretch_u",
        "texture_decal_stretch_v",
        "texture_attached_to_mesh",
        "texture_attached_source_face",
        "texture_border_color",
        "texture_border_role_color",
        "texture_border_material_color",
        "texture_pre_projection_color",
        "texture_pre_projection_role_color",
        "texture_pre_projection_material_color",
        "texture_saved_color",
        "texture_saved_role_color",
        "texture_saved_material_color",
    ):
        try:
            if hasattr(out, _name):
                delattr(out, _name)
        except Exception:
            pass
    try:
        saved_role, saved_material = _texture_border_colors_for_source(mesh)
        if saved_role:
            out.color = str(saved_role)
    except Exception:
        saved_material = None
    try:
        material = getattr(out, "material", None)
        if material is not None and not isinstance(material, dict):
            material = copy.deepcopy(material)
            material.texture_id = None
            if saved_material:
                material.base_color = str(saved_material)
            out.material = material
        elif isinstance(material, dict):
            material = copy.deepcopy(material)
            material.pop("texture_id", None)
            if saved_material:
                material["base_color"] = str(saved_material)
            out.material = material
    except Exception:
        pass
    try:
        engraving = getattr(out, "engraving", None)
        if engraving is not None:
            engraving.texture_usage = "none"
    except Exception:
        pass
    return out
