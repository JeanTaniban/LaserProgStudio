# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import math
from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.geometry_ops.text_relief import make_text_relief_mesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.gizmos import GizmoHandle
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool
from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui


def _flat_square(name: str, z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, z), (10.0, 0.0, z), (10.0, 10.0, z), (0.0, 10.0, z)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#CCC",
    )


def _tiny_png(path: Path) -> None:
    path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))


class _Plotter:
    def __init__(self) -> None:
        self.render_count = 0
        self.removed = []

    def remove_actor(self, actor, render: bool = False):
        self.removed.append((actor, render))

    def render(self):
        self.render_count += 1


class _ViewportOwner:
    def __init__(self) -> None:
        self.plotter = _Plotter()
        self.gizmo_actors = {}
        self.gizmo_actor_ids = {}
        self.gizmo_key_by_addr = {}
        self.calls = []

    # Matches the existing desktop bridge signature: no render= keyword.
    def _add_overlay_mesh_actor(self, mesh, *, key, axis, color, pickable):
        actor = SimpleNamespace(key=key, axis=axis, color=color, pickable=pickable)
        self.calls.append(actor)
        self.gizmo_actors[key] = actor
        return actor


def test_creator_viewport_adapter_calls_existing_overlay_bridge_without_render_kw(monkeypatch) -> None:
    import laserprog_studio.application.creator_viewport_ui as viewport_ui

    monkeypatch.setattr(viewport_ui, "_line_mesh", lambda *args, **kwargs: object())
    monkeypatch.setattr(viewport_ui, "_handle_mesh", lambda *args, **kwargs: object())

    owner = _ViewportOwner()
    ctx = ToolContext(owner=owner)
    owner_tool = "texture_projection"
    ctx.preview.show_line("preview-line", owner_tool, (0.0, 0.0, 0.0), (4.0, 0.0, 0.0), payload={"line_style": "preview"})
    ctx.gizmos.create_handle(
        GizmoHandle(
            id="texture_projection:move",
            owner_tool=owner_tool,
            position=(1.0, 1.0, 0.0),
            radius_px=12,
            color=(0.0, 0.5, 1.0, 1.0),
            kind="texture_projector:move",
            style_id="target",
            selectable=True,
        )
    )

    render_creator_viewport_ui(owner, ctx, owner_tool, render=True)

    assert owner.plotter.render_count == 1
    assert any(call.key.startswith("creator_ui_texture_projection_preview_") for call in owner.calls)
    handle_calls = [call for call in owner.calls if call.key.startswith("creator_ui_texture_projection_handle_")]
    assert handle_calls
    assert handle_calls[0].axis == "texmove"
    assert handle_calls[0].pickable is True


def test_texture_projection_hover_updates_creator_selection_state_and_styles(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0))

    move = tool._projector_handle_screen_positions(ctx)["texture_projection:move"]
    assert move == (105.0, 495.0, 0.5)
    assert tool.hover_projector_handle(ctx, move[0], move[1]) is True

    assert ctx.selection.state.hover_id == "texture_projection:move"
    handle = ctx.projected_drawing.for_tool(tool.id).get("texture_projection:move")
    assert handle is not None
    assert handle.style.size_px > 18
    assert not tuple(ctx.gizmos.handles(owner_tool=tool.id))


