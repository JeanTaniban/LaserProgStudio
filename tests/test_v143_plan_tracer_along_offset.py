from __future__ import annotations

import math

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.duplicate import (
    DUPLICATE_OPTIONS_WINDOW_ID,
    _FIELD_EDGE_OFFSET,
    _PathSample,
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


def _payload() -> SketchPayload:
    return SketchPayload(
        points={"a": (0.0, 0.0), "b": (2.0, 0.0)},
        lines=[{"start": "a", "end": "b", "metadata": {}}],
        pivot=(0.0, 0.0),
    )


def _add_line(tool: PlanTrace2DCreatorTool, ctx: ToolContext, length: float = 100.0) -> None:
    p0 = tool._state.sketch.add_point((0.0, 0.0), point_id="plan_trace:point:offset0")
    p1 = tool._state.sketch.add_point((length, 0.0), point_id="plan_trace:point:offset1")
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(line.id))


def test_v143_offset_uses_path_normal_even_when_follow_is_disabled() -> None:
    service = PlanTrace2DCreatorTool()._services.duplicate
    service.edge_normal_offset = 8.0
    service.follow_rotation = False

    horizontal = service._along_target(_PathSample((12.0, 20.0), 0.0))
    vertical = service._along_target(_PathSample((12.0, 20.0), math.pi / 2.0))

    assert horizontal == (12.0, 28.0)
    assert abs(vertical[0] - 4.0) <= 1.0e-9
    assert abs(vertical[1] - 20.0) <= 1.0e-9


def test_v143_mirror_reverses_offset_side_without_changing_magnitude() -> None:
    service = PlanTrace2DCreatorTool()._services.duplicate
    service.edge_normal_offset = 6.5
    sample = _PathSample((40.0, 10.0), 0.0)

    assert service._along_target(sample) == (40.0, 16.5)
    service.mirror_along = True
    assert service._along_target(sample) == (40.0, 3.5)


def test_v143_signed_negative_offset_can_choose_the_opposite_side_directly() -> None:
    service = PlanTrace2DCreatorTool()._services.duplicate
    service.edge_normal_offset = -4.0

    assert service._along_target(_PathSample((5.0, 5.0), 0.0)) == (5.0, 1.0)


def test_v143_along_preview_and_build_share_the_same_offset_targets(monkeypatch) -> None:
    prefab = PlanTracePrefab("user:offset", "Offset", _payload())
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (prefab,))
    tool, ctx = _open()
    _add_line(tool, ctx)
    service = tool._services.duplicate
    service.selected_prefab_id = prefab.id
    service.copy_count = 3
    service.edge_normal_offset = 7.0
    service.stage = "edge"

    expected = [service._along_target(sample) for sample in service._along_samples(ctx)]
    captured: list[tuple[float, float]] = []
    original = service.services.selection_edit.paste_payload

    def _capture(*args, **kwargs):
        captured.append(kwargs["target"])
        return original(*args, **kwargs)

    monkeypatch.setattr(service.services.selection_edit, "paste_payload", _capture)
    assert service._build_along_selected(ctx)
    assert captured == expected


def test_v143_compact_along_overlay_exposes_live_signed_offset(monkeypatch) -> None:
    prefab = PlanTracePrefab("user:offset", "Offset", _payload())
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
    assert _FIELD_EDGE_OFFSET in field_ids

    assert service.handle_field_change(ctx, _FIELD_EDGE_OFFSET, "-12.5")
    assert service.edge_normal_offset == -12.5
