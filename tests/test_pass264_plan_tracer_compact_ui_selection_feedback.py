from __future__ import annotations

from laserprog_studio.tool_api import metrics as metric_api
from laserprog_studio.tool_api._ui_motif_builder import CreatorUiMotifBuilder
from laserprog_studio.tool_api import actors as actor_factory
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.overlay import OverlayManager
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tooling.plan_trace_2d.constants import _DELETE_BUTTON_ID, _TOOLBOX_ID


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def test_plan_tracer_toolbox_is_readable_sectioned_and_delete_disabled_until_selection() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = _ctx()
    _lock_plane(tool, ctx)

    toolbox = ctx.overlay.window(_TOOLBOX_ID)
    assert toolbox is not None and toolbox.visible is True
    assert 720 <= toolbox.width_px <= 1240
    assert [section.id for section in toolbox.toolbar_sections] == ["select", "draw", "shapes", "measure", "build"]
    delete = ctx.overlay.button(_DELETE_BUTTON_ID)
    assert delete is not None
    assert delete.enabled is False

    # A Plan tracer selection enables the destructive action; clearing it disables
    # the same global button state again.
    actor = actor_factory.point(
        "plan_trace_2d:test_point",
        (0.0, 0.0, 0.0),
        owner_tool=TOOL_PLAN_TRACE,
        interaction="selectable",
        metadata={"plan_trace_role": "point"},
    )
    ctx.actor_registry(TOOL_PLAN_TRACE).add(actor, replace=True)
    ctx.selection.select(actor.id)
    tool._services.overlay._sync_reports(ctx)
    assert ctx.overlay.button(_DELETE_BUTTON_ID).enabled is True  # type: ignore[union-attr]
    ctx.selection.clear_selection(owner_tool=TOOL_PLAN_TRACE)
    tool._services.overlay._sync_reports(ctx)
    assert ctx.overlay.button(_DELETE_BUTTON_ID).enabled is False  # type: ignore[union-attr]


def test_metric_overlay_spec_is_a_compact_confirmation_bar() -> None:
    session = metric_api.line_metric_session("metric.demo", length=40.0, angle_degrees=180.0)
    window = metric_api.build_metric_edit_window(
        window_id="metric.demo",
        owner_tool="demo",
        session=session,
        validate_button_id="metric.validate",
        cancel_button_id="metric.cancel",
    )

    assert window.width_px <= 420
    assert window.title == ""
    assert [field.label for field in window.fields] == ["Length", "Angle"]
    assert all(button.icon is None for button in window.buttons)
    assert window.cursor_offset_px[1] < 72


def test_creator_ui_interaction_refreshes_public_plan2d_line_selection_feedback() -> None:
    ctx = ToolContext()
    owner = TOOL_PLAN_TRACE
    actor = actor_factory.line(
        f"{owner}:line:edge_1",
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        owner_tool=owner,
        interaction="selectable",
        line_style="grabbable",
        metadata={
            "motif_family": owner,
            "motif_kind": "line",
            "line_style": "grabbable",
            "visual_state": "auto",
            "api_ui_visible": True,
        },
    )
    ctx.actor_registry(owner).add(actor, replace=True)
    ctx.selection.select(actor.id)

    CreatorUiMotifBuilder(ctx, owner_tool=owner).refresh_interaction_visuals()

    selected_previews = [item for item in ctx.preview.items(owner_tool=owner) if item.payload and item.payload.get("style_id") == "selected"]
    assert selected_previews, "selected Plan2D linework must be redrawn with the shared selected style"
    assert selected_previews[0].payload["color"] == "#f0a805"
