from __future__ import annotations

import ast
from pathlib import Path

from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedFace, ProjectedHandle, ProjectedLine, ProjectedText
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.constants import _PENDING_PREVIEW_PREFIX
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _FaceScene:
    def __init__(self) -> None:
        self.meshes = []

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 7.0),
            object_id="part_a",
            object_index=3,
            normal=(0.0, 0.0, 1.0),
        )


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _FaceScene()
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _open_locked() -> tuple[ToolContext, PlanTrace2DCreatorTool]:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    # Keep geometry assertions independent from persisted user snap preferences.
    ctx.snap.set_smart_snap(False)
    ctx.snap.set_grid_snap(False)
    ctx.snap.grid_provider.enabled = False
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT),
        ctx,
    )
    return ctx, tool


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT),
        ctx,
    )


def _metadata(primitive) -> dict[str, object]:
    return dict(getattr(primitive, "metadata", ()))


def test_plan_tracer_runtime_has_no_direct_legacy_render_api_calls() -> None:
    roots = (
        Path("src/laserprog_studio/tooling/plan_trace_2d_tool.py"),
        Path("src/laserprog_studio/tooling/plan_trace_2d"),
        Path("src/laserprog_studio/tool_api/plan2d"),
    )
    files: list[Path] = []
    for root in roots:
        files.extend(root.rglob("*.py") if root.is_dir() else (root,))

    forbidden: list[tuple[str, int, str]] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Name) or node.value.id != "ctx":
                continue
            if node.attr in {"preview", "gizmos", "actor_registry"}:
                forbidden.append((str(path), int(node.lineno), node.attr))
    assert forbidden == []


def test_plan_tracer_points_and_pending_lines_live_only_in_projected_drawing() -> None:
    ctx, tool = _open_locked()
    _click(tool, ctx, 30.0, 40.0)

    point = next(
        primitive
        for primitive in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives
        if isinstance(primitive, ProjectedHandle) and _metadata(primitive).get("plan_trace_role") == "point"
    )
    assert point.position == (30.0, 40.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)

    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(140.0, 130.0)), ctx)
    pending = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(f"{_PENDING_PREVIEW_PREFIX}:line")
    assert isinstance(pending, ProjectedLine)
    assert pending.points[-1] == (140.0, 130.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert _metadata(pending).get("projected_no_selection_actor") is True

    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()
    assert ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE) == ()


def test_plan_tracer_face_selection_feedback_is_projected_and_legacy_stays_empty() -> None:
    ctx, tool = _open_locked()
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 160.0, 140.0)

    face_actor = next(
        actor
        for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE)
        if actor.metadata.get("plan_trace_role") == "face"
    )
    ctx.selection.select(face_actor.id)
    changed = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).sync_interaction_state(render=False)
    face = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(face_actor.id)

    assert changed >= 1
    assert isinstance(face, ProjectedFace)
    assert face.style.fill_color.lower() == "#f0a805"
    assert face.style.outline_color is not None and face.style.outline_color.lower() == "#f0a805"
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()
    assert ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE) == ()


def test_plan2d_face_holes_and_dimension_labels_use_projected_primitives() -> None:
    ctx = _ctx()
    plan2d.register_plan_face(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        face_id="face.hole",
        polygon_world_points=((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 20.0, 0.0), (0.0, 20.0, 0.0)),
        hole_world_polygons=(((5.0, 5.0, 0.0), (15.0, 5.0, 0.0), (15.0, 15.0, 0.0), (5.0, 15.0, 0.0)),),
    )
    plan2d.register_plan_dimension(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        dimension_id="dimension.1",
        dimension_world_line=((0.0, 0.0, 0.0), (20.0, 0.0, 0.0)),
        label_world_pos=(10.0, 3.0, 0.0),
        label="20.00 mm",
    )

    face = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get("face.hole")
    label = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get("dimension.1:label")
    assert isinstance(face, ProjectedFace)
    assert len(face.holes) == 1
    assert isinstance(label, ProjectedText)
    assert label.text == "20.00 mm"
    assert ctx.selection.actor("dimension.1:label") is None
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()
    assert ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE) == ()


def test_plan_tracer_polyline_sync_count_stays_constant_as_sketch_grows(monkeypatch) -> None:
    ctx, tool = _open_locked()
    tool._set_active_tool(ctx, "polyline", reason="performance-test", render=False)
    calls: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        ctx.projected_drawing,
        "_render_tool_now",
        lambda owner, *, render: calls.append((str(owner), bool(render))) or True,
    )

    calls_per_click: list[int] = []
    for index in range(40):
        before = len(calls)
        _click(tool, ctx, 20.0 + index * 8.0, 30.0 + (index % 3) * 11.0)
        calls_per_click.append(len(calls) - before)

    # A click may synchronise the cursor, the committed sketch, and one transient
    # preview visibility update.  The number must not grow with the actor count.
    assert max(calls_per_click) <= 4
    assert max(calls_per_click[-10:]) <= max(calls_per_click[:10]) + 1
    assert len(calls) <= 160

    before_move = len(calls)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(777.0, 66.0)), ctx)
    assert len(calls) - before_move == 1
