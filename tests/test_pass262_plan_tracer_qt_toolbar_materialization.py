from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.overlay import OverlayManager
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.constants import _TOOLBOX_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def test_pass262_qt_overlay_rebuild_receives_widgets_in_correct_order() -> None:
    """Regression guard for Plan Tracer's second overlay in the real desktop UI.

    The anchor prompt only uses QLabel, so it survived the bad argument order.
    The drawing toolbox is a toolbar with buttons; when QLineEdit was omitted in
    this call, every later Qt class shifted left and toolbar rebuild aborted
    before the mode buttons could be materialised.
    """

    source = Path("src/laserprog_studio/tool_core/overlay/qt_adapter.py").read_text(encoding="utf-8")

    expected = "self._rebuild(widget, spec, QLabel, QLineEdit, ToolCoreOverlayButton, QSizePolicy, QVBoxLayout, QHBoxLayout, QButtonGroup, Qt)"
    assert expected in source
    assert "self._rebuild(widget, spec, QLabel, ToolCoreOverlayButton, QSizePolicy" not in source


def test_pass262_plan_tracer_toolbox_spec_contains_toolbar_buttons_after_anchor_transition() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = type("Ctx", (), {})()
    ctx.overlay = OverlayManager()
    ctx.owner = object()

    class _Inspector:
        def values(self):
            return {}

        def set_visible(self, *_args):
            return None

    ctx.inspector = _Inspector()

    sync_calls = []

    class _Rendering:
        def _sync_overlays(self, sync_ctx):
            sync_calls.append(sync_ctx)

    tool._services.overlay.services.rendering = _Rendering()
    tool._services.overlay._show_anchor_prompt(ctx)
    tool._services.overlay._show_toolbox(ctx)

    prompt = ctx.overlay.window("plan_trace_2d.anchor_prompt")
    toolbox = ctx.overlay.window(_TOOLBOX_ID)

    assert prompt is not None and prompt.visible is False
    assert toolbox is not None and toolbox.visible is True
    assert toolbox.owner_tool == TOOL_PLAN_TRACE
    assert toolbox.overlay_kind == "command_deck"
    assert toolbox.persistent is True
    assert [button.label for button in toolbox.buttons[:10]] == [
        "Modify",
        "Point",
        "Line",
        "Polyline",
        "Rectangle",
        "Circle",
        "Half-circle",
        "Arc",
        "Curve",
        "Dimension",
    ]
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.point"
    assert sync_calls[-1] is ctx
