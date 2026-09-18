# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.free_space import resolve_cloth_point
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.picking import ClothSnapTargetCache
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool
from laserprog_studio.tooling.ids import TOOL_CLOTH
from laserprog_studio.tool_api.tracing import TraceMode


def _context() -> ToolContext:
    ctx = ToolContext()
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    return ctx


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float, z: float = 0.0) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, z), button=MouseButton.LEFT), ctx) is False
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, z), button=MouseButton.LEFT), ctx)


def test_three_independent_lines_create_a_face_as_soon_as_the_loop_closes() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_line", ctx)
    for a, b in (((0.0, 0.0), (20.0, 0.0)), ((20.0, 0.0), (10.0, 15.0)), ((10.0, 15.0), (0.0, 0.0))):
        _click(tool, ctx, *a)
        _click(tool, ctx, *b)
    assert len(tool.session.document.curves) == 3
    assert len(tool.session.document.patches) == 1
    assert "automatically" in tool.session.status.lower()
    assert tool.can_apply(ctx)


def test_arc_and_line_loop_create_a_face_without_manual_face_mode() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    drawing.begin(TraceMode.ARC)
    drawing.add_position((0.0, 0.0, 0.0))
    drawing.add_position((20.0, 0.0, 0.0))
    arc = drawing.add_position((10.0, 10.0, 0.0))
    assert arc.committed and len(document.patches) == 0

    drawing.begin(TraceMode.LINE)
    drawing.add_position((20.0, 0.0, 0.0), existing_point_id="p2")
    closing = drawing.add_position((0.0, 0.0, 0.0), existing_point_id="p1")
    assert closing.committed
    assert closing.created_patch_id is not None
    assert len(document.patches) == 1


def test_smart_snap_exposes_midpoint_center_and_official_plan_cursor_styles() -> None:
    ctx = _context()
    document = ClothDocument()
    a = document.add_point((0.0, 0.0, 0.0))
    b = document.add_point((20.0, 0.0, 0.0))
    document.add_line(a.id, b.id)
    cache = ClothSnapTargetCache()
    placement = resolve_cloth_point(
        ctx,
        (10.0, 1.0),
        document=document,
        owner_tool=TOOL_CLOTH,
        event_world_pos=(10.0, 1.0, 0.0),
        snap_target_cache=cache,
    )
    assert placement.position == (10.0, 0.0, 0.0)
    assert placement.snap_kind == "midpoint"
    assert placement.label == "Midpoint"

    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._bind_session(tool._machine.start_new())
    tool.session.document.points = document.points
    tool.session.document.curves = document.curves
    tool.session.document.revision = document.revision
    tool._interaction.enter_draw()
    tool._drawing.begin("line")
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(10.0, 1.0), world_pos=(10.0, 1.0, 0.0), button=MouseButton.NONE), ctx)
    cursor = ctx.projected_drawing.for_tool(TOOL_CLOTH).get("cloth:cursor")
    assert cursor is not None
    metadata = dict(cursor.metadata)
    assert metadata["plan_trace_role"] == "cursor"
    assert metadata["snap_kind"] == "midpoint"
    from laserprog_studio.tool_api.plan2d import snap_cursor_style_for_kind

    assert metadata["point_style"] == snap_cursor_style_for_kind("midpoint").point_style


def test_cursor_moves_do_not_rebuild_the_surface_mesh(monkeypatch) -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    for point in ((0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)):
        _click(tool, ctx, *point)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}close_polyline", ctx)

    import laserprog_studio.tooling.cloth.rendering as rendering

    real_builder = rendering.build_cloth_surface_mesh
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_builder(*args, **kwargs)

    monkeypatch.setattr(rendering, "build_cloth_surface_mesh", counted)
    # Force exactly one document-side rebuild, then exercise the hot cursor path.
    tool._renderer._surface_cache_revision = -1
    tool._renderer._static_signature = None
    tool._renderer.sync(ctx)
    assert calls == 1
    for index in range(25):
        tool.on_event(
            ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(50.0 + index, 10.0), world_pos=(50.0 + index, 10.0, 0.0), button=MouseButton.NONE),
            ctx,
        )
    assert calls == 1


def test_command_deck_marks_faces_as_automatic_and_keeps_manual_repair_secondary() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert window is not None and window.overlay_kind == "command_deck"
    labels = {button.display_label for button in window.buttons}
    assert {
        "Draw textile",
        "Textile properties",
        "Create from mesh",
        "Join textile faces",
        "Draw polyline",
        "Flat preview",
        "Apply",
    }.issubset(labels)
    assert all((button.slot_width_px or 0) <= 124 for button in window.buttons)


def test_auto_face_can_create_an_adjacent_panel_across_one_shared_edge() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)

    def line(a, b, *, a_id=None, b_id=None):
        drawing.begin(TraceMode.LINE)
        drawing.add_position(a, existing_point_id=a_id)
        return drawing.add_position(b, existing_point_id=b_id)

    line((0.0, 0.0, 0.0), (20.0, 0.0, 0.0))
    line((20.0, 0.0, 0.0), (10.0, 15.0, 0.0), a_id="p2")
    first = line((10.0, 15.0, 0.0), (0.0, 0.0, 0.0), a_id="p3", b_id="p1")
    assert first.created_patch_id is not None
    assert len(document.patches) == 1

    line((20.0, 0.0, 0.0), (30.0, 15.0, 0.0), a_id="p2")
    second = line((30.0, 15.0, 0.0), (10.0, 15.0, 0.0), b_id="p3")
    assert second.created_patch_id is not None
    assert len(document.patches) == 2
    assert len(document.folds) == 1


def test_auto_face_does_not_duplicate_an_existing_boundary() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    for a, b, a_id, b_id in (
        ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), None, None),
        ((20.0, 0.0, 0.0), (10.0, 15.0, 0.0), "p2", None),
        ((10.0, 15.0, 0.0), (0.0, 0.0, 0.0), "p3", "p1"),
    ):
        drawing.begin(TraceMode.LINE)
        drawing.add_position(a, existing_point_id=a_id)
        drawing.add_position(b, existing_point_id=b_id)
    assert len(document.patches) == 1

    # Recommitting an already existing boundary must not create an overlapping panel.
    drawing.begin(TraceMode.LINE)
    drawing.add_position((0.0, 0.0, 0.0), existing_point_id="p1")
    result = drawing.add_position((20.0, 0.0, 0.0), existing_point_id="p2")
    assert result.committed
    assert len(document.patches) == 1
