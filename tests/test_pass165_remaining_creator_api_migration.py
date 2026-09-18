# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter
from laserprog_studio.tooling.extrude_down_tool import ExtrudeDownCreatorTool, ExtrudeDownTool
from laserprog_studio.tooling.ids import (
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MATERIAL,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_RELIEF,
    TOOL_MOD_SPLIT,
    TOOL_PLAN_TRACE,
    TOOL_TEXTURE_PROJECTION,
    TOOL_VENT_GENERATOR,
)
from laserprog_studio.tooling.joint_tool import JointCreatorTool, JointTool
from laserprog_studio.tooling.layflat_tool import LayflatCreatorTool, LayflatTool
from laserprog_studio.tooling.material_tool import MaterialCreatorTool, MaterialTool
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.tooling.relief_tool import ReliefCreatorTool, ReliefTool
from laserprog_studio.tooling.split_tool import SplitPlaneCreatorTool, SplitPlaneTool
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool, TextureProjectionTool
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool, VentGeneratorTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


MIGRATED = {
    TOOL_LAYFLAT: (LayflatTool, LayflatCreatorTool),
    TOOL_JOINT: (JointTool, JointCreatorTool),
    TOOL_MATERIAL: (MaterialTool, MaterialCreatorTool),
    TOOL_TEXTURE_PROJECTION: (TextureProjectionTool, TextureProjectionCreatorTool),
    TOOL_MOD_RELIEF: (ReliefTool, ReliefCreatorTool),
    TOOL_MOD_EXTRUDE_DOWN: (ExtrudeDownTool, ExtrudeDownCreatorTool),
    TOOL_MOD_SPLIT: (SplitPlaneTool, SplitPlaneCreatorTool),
    TOOL_VENT_GENERATOR: (VentGeneratorTool, VentGeneratorCreatorTool),
}


def test_remaining_tools_use_creator_runtime_and_declarative_panels() -> None:
    for tool_id, (runtime_cls, creator_cls) in MIGRATED.items():
        spec = get_tool_spec(tool_id)
        runtime = get_studio_tool(tool_id)
        panel = get_tool_panel_spec(tool_id)

        assert spec is not None, tool_id
        assert spec.open_hook is None, tool_id
        assert spec.close_hook is None, tool_id
        assert isinstance(runtime, runtime_cls), tool_id
        assert isinstance(runtime, CreatorStudioToolAdapter), tool_id
        assert isinstance(runtime.creator, creator_cls), tool_id
        assert panel is not None, tool_id
        assert panel.builder == "panel_declarative_creator_tool", tool_id


def test_planar_tools_are_creator_runtime_tools() -> None:
    plan = get_tool_panel_spec(TOOL_PLAN_TRACE)
    vent = get_tool_panel_spec(TOOL_VENT_GENERATOR)

    assert get_tool_spec(TOOL_PLAN_TRACE).open_hook is None
    assert get_tool_spec(TOOL_VENT_GENERATOR).open_hook is None
    assert plan is not None and plan.builder == "panel_declarative_creator_tool"
    assert vent is not None and vent.builder == "panel_declarative_creator_tool"
