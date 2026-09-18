from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.duplicate import (
    DUPLICATE_ACTION_PREFIX,
    DUPLICATE_LIBRARY_WINDOW_ID,
    DUPLICATE_NAME_WINDOW_ID,
    DUPLICATE_OPTIONS_WINDOW_ID,
    DUPLICATE_WINDOW_ID,
    _FIELD_PREFAB,
)
from laserprog_studio.tooling.plan_trace_2d.prefabs import PlanTracePrefab
from laserprog_studio.tooling.plan_trace_2d.selection_edit import SketchPayload
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.application.creator_box_selection_overlay import ensure_renderer_props


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 0.0), object_id="ground", object_index=0)


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    return tool, ctx


def _payload() -> SketchPayload:
    return SketchPayload(
        points={"a": (0.0, 2.0), "b": (4.0, 2.0)},
        lines=[{"start": "a", "end": "b", "metadata": {}}],
        pivot=(0.0, 0.0),
    )


def test_v140_duplicate_library_is_compact_and_picker_is_contextual(monkeypatch) -> None:
    first = PlanTracePrefab("user:first", "First", _payload())
    second = PlanTracePrefab("user:second", "Second", _payload())
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (first, second))
    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)

    main = ctx.overlay.window(DUPLICATE_WINDOW_ID)
    assert main is not None
    assert ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID) is None
    action_ids = {action.id for section in main.toolbar_sections for action in section.actions}
    assert DUPLICATE_ACTION_PREFIX + "select_prefab" in action_ids
    assert DUPLICATE_ACTION_PREFIX + "place_one" in action_ids

    service = tool._services.duplicate
    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "select_prefab")
    picker = ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID)
    assert picker is not None
    assert picker.title == "Select prefab"
    assert picker.width_px <= 340
    assert next(field for field in picker.fields if field.id == _FIELD_PREFAB).kind == "select"

    assert service.handle_field_change(ctx, _FIELD_PREFAB, second.id)
    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "choose_prefab")
    assert service.selected_prefab_id == second.id
    assert not ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID).visible


def test_v140_prefab_name_uses_small_dedicated_dialog(monkeypatch) -> None:
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: ())
    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.capture_payload = _payload()
    service.stage = "pivot_ready"
    service.prefab_name = "Bracket"
    service.name_prompt_mode = "create"
    service._sync(ctx, render=False)

    dialog = ctx.overlay.window(DUPLICATE_NAME_WINDOW_ID)
    assert dialog is not None
    assert dialog.modal
    assert dialog.width_px <= 310
    assert len(dialog.fields) == 1
    assert ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID) is None


def test_v148_pivot_step_is_instruction_only_until_the_viewport_pivot_is_picked(monkeypatch) -> None:
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: ())
    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.stage = "pivot"
    service.name_prompt_mode = None
    service._sync(ctx, render=False)

    prompt = ctx.overlay.window(DUPLICATE_WINDOW_ID)
    assert prompt is not None and prompt.visible
    assert prompt.overlay_kind == "prompt"
    assert len(prompt.fields) == 1
    assert "click" in str(prompt.fields[0].value).lower()
    assert "pivot" in str(prompt.fields[0].value).lower()
    assert prompt.buttons == []
    assert ctx.overlay.window(DUPLICATE_NAME_WINDOW_ID) is None

    service.capture_payload = _payload()
    service.stage = "pivot_ready"
    service.prefab_name = "Bracket"
    service.name_prompt_mode = "create"
    service._sync(ctx, render=False)

    assert ctx.overlay.window(DUPLICATE_WINDOW_ID).visible is False
    dialog = ctx.overlay.window(DUPLICATE_NAME_WINDOW_ID)
    assert dialog is not None and dialog.visible and dialog.modal


def test_v140_along_options_are_compact_and_include_mirror(monkeypatch) -> None:
    prefab = PlanTracePrefab("user:first", "First", _payload())
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (prefab,))
    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.stage = "edge"
    service._sync(ctx, render=False)

    options = ctx.overlay.window(DUPLICATE_OPTIONS_WINDOW_ID)
    assert options is not None
    assert options.title == "Place along"
    assert options.width_px <= 310
    labels = {button.label for button in options.buttons}
    assert {"Follow", "Mirror", "Build", "Cancel"}.issubset(labels)


def test_v140_filtered_edge_selection_refreshes_visual_state(monkeypatch) -> None:
    prefab = PlanTracePrefab("user:first", "First", _payload())
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (prefab,))
    tool, ctx = _open()
    p0 = tool._state.sketch.add_point((0.0, 0.0), point_id="plan_trace:point:test0")
    p1 = tool._state.sketch.add_point((10.0, 0.0), point_id="plan_trace:point:test1")
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.stage = "edge"
    service._sync(ctx, render=False)
    actor_id = tool._services.sketch_sync._line_actor_id(line.id)
    changed: list[tuple[str, ...]] = []

    import laserprog_studio.tooling.plan_trace_2d.duplicate as duplicate_module

    real_sync = duplicate_module.plan2d.sync_plan_actor_visuals

    def capture_sync(*args, **kwargs):
        changed.append(tuple(kwargs.get("changed_actor_ids") or ()))
        return real_sync(*args, **kwargs)

    monkeypatch.setattr(duplicate_module.plan2d, "sync_plan_actor_visuals", capture_sync)
    assert service.handle_event(ctx, ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(5.0, 0.0), button=MouseButton.LEFT))
    assert ctx.selection.is_selected(actor_id)
    assert any(actor_id in ids for ids in changed)
    registry_item = ctx.projected_drawing.for_tool(tool.id).get(actor_id)
    assert registry_item is not None
    assert getattr(registry_item.style, "color", None) == "#f0a805"


def test_v140_mirror_reflects_prefab_across_path_tangent() -> None:
    tool, ctx = _open()
    result = tool._services.selection_edit.paste_payload(
        ctx,
        _payload(),
        target=(10.0, 10.0),
        rotation_rad=0.0,
        mirror_y=True,
        compile_after=False,
        select_created=False,
    )
    points = [tool._state.sketch.points[point_id].position for point_id in result.point_ids]
    assert sorted(points) == [(10.0, 8.0), (14.0, 8.0)]


class _FakeRenderer:
    def __init__(self):
        self.props: list[object] = []

    def HasViewProp(self, actor):
        return actor in self.props

    def AddActor2D(self, actor):
        self.props.append(actor)


def test_v140_selection_rectangle_reattaches_after_renderer_prop_reset() -> None:
    fill = object()
    outline = object()
    renderer = _FakeRenderer()
    assert ensure_renderer_props(renderer, (fill, outline))
    assert renderer.props == [fill, outline]
    renderer.props.clear()  # simulate scene/projected-overlay renderer rebuild
    assert ensure_renderer_props(renderer, (fill, outline))
    assert renderer.props == [fill, outline]
