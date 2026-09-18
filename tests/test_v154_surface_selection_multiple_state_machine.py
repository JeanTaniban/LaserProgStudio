# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.smart_surface_selection_test_tool import SmartSurfaceSelectionTestCreatorTool


def _cube() -> WorkMesh:
    vertices = [
        (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh("Cube", vertices, triangles)


def _quiet_tool() -> SmartSurfaceSelectionTestCreatorTool:
    tool = SmartSurfaceSelectionTestCreatorTool()
    tool._diagnostics_enabled = False
    tool._diagnostics.enabled = False
    tool._sync = lambda *_args, **_kwargs: None
    tool._update_timing_fields = lambda *_args, **_kwargs: None
    return tool


def test_pointer_state_machine_emits_click_and_rejects_drag() -> None:
    machine = surface_selection.SurfaceSelectionPointerMachine(drag_threshold_px=6.0)

    machine.press((10.0, 10.0))
    assert machine.state is surface_selection.SurfaceSelectionPointerState.PRESSED
    assert machine.release((12.0, 11.0)) is surface_selection.SurfaceSelectionPointerAction.CLICK
    assert machine.state is surface_selection.SurfaceSelectionPointerState.READY

    machine.press((10.0, 10.0))
    machine.move((30.0, 10.0))
    assert machine.state is surface_selection.SurfaceSelectionPointerState.DRAGGING
    assert machine.release((30.0, 10.0)) is surface_selection.SurfaceSelectionPointerAction.NONE
    assert machine.state is surface_selection.SurfaceSelectionPointerState.READY


def test_pointer_state_machine_suppresses_release_after_double_click() -> None:
    machine = surface_selection.SurfaceSelectionPointerMachine()
    machine.press((20.0, 20.0))
    assert machine.double_click((20.0, 20.0)) is surface_selection.SurfaceSelectionPointerAction.DOUBLE_CLICK
    assert machine.state is surface_selection.SurfaceSelectionPointerState.DOUBLE_CLICK_GUARD
    assert machine.release((20.0, 20.0)) is surface_selection.SurfaceSelectionPointerAction.NONE
    assert machine.state is surface_selection.SurfaceSelectionPointerState.READY


def test_session_tracks_multiple_complete_logical_regions() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    first = surface_selection.auto_surface_region(snapshot, 0)
    second = surface_selection.auto_surface_region(snapshot, 4)
    session = surface_selection.SurfaceSelectionSession()

    session.adopt(snapshot, first)
    assert session.selected_region_count == 1
    assert session.selection_mode == "automatic"

    combined = session.add_region(snapshot, second)
    assert set(combined.face_indices) == {0, 1, 4, 5}
    assert session.selected_region_count == 2
    assert session.selection_mode == "multiple"

    duplicate = session.add_region(snapshot, second)
    assert duplicate is combined
    assert session.selected_region_count == 2

    replaced = session.adopt(snapshot, second)
    assert set(replaced.face_indices) == {4, 5}
    assert session.selected_region_count == 1
    assert session.selection_mode == "automatic"


def test_shift_click_adds_algorithmic_region_and_plain_click_replaces() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    regions = {
        0: surface_selection.auto_surface_region(snapshot, 0),
        4: surface_selection.auto_surface_region(snapshot, 4),
    }
    tool = _quiet_tool()
    tool._pick = lambda _ctx, _screen, operation=None: (SimpleNamespace(hit=True), snapshot, int(_screen[0]))
    tool._evaluate = lambda _snapshot, face_index, operation=None: regions[int(face_index)]
    ctx = ToolContext()

    first_click = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(0.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert tool._handle_click(ctx, first_click)
    assert set(tool._session.selected_face_indices) == {0, 1}
    assert tool._session.selected_region_count == 1

    add_click = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(4.0, 0.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    assert tool._handle_click(ctx, add_click)
    assert set(tool._session.selected_face_indices) == {0, 1, 4, 5}
    assert tool._session.selected_region_count == 2

    replace_click = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(4.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert tool._handle_click(ctx, replace_click)
    assert set(tool._session.selected_face_indices) == {4, 5}
    assert tool._session.selected_region_count == 1


def test_double_click_only_clears_when_pointer_is_in_empty_space() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    region = surface_selection.auto_surface_region(snapshot, 0)
    tool = _quiet_tool()
    tool._session.adopt(snapshot, region)
    ctx = ToolContext()

    tool._pick = lambda _ctx, _screen, operation=None: (SimpleNamespace(hit=True), snapshot, 0)
    face_double = ToolEvent(
        ToolEventType.MOUSE_DOUBLE_CLICK,
        screen_pos=(10.0, 10.0),
        button=MouseButton.LEFT,
    )
    assert tool._handle_double_click(ctx, face_double)
    assert set(tool._session.selected_face_indices) == {0, 1}

    tool._pick = lambda _ctx, _screen, operation=None: (SimpleNamespace(hit=False), None, None)
    empty_double = ToolEvent(
        ToolEventType.MOUSE_DOUBLE_CLICK,
        screen_pos=(50.0, 50.0),
        button=MouseButton.LEFT,
    )
    assert tool._handle_double_click(ctx, empty_double)
    assert tool._session.result is None
    assert tool._session.selection_mode == "empty"


def test_test_tool_has_no_editable_double_click_ui_or_backend(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tool = SmartSurfaceSelectionTestCreatorTool()
    ctx = ToolContext()
    tool.on_open(ctx)
    try:
        panel = ctx.inspector.panel
        assert panel is not None
        assert "region_count" in panel.field_ids()
        assert "editable_auto_double_click" not in panel.field_ids()
    finally:
        tool.on_close(ctx)

    source_path = __import__(
        "laserprog_studio.tooling.smart_surface_selection_test_tool",
        fromlist=["SmartSurfaceSelectionTestCreatorTool"],
    ).__file__
    source = open(source_path, encoding="utf-8").read()
    assert "begin_editable_auto" not in source
    assert "auto_edit_active" not in source
    assert "editable_auto_selection" not in source


def test_tool_event_machine_never_turns_double_click_release_into_click() -> None:
    tool = _quiet_tool()
    calls = {"click": 0, "double": 0}
    tool._handle_click = lambda _ctx, _event: calls.__setitem__("click", calls["click"] + 1) or True
    tool._handle_double_click = lambda _ctx, _event: calls.__setitem__("double", calls["double"] + 1) or True
    ctx = ToolContext()

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 10.0), button=MouseButton.LEFT)
    double = ToolEvent(ToolEventType.MOUSE_DOUBLE_CLICK, screen_pos=(10.0, 10.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(10.0, 10.0), button=MouseButton.LEFT)

    assert tool.on_event(press, ctx) is False
    assert tool.on_event(double, ctx) is True
    assert tool.on_event(release, ctx) is True
    assert calls == {"click": 0, "double": 1}


def test_tool_event_machine_never_turns_camera_drag_into_click() -> None:
    tool = _quiet_tool()
    calls = {"click": 0}
    tool._handle_click = lambda _ctx, _event: calls.__setitem__("click", calls["click"] + 1) or True
    ctx = ToolContext()

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 10.0), button=MouseButton.LEFT)
    move = ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(30.0, 10.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(30.0, 10.0), button=MouseButton.LEFT)

    assert tool.on_event(press, ctx) is False
    tool.on_event(move, ctx)
    assert tool.on_event(release, ctx) is True
    assert calls["click"] == 0
