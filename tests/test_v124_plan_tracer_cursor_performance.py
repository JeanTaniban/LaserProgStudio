from __future__ import annotations

from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api.plan2d.actors import register_plan_cursor, sync_plan_actor_visuals
from laserprog_studio.tool_core.context import ToolContext


def test_projected_batch_collapses_cursor_and_preview_updates_into_one_incremental_delta() -> None:
    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("plan_trace")
    registry.add(
        draw2d.line(
            "plan_trace:preview",
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            interaction="fixed",
        ),
        render=False,
    )
    register_plan_cursor(
        ctx,
        owner_tool="plan_trace",
        cursor_id="plan_trace:cursor",
        world_pos=(1.0, 0.0, 0.0),
        visible=True,
        snap_kind="free",
        snapped=False,
    )
    base_revision = ctx.projected_drawing.state_token("plan_trace")[0]

    with registry.batch():
        registry.add(
            draw2d.line(
                "plan_trace:preview",
                (0.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                interaction="fixed",
            ),
            replace=True,
            render=False,
        )
        register_plan_cursor(
            ctx,
            owner_tool="plan_trace",
            cursor_id="plan_trace:cursor",
            world_pos=(2.0, 0.0, 0.0),
            visible=True,
            snap_kind="free",
            snapped=False,
        )

    revision = ctx.projected_drawing.state_token("plan_trace")[0]
    change = ctx.projected_drawing._change_for("plan_trace", revision)
    assert revision == base_revision + 2
    assert change is not None
    assert change.operation == "update_many"
    assert change.base_revision == base_revision
    assert {item.id for item in change.before} == {"plan_trace:preview", "plan_trace:cursor"}
    assert {item.id for item in change.after} == {"plan_trace:preview", "plan_trace:cursor"}


def test_position_only_plan_actor_sync_skips_owner_wide_interaction_scan(monkeypatch) -> None:
    ctx = ToolContext()
    register_plan_cursor(
        ctx,
        owner_tool="plan_trace",
        cursor_id="plan_trace:cursor",
        world_pos=(1.0, 0.0, 0.0),
        visible=True,
        snap_kind="free",
        snapped=False,
    )
    interaction_calls: list[str] = []
    monkeypatch.setattr(
        ctx.projected_drawing,
        "sync_interaction_state",
        lambda owner_tool, *, render=True: interaction_calls.append(str(owner_tool)) or 0,
    )

    sync_plan_actor_visuals(
        ctx,
        owner_tool="plan_trace",
        changed_actor_ids=("plan_trace:cursor",),
        position_only=True,
        render=False,
    )
    assert interaction_calls == []

    sync_plan_actor_visuals(
        ctx,
        owner_tool="plan_trace",
        changed_actor_ids=("plan_trace:cursor",),
        position_only=False,
        render=False,
    )
    assert interaction_calls == ["plan_trace"]
