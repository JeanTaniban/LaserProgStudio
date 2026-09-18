# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from pathlib import Path

import pytest

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.folding.geometry import arbitrary_face_plane, deform_mesh, deform_vertices, sample_curve
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingPhase, FoldingSession
from laserprog_studio.tooling.folding.serialization import FOLDING_SOURCE_KEY, attach_folding_source, restore_folding_source
from laserprog_studio.tooling.folding.state_machine import FoldingWorkflowMachine
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool
from laserprog_studio.tooling.ids import TOOL_FOLDING
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.toolbar_catalog import get_toolbar_item_spec
from laserprog_studio.ui.toolbar_icons import toolbar_icon_path
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _strip_mesh() -> WorkMesh:
    vertices = []
    for x in (-2.0, 0.0, 2.5, 5.0, 7.5, 10.0, 12.0):
        vertices.extend(((x, -1.0, 0.0), (x, 1.0, 0.0), (x, -1.0, 2.0), (x, 1.0, 2.0)))
    triangles = []
    for section in range(6):
        a = section * 4
        b = (section + 1) * 4
        triangles.extend(((a, b, a + 1), (a + 1, b, b + 1), (a + 2, a + 3, b + 2), (a + 3, b + 3, b + 2)))
    return WorkMesh(name="fold strip", vertices=vertices, triangles=triangles, color="#AACCEE")


def _plane():
    return arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def test_folding_is_registered_as_a_declarative_creator_tool_with_light_icon() -> None:
    spec = get_tool_spec(TOOL_FOLDING)
    assert spec is not None
    assert spec.panel_index == 33
    assert spec.open_without_initial_selection is True
    assert get_studio_tool(TOOL_FOLDING).__class__.__name__ == "FoldingTool"
    assert get_tool_panel_spec(TOOL_FOLDING).builder == "panel_declarative_creator_tool"
    item = get_toolbar_item_spec("tool:folding")
    assert item is not None and item.tool_id == TOOL_FOLDING and item.code == "FLD"
    icon = Path(toolbar_icon_path("tool:folding"))
    assert icon.exists()
    assert icon.stat().st_size < 20_000


def test_state_machine_follows_mesh_face_start_end_curve_sequence() -> None:
    session = FoldingSession()
    machine = FoldingWorkflowMachine(session)
    session.target_object_id = "mesh-a"
    session.source_mesh = _strip_mesh()
    assert machine.select_mesh().phase is FoldingPhase.SELECT_FACE
    session.plane = _plane()
    assert machine.select_face().phase is FoldingPhase.PLACE_START
    session.curve.start = (0.0, 0.0, 0.0)
    assert machine.place_start().phase is FoldingPhase.PLACE_END
    session.curve.end = (10.0, 0.0, 0.0)
    assert machine.place_end().phase is FoldingPhase.ADJUST_CURVE
    assert session.dirty is True


def test_zero_offset_curve_keeps_every_vertex_identical() -> None:
    mesh = _strip_mesh()
    curve = FoldingCurve((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), 0.0, 0.0)
    result = deform_mesh(mesh, _plane(), curve)
    assert result.vertices == pytest.approx(mesh.vertices)
    assert result.triangles == mesh.triangles


def test_only_vertices_between_start_and_end_are_deformed() -> None:
    vertices = [(-1.0, 0.5, 0.0), (0.0, 0.5, 0.0), (5.0, 0.5, 0.0), (10.0, 0.5, 0.0), (11.0, 0.5, 0.0)]
    curve = FoldingCurve((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), 4.0, 4.0)
    result = deform_vertices(vertices, _plane(), curve)
    assert result[0] == pytest.approx(vertices[0])
    assert result[1] == pytest.approx(vertices[1])
    assert result[3] == pytest.approx(vertices[3])
    assert result[4] == pytest.approx(vertices[4])
    assert result[2][1] > 4.0


def test_curve_joins_the_unchanged_mesh_with_zero_endpoint_tangent() -> None:
    curve = FoldingCurve((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), 6.0, -4.0)
    points = sample_curve(_plane(), curve, count=10001)
    assert points[0] == pytest.approx(curve.start, abs=1.0e-9)
    assert points[-1] == pytest.approx(curve.end, abs=1.0e-9)
    first_slope = (points[1][1] - points[0][1]) / (points[1][0] - points[0][0])
    last_slope = (points[-1][1] - points[-2][1]) / (points[-1][0] - points[-2][0])
    assert abs(first_slope) < 0.01
    assert abs(last_slope) < 0.01


