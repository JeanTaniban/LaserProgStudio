# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.geometry_ops.acoustic_diffuser import AcousticDiffuserSettings
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.app_services import OperationResult
from laserprog_studio.tooling.acoustic_diffuser_tool import AcousticDiffuserCreatorTool, AcousticDiffuserTool
from laserprog_studio.tooling.ids import TOOL_ACOUSTIC_DIFFUSER
from laserprog_studio.tooling.registry import get_studio_tool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_pass156_acoustic_diffuser_uses_creator_runtime_and_panel() -> None:
    tool = get_studio_tool(TOOL_ACOUSTIC_DIFFUSER)
    assert isinstance(tool, AcousticDiffuserTool)
    panel = get_tool_panel_spec(TOOL_ACOUSTIC_DIFFUSER)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_pass156_acoustic_creator_panel_and_operation_contract() -> None:
    ctx = ToolContext()
    tool = AcousticDiffuserCreatorTool()
    tool.on_open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.owner_tool == TOOL_ACOUSTIC_DIFFUSER
    assert ctx.inspector.value("resolution") == "low"
    assert ctx.inspector.value("vent_style") == "holes"
    assert "Helmholtz" in ctx.inspector.value("acoustic_report")

    result = ctx.operations.acoustic_diffuser(
        params={
            "target_frequency_hz": 1200.0,
            "outer_diameter_mm": 120.0,
            "speaker_diameter_mm": 60.0,
            "skirt_thickness_mm": 24.0,
            "vent_style": "none",
            "resolution": "low",
            "vent_count": 3,
            "vent_size_mm": 8.0,
        },
        preview=False,
        owner_tool=TOOL_ACOUSTIC_DIFFUSER,
    )
    assert isinstance(result, OperationResult)
    assert result.ok
    assert len(result.meshes) == 2
    assert result.metadata["mesh_count"] == 2
    assert result.metadata["target_frequency_hz"] == 1200.0


def test_pass156_acoustic_creator_has_no_direct_owner_ui_dependencies() -> None:
    source = Path("src/laserprog_studio/tooling/acoustic_diffuser_tool.py").read_text(encoding="utf-8")
    forbidden = (
        "ctx.owner",
        "getattr(ctx, \"owner\"",
        "acoustic_diffuser_target_f",
        "acoustic_diffuser_report",
        "set_preview_meshes",
        "selected_indices =",
        "focus_camera_on",
    )
    for needle in forbidden:
        assert needle not in source


def test_pass156_acoustic_values_map_resolution_to_backend_quality() -> None:
    ctx = ToolContext()
    tool = AcousticDiffuserCreatorTool()
    tool.on_open(ctx)
    ctx.inspector.update_values({"resolution": "high", "vent_style": "slots", "vent_count": 7}, notify=False)
    settings = tool.settings(ctx)
    assert isinstance(settings, AcousticDiffuserSettings)
    assert settings.quality == 112
    assert settings.vent_style == "slots"
    assert settings.vent_count == 7
