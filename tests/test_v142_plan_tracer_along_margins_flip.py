from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.duplicate import (
    DUPLICATE_OPTIONS_WINDOW_ID,
    _FIELD_EDGE_END_MARGIN,
    _FIELD_EDGE_START_MARGIN,
)
from laserprog_studio.tooling.plan_trace_2d.prefabs import PlanTracePrefab
from laserprog_studio.tooling.plan_trace_2d.selection_edit import SketchPayload
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 0.0),
            object_id="ground",
            object_index=0,
        )


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    tool.on_open(ctx)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    return tool, ctx


def _add_line(tool: PlanTrace2DCreatorTool, ctx: ToolContext, length: float = 100.0):
    p0 = tool._state.sketch.add_point((0.0, 0.0), point_id="plan_trace:point:margin0")
    p1 = tool._state.sketch.add_point((length, 0.0), point_id="plan_trace:point:margin1")
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(line.id))
    return line


def _payload() -> SketchPayload:
    return SketchPayload(
        points={"a": (1.0, 2.0), "b": (3.0, 2.0)},
        lines=[{"start": "a", "end": "b", "metadata": {}}],
        pivot=(0.0, 0.0),
    )


def test_v142_along_respects_independent_start_and_end_margins() -> None:
    tool, ctx = _open()
    _add_line(tool, ctx)
    service = tool._services.duplicate
    service.copy_count = 3
    service.edge_start_margin = 10.0
    service.edge_end_margin = 20.0

    samples = service._along_samples(ctx)

    assert [round(sample.point[0], 6) for sample in samples] == [10.0, 45.0, 80.0]
    assert all(abs(sample.point[1]) <= 1.0e-9 for sample in samples)


def test_v142_along_rejects_margins_that_leave_no_distribution_length() -> None:
    tool, ctx = _open()
    _add_line(tool, ctx)
    service = tool._services.duplicate
    service.copy_count = 2
    service.edge_start_margin = 60.0
    service.edge_end_margin = 40.0

    assert service._along_samples(ctx) == []

    service.copy_count = 1
    samples = service._along_samples(ctx)
    assert len(samples) == 1
    assert samples[0].point == (60.0, 0.0)


def test_v142_preview_limit_is_a_subset_of_final_margin_distribution() -> None:
    tool, ctx = _open()
    _add_line(tool, ctx)
    service = tool._services.duplicate
    service.copy_count = 401
    service.edge_start_margin = 10.0
    service.edge_end_margin = 10.0

    final_x = {round(sample.point[0], 9) for sample in service._along_samples(ctx)}
    preview = service._along_samples(ctx, preview_limit=17)

    assert len(preview) == 17
    assert all(round(sample.point[0], 9) in final_x for sample in preview)
    assert preview[0].point[0] == 10.0
    assert preview[-1].point[0] == 90.0


def test_v142_flip_reflects_on_local_x_axis_independently_from_mirror() -> None:
    payload = _payload()
    service_type = type(PlanTrace2DCreatorTool()._services.duplicate)

    normal = service_type._payload_preview_points(payload, target=(10.0, 10.0))
    mirrored = service_type._payload_preview_points(payload, target=(10.0, 10.0), mirror_y=True)
    flipped = service_type._payload_preview_points(payload, target=(10.0, 10.0), mirror_x=True)
    both = service_type._payload_preview_points(payload, target=(10.0, 10.0), mirror_x=True, mirror_y=True)

    assert normal == ((11.0, 12.0), (13.0, 12.0))
    assert mirrored == ((11.0, 8.0), (13.0, 8.0))
    assert flipped == ((9.0, 12.0), (7.0, 12.0))
    assert both == ((9.0, 8.0), (7.0, 8.0))


def test_v142_paste_payload_applies_flip_to_real_geometry() -> None:
    tool, ctx = _open()
    result = tool._services.selection_edit.paste_payload(
        ctx,
        _payload(),
        target=(10.0, 10.0),
        mirror_x=True,
        mirror_y=True,
        compile_after=False,
        select_created=False,
    )
    positions = tuple(tool._state.sketch.points[point_id].position for point_id in result.point_ids)
    assert positions == ((9.0, 8.0), (7.0, 8.0))


def test_v142_along_overlay_exposes_margins_and_flip(monkeypatch) -> None:
    prefab = PlanTracePrefab("user:test", "Test", _payload())
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (prefab,))
    tool, ctx = _open()
    _add_line(tool, ctx)
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.selected_prefab_id = prefab.id
    service.stage = "edge"
    service._sync(ctx, render=False)

    options = ctx.overlay.window(DUPLICATE_OPTIONS_WINDOW_ID)
    assert options is not None
    assert options.width_px <= 310
    field_ids = {field.id for field in options.fields}
    assert {_FIELD_EDGE_START_MARGIN, _FIELD_EDGE_END_MARGIN}.issubset(field_ids)
    labels = {button.label for button in options.buttons}
    assert {"Follow", "Mirror", "Flip", "Build", "Cancel"}.issubset(labels)
