# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from types import SimpleNamespace

from laserprog_studio.application.creator_pointer_interaction import (
    creator_camera_navigation_active,
    handle_creator_tool_pointer_event,
)
from laserprog_studio.application.creator_scene_picking import bind_creator_scene_picking
from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.interaction import ClothUxStage
from laserprog_studio.tooling.cloth.picking import face_vertices_for_pick
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool
from laserprog_studio.tooling.folding.models import FoldingPhase
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter


class _Points:
    def __init__(self, values):
        self.values = tuple(values)

    def GetNumberOfPoints(self):
        return len(self.values)

    def GetPoint(self, index):
        return self.values[index]


class _Cell:
    def __init__(self, values, point_ids=(0, 1, 2)):
        self.values = values
        self.point_ids = point_ids

    def GetPoints(self):
        return _Points(self.values)

    def GetPointIds(self):
        return _PointIds(self.point_ids)


class _PointIds:
    def __init__(self, values):
        self.values = tuple(values)

    def GetNumberOfIds(self):
        return len(self.values)

    def GetId(self, index):
        return self.values[index]


class _Dataset:
    values = ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 8.0, 0.0))

    def GetCell(self, _index):
        return _Cell(self.values)

    def GetPoint(self, index):
        return self.values[index]


class _Mapper:
    def GetInput(self):
        return _Dataset()


class _Actor:
    def GetVisibility(self):
        return 1

    def GetPickable(self):
        return 1

    def GetMapper(self):
        return _Mapper()

    def GetAddressAsString(self, _prefix):
        return "actor-0"


class _Picker:
    def __init__(self, actor):
        self.actor = actor

    def SetTolerance(self, _value):
        pass

    def PickFromListOn(self):
        pass

    def AddPickList(self, _actor):
        pass

    def Pick(self, _x, _y, _z, _renderer):
        return 1

    def GetActor(self):
        return self.actor

    def GetViewProp(self):
        return self.actor

    def GetCellId(self):
        return 0

    def GetPickPosition(self):
        return (4.0, 2.0, 0.0)

    def GetPickNormal(self):
        return (0.0, 0.0, 1.0)


class _VtkModule:
    def __init__(self, actor):
        self.actor = actor

    def vtkCellPicker(self):
        return _Picker(self.actor)

    def vtkPropPicker(self):
        return _Picker(self.actor)


def _mesh() -> WorkMesh:
    return WorkMesh(
        name="Plan Tracer output",
        vertices=[
            (0.0, 0.0, 0.0),
            (20.0, 0.0, 0.0),
            (20.0, 8.0, 0.0),
            (0.0, 8.0, 0.0),
            (0.0, 0.0, 2.0),
            (20.0, 0.0, 2.0),
            (20.0, 8.0, 2.0),
            (0.0, 8.0, 2.0),
        ],
        triangles=[
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
        ],
        color="#88AA44",
    )


