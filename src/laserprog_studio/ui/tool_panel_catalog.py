# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from ..tooling.ids import (
    TOOL_BOX,
    TOOL_ENGRAVING,
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MATERIAL,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_HOLLOW,
    TOOL_MOD_RELIEF,
    TOOL_MOD_REPAIR,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_SPLIT,
    TOOL_NONE,
    TOOL_PRIMITIVE,
    TOOL_TEXTURE_PROJECTION,
    TOOL_PLAN_TRACE,
    TOOL_VENT_GENERATOR,
    TOOL_MECHANICAL_MOTION,
    TOOL_FOLDING,
    TOOL_CLOTH,
    TOOL_VOLUME_MEASURE,
    TOOL_ACOUSTIC_DIFFUSER,
    TOOL_SMART_SURFACE_SELECTION_TEST,
)


@dataclass(frozen=True)
class ToolPanelSpec:
    key: str
    label: str
    builder: str
    panel_index: int
    family: str


TOOL_PANEL_SPECS: tuple[ToolPanelSpec, ...] = (
    ToolPanelSpec(TOOL_NONE, "No tool", "panel_no_tool", 0, "system"),
    ToolPanelSpec(TOOL_PRIMITIVE, "Primitives", "panel_declarative_creator_tool", 1, "fabrication"),
    ToolPanelSpec(TOOL_BOX, "Box generator", "panel_declarative_creator_tool", 2, "fabrication"),
    ToolPanelSpec(TOOL_LAYFLAT, "Lay flat", "panel_declarative_creator_tool", 3, "fabrication"),
    ToolPanelSpec(TOOL_JOINT, "Joint builder", "panel_declarative_creator_tool", 4, "fabrication"),
    ToolPanelSpec(TOOL_ENGRAVING, "Engraving roles", "panel_declarative_creator_tool", 5, "fabrication"),
    ToolPanelSpec(TOOL_MATERIAL, "Materials", "panel_declarative_creator_tool", 6, "surface"),
    ToolPanelSpec(TOOL_MOD_SPLIT, "Split modifier", "panel_declarative_creator_tool", 7, "modifier"),
    ToolPanelSpec(TOOL_MOD_SIMPLIFY, "Simplify", "panel_declarative_creator_tool", 8, "modifier"),
    ToolPanelSpec(TOOL_MOD_RELIEF, "Relief", "panel_declarative_creator_tool", 9, "modifier"),
    ToolPanelSpec(TOOL_MOD_EXTRUDE_DOWN, "Extrude down", "panel_declarative_creator_tool", 10, "modifier"),
    ToolPanelSpec(TOOL_MOD_HOLLOW, "Hollow", "panel_declarative_creator_tool", 11, "modifier"),
    ToolPanelSpec(TOOL_TEXTURE_PROJECTION, "Texture projection", "panel_declarative_creator_tool", 12, "surface"),
    ToolPanelSpec(TOOL_MOD_REPAIR, "Repair mesh", "panel_declarative_creator_tool", 13, "modifier"),
    ToolPanelSpec(TOOL_VOLUME_MEASURE, "Cavity volume", "panel_declarative_creator_tool", 14, "fabrication"),
    ToolPanelSpec(TOOL_ACOUSTIC_DIFFUSER, "Acoustic diffuser", "panel_declarative_creator_tool", 15, "fabrication"),
    ToolPanelSpec(TOOL_PLAN_TRACE, "Plan tracer", "panel_declarative_creator_tool", 30, "planar"),
    ToolPanelSpec(TOOL_VENT_GENERATOR, "Vent generator", "panel_declarative_creator_tool", 31, "planar"),
    ToolPanelSpec(TOOL_MECHANICAL_MOTION, "Mechanical motion", "panel_declarative_creator_tool", 32, "fabrication"),
    ToolPanelSpec(TOOL_FOLDING, "Folding", "panel_declarative_creator_tool", 33, "modifier"),
    ToolPanelSpec(TOOL_CLOTH, "Cloth", "panel_declarative_creator_tool", 34, "surface"),
    ToolPanelSpec(TOOL_SMART_SURFACE_SELECTION_TEST, "Selection API test", "panel_declarative_creator_tool", 35, "diagnostic"),
)


def iter_tool_panel_specs() -> tuple[ToolPanelSpec, ...]:
    return TOOL_PANEL_SPECS


def get_tool_panel_spec(key: str) -> ToolPanelSpec | None:
    for spec in TOOL_PANEL_SPECS:
        if spec.key == key:
            return spec
    return None
