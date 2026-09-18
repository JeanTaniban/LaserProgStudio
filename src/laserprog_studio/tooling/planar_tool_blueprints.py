# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from ..ui.toolbar_catalog import ToolbarItemSpec
from .base import ToolSpec
from .ids import TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR


@dataclass(frozen=True, slots=True)
class PlanarToolBlueprint:
    """Reference contract for a planar tool registration.

    Pass 20 promoted the planar tools from future blueprints to registered
    built-ins.  This small structure remains as documentation for the ids,
    toolbar entries and runtime contracts expected by tests and future planar
    extensions. Both Plan tracer and Vent generator are registered runtime tools;
    the shared planar controller owns pointer/snap services.
    """

    tool: ToolSpec
    toolbar_item: ToolbarItemSpec
    expected_panel_builder: str


PLAN_TRACE_BLUEPRINT = PlanarToolBlueprint(
    tool=ToolSpec(
        id=TOOL_PLAN_TRACE,
        label="Plan tracer",
        category="tool",
        panel_index=30,
        button_attr="btn_tool_plan_trace",
        selection_policy="none",
        display_order=65,
    ),
    toolbar_item=ToolbarItemSpec(
        "tool:plan_trace",
        "PLN",
        "Plan tracer",
        "Draw a locked 2D polygon on a view, then extrude it.",
        "tool",
        "tool",
        65,
        tool_id=TOOL_PLAN_TRACE,
        button_attr="btn_tool_plan_trace",
        default_visible=True,
    ),
    expected_panel_builder="creator_api_plan_trace_2d",
)


VENT_GENERATOR_BLUEPRINT = PlanarToolBlueprint(
    tool=ToolSpec(
        id=TOOL_VENT_GENERATOR,
        label="Vent generator",
        category="tool",
        panel_index=31,
        button_attr="btn_tool_vent_generator",
        selection_policy="none",
        display_order=66,
    ),
    toolbar_item=ToolbarItemSpec(
        "tool:vent_generator",
        "EVT",
        "Vent generator",
        "Draw a vent path with waypoints and generate its mesh.",
        "tool",
        "tool",
        66,
        tool_id=TOOL_VENT_GENERATOR,
        button_attr="btn_tool_vent_generator",
        default_visible=True,
    ),
    expected_panel_builder="panel_declarative_creator_tool",
)


PLANAR_TOOL_BLUEPRINTS: tuple[PlanarToolBlueprint, ...] = (
    PLAN_TRACE_BLUEPRINT,
    VENT_GENERATOR_BLUEPRINT,
)