def test_relief_font_input_accepts_qfont_like_values(monkeypatch) -> None:
    import laserprog_studio.geometry_ops.text_relief as text_relief

    calls: list[str] = []

    class FakeFont:
        def family(self) -> str:
            return "Liberation Sans"

    def fake_font_geometry(text: str, depth: float, font_family: str):
        calls.append(font_family)
        return (
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
            [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        )

    def fail_vtk(*_args, **_kwargs):
        raise AssertionError("QFont-like values should resolve to the selected family")

    monkeypatch.setattr(text_relief, "_make_font_text_geometry", fake_font_geometry)
    monkeypatch.setattr(text_relief, "_make_vtk_text_polydata", fail_vtk)

    mesh = make_text_relief_mesh(
        text="A",
        anchor_point=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        font_family=FakeFont(),
    )

    assert calls == ["Liberation Sans"]
    assert mesh.material["font_family"] == "Liberation Sans"


def test_texture_projector_drag_uses_fast_path_until_release(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y, depth: (float(x) - 100.0, float(y) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0))

    preview_calls: list[tuple[int, dict[str, object]]] = []

    def count_preview(_ctx, index: int, **kwargs):
        preview_calls.append((int(index), dict(kwargs)))
        return True

    monkeypatch.setattr(tool, "preview_index", count_preview)

    preview_meshes = list(ctx.document.meshes(include_preview=True))
    decal = preview_meshes[-1]
    before_uvs = tuple(tuple(float(v) for v in uv) for uv in getattr(decal, "uvs"))

    assert tool.start_projector_drag(ctx, 105.0, 118.0, kind="texrot") is True
    assert tool.update_projector_drag(ctx, 112.0, 122.0) is True
    assert preview_calls == []
    assert ctx.inspector.value("rotation_deg") != 0.0
    live_decal = list(ctx.document.meshes(include_preview=True))[-1]
    after_uvs = tuple(tuple(float(v) for v in uv) for uv in getattr(live_decal, "uvs"))
    assert after_uvs != before_uvs

    assert tool.finish_projector_drag(ctx) is True
    assert len(preview_calls) == 1
    assert preview_calls[0][0] == 0


def test_texture_projector_rotation_drag_matches_clockwise_screen_direction(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y, depth: (float(x) - 100.0, float(y) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    # Center is projected to (105, 105).  Moving from the top of the ring to the
    # right side is a clockwise screen movement.  The UV math defines positive
    # texture rotation as visually counter-clockwise, so this drag must decrease
    # the rotation value for the bitmap to follow the hand.
    assert tool.start_projector_drag(ctx, 105.0, 93.0, kind="texrot") is True
    assert tool.update_projector_drag(ctx, 117.0, 105.0) is True
    assert float(ctx.inspector.value("rotation_deg")) < 0.0


def test_texture_projector_rotation_uses_plane_intersection_not_screen_angle(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)

    class ObliqueOwner:
        def __init__(self) -> None:
            self.plotter = SimpleNamespace(render=lambda: None, height=lambda: 600)
            self.gizmo_actors = {}

        def _world_to_display(self, point):
            # Deliberately squash the texture plane in screen Y.  A screen-space
            # atan2 sees a distorted ellipse here; the correct result must come
            # from ray/plane intersection in world space.
            x, y, z = (float(v) for v in point)
            return (100.0 + x, 100.0 + 0.20 * y + 0.02 * z, 0.5)

        def _display_to_world_at_depth(self, x, y_vtk, depth):
            qt_y = 600.0 - float(y_vtk)
            return (float(x) - 100.0, (qt_y - 100.0) / 0.20, -10.0 + 20.0 * float(depth))

    owner = ObliqueOwner()
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    # World vectors around the texture center: +V -> -U is +90 degrees in the
    # texture plane.  With the fake camera this is not +90 degrees in screen
    # space, so the old screen-angle implementation would return the wrong sign.
    assert tool.start_projector_drag(ctx, 105.0, 103.0, kind="texrot") is True
    assert tool.update_projector_drag(ctx, 95.0, 101.0) is True
    rotation = float(ctx.inspector.value("rotation_deg"))
    assert 80.0 < rotation < 100.0


def test_texture_projector_gizmo_ring_size_does_not_follow_texture_scale(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    state_small = tool._projector_state(ctx)
    assert state_small is not None
    ring_small = float(state_small["radius"])
    frame_small = float(state_small["half_w"])

    ctx.inspector.update_value("scale", 4.0, notify=False)
    state_large = tool._projector_state(ctx)
    assert state_large is not None

    assert float(state_large["radius"]) == ring_small
    assert float(state_large["half_w"]) > frame_small * 3.5


def test_texture_projector_angle_and_scale_snaps_are_practical(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True
    state = tool._projector_state(ctx)
    assert state is not None

    angle_candidates = tool._projector._rotation_snap_candidates_for_state(state)
    assert tool._projector._snap_rotation(43.5, angle_candidates)[0] == 45.0

    scale_candidates = tool._projector._scale_snap_candidates_for_state(state)
    assert scale_candidates
    fit_value = scale_candidates[0][0]
    snapped, label = tool._projector._snap_scale(fit_value * 1.03, scale_candidates)
    assert abs(snapped - fit_value) < 1e-9
    assert label in {"fit width", "fit height", "fit inside", "cover bounds"}


def test_texture_projector_face_frame_uses_real_texture_dimensions_not_triangle_diagonal(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    state = tool._projector_state(ctx)
    assert state is not None
    # Triangle 0 contains the quad diagonal (0 -> 2).  The texture UI must still
    # align to the face/bounds X axis instead of turning 45 degrees.
    u = tuple(float(v) for v in state["base_u"])
    assert abs(u[0]) > 0.99
    assert abs(u[1]) < 1e-6
    assert math.isclose(float(state["tile_width"]), 10.0, rel_tol=1e-6)
    assert math.isclose(float(state["half_w"]), 5.0, rel_tol=1e-6)
    scale_candidates = dict((label, value) for value, label in tool._projector._scale_snap_candidates_for_state(state))
    assert math.isclose(scale_candidates["fit width"], 1.0, rel_tol=1e-6)


def test_texture_projector_scale_snap_measures_current_image_rotation(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    rect = WorkMesh(
        name="rect",
        vertices=[(0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#CCC",
    )
    store = ModelStore()
    store.set_meshes([rect], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True
    ctx.inspector.update_value("rotation_deg", 45.0, notify=False)

    state = tool._projector_state(ctx)
    assert state is not None
    candidates = dict((label, value) for value, label in tool._projector._scale_snap_candidates_for_state(state))
    expected_rotated_extent = (20.0 + 10.0) / math.sqrt(2.0)
    # The square texture tile is 20 units wide at scale 1.  At 45°, the rectangle
    # projects to ~21.21 units along each image axis, so the useful snap is ~1.06,
    # not the old mesh_span*0.30 heuristic (~1.77) and not an unrotated 1.0.
    assert math.isclose(candidates["fit width"], expected_rotated_extent / 20.0, rel_tol=1e-6)
    assert candidates["fit height"] >= candidates["fit width"]


def test_texture_projector_same_face_click_resets_transient_drag_and_moves_origin(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True
    assert tool.start_projector_drag(ctx, 105.0, 105.0, kind="texmove") is True
    assert tool._projector_drag is not None
    assert ctx.selection.state.grab_active is True

    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(2.0, 3.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    assert tool._projector_drag is None
    assert ctx.selection.state.grab_active is False
    assert tuple(float(v) for v in ctx.inspector.value("projection_origin")) == (2.0, 3.0, 0.0)


def test_texture_projector_move_drag_clamps_center_inside_painted_face(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y_vtk, depth: (float(x) - 100.0, 600.0 - float(y_vtk) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
        gizmo_actors={},
    )
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    assert tool.start_projector_drag(ctx, 105.0, 105.0, kind="texmove") is True
    assert tool.update_projector_drag(ctx, 230.0, -80.0) is True
    origin = tuple(float(v) for v in ctx.inspector.value("projection_origin"))

    assert 0.0 <= origin[0] <= 10.0
    assert 0.0 <= origin[1] <= 10.0
    assert origin == (10.0, 0.0, 0.0)
