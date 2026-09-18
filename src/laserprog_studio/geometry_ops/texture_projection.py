# -*- coding: utf-8 -*-
from __future__ import annotations

# Stable aggregate import for the texture projection geometry pipeline.
#
# The implementation is intentionally split across focused modules so future
# texture features can evolve without editing a 900+ line geometry file.  Keep
# importing from this module in older callers; new geometry code should prefer
# the focused modules below.

from .texture_projection_types import TextureProjectionParams, Vec3
from .texture_projection_vector import (
    _apply_uv_transform,
    _bounds,
    _cross,
    _dot,
    _image_aspect,
    _length,
    _norm,
    _sub,
    _unit,
    _uv_from_plane_coords,
)
from .texture_projection_faces import (
    _coplanar_face_vertex_coords,
    _face_edge_axis,
    _oriented_face_normal,
    _selected_face_ids_for_anchor,
    _stable_planar_axes,
    _store_texture_edit_frame,
    _texture_anchor_frame_for_mesh,
    _triangle_centroid,
    _triangle_normal,
)
from .texture_projection_uv import _uvs_from_projected_coords, compute_projected_uvs
from .texture_projection_decal import (
    _clear_mesh_texture_metadata,
    _copy_material_for_texture,
    _decal_source_name,
    _is_texture_decal,
    _make_anchor_texture_decal,
    _texture_projection_record,
)
from .texture_projection_operations import (
    apply_texture_projection,
    apply_texture_projection_to_mesh,
    clear_texture_projection,
)

__all__ = [
    "TextureProjectionParams",
    "Vec3",
    "apply_texture_projection",
    "apply_texture_projection_to_mesh",
    "clear_texture_projection",
    "compute_projected_uvs",
    "_is_texture_decal",
    "_dot",
    "_sub",
    "_uv_from_plane_coords",
    "_store_texture_edit_frame",
]
