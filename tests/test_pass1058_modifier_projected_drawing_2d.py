# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.extrude_down_tool import ExtrudeDownCreatorTool
from laserprog_studio.tooling.ids import TOOL_MOD_EXTRUDE_DOWN, TOOL_MOD_SPLIT
from laserprog_studio.tooling.split_tool import SplitPlaneCreatorTool


def _cube_mesh(name: str = "cube") -> WorkMesh:
    vertices = [
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
        (10.0, 0.0, 10.0),
        (10.0, 10.0, 10.0),
        (0.0, 10.0, 10.0),
    ]
    triangles = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    return WorkMesh(name=name, vertices=vertices, triangles=triangles)


def _ctx() -> ToolContext:
    ctx = ToolContext(document=SceneDocument.from_meshes("main", [_cube_mesh()]))
    ctx.scene_selection.set_selected([0])
    # Deterministic headless projection: +1 mm along Z is +10 px on screen Y.
    ctx.viewport.world_to_screen = lambda p: (float(p[0]) * 10.0, float(p[2]) * 10.0)
    return ctx


def test_split_modifier_uses_projected_drawing_2d_plane_and_handle() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_SPLIT)
    ids = {primitive.id for primitive in snapshot.primitives}
    assert "modifier_split:plane_face" in ids
    assert "modifier_split:plane_outline" in ids
    assert "modifier_split:plane_handle" in ids

    handle_actor = ctx.selection.actor("modifier_split:plane_handle")
    assert handle_actor is not None
    assert (handle_actor.metadata or {}).get("projected_drawing_id") == "modifier_split:plane_handle"
    assert handle_actor.grabbable


def test_split_modifier_drag_updates_offset_in_projected_api() -> None:
    ctx = _ctx()
    tool = SplitPlaneCreatorTool()
    tool.on_open(ctx)
    handle = ctx.selection.actor("modifier_split:plane_handle")
    assert handle is not None

    ctx.selection.select("modifier_split:plane_handle")
    ctx.selection.begin_grab("modifier_split:plane_handle", (0.0, 0.0), handle.points[0])
    ctx.selection.update_grab_screen((0.0, 10.0))
    moved = tool.resolve_drag_positions(object(), ctx)

    assert moved and "modifier_split:plane_handle" in moved
    assert float(ctx.inspector.value("offset_mm", 0.0)) > 0.9
    assert ctx.inspector.value("split_preset", "") == "custom"


def test_extrude_down_modifier_uses_projected_drawing_2d_plane_and_handle() -> None:
    ctx = _ctx()
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_MOD_EXTRUDE_DOWN)
    ids = {primitive.id for primitive in snapshot.primitives}
    assert "modifier_extrude_down:plane_face" in ids
    assert "modifier_extrude_down:plane_outline" in ids
    assert "modifier_extrude_down:plane_handle" in ids

    handle_actor = ctx.selection.actor("modifier_extrude_down:plane_handle")
    assert handle_actor is not None
    assert (handle_actor.metadata or {}).get("projected_drawing_id") == "modifier_extrude_down:plane_handle"
    assert handle_actor.grabbable


def test_extrude_down_drag_updates_plane_z_in_projected_api() -> None:
    ctx = _ctx()
    tool = ExtrudeDownCreatorTool()
    tool.on_open(ctx)
    start_z = float(ctx.inspector.value("plane_z", 0.0))
    handle = ctx.selection.actor("modifier_extrude_down:plane_handle")
    assert handle is not None

    ctx.selection.select("modifier_extrude_down:plane_handle")
    ctx.selection.begin_grab("modifier_extrude_down:plane_handle", (0.0, 0.0), handle.points[0])
    ctx.selection.update_grab_screen((0.0, 10.0))
    moved = tool.resolve_drag_positions(object(), ctx)

    assert moved and "modifier_extrude_down:plane_handle" in moved
    assert float(ctx.inspector.value("plane_z", 0.0)) > start_z
    assert ctx.inspector.value("extrude_down_preset", "") == "custom"