def test_applied_mesh_stores_undeformed_source_and_can_be_edited_again() -> None:
    source = _strip_mesh()
    plane = _plane()
    curve = FoldingCurve((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), 3.0, -2.0)
    folded = attach_folding_source(deform_mesh(source, plane, curve), source_mesh=source, plane=plane, curve=curve)
    assert FOLDING_SOURCE_KEY in folded.metadata
    restored = restore_folding_source(folded)
    assert restored is not None
    restored_source, restored_plane, restored_curve = restored
    assert restored_source.vertices == source.vertices
    assert restored_source.triangles == source.triangles
    assert restored_plane.normal == pytest.approx(plane.normal)
    assert restored_curve.control_1_offset_mm == pytest.approx(3.0)
    assert restored_curve.control_2_offset_mm == pytest.approx(-2.0)


def test_creator_lifecycle_stages_applies_and_reopens_editable_folding() -> None:
    store = ModelStore()
    source = _strip_mesh()
    store.set_meshes([source], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)

    session = tool.session
    session.target_object_id = source.mesh_id
    session.target_index = 0
    session.target_name = source.name
    session.source_mesh = source
    session.plane = _plane()
    session.curve = FoldingCurve((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), 4.0, 2.0)
    session.phase = FoldingPhase.ADJUST_CURVE
    assert tool._update_preview(ctx, force=True)
    assert store.has_preview
    assert tool.can_apply(ctx)
    assert tool.apply(ctx)
    assert not store.has_preview
    assert FOLDING_SOURCE_KEY in store.committed_meshes[0].metadata

    second = FoldingCreatorTool()
    second.open(ctx)
    assert second._select_target(ctx, source.mesh_id, 0)
    assert second.session.phase is FoldingPhase.ADJUST_CURVE
    assert second.session.editing_existing is True
    assert second.session.source_mesh.vertices == source.vertices
    second.cancel(ctx)
    assert not store.has_preview


def test_viewport_interaction_declares_all_five_workflow_steps() -> None:
    store = ModelStore()
    store.set_meshes([_strip_mesh()], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    assert tuple(step.id for step in ctx.workflow.state.steps) == ("mesh", "face", "start", "end", "curve")
    assert ctx.inspector.panel.id == "folding.tool"
    assert ctx.inspector.field_state("folding_control_1").enabled is False


def test_full_click_workflow_selects_mesh_face_and_interval() -> None:
    mesh = _strip_mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)

    class PickScene:
        def pick_object_at(self, _screen_pos, **_filters):
            return {"kind": "object", "object_id": mesh.mesh_id, "object_index": 0}

        def pick_face_at(self, _screen_pos, **_filters):
            return {
                "kind": "face",
                "object_id": mesh.mesh_id,
                "object_index": 0,
                "element_index": 3,
                "world_pos": (1.0, 0.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

    ctx = ToolContext(scene=PickScene())
    ctx.document.bind(store)
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    tool = FoldingCreatorTool()
    tool.open(ctx)

    def click(x, y):
        assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx) is False
        return tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), button=MouseButton.LEFT), ctx)

    assert click(5.0, 5.0)
    assert tool.session.phase is FoldingPhase.SELECT_FACE
    assert click(5.0, 5.0)
    assert tool.session.phase is FoldingPhase.PLACE_START
    assert click(0.0, 0.0)
    assert tool.session.phase is FoldingPhase.PLACE_END
    assert click(10.0, 0.0)
    assert tool.session.phase is FoldingPhase.ADJUST_CURVE
    assert store.has_preview
    ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_FOLDING).items()}
    assert {"folding:start", "folding:end", "folding:curve", "folding:control:1", "folding:control:2"}.issubset(ids)


def test_camera_drag_is_not_interpreted_as_a_folding_click() -> None:
    mesh = _strip_mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)

    class PickScene:
        def pick_object_at(self, _screen_pos, **_filters):
            return {"kind": "object", "object_id": mesh.mesh_id, "object_index": 0}

    ctx = ToolContext(scene=PickScene())
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 10.0), button=MouseButton.LEFT), ctx) is False
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(40.0, 30.0), button=MouseButton.LEFT), ctx) is False
    assert tool.session.phase is FoldingPhase.SELECT_MESH
