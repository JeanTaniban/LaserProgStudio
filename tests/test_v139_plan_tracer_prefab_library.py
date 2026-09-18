from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.duplicate import (
    DUPLICATE_ACTION_PREFIX,
    DUPLICATE_LIBRARY_WINDOW_ID,
    _FIELD_NAME,
    _FIELD_PREFAB,
)
from laserprog_studio.tooling.plan_trace_2d.prefabs import (
    PlanTracePrefab,
    load_prefabs,
    rename_prefab,
    save_prefab,
)
from laserprog_studio.tooling.plan_trace_2d.selection_edit import SketchPayload
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 0.0), object_id="ground", object_index=0)


def _payload(scale: float = 1.0) -> SketchPayload:
    return SketchPayload(
        points={"a": (0.0, 0.0), "b": (10.0 * scale, 0.0), "c": (0.0, 5.0 * scale)},
        lines=[
            {"start": "a", "end": "b", "metadata": {}},
            {"start": "b", "end": "c", "metadata": {}},
            {"start": "c", "end": "a", "metadata": {}},
        ],
        pivot=(0.0, 0.0),
    )


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    return tool, ctx


def test_v140_duplicate_opens_catalog_only_when_select_is_requested(monkeypatch) -> None:
    first = PlanTracePrefab("user:bracket", "Bracket", _payload(1.0))
    second = PlanTracePrefab("user:slot", "Slot", _payload(0.5))
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (first, second))

    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    assert ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID) is None
    service = tool._services.duplicate
    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "select_prefab")
    window = ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID)
    assert window is not None
    assert window.overlay_kind == "popover"
    assert window.anchor == "viewport_top_right"
    assert window.width_px <= 340

    prefab_field = next(field for field in window.fields if field.id == _FIELD_PREFAB)
    assert prefab_field.kind == "select"
    assert prefab_field.enabled
    assert tuple(value for value, _label in prefab_field.options) == (first.id, second.id)
    assert all("pts" in label and "curves" in label for _value, label in prefab_field.options)

    button_ids = {button.id for button in window.buttons}
    assert DUPLICATE_ACTION_PREFIX + "choose_prefab" in button_ids
    assert DUPLICATE_ACTION_PREFIX + "rename_prompt" in button_ids
    assert DUPLICATE_ACTION_PREFIX + "delete_prefab" in button_ids


def test_v140_selecting_catalog_item_updates_active_prefab(monkeypatch) -> None:
    first = PlanTracePrefab("user:bracket", "Bracket", _payload(1.0))
    second = PlanTracePrefab("user:slot", "Slot", _payload(0.5))
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (first, second))

    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "select_prefab")
    assert service.handle_field_change(ctx, _FIELD_PREFAB, second.id)
    assert service.selected_prefab_id == second.id
    assert service.prefab_name == second.name
    window = ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID)
    assert window is not None
    assert next(field for field in window.fields if field.id == _FIELD_PREFAB).value == second.id


def test_v139_prefab_rename_is_atomic_and_keeps_geometry(tmp_path) -> None:
    path = tmp_path / "prefabs.json"
    saved = save_prefab("Old name", _payload(), path=path)
    renamed = rename_prefab(saved.id, "Useful bracket", path=path)
    loaded = load_prefabs(path)

    assert renamed.name == "Useful bracket"
    assert renamed.id == "user:useful bracket"
    assert renamed.payload.to_dict() == saved.payload.to_dict()
    assert [(item.id, item.name) for item in loaded] == [(renamed.id, renamed.name)]


def test_v140_new_prefab_gets_unique_default_name_without_permanent_catalog(monkeypatch) -> None:
    existing = PlanTracePrefab("user:prefab 1", "Prefab 1", _payload())
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (existing,))
    tool, ctx = _open()
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate

    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "create")
    assert service.stage == "capture"
    assert service.prefab_name == "Prefab 2"
    assert ctx.overlay.window(DUPLICATE_LIBRARY_WINDOW_ID) is None

