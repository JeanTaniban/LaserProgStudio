# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import base64
from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool


def _flat_square(name: str, z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, z), (10.0, 0.0, z), (10.0, 10.0, z), (0.0, 10.0, z)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#CCC",
    )


def _tiny_png(path: Path) -> None:
    path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))


def _attribute_chain(node: ast.Attribute) -> str:
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def test_texture_projector_runtime_no_longer_calls_legacy_preview_or_gizmos() -> None:
    source = Path("src/laserprog_studio/tooling/_texture_projection_projector.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = _attribute_chain(node)
        if chain.startswith(("ctx.preview", "ctx.gizmos", "ctx.actor_registry")):
            forbidden.append((int(node.lineno), chain))
    assert forbidden == []


def test_texture_projector_declares_only_projected_drawing_primitives(tmp_path: Path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y, depth: (float(x) - 100.0, float(y) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))

    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    projected = {item.id: item for item in ctx.projected_drawing.for_tool(tool.id).items()}
    assert {"texture_projection:move", "texture_projection:rotate", "texture_projection:scale"}.issubset(projected)
    assert {"texture_projection:frame", "texture_projection:rotation_ring", "texture_projection:cross_u", "texture_projection:cross_v", "texture_projection:label"}.issubset(projected)
    assert not tuple(ctx.gizmos.handles(owner_tool=tool.id))
    assert not tuple(ctx.preview.items(owner_tool=tool.id))
    assert any(actor.id == "texture_projection:move" for actor in ctx.selection.actors(owner_tool=tool.id))


def test_texture_projector_fast_drag_updates_projected_positions(tmp_path: Path) -> None:
    image_path = tmp_path / "texture.png"
    _tiny_png(image_path)
    store = ModelStore()
    store.set_meshes([_flat_square("panel")], push_undo=False)
    owner = SimpleNamespace(
        _world_to_display=lambda point: (100.0 + float(point[0]), 100.0 + float(point[1]), 0.5),
        _display_to_world_at_depth=lambda x, y, depth: (float(x) - 100.0, float(y) - 100.0, float(depth)),
        plotter=SimpleNamespace(render=lambda: None, height=lambda: 600),
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("texture_path", str(image_path))
    assert tool.preview_index(ctx, 0, seed_face_index=0, projection_origin=(5.0, 5.0, 0.0), projection_normal=(0.0, 0.0, 1.0)) is True

    before = ctx.projected_drawing.for_tool(tool.id).get("texture_projection:rotate")
    assert before is not None
    assert tool.start_projector_drag(ctx, 105.0, 118.0, kind="texrot") is True
    assert tool.update_projector_drag(ctx, 112.0, 122.0) is True
    after = ctx.projected_drawing.for_tool(tool.id).get("texture_projection:rotate")
    assert after is not None
    assert getattr(after, "position") != getattr(before, "position")
