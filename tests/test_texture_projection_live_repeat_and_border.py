# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from laserprog_studio.domain.material import MeshMaterial
from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams, apply_texture_projection
from laserprog_studio.rendering import textures as texture_rendering
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool


def _tiny_png(path: Path) -> None:
    path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))


def _flat_square(name: str, z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, z), (10.0, 0.0, z), (10.0, 10.0, z), (0.0, 10.0, z)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#00C853",
        material=MeshMaterial(name="Plywood", base_color="#AA7744"),
    )


def test_decal_panel_lift_is_large_enough_to_avoid_depth_fighting() -> None:
    mesh = _flat_square("panel")
    params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=Path("demo.png"),
        seed_face_index=0,
        projection_origin=(5.0, 5.0, 0.0),
        projection_normal=(0.0, 0.0, 1.0),
        image_width=64,
        image_height=64,
    )

    out = apply_texture_projection([mesh], [0], params)
    decal = out[1]

    assert bool(getattr(decal, "is_texture_decal", False))
    assert min(float(v[2]) for v in decal.vertices) >= 0.01


def test_repeat_checkbox_retraces_preview_immediately(tmp_path: Path) -> None:
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

    ctx.inspector.update_value("repeat", True)

    preview_meshes = list(ctx.document.meshes(include_preview=True))
    decal = preview_meshes[-1]
    assert bool(getattr(decal.texture_projections[0], "repeat", False)) is True


def test_non_repeated_texture_uses_neutral_border_color_from_mode(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    Image.new("RGBA", (2, 2), (255, 0, 0, 255)).save(image_path)
    mesh = _flat_square("panel")
    setattr(mesh, "texture_border_role_color", "#00C853")
    setattr(mesh, "texture_border_material_color", "#AA7744")

    owner = SimpleNamespace(render_state=SimpleNamespace(display_mode="material"))
    material_border = texture_rendering.texture_border_color_for_mesh(owner, mesh)
    assert tuple(round(c, 3) for c in material_border[:3]) == tuple(round(c, 3) for c in (0xAA / 255.0, 0x77 / 255.0, 0x44 / 255.0))

    array = texture_rendering._padded_texture_array(image_path, material_border, border_px=1)
    assert tuple(int(v) for v in array[0, 0]) == (0xAA, 0x77, 0x44, 255)
    assert tuple(int(v) for v in array[1, 1]) == (255, 0, 0, 255)


class _FakeVtkTexture:
    def __init__(self) -> None:
        self.wrap = None
        self.border = None

    def SetRepeat(self, value):
        self.wrap = 1 if value else 0

    def SetInterpolate(self, _value):
        pass

    def SetEdgeClamp(self, _value):
        pass

    def RepeatOff(self):
        self.wrap = 0

    def InterpolateOn(self):
        pass

    def EdgeClampOff(self):
        pass

    def SetWrap(self, value):
        self.wrap = int(value)

    def SetBorderColor(self, *value):
        self.border = tuple(float(v) for v in value)


class _FakeTexture:
    def __init__(self) -> None:
        self.vtk = _FakeVtkTexture()
        self.wrap = None
        self.border_color = None
        self.repeat = None
        self.interpolate = None

    def GetTexture(self):
        return self.vtk


def test_non_repeated_texture_config_prefers_clamp_to_border_over_edge_stretch() -> None:
    texture = _FakeTexture()

    texture_rendering._configure_texture(texture, repeat=False, border_color=(0.2, 0.3, 0.4, 1.0))

    assert texture.wrap == 3
    assert texture.vtk.wrap == 3
    assert texture.vtk.border == (0.2, 0.3, 0.4, 1.0)