def _live_context(monkeypatch):
    mesh = _mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    actor = _Actor()
    owner = SimpleNamespace(
        actors_by_index={0: actor},
        plotter=SimpleNamespace(renderer=object(), height=lambda: 600.0),
        _qt_to_vtk_candidates=lambda _x, _y: [(100, 200, "primary")],
        _resolve_picked_actor=lambda picked: ("mesh", 0) if picked is actor else None,
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    monkeypatch.setitem(sys.modules, "vtk", _VtkModule(actor))
    assert bind_creator_scene_picking(ctx, owner)
    return ctx, mesh


def test_live_creator_picker_resolves_object_face_and_displayed_cell(monkeypatch) -> None:
    ctx, mesh = _live_context(monkeypatch)

    obj = ctx.pick.object_at((100.0, 100.0))
    face = ctx.pick.face_at((100.0, 100.0))

    assert obj.hit and obj.kind == "object"
    assert obj.object_id == mesh.mesh_id and obj.object_index == 0
    assert face.hit and face.kind == "face"
    assert face.world_pos == (4.0, 2.0, 0.0)
    assert face.normal == (0.0, 0.0, 1.0)
    assert face_vertices_for_pick(ctx, face) == (
        (0.0, 0.0, 0.0),
        (20.0, 0.0, 0.0),
        (20.0, 8.0, 0.0),
    )


def test_live_creator_picker_resolves_nearest_displayed_mesh_edge(monkeypatch) -> None:
    ctx, mesh = _live_context(monkeypatch)

    edge = ctx.pick.edge_at((100.0, 100.0))

    assert edge.hit and edge.kind == "edge"
    assert edge.object_id == mesh.mesh_id and edge.object_index == 0
    # Pick position (4, 2) lies closest to the triangle's diagonal edge.
    assert edge.metadata["edge_vertex_indices"] == (2, 0)
    assert edge.metadata["edge_vertices"] == ((20.0, 8.0, 0.0), (0.0, 0.0, 0.0))


def test_folding_can_select_a_plan_tracer_mesh_through_live_picker(monkeypatch) -> None:
    ctx, mesh = _live_context(monkeypatch)
    tool = FoldingCreatorTool()
    tool.open(ctx)

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 100.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(101.0, 100.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_press_passthrough(press, ctx)
    assert tool.wants_pointer_release_passthrough(release, ctx)
    assert tool.on_event(release, ctx)

    assert tool.session.target_object_id == mesh.mesh_id
    assert tool.session.phase is FoldingPhase.SELECT_FACE


def test_cloth_uses_a_live_mesh_face_as_the_first_3d_point_without_locking_a_plane(monkeypatch) -> None:
    ctx, _mesh = _live_context(monkeypatch)
    tool = ClothCreatorTool()
    tool.open(ctx)

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 100.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(101.0, 100.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_press_passthrough(press, ctx)
    assert tool.wants_pointer_release_passthrough(release, ctx)
    assert tool.on_event(release, ctx)

    assert tool.interaction.stage is ClothUxStage.DRAW
    assert tool.interaction.active_plane is None
    assert tool.interaction.reference_face_index is None
    assert tool._drawing.pending_world_points == ((4.0, 2.0, 0.0),)


def test_creator_runtime_installs_live_picking_backend_on_the_viewport(monkeypatch) -> None:
    ctx, _mesh = _live_context(monkeypatch)
    owner = ctx.owner
    # Force the runtime path to perform the installation itself.
    delattr(ctx.viewport, "pick_object_at")
    delattr(ctx.viewport, "pick_face_at")
    delattr(ctx.viewport, "pick_edge_at")
    ctx.viewport._creator_scene_picking_owner = None
    adapter = CreatorStudioToolAdapter(
        spec=ToolSpec(id="folding", label="Folding", category="tool", panel_index=0),
        creator=FoldingCreatorTool(),
    )
    app_context = SimpleNamespace(tool_context=ctx, owner=owner, active_scene=ctx.document.raw)

    resolved = adapter.tool_context(app_context)

    assert callable(getattr(resolved.viewport, "pick_object_at", None))
    assert callable(getattr(resolved.viewport, "pick_face_at", None))
    assert callable(getattr(resolved.viewport, "pick_edge_at", None))


def test_picking_facade_continues_after_a_scene_backend_miss(monkeypatch) -> None:
    ctx, mesh = _live_context(monkeypatch)
    ctx.scene = SimpleNamespace(pick_object_at=lambda _screen, **_filters: None)

    result = ctx.pick.object_at((100.0, 100.0))

    assert result.hit
    assert result.object_id == mesh.mesh_id


class _Qt:
    LeftButton = 1
    MiddleButton = 2
    RightButton = 4
    NoButton = 0
    ShiftModifier = 8
    ControlModifier = 16
    AltModifier = 32


class _QEvent:
    MouseButtonPress = 1
    MouseMove = 2
    MouseButtonRelease = 3
    MouseButtonDblClick = 4


class _MouseEvent:
    def __init__(self, button=_Qt.LeftButton):
        self._button = button

    def button(self):
        return self._button

    def modifiers(self):
        return _Qt.NoButton


def test_shared_pointer_bridge_keeps_small_jitter_as_click_candidate() -> None:
    ctx = ToolContext()
    calls = {"begin": 0, "events": 0}

    class _Creator:
        def wants_pointer_press_passthrough(self, event, _ctx):
            return event.button is MouseButton.LEFT

        def on_camera_interaction_begin(self, _ctx, **_payload):
            calls["begin"] += 1

    creator = _Creator()

    class _Tool:
        id = "folding"

        def __init__(self, creator_obj):
            self.creator = creator_obj

        def tool_context(self, _context):
            return ctx

        def on_event(self, _event, _context):
            calls["events"] += 1
            return False

    tool = _Tool(creator)
    owner = SimpleNamespace(context=SimpleNamespace(), active_tool="folding")

    assert handle_creator_tool_pointer_event(
        owner,
        tool,
        _QEvent.MouseButtonPress,
        _MouseEvent(),
        10.0,
        10.0,
        _Qt.LeftButton,
        Qt=_Qt,
        QEvent=_QEvent,
    ) is False
    assert handle_creator_tool_pointer_event(
        owner,
        tool,
        _QEvent.MouseMove,
        _MouseEvent(),
        13.0,
        12.0,
        _Qt.LeftButton,
        Qt=_Qt,
        QEvent=_QEvent,
    ) is False
    assert creator_camera_navigation_active(owner) is False
    assert calls == {"begin": 0, "events": 0}

    assert handle_creator_tool_pointer_event(
        owner,
        tool,
        _QEvent.MouseMove,
        _MouseEvent(),
        20.0,
        10.0,
        _Qt.LeftButton,
        Qt=_Qt,
        QEvent=_QEvent,
    ) is False
    assert creator_camera_navigation_active(owner) is True
    assert calls["begin"] == 1


def test_consumed_passthrough_release_resets_host_and_vtk_pointer_state() -> None:
    ctx = ToolContext()
    calls: list[bool] = []

    class _Creator:
        def wants_pointer_press_passthrough(self, event, _ctx):
            return event.button is MouseButton.LEFT

        def wants_pointer_release_passthrough(self, event, _ctx):
            return event.button in {MouseButton.LEFT, MouseButton.NONE}

    class _Tool:
        id = "cloth"

        def __init__(self):
            self.creator = _Creator()

        def tool_context(self, _context):
            return ctx

        def on_event(self, event, _context):
            return event.type is ToolEventType.MOUSE_RELEASE

    owner = SimpleNamespace(
        context=SimpleNamespace(),
        active_tool="cloth",
        _reset_viewport_pointer_state=lambda *, release_vtk=True: calls.append(bool(release_vtk)),
    )
    tool = _Tool()

    assert handle_creator_tool_pointer_event(
        owner, tool, _QEvent.MouseButtonPress, _MouseEvent(), 30.0, 40.0, _Qt.LeftButton, Qt=_Qt, QEvent=_QEvent
    ) is False
    assert handle_creator_tool_pointer_event(
        owner, tool, _QEvent.MouseButtonRelease, _MouseEvent(), 31.0, 40.0, _Qt.NoButton, Qt=_Qt, QEvent=_QEvent
    ) is True
    assert calls == [True]


def test_folding_and_cloth_accept_a_nobutton_release_after_a_recorded_press() -> None:
    folding_ctx = ToolContext()
    folding = FoldingCreatorTool()
    folding._pointer_press_screen = (1.0, 1.0)
    assert folding.wants_pointer_release_passthrough(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(1.0, 1.0), button=MouseButton.NONE),
        folding_ctx,
    )

    cloth_ctx = ToolContext()
    cloth = ClothCreatorTool()
    cloth._pointer_press_screen = (1.0, 1.0)
    assert cloth.wants_pointer_release_passthrough(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(1.0, 1.0), button=MouseButton.NONE),
        cloth_ctx,
    )
