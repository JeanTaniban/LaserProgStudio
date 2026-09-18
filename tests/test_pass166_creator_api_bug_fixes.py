# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.layflat_tool import LayflatCreatorTool, _fusion_mode
from laserprog_studio.tooling.relief_tool import ReliefCreatorTool
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool, texture_params_from_values


def _flat_square(name: str, z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, z), (10.0, 0.0, z), (10.0, 10.0, z), (0.0, 10.0, z)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#CCC",
    )


def _tiny_png(path) -> None:
    # 1x1 transparent PNG, written without requiring Pillow in the test env.
    path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))


def test_layflat_no_merge_keeps_overlapping_parts_separate() -> None:
    store = ModelStore()
    # Same footprint: overlap grouping would collapse these into one piece, so
    # this catches the no-merge regression directly.
    store.set_meshes([_flat_square("joint-a"), _flat_square("joint-b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)

    tool = LayflatCreatorTool()
    tool.open(ctx)
    result = ctx.operations.layflat(inputs=(), params={"fusion_mode": "none", "packing_constraint": "none", "spacing_mm": 0.0}, preview=False, owner_tool=tool.id)

    assert result.ok, result.errors
    assert _fusion_mode("none") == "none"
    assert result.metadata["fusion_mode"] == "none"
    assert result.metadata["source_count"] == 2
    assert result.metadata["piece_count"] == 2
    assert len(result.meshes) == 2


def test_relief_face_click_persists_target_and_preview_refresh(monkeypatch) -> None:
    import laserprog_studio.tooling.relief_tool as relief_module
    from laserprog_studio.geometry_ops.result import OperationResult as GeometryResult

    calls: list[str] = []

    def fake_relief(base, anchor, *, text, size_mm, depth_mm, rotation_deg, mode, align, font_family):
        calls.append(str(font_family))
        out = list(base)
        preview = WorkMesh(
            name=f"relief-{font_family or 'default'}",
            vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            triangles=[(0, 1, 2)],
            color="#FFF",
        )
        out.append(preview)
        return GeometryResult.success(out)

    monkeypatch.setattr(relief_module, "add_text_relief_preview", fake_relief)

    store = ModelStore()
    store.set_meshes([_flat_square("target")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = ReliefCreatorTool()
    tool.open(ctx)

    assert tool.set_anchor_from_pick(ctx, 0, (3.0, 4.0, 0.0), (0.0, 0.0, 1.0)) is True
    assert store.has_preview
    assert ctx.inspector.value("target_index") == 0
    assert ctx.inspector.value("has_anchor") == "true"
    assert ctx.scene_selection.selected_indices() == (0,)
    assert store.preview_meshes[-1].name == "relief-VTK VectorText"

    ctx.inspector.update_value("font_family", "Test Font")
    ctx.inspector.trigger("preview")

    assert calls[-1] == "Test Font"
    assert ctx.scene_selection.selected_indices() == (0,)
    assert store.preview_meshes[-1].name == "relief-Test Font"


def test_texture_projection_creator_persists_face_anchor_and_uses_asset_api(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    owner = SimpleNamespace(render_state=SimpleNamespace(display_mode="wireframe"), display_mode_combo=None)
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    ctx.inspector.update_value("coverage_angle_deg", 30.0)

    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    assert store.has_preview
    assert ctx.inspector.value("target_index") == 0
    assert ctx.inspector.value("seed_face_index") == 0
    assert ctx.inspector.value("projection_origin") == (5.0, 5.0, 0.0)
    assert ctx.scene_selection.selected_indices() == (0,)
    assert owner.render_state.display_mode == "material"

    params = tool.params_from_context(ctx, target_index=0)
    assert params.seed_face_index == 0
    assert params.projection_origin == (5.0, 5.0, 0.0)
    assert params.texture_id.startswith("tex_")
    assert any(asset.id == params.texture_id for asset in ctx.assets.list_textures())


def test_texture_projection_preview_selected_keeps_multi_selection(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    store = ModelStore()
    store.set_meshes([_flat_square("a"), _flat_square("b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0, 1), active_index=1)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    # Hidden target_index may contain the active selection. Preview selected must
    # still texture both selected meshes unless a face anchor is active.
    ctx.inspector.update_value("target_index", 1, notify=False)

    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert ctx.scene_selection.selected_indices() == (0, 1)
    assert store.preview_meshes[0].texture_projections
    assert store.preview_meshes[1].texture_projections


def test_texture_params_string_booleans_are_not_truthy_by_accident(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    params = texture_params_from_values({"texture_path": str(image_path), "repeat": "false", "attach_to_mesh": "false", "preserve_aspect": "false"})

    assert params.repeat is False
    assert params.attach_to_mesh is False
    assert params.preserve_aspect is False
