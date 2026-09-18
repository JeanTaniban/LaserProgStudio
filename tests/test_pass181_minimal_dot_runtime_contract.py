# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import CREATOR_UI_RUNTIME_CONTRACT
from laserprog_studio.tool_api.styles import InteractionVisualState, PointStyleId, point_style, resolve_actor_visual


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_pass181_minimal_dot_selected_and_grabbed_feedback_overrides_baseline_state() -> None:
    minimal = point_style(PointStyleId.MINIMAL)

    selected = resolve_actor_visual(
        interaction="grabbable",
        point_style_id=PointStyleId.MINIMAL,
        visual_state=InteractionVisualState.GRABBABLE,
        selected=True,
    )
    grabbed = resolve_actor_visual(
        interaction="grabbable",
        point_style_id=PointStyleId.MINIMAL,
        visual_state=InteractionVisualState.GRABBABLE,
        selected=True,
        grabbed=True,
    )

    assert selected.visual_state is InteractionVisualState.SELECTED
    assert selected.point_color == minimal.selected_color
    assert selected.radius_px == 3
    assert grabbed.visual_state is InteractionVisualState.GRABBED
    assert grabbed.point_color == minimal.grabbed_color
    assert grabbed.radius_px == 3


def test_pass181_disabled_still_wins_over_runtime_feedback() -> None:
    minimal = point_style(PointStyleId.MINIMAL)

    disabled = resolve_actor_visual(
        interaction="grabbable",
        point_style_id=PointStyleId.MINIMAL,
        visual_state=InteractionVisualState.DISABLED,
        selected=True,
        grabbed=True,
        visible=True,
    )

    assert disabled.visual_state is InteractionVisualState.DISABLED
    assert disabled.point_color == minimal.disabled_color


def test_pass181_runtime_contract_is_public_and_documented() -> None:
    assert CREATOR_UI_RUNTIME_CONTRACT == "native_non_overridable"

    direction = _read("docs/tool_creator/00_creator_ui_direction.md")
    style_doc = _read("docs/tool_creator/12_native_interaction_styles.md")
    checklist = _read("docs/tool_creator/09_creator_api_checklist.md")

    assert "CREATOR_UI_RUNTIME_CONTRACT = \"native_non_overridable\"" in direction
    assert "runtime interaction feedback always wins" in direction.lower()
    assert "selected dot is yellow" in style_doc
    assert "grabbed/dragged dot is orange" in style_doc
    assert "does not override native selected/grabbed feedback" in checklist
