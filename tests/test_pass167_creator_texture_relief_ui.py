# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.geometry_ops.text_relief import make_text_relief_mesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool


def _flat_square(name: str, z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, z), (20.0, 0.0, z), (20.0, 12.0, z), (0.0, 12.0, z)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#CCC",
    )


def _tiny_png(path: Path) -> None:
    path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))


def test_relief_uses_real_font_geometry_path_when_font_selected(monkeypatch) -> None:
    import laserprog_studio.geometry_ops.text_relief as text_relief

    calls: list[str] = []

    def fake_font_geometry(text: str, depth: float, font_family: str):
        calls.append(font_family)
        return (
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
            [(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        )

    def fail_vtk(*_args, **_kwargs):
        raise AssertionError("real font path should be tried before VTK fallback")

    monkeypatch.setattr(text_relief, "_make_font_text_geometry", fake_font_geometry)
    monkeypatch.setattr(text_relief, "_make_vtk_text_polydata", fail_vtk)

    mesh = make_text_relief_mesh(
        text="A",
        anchor_point=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        font_family="Liberation Sans",
    )

    assert calls == ["Liberation Sans"]
    assert mesh.material["font_family"] == "Liberation Sans"
    assert mesh.vertices
    assert mesh.triangles


def test_font_field_adapter_uses_native_font_combo() -> None:
    source = Path("src/laserprog_studio/ui/inspector_panel_adapter.py").read_text(encoding="utf-8")

    assert "QFontComboBox" in source
    assert "currentFontChanged" in source
    assert "QFontDialog" not in source


def test_texture_projection_declares_projected_handles_previews_and_overlay(tmp_path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))

    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(10.0, 6.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    projected = {item.id: item for item in ctx.projected_drawing.for_tool(tool.id).items()}
    handles = {item.metadata[0][1] if item.metadata else item.id: item for item in projected.values() if item.id in {"texture_projection:move", "texture_projection:rotate", "texture_projection:scale"}}
    assert "texture_projector:move" in handles
    assert "texture_projector:rotate" in handles
    assert "texture_projector:scale" in handles
    assert {handle.shape.value for handle in handles.values()} >= {"target", "ring", "square"}
    assert min(handle.style.size_px for handle in handles.values()) >= 18

    projector_actors = [actor for actor in ctx.selection.actors(owner_tool=tool.id) if actor.id.startswith(f"{tool.id}:")]
    assert projector_actors
    assert 18.0 <= min(float(actor.hit_radius_px) for actor in projector_actors) <= 22.0

    assert projected[f"{tool.id}:rotation_ring"].style.width_px >= 5.0
    assert f"{tool.id}:frame" in projected
    assert f"{tool.id}:rotation_ring" in projected
    assert not tuple(ctx.gizmos.handles(owner_tool=tool.id))
    assert not tuple(ctx.preview.items(owner_tool=tool.id))
    assert any(actor.id.endswith(":scale") for actor in ctx.selection.actors(owner_tool=tool.id))
    assert any(window.owner_tool == tool.id and "projector" in window.id for window in ctx.overlay.windows.values())


def test_texture_projection_controller_adapter_prefers_creator_ui() -> None:
    source = Path("src/laserprog_studio/controllers/texture_projection_tool.py").read_text(encoding="utf-8")
    interaction = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")

    assert "render_projector_ui" in source
    assert "pick_projector_handle" in source
    assert "start_projector_drag" in source
    assert "update_projector_drag" in source
    assert "finish_projector_drag" in source
    assert "texscale" in interaction
