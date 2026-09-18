# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tooling.ids import TOOL_VOLUME_MEASURE
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec
from laserprog_studio.tooling.cavity_volume_tool import CavityVolumeCreatorTool, format_cavity_volume_report
from laserprog_studio.geometry_ops.cavity_volume import CavityVolumeReport

ROOT = Path(__file__).resolve().parents[1]


def test_cavity_volume_uses_creator_runtime_and_declarative_panel() -> None:
    tool = get_studio_tool(TOOL_VOLUME_MEASURE)
    spec = get_tool_spec(TOOL_VOLUME_MEASURE)
    panel = get_tool_panel_spec(TOOL_VOLUME_MEASURE)

    assert spec is not None
    assert spec.open_hook is None
    assert spec.close_hook is None
    assert tool is not None
    assert tool.__class__.__name__ == "CavityVolumeTool"
    assert isinstance(tool.creator, CavityVolumeCreatorTool)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_cavity_volume_legacy_ui_paths_are_removed() -> None:
    src_root = ROOT / "src" / "laserprog_studio"
    assert not (src_root / "controllers" / "cavity_volume_tool.py").exists()

    forbidden = (
        "panel_volume_measure_tool",
        "update_cavity_volume_report",
        "_refresh_cavity_report_from_selection",
        "volume_measure_button",
        "volume_measure_report",
        "CavityVolumeToolMixin",
    )
    for path in src_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"legacy token {token!r} remains in {path}"


def test_cavity_volume_creator_tool_is_owner_isolated() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "tooling" / "cavity_volume_tool.py").read_text(encoding="utf-8")
    forbidden = ("ctx.owner", "getattr(ctx, \"owner\"", "mesh_list", "selected_indices =")
    for token in forbidden:
        assert token not in source


def test_cavity_volume_report_formatter_keeps_existing_units() -> None:
    report = CavityVolumeReport(
        mesh_name="demo",
        triangle_count=12,
        vertex_count=8,
        shell_count=2,
        closed_shell_count=2,
        cavity_count=1,
        outer_volume_mm3=2_000_000.0,
        cavity_volume_mm3=125_000.0,
        warning=None,
    )

    text = format_cavity_volume_report(report, selected_index="00")

    assert "Part(s): 00 - demo" in text
    assert "0.1250 L" in text
    assert "125 000 mm³" in text
    assert "Closed shells: 2/2" in text
