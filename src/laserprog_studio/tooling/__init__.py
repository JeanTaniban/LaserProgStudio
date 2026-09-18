# -*- coding: utf-8 -*-
from __future__ import annotations

from .base import SelectionPolicy, ToolCategory, ToolSpec
from .ids import (
    TOOL_BOX,
    TOOL_ENGRAVING,
    TOOL_MATERIAL,
    TOOL_TEXTURE_PROJECTION,
    TOOL_PLAN_TRACE,
    TOOL_VENT_GENERATOR,
    TOOL_MECHANICAL_MOTION,
    TOOL_VOLUME_MEASURE,
    TOOL_ACOUSTIC_DIFFUSER,
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MOD_SPLIT,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_RELIEF,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_HOLLOW,
    TOOL_MOD_REPAIR,
    TOOL_NONE,
    TOOL_PRIMITIVE,
    TRANSFORM_NONE,
    TRANSFORM_ROTATE,
    TRANSFORM_SCALE,
    TRANSFORM_TRANSLATE,
)
from .tool import HookToolAdapter, StudioTool
def __getattr__(name: str):
    if name in {"PLANAR_TOOL_BLUEPRINTS", "PLAN_TRACE_BLUEPRINT", "VENT_GENERATOR_BLUEPRINT"}:
        from .planar_tool_blueprints import PLANAR_TOOL_BLUEPRINTS, PLAN_TRACE_BLUEPRINT, VENT_GENERATOR_BLUEPRINT

        return {
            "PLANAR_TOOL_BLUEPRINTS": PLANAR_TOOL_BLUEPRINTS,
            "PLAN_TRACE_BLUEPRINT": PLAN_TRACE_BLUEPRINT,
            "VENT_GENERATOR_BLUEPRINT": VENT_GENERATOR_BLUEPRINT,
        }[name]
    if name in {"get_studio_tool", "get_tool_spec", "iter_studio_tools", "iter_tool_specs", "register_tool_spec", "reset_tool_registry", "tool_label", "unregister_tool_spec", "validate_tool_registry"}:
        from . import registry

        return getattr(registry, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SelectionPolicy",
    "ToolCategory",
    "ToolSpec",
    "StudioTool",
    "HookToolAdapter",
    "get_tool_spec",
    "get_studio_tool",
    "iter_tool_specs",
    "iter_studio_tools",
    "tool_label",
    "register_tool_spec",
    "unregister_tool_spec",
    "reset_tool_registry",
    "validate_tool_registry",
    "TOOL_NONE",
    "TOOL_BOX",
    "TOOL_LAYFLAT",
    "TOOL_JOINT",
    "TOOL_PRIMITIVE",
    "TOOL_ENGRAVING",
    "TOOL_MATERIAL",
    "TOOL_TEXTURE_PROJECTION",
    "TOOL_PLAN_TRACE",
    "TOOL_VENT_GENERATOR",
    "TOOL_MECHANICAL_MOTION",
    "TOOL_VOLUME_MEASURE",
    "TOOL_ACOUSTIC_DIFFUSER",
    "TOOL_MOD_SPLIT",
    "TOOL_MOD_SIMPLIFY",
    "TOOL_MOD_RELIEF",
    "TOOL_MOD_EXTRUDE_DOWN",
    "TOOL_MOD_HOLLOW",
    "TOOL_MOD_REPAIR",
    "TRANSFORM_NONE",
    "TRANSFORM_TRANSLATE",
    "TRANSFORM_ROTATE",
    "TRANSFORM_SCALE",
    "PLANAR_TOOL_BLUEPRINTS",
    "PLAN_TRACE_BLUEPRINT",
    "VENT_GENERATOR_BLUEPRINT",
]

