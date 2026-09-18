# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.app_context import AppContext
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState
from laserprog_studio.tool_api import ToolContext
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter
from laserprog_studio.tooling.primitive_tool import PrimitiveCreatorTool


def _window_stub():
    return SimpleNamespace(
        selection_state=SelectionState(),
        transform_state=TransformState(),
        tool_state=ToolState(),
        preview_state=PreviewState(),
        ui_layout_state=UiLayoutState(),
        render_state=RenderState(),
        clipboard_state=ClipboardState(),
        model_store=None,
        project_store=None,
    )


def _primitive_adapter() -> CreatorStudioToolAdapter:
    return CreatorStudioToolAdapter(
        ToolSpec(id="primitive", label="Primitives", category="tool", panel_index=1),
        PrimitiveCreatorTool(),
    )


def test_pass152_app_context_has_explicit_creator_context_slot() -> None:
    window = _window_stub()
    context = AppContext.from_window(window)

    assert hasattr(context, "tool_context")
    assert context.tool_context is None



def test_pass152_creator_runtime_publishes_context_to_app_context_and_owner() -> None:
    window = _window_stub()
    context = AppContext.from_window(window)
    adapter = _primitive_adapter()

    ctx = adapter.tool_context(context)

    assert isinstance(ctx, ToolContext)
    assert context.tool_context is ctx
    assert window.tool_context is ctx
    assert ctx.owner is window



def test_pass152_creator_open_populates_context_visible_to_declarative_panel() -> None:
    window = _window_stub()
    context = AppContext.from_window(window)
    adapter = _primitive_adapter()

    adapter.on_open(context)

    ctx = context.tool_context
    assert isinstance(ctx, ToolContext)
    assert window.tool_context is ctx
    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.owner_tool == "primitive"
