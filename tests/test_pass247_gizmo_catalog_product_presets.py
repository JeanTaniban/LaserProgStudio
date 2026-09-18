# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.gizmo_catalog import (
    ALL_PRESET_ID,
    CUSTOM_PRESET_ID,
    HIDDEN_PRESET_ID,
    detect_gizmo_catalog_view_preset,
    get_gizmo_catalog_view_preset,
    gizmo_catalog_view_preset_choices,
)
from laserprog_studio.tooling.ids import TOOL_GIZMO_CATALOG
from laserprog_studio.tooling.registry import get_studio_tool


@dataclass
class _AppCtx:
    tool_context: ToolContext
    active_scene: object | None = None
    owner: object | None = None


def _open_catalog() -> tuple[ToolContext, object]:
    ctx = ToolContext()
    runtime = get_studio_tool(TOOL_GIZMO_CATALOG)
    runtime.on_open(_AppCtx(tool_context=ctx))
    assert ctx.inspector.panel is not None
    return ctx, runtime


def test_pass247_gizmo_catalog_exposes_product_view_presets() -> None:
    choices = dict(gizmo_catalog_view_preset_choices())

    assert choices[ALL_PRESET_ID] == "All motifs"
    assert choices["tool_author"] == "Tool author essentials"
    assert choices["interaction_tuning"] == "Interaction tuning"
    assert choices["viewport_feedback"] == "Viewport feedback"
    assert choices[HIDDEN_PRESET_ID] == "Clean viewport"
    assert choices[CUSTOM_PRESET_ID] == "Custom"
    assert get_gizmo_catalog_view_preset("missing").id == CUSTOM_PRESET_ID



def test_gizmo_catalog_no_longer_exposes_legacy_family_presets() -> None:
    ctx, _runtime = _open_catalog()
    field_ids = set(ctx.inspector.panel.field_ids())
    assert "catalog_view" not in field_ids
    assert "focus_report" not in field_ids
    assert "show_projected_drawing_2d" in field_ids
    assert not any(field_id.startswith("show_actor_") for field_id in field_ids)


def test_gizmo_catalog_visibility_toggle_preserves_the_declarative_scene() -> None:
    ctx, _runtime = _open_catalog()
    before = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)

    ctx.inspector.update_value("show_projected_drawing_2d", False)
    hidden = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)

    assert hidden.visible is False
    assert hidden.primitives == before.primitives
    assert ctx.gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.preview.items(owner_tool=TOOL_GIZMO_CATALOG) == ()


def test_gizmo_catalog_actions_control_only_projected_visibility() -> None:
    ctx, _runtime = _open_catalog()

    ctx.inspector.trigger("hide_all")
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).visible is False
    assert ctx.inspector.value("visible_report") == "Projected scene hidden."

    ctx.inspector.trigger("show_all")
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).visible is True
    assert ctx.inspector.value("visible_report") == "Projected scene visible."


def test_gizmo_catalog_creates_no_overlay_samples() -> None:
    ctx, runtime = _open_catalog()
    before = ctx.inspector.value("visible_report")

    runtime.on_overlay_button_clicked("gizmo_catalog:overlay:mode:line", _AppCtx(tool_context=ctx))

    assert ctx.inspector.value("visible_report") == before
    assert not any(window.owner_tool == TOOL_GIZMO_CATALOG for window in ctx.overlay.windows.values())

