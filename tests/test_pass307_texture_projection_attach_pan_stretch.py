# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import _path_setup  # noqa: F401
from PIL import Image

from laserprog_studio.domain.material import MeshMaterial
from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams, apply_texture_projection, clear_texture_projection
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool
from laserprog_studio.tooling._texture_projection_constants import HANDLE_STRETCH_U_POS, HANDLE_STRETCH_V_POS
from laserprog_studio.tooling._texture_projection_params import texture_params_from_values
from laserprog_studio.rendering import textures as texture_rendering


def _tex(tmp_path: Path, size: tuple[int, int] = (400, 100)) -> Path:
    path = tmp_path / "tex.png"
    Image.new("RGB", size, "black").save(path)
    return path


def _plate() -> WorkMesh:
    return WorkMesh(
        name="plate",
        vertices=[(0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#B8B8B8",
    )


def test_rotation_is_normalized_and_stretch_is_preserved(tmp_path: Path) -> None:
    params = texture_params_from_values({
        "texture_path": str(_tex(tmp_path)),
        "rotation_deg": 99840.0,
        "stretch_u": 2.5,
        "stretch_v": 0.5,
    })
    assert -180.0 <= params.rotation_deg < 180.0
    assert params.rotation_deg == 120.0
    assert params.stretch_u == 2.5
    assert params.stretch_v == 0.5


def test_anchor_attach_to_mesh_stays_on_real_mesh_with_coverage_mask(tmp_path: Path) -> None:
    params = TextureProjectionParams(
        texture_id="tex_patch",
        texture_path=_tex(tmp_path, (4, 4)),
        seed_face_index=0,
        projection_origin=(10, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=True,
    )
    meshes = apply_texture_projection([_plate()], [0], params)
    assert len(meshes) == 1
    assert not bool(getattr(meshes[0], "is_texture_decal", False))
    assert getattr(meshes[0], "uvs", None) is not None
    assert meshes[0].texture_projections[0].placement == "mesh"
    assert bool(getattr(meshes[0], "texture_attached_to_mesh", False))


def test_anchor_without_attach_creates_visual_decal_patch(tmp_path: Path) -> None:
    params = TextureProjectionParams(
        texture_id="tex_patch",
        texture_path=_tex(tmp_path, (4, 4)),
        seed_face_index=0,
        projection_origin=(10, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=False,
    )
    meshes = apply_texture_projection([_plate()], [0], params)
    assert len(meshes) == 2
    assert getattr(meshes[0], "uvs", None) is None
    assert bool(getattr(meshes[1], "is_texture_decal", False))
    assert meshes[1].texture_projections[0].placement == "decal"


def test_face_click_resets_bad_persisted_transform_and_forces_planar(tmp_path: Path) -> None:
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_plate()], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_values({
        "texture_path": str(_tex(tmp_path)),
        "projection_mode": "spherical",
        "scale": 999.0,
        "stretch_u": 12.0,
        "stretch_v": 7.0,
        "rotation_deg": 99840.0,
        "offset_u": 42.0,
        "offset_v": -42.0,
    }, notify=False)
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10, 5, 0), projection_normal=(0, 0, 1))
    assert ctx.inspector.value("projection_mode") == "planar"
    assert float(ctx.inspector.value("scale")) == 1.0
    assert float(ctx.inspector.value("stretch_u")) == 1.0
    assert float(ctx.inspector.value("stretch_v")) == 1.0
    assert float(ctx.inspector.value("rotation_deg")) == 0.0
    state = tool._projector_state(ctx)
    assert state is not None
    assert float(state["half_w"]) <= 10.0
    assert float(state["half_h"]) <= 5.0


def test_texture_tool_press_passthrough_only_blocks_on_handles(tmp_path: Path) -> None:
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_plate()], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(_tex(tmp_path)), notify=False)
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10, 5, 0), projection_normal=(0, 0, 1))
    handles = tool._projector_handle_screen_positions(ctx)
    move = handles["texture_projection:move"]
    # The host projection uses VTK display Y internally, while mouse events are
    # Qt-style.  A click at the old unflipped Y coordinate must be treated as far
    # away; otherwise a camera drag below the visible handle is falsely grabbed.
    old_vtk_y = 105.0
    mirrored_wrong = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(move[0], old_vtk_y), world_pos=None, button=MouseButton.LEFT)
    away = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 10.0), world_pos=None, button=MouseButton.LEFT)
    on_handle = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(move[0], move[1]), world_pos=None, button=MouseButton.LEFT)
    assert abs(float(move[1]) - old_vtk_y) > 300.0
    assert tool.wants_pointer_press_passthrough(mirrored_wrong, ctx) is True
    assert tool.wants_pointer_press_passthrough(away, ctx) is True
    assert tool.wants_pointer_press_passthrough(on_handle, ctx) is False


