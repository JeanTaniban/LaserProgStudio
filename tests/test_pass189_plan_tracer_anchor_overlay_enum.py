from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.projected_drawing import ProjectedHandle
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _FaceScene:
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


class _Owner:
    def __init__(self) -> None:
        self.locked_views: list[str] = []

    def _camera_forward_vector(self):
        return (-1.0, 0.0, 0.0)

    def _set_fixed_orthographic_view(self, view_id: str) -> None:
        self.locked_views.append(str(view_id))


def _ctx(*, owner: _Owner | None = None) -> ToolContext:
    ctx = ToolContext(owner=owner)
    ctx.scene = _FaceScene()
    ctx.pick.bind_context(ctx)
    return ctx


def test_plan_trace_keeps_opening_view_until_surface_anchor_prompt_is_completed() -> None:
    owner = _Owner()
    ctx = _ctx(owner=owner)
    tool = PlanTrace2DCreatorTool()

    tool.on_open(ctx)

    assert tool._state.view.value == "right"
    assert owner.locked_views == []
    prompt = ctx.overlay.window("plan_trace_2d.anchor_prompt")
    assert prompt is not None
    assert ctx.overlay.window("plan_trace_2d.toolbox") is None or not ctx.overlay.window("plan_trace_2d.toolbox").visible
    assert prompt.buttons == []
    fields = {field.id: field.value for field in prompt.fields}
    assert "Select a scene surface" in fields["plan_trace_2d.anchor_prompt"]


def test_plan_trace_anchor_click_adds_visible_target_and_offsets_drawing_plane() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), world_pos=(1.0, 2.0, 7.0), button=MouseButton.LEFT),
        ctx,
    )

    assert tool._state.plane is not None
    assert tool._state.display_plane is not None
    assert tool._state.plane.depth == 7.0
    assert tool._state.display_plane.depth == 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET
    assert tool._state.anchor_world == (1.0, 2.0, 7.0)
    anchor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:height_anchor")
    assert anchor is not None
    assert anchor.metadata["plan_trace_role"] == "height_anchor"
    assert anchor.metadata["point_style"] == "target"
    handle = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(f"{TOOL_PLAN_TRACE}:height_anchor")
    assert isinstance(handle, ProjectedHandle) and handle.shape.value == "target"
    assert ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE) == ()


def test_plan_trace_overlay_is_the_only_drawing_mode_source() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    # No drawing mode can be selected before the raycast anchor prompt is completed.
    assert ctx.overlay.toggle_button("plan_trace_2d.tool.line") is False
    tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), world_pos=(1.0, 2.0, 7.0), button=MouseButton.LEFT),
        ctx,
    )
    ctx.overlay.toggle_button("plan_trace_2d.tool.line")
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(3.0, 4.0), world_pos=(3.0, 4.0, 7.0)), ctx)

    assert tool._state.active_tool == "line"
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.line"
    assert sum(1 for button in ctx.overlay.buttons.values() if button.group == "plan_trace_2d.tool" and button.checked) == 1
    panel_source = Path("src/laserprog_studio/tooling/plan_trace_2d_tool.py").read_text(encoding="utf-8")
    assert 'buttons=(("reset", "Reset"),)' in panel_source
    assert '"modify": lambda' not in panel_source
    assert '"point": lambda' not in panel_source


def test_plan_trace_anchor_transition_syncs_persistent_mode_toolbox(monkeypatch) -> None:
    """Regression guard for the real desktop overlay after the anchor click.

    The drawing-mode toolbar must be materialised as soon as the plan height is
    picked, before later actor/viewport rendering work can fail or be deferred.
    """

    ctx = _ctx(owner=SimpleNamespace())
    calls: list[tuple[object, object]] = []

    def fake_sync(owner: object, manager: object) -> int:
        calls.append((owner, manager))
        return 1

    monkeypatch.setattr("laserprog_studio.tool_core.overlay.sync_qt_overlay_windows", fake_sync)

    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    calls.clear()

    tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), world_pos=(1.0, 2.0, 7.0), button=MouseButton.LEFT),
        ctx,
    )

    toolbox = ctx.overlay.window("plan_trace_2d.toolbox")
    assert toolbox is not None
    assert toolbox.visible is True
    assert toolbox.persistent is True
    assert ctx.overlay.window("plan_trace_2d.anchor_prompt").visible is False  # type: ignore[union-attr]
    assert [button.id for button in toolbox.buttons if button.group == "plan_trace_2d.tool"] == [
        "plan_trace_2d.tool.modify",
        "plan_trace_2d.tool.point",
        "plan_trace_2d.tool.line",
        "plan_trace_2d.tool.polyline",
        "plan_trace_2d.tool.rectangle",
        "plan_trace_2d.tool.circle",
        "plan_trace_2d.tool.half_circle",
        "plan_trace_2d.tool.arc",
        "plan_trace_2d.tool.bezier",
        "plan_trace_2d.tool.dimension",
        "plan_trace_2d.tool.mesh_trace",
    ]
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.point"
    assert calls and calls[0] == (ctx.owner, ctx.overlay)


def test_planar_drawing_api_documents_visible_anchor_offset() -> None:
    assert plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET > 0.0
    picked = plan2d.pick_plan_height(_ctx(), (3.0, 4.0), event_world_pos=(3.0, 4.0, 7.0), view="top")
    visible = plan2d.offset_plan_height_pick_for_visibility(picked, margin_world=0.5)
    assert visible.plane.depth == 7.5
    assert visible.world_pos == (3.0, 4.0, 7.5)


def test_plan_tracer_docs_explain_opening_camera_anchor_target_and_overlay_enum() -> None:
    doc = Path("docs/tool_creator/17_plan_tracer_2d.md").read_text(encoding="utf-8")
    assert "Click the anchor height point" in doc
    assert "target" in doc
    assert "overlay is the only drawing-mode source" in doc
    assert "exclusive enum" in doc
    assert "fallback depth `0`" in doc
