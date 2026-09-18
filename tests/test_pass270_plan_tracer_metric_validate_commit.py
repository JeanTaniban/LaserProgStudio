from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_api.plan2d import metrics as metric_api
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.overlay.qt_adapter import QtOverlayAdapter
from laserprog_studio.tooling.plan_trace_2d.constants import _METRIC_OVERLAY_ID, _METRIC_VALIDATE_BUTTON_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


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


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_metric_field_commit_is_deferred_until_validate_without_rematerialising_overlay() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 40.0, 40.0)

    def _must_not_reopen_overlay(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("successful field edits must not rebuild the metric overlay")

    before_xs = [point.position[0] for point in tool._state.sketch.points.values()]
    before_span = round(max(before_xs) - min(before_xs), 6)
    tool._services.metrics._show_metric_overlay = _must_not_reopen_overlay  # type: ignore[method-assign]
    assert tool.on_overlay_field_changed(_METRIC_OVERLAY_ID, f"{_METRIC_OVERLAY_ID}.metric.width", "12 mm", ctx) is True

    # Text commits may update the geometry immediately, but they must not
    # rebuild/rematerialise the overlay before the Validate button receives the
    # same physical click.
    xs = [point.position[0] for point in tool._state.sketch.points.values()]
    assert round(max(xs) - min(xs), 6) == 12.0
    assert tool._state.metric_draft is not None
    window = ctx.overlay.window(_METRIC_OVERLAY_ID)
    assert window is not None and window.visible is True

    tool.on_overlay_button_clicked(_METRIC_VALIDATE_BUTTON_ID, ctx)
    xs = [point.position[0] for point in tool._state.sketch.points.values()]
    assert round(max(xs) - min(xs), 6) == 12.0


def test_validate_after_metric_text_commit_keeps_rebuilt_geometry() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 40.0, 0.0)

    ctx.overlay.update_field(_METRIC_OVERLAY_ID, f"{_METRIC_OVERLAY_ID}.metric.length", "18 mm")
    tool.on_overlay_button_clicked(_METRIC_VALIDATE_BUTTON_ID, ctx)

    assert tool._state.metric_draft is None
    window = ctx.overlay.window(_METRIC_OVERLAY_ID)
    assert window is not None and window.visible is False
    line = next(iter(tool._state.sketch.lines.values()))
    start = tool._state.sketch.points[line.start_point_id].position
    end = tool._state.sketch.points[line.end_point_id].position
    assert round(((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5, 6) == 18.0


class _FakeEdit:
    def __init__(self, text: str, *, focused: bool = False) -> None:
        self._text = text
        self._focused = bool(focused)

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802 - Qt-compatible fake
        self._text = str(text)

    def hasFocus(self) -> bool:  # noqa: N802 - Qt-compatible fake
        return self._focused


def test_qt_validate_button_flushes_live_line_edit_text_before_tool_callback() -> None:
    manager = ToolContext().overlay
    session = metric_api.rectangle_metric_session(_METRIC_OVERLAY_ID, width=40.0, height=40.0)
    manager.show_window(
        metric_api.build_metric_edit_window(
            window_id=_METRIC_OVERLAY_ID,
            owner_tool="plan_trace",
            session=session,
            validate_button_id=_METRIC_VALIDATE_BUTTON_ID,
            cancel_button_id="plan_trace_2d.metric.cancel",
        )
    )
    width_field_id = f"{_METRIC_OVERLAY_ID}.metric.width"
    owner = SimpleNamespace(
        _tool_core_overlay_widgets={
            _METRIC_OVERLAY_ID: SimpleNamespace(_tool_core_overlay_field_edits={width_field_id: _FakeEdit("22 mm")})
        }
    )
    adapter = QtOverlayAdapter(owner, manager)
    flushed: list[tuple[str, str, str]] = []
    clicked: list[str] = []
    adapter._notify_active_tool_overlay_field = lambda window_id, field_id, value: flushed.append((window_id, field_id, value))  # type: ignore[method-assign]
    adapter._notify_active_tool_overlay_button = lambda button_id: clicked.append(button_id)  # type: ignore[method-assign]

    adapter._overlay_button_clicked(_METRIC_VALIDATE_BUTTON_ID)

    assert flushed == [(_METRIC_OVERLAY_ID, width_field_id, "22 mm")]
    assert clicked == [_METRIC_VALIDATE_BUTTON_ID]
    window = manager.window(_METRIC_OVERLAY_ID)
    assert window is not None
    assert next(field for field in window.fields if field.id == width_field_id).value == "22 mm"


def test_circle_radius_commit_updates_diameter_editor_before_validate_flush() -> None:
    manager = ToolContext().overlay
    session = metric_api.circle_metric_session(_METRIC_OVERLAY_ID, radius=10.0)
    manager.show_window(
        metric_api.build_metric_edit_window(
            window_id=_METRIC_OVERLAY_ID,
            owner_tool="plan_trace",
            session=session,
            validate_button_id=_METRIC_VALIDATE_BUTTON_ID,
            cancel_button_id="plan_trace_2d.metric.cancel",
            overlay_kind="metric_bar",
        )
    )

    radius_field_id = f"{_METRIC_OVERLAY_ID}.metric.radius"
    diameter_field_id = f"{_METRIC_OVERLAY_ID}.metric.diameter"
    radius_edit = _FakeEdit("30 mm")
    diameter_edit = _FakeEdit("20 mm")
    owner = SimpleNamespace(
        _tool_core_overlay_widgets={
            _METRIC_OVERLAY_ID: SimpleNamespace(
                _tool_core_overlay_field_edits={
                    radius_field_id: radius_edit,
                    diameter_field_id: diameter_edit,
                }
            )
        }
    )
    adapter = QtOverlayAdapter(owner, manager)

    def _consume_linked_circle_edit(window_id: str, field_id: str, value: str) -> bool:
        assert window_id == _METRIC_OVERLAY_ID
        assert field_id == radius_field_id
        assert value == "30 mm"
        manager.update_field(_METRIC_OVERLAY_ID, radius_field_id, "30.0 mm")
        manager.update_field(_METRIC_OVERLAY_ID, diameter_field_id, "60.0 mm")
        return True

    adapter._notify_active_tool_overlay_field = _consume_linked_circle_edit  # type: ignore[method-assign]

    adapter._overlay_field_committed(_METRIC_OVERLAY_ID, radius_field_id, "30 mm")

    assert diameter_edit.text() == "60.0 mm"
    assert radius_edit.text() == "30.0 mm"

    # The following Validate click now has no stale linked value to flush.
    # Before this fix the diameter editor still contained 20 mm and overwrote
    # the radius edit when the button helper committed all live fields.
    flushed: list[tuple[str, str, str]] = []
    adapter._notify_active_tool_overlay_field = lambda window_id, field_id, value: flushed.append((window_id, field_id, value)) or True  # type: ignore[method-assign]
    adapter._notify_active_tool_overlay_button = lambda _button_id: None  # type: ignore[method-assign]
    adapter._overlay_button_clicked(_METRIC_VALIDATE_BUTTON_ID)

    assert flushed == []

def test_overlay_signature_does_not_rebuild_for_editable_value_changes() -> None:
    manager = ToolContext().overlay
    session = metric_api.circle_metric_session(_METRIC_OVERLAY_ID, radius=10.0)
    manager.show_window(
        metric_api.build_metric_edit_window(
            window_id=_METRIC_OVERLAY_ID,
            owner_tool="plan_trace",
            session=session,
            validate_button_id=_METRIC_VALIDATE_BUTTON_ID,
            cancel_button_id="plan_trace_2d.metric.cancel",
            overlay_kind="metric_bar",
        )
    )
    adapter = QtOverlayAdapter(SimpleNamespace(), manager)
    before = adapter._spec_signature(manager.window(_METRIC_OVERLAY_ID))  # type: ignore[arg-type]

    manager.update_field(_METRIC_OVERLAY_ID, f"{_METRIC_OVERLAY_ID}.metric.diameter", "60.0 mm")
    after = adapter._spec_signature(manager.window(_METRIC_OVERLAY_ID))  # type: ignore[arg-type]

    assert before == after