def test_edge_handles_exist_for_non_uniform_stretch(tmp_path: Path) -> None:
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_plate()], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(_tex(tmp_path)), notify=False)
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10, 5, 0), projection_normal=(0, 0, 1))
    handles = tool._projector_handle_screen_positions(ctx)
    assert HANDLE_STRETCH_U_POS in handles
    assert HANDLE_STRETCH_V_POS in handles
    assert tool.start_projector_drag(ctx, handles[HANDLE_STRETCH_U_POS][0], handles[HANDLE_STRETCH_U_POS][1], kind="texstretch_u")
    assert tool.update_projector_drag(ctx, handles[HANDLE_STRETCH_U_POS][0] + 10.0, handles[HANDLE_STRETCH_U_POS][1])
    assert float(ctx.inspector.value("stretch_u")) > 1.0


def test_projector_manual_picker_uses_qt_y_not_vtk_y(tmp_path: Path) -> None:
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_plate()], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(_tex(tmp_path)), notify=False)
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10, 5, 0), projection_normal=(0, 0, 1))

    handles = tool._projector_handle_screen_positions(ctx)
    move = handles["texture_projection:move"]
    # Visual position in Qt coordinates is height - vtk_y = 600 - 105 = 495.
    assert move[1] == 495.0
    assert tool.pick_projector_handle(ctx, move[0], move[1]) is not None
    assert tool.pick_projector_handle(ctx, move[0], 105.0) is None


def test_texture_native_selection_and_manual_picker_share_qt_coordinates(tmp_path: Path) -> None:
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_plate()], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(_tex(tmp_path)), notify=False)
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10, 5, 0), projection_normal=(0, 0, 1))

    projector = tool._projector._qt_world_to_screen(ctx)
    assert callable(projector)
    ctx.viewport.world_to_screen = projector
    handles = tool._projector_handle_screen_positions(ctx)
    move = handles["texture_projection:move"]
    native_hit = ctx.selection.hit_test((move[0], move[1]), projector, owner_tool=tool.id, selectable_only=True)
    mirrored_miss = ctx.selection.hit_test((move[0], 105.0), projector, owner_tool=tool.id, selectable_only=True)
    assert native_hit is not None and native_hit.actor_id == "texture_projection:move"
    assert mirrored_miss is None
    assert tool.pick_projector_handle(ctx, move[0], move[1]) == ("gizmo", "texmove")
    assert tool.pick_projector_handle(ctx, move[0], 105.0) is None

def _cube_box() -> WorkMesh:
    return WorkMesh(
        name="cube",
        vertices=[
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (10.0, 10.0, 0.0),
            (0.0, 10.0, 0.0),
            (0.0, 0.0, 10.0),
            (10.0, 0.0, 10.0),
            (10.0, 10.0, 10.0),
            (0.0, 10.0, 10.0),
        ],
        triangles=[
            (0, 2, 1), (0, 3, 2),      # bottom
            (4, 5, 6), (4, 6, 7),      # top
            (0, 1, 5), (0, 5, 4),      # front
            (1, 2, 6), (1, 6, 5),      # right
            (2, 3, 7), (2, 7, 6),      # back
            (3, 0, 4), (3, 4, 7),      # left
        ],
        color="#B8B8B8",
    )




