from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401
from PIL import Image

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams, apply_texture_projection
from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh
from laserprog_studio.boolean_ops import is_closed_triangle_mesh


def _plate() -> WorkMesh:
    return WorkMesh(
        name="plate",
        vertices=[(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#B8B8B8",
    )


def _tex(tmp_path: Path) -> Path:
    path = tmp_path / "tex.png"
    Image.new("RGB", (4, 4), "black").save(path)
    return path


def test_switch_from_decal_to_attached_removes_old_decal(tmp_path: Path) -> None:
    path = _tex(tmp_path)
    decal_params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=False,
    )
    meshes = apply_texture_projection([_plate()], [0], decal_params)
    assert len(meshes) == 2
    assert bool(getattr(meshes[1], "is_texture_decal", False))

    attached_params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=True,
    )
    meshes = apply_texture_projection(meshes, [0], attached_params)
    assert len(meshes) == 1
    assert not bool(getattr(meshes[0], "is_texture_decal", False))
    assert getattr(meshes[0], "uvs", None) is not None
    assert meshes[0].texture_projections[0].placement == "mesh"
    assert bool(getattr(meshes[0], "texture_attached_to_mesh", False))


def test_switch_from_attached_to_decal_clears_source_mesh_texture(tmp_path: Path) -> None:
    path = _tex(tmp_path)
    attached_params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=True,
    )
    meshes = apply_texture_projection([_plate()], [0], attached_params)
    assert len(meshes) == 1
    assert getattr(meshes[0], "uvs", None) is not None
    assert not bool(getattr(meshes[0], "is_texture_decal", False))
    assert meshes[0].texture_projections[0].placement == "mesh"

    decal_params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=False,
    )
    meshes = apply_texture_projection(meshes, [0], decal_params)
    assert len(meshes) == 2
    assert getattr(meshes[0], "uvs", None) is None
    assert meshes[0].texture_projections == []
    assert bool(getattr(meshes[1], "is_texture_decal", False))
    assert meshes[1].texture_projections[0].placement == "decal"


def test_repair_report_exposes_extended_backend_field() -> None:
    mesh = WorkMesh(
        name="open_plate",
        vertices=[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
        triangles=[(0, 1, 2), (0, 2, 3), (0, 1, 2)],
        color="#AAA",
    )
    repaired, report = repair_work_mesh(mesh, tolerance_mm=0.001, fill_holes=False, remove_tiny_faces=True)
    assert hasattr(report, "trimesh_repair_used")
    assert report.removed_duplicate_triangles >= 1
    # The result can remain open because this was an open plate, but it must still be valid triangles.
    assert len(repaired.triangles) >= 1
    assert is_closed_triangle_mesh(repaired.vertices, repaired.triangles)[1] >= 0


def test_attached_texture_keeps_edit_gizmo_frame_metadata(tmp_path: Path) -> None:
    path = _tex(tmp_path)
    params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=8,
        image_height=4,
        attach_to_mesh=True,
        preserve_aspect=True,
    )
    meshes = apply_texture_projection([_plate()], [0], params)
    mesh = meshes[0]
    assert mesh.texture_projections[0].placement == "mesh"
    assert not bool(getattr(mesh, "is_texture_decal", False))
    assert getattr(mesh, "texture_attached_to_mesh", False) is True
    assert tuple(round(v, 6) for v in getattr(mesh, "texture_decal_origin")) == (5, 5, 0)
    assert tuple(round(v, 6) for v in getattr(mesh, "texture_decal_normal")) == (0, 0, 1)
    assert getattr(mesh, "texture_decal_u_axis", None) is not None
    assert getattr(mesh, "texture_decal_v_axis", None) is not None
    assert float(getattr(mesh, "texture_decal_tile_width")) > 0
    assert float(getattr(mesh, "texture_decal_tile_height")) > 0


def test_attached_texture_origin_move_changes_uvs(tmp_path: Path) -> None:
    """Regression: Attach-to-mesh TEX centre drag must actually move the UVs."""
    path = _tex(tmp_path)
    base_params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=True,
        preserve_aspect=True,
    )
    moved_params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=path,
        usage="engrave",
        seed_face_index=0,
        projection_origin=(6, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=True,
        preserve_aspect=True,
    )
    mesh_a = apply_texture_projection([_plate()], [0], base_params)[0]
    mesh_b = apply_texture_projection([_plate()], [0], moved_params)[0]
    assert mesh_a.uvs is not None
    assert mesh_b.uvs is not None
    assert mesh_a.uvs != mesh_b.uvs
    # Moving the projection origin +1mm along the face U axis shifts all U samples.
    delta_u = mesh_b.uvs[0][0] - mesh_a.uvs[0][0]
    assert abs(delta_u) > 1e-6
