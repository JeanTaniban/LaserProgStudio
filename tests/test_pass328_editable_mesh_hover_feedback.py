# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.folding.geometry import arbitrary_face_plane, deform_mesh
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingPhase
from laserprog_studio.tooling.folding.serialization import attach_folding_source
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool
from laserprog_studio.tooling.ids import TOOL_FOLDING, TOOL_MECHANICAL_MOTION
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion_tool import MechanicalMotionCreatorTool


def _simple_mesh(name: str = "part") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (10.0, 5.0, 0.0),
            (0.0, 5.0, 0.0),
            (0.0, 0.0, 2.0),
            (10.0, 0.0, 2.0),
            (10.0, 5.0, 2.0),
            (0.0, 5.0, 2.0),
        ],
        triangles=[
            (0, 1, 2), (0, 2, 3),
            (4, 6, 5), (4, 7, 6),
            (0, 4, 5), (0, 5, 1),
            (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3),
            (3, 7, 4), (3, 4, 0),
        ],
        color="#AACCEE",
    )


def _folded_mesh() -> WorkMesh:
    source = _simple_mesh("folded part")
    plane = arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    curve = FoldingCurve((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), 2.5, -1.0)
    return attach_folding_source(
        deform_mesh(source, plane, curve),
        source_mesh=source,
        plane=plane,
        curve=curve,
    )


def _mechanical_meshes() -> list[WorkMesh]:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    session.add_gear((0.0, 0.0, 0.0), teeth=20)
    session.add_gear((32.0, 0.0, 0.0), teeth=12)
    return list(session.applied_meshes())


def _yellow_hover_meshes(ctx: ToolContext, tool_id: str):
    return tuple(
        item
        for item in ctx.projected_drawing.for_tool(tool_id).items()
        if dict(getattr(item, "metadata", ()) or {}).get("editable_hover_role")
    )


def test_mechanical_startup_hover_outlines_the_complete_existing_assembly(monkeypatch) -> None:
    meshes = _mechanical_meshes()
    store = ModelStore()
    store.set_meshes(meshes, push_undo=False)
    owner = SimpleNamespace(selected_indices=[], active_index=None)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)

    from laserprog_studio.tool_api import plan2d

    hit = SimpleNamespace(hit=True, object_index=0, object_id=meshes[0].mesh_id)
    monkeypatch.setattr(plan2d, "pick_plan_surface_anchor_by_raycast", lambda *_args, **_kwargs: hit)

    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(120.0, 80.0)), ctx) is False
    highlights = _yellow_hover_meshes(ctx, TOOL_MECHANICAL_MOTION)
    assert len(highlights) == len(meshes)
    assert all(item.style.outline_color == "#FFD54F" for item in highlights)
    assert all(item.style.outline_width_px == 5.0 for item in highlights)
    assert all(dict(item.metadata).get("projected_no_selection_actor") is True for item in highlights)

    revision = ctx.projected_drawing.for_tool(TOOL_MECHANICAL_MOTION).snapshot().revision
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(121.0, 80.0)), ctx)
    assert ctx.projected_drawing.for_tool(TOOL_MECHANICAL_MOTION).snapshot().revision == revision

    monkeypatch.setattr(
        plan2d,
        "pick_plan_surface_anchor_by_raycast",
        lambda *_args, **_kwargs: SimpleNamespace(hit=False, object_index=None, object_id=None),
    )
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(500.0, 500.0)), ctx)
    assert not _yellow_hover_meshes(ctx, TOOL_MECHANICAL_MOTION)


def test_folding_hover_marks_every_selectable_mesh_and_clears_on_open() -> None:
    folded = _folded_mesh()
    fresh = _simple_mesh("fresh part")
    store = ModelStore()
    store.set_meshes([folded, fresh], push_undo=False)

    class PickScene:
        def pick_object_at(self, screen_pos, **_filters):
            if float(screen_pos[0]) < 100.0:
                return {"kind": "object", "object_id": folded.mesh_id, "object_index": 0}
            if float(screen_pos[0]) < 200.0:
                return {"kind": "object", "object_id": fresh.mesh_id, "object_index": 1}
            return {"kind": "miss"}

    ctx = ToolContext(scene=PickScene())
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(50.0, 40.0)), ctx)
    highlights = _yellow_hover_meshes(ctx, TOOL_FOLDING)
    assert len(highlights) == 1
    assert highlights[0].style.outline_color == "#FFD54F"
    assert highlights[0].style.fill_opacity < 0.05

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(150.0, 40.0)), ctx)
    fresh_highlights = _yellow_hover_meshes(ctx, TOOL_FOLDING)
    assert len(fresh_highlights) == 1
    assert dict(fresh_highlights[0].metadata).get("source_object_id") == fresh.mesh_id

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(50.0, 40.0)), ctx)
    assert _yellow_hover_meshes(ctx, TOOL_FOLDING)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(50.0, 40.0), button=MouseButton.LEFT),
        ctx,
    ) is False
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(50.0, 40.0), button=MouseButton.LEFT),
        ctx,
    ) is True
    assert tool.session.phase is FoldingPhase.ADJUST_CURVE
    assert tool.session.editing_existing is True
    assert not _yellow_hover_meshes(ctx, TOOL_FOLDING)