def test_attached_face_projection_saves_source_colour_for_uncovered_faces(tmp_path: Path) -> None:
    tex = _tex(tmp_path, (16, 16))
    source = _cube_box()
    source.color = "#336699"
    source.material = MeshMaterial(name="saved plywood", base_color="#884422")
    params = TextureProjectionParams(
        texture_id="tex_face",
        texture_path=tex,
        seed_face_index=2,
        projection_origin=(5.0, 5.0, 10.0),
        projection_normal=(0.0, 0.0, 1.0),
        image_width=16,
        image_height=16,
        attach_to_mesh=True,
        repeat=True,
    )

    mesh = apply_texture_projection([source], [0], params)[0]

    assert mesh.color == "#336699"
    assert getattr(mesh, "texture_pre_projection_role_color") == "#336699"
    assert getattr(mesh, "texture_pre_projection_material_color") == "#884422"
    assert getattr(mesh, "texture_saved_role_color") == "#336699"
    assert getattr(mesh, "texture_saved_material_color") == "#884422"
    assert mesh.texture_projections[0].repeat is False
    assert (0.0, 0.0) in [(round(float(u), 6), round(float(v), 6)) for u, v in mesh.uvs]
    assert all((float(u), float(v)) == (0.0, 0.0) or (0.0 < float(u) < 1.0 and 0.0 < float(v) < 1.0) for u, v in mesh.uvs)

    material_owner = SimpleNamespace(render_state=SimpleNamespace(display_mode="material"))
    role_owner = SimpleNamespace(render_state=SimpleNamespace(display_mode="role"))
    material_border = texture_rendering.texture_border_color_for_mesh(material_owner, mesh)
    role_border = texture_rendering.texture_border_color_for_mesh(role_owner, mesh)
    assert tuple(round(v, 3) for v in material_border[:3]) == tuple(round(v, 3) for v in (0x88 / 255.0, 0x44 / 255.0, 0x22 / 255.0))
    assert tuple(round(v, 3) for v in role_border[:3]) == tuple(round(v, 3) for v in (0x33 / 255.0, 0x66 / 255.0, 0x99 / 255.0))


def test_reapplying_and_clearing_attached_texture_restores_saved_colour(tmp_path: Path) -> None:
    tex = _tex(tmp_path, (8, 8))
    source = _cube_box()
    source.color = "#245A8D"
    source.material = MeshMaterial(name="painted", base_color="#C09040")
    params = TextureProjectionParams(
        texture_id="tex_face",
        texture_path=tex,
        seed_face_index=2,
        projection_origin=(5.0, 5.0, 10.0),
        projection_normal=(0.0, 0.0, 1.0),
        image_width=8,
        image_height=8,
        attach_to_mesh=True,
    )

    first = apply_texture_projection([source], [0], params)
    second = apply_texture_projection(first, [0], params)
    mesh = second[0]

    assert getattr(mesh, "texture_pre_projection_role_color") == "#245A8D"
    assert getattr(mesh, "texture_pre_projection_material_color") == "#C09040"
    assert getattr(mesh.material, "base_color") == "#FFFFFF"

    cleared = clear_texture_projection(second, [0])[0]
    assert cleared.uvs is None
    assert cleared.texture_projections == []
    assert cleared.color == "#245A8D"
    assert getattr(cleared.material, "texture_id", None) is None
    assert getattr(cleared.material, "base_color") == "#C09040"
    assert not hasattr(cleared, "texture_pre_projection_role_color")
    assert not hasattr(cleared, "texture_saved_material_color")

def test_attached_face_projection_keeps_uncovered_cube_faces_opaque_uv_safe(tmp_path: Path) -> None:
    tex = _tex(tmp_path, (8, 8))
    params = TextureProjectionParams(
        texture_id="tex_face",
        texture_path=tex,
        seed_face_index=2,
        projection_origin=(5.0, 5.0, 10.0),
        projection_normal=(0.0, 0.0, 1.0),
        image_width=8,
        image_height=8,
        attach_to_mesh=True,
        repeat=True,
    )

    mesh = apply_texture_projection([_cube_box()], [0], params)[0]

    assert len(mesh.vertices) > 8  # covered/uncovered shared points are split
    assert mesh.texture_projections[0].placement == "mesh"
    assert mesh.texture_projections[0].repeat is False
    assert all(0.0 <= float(u) <= 1.0 and 0.0 <= float(v) <= 1.0 for u, v in mesh.uvs)
    assert (0.0, 0.0) in [(round(float(u), 6), round(float(v), 6)) for u, v in mesh.uvs]
