# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import TOOL_API_VERSION, styles
from laserprog_studio.tool_api.actors import point, line
from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabLineStyle, LabPointStyle, LabVisualState
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.diagnostic.runner import CoreDiagRunner


def test_pass131_native_style_catalog_is_public_and_complete() -> None:
    assert TOOL_API_VERSION == "0.13.0"
    assert {item.value for item in LabPointStyle} == {style.id for style in styles.list_point_styles()}
    assert {"solid", "ring", "target", "diamond", "square", "arrow", "axis", "chevron", "triad", "minimal", "translate_arrow"}.issubset(
        {style.id for style in styles.list_point_styles()}
    )
    assert {"solid", "selectable", "grabbable", "hover", "selected", "grabbed", "fixed", "guide", "construction", "axis", "preview", "warning", "error"}.issubset(
        {style.id for style in styles.list_line_styles()}
    )
    visual = styles.resolve_actor_visual(interaction="grabbable", point_style_id="chevron", line_style_id="warning", visual_state="grabbed")
    assert visual.point_style_id == "chevron"
    assert visual.line_style_id == "warning"
    assert visual.visual_state.value == "grabbed"
    assert visual.radius_px > 11
    assert visual.line_payload["style_id"] == "warning"


def test_pass131_actor_factories_accept_native_visual_styles() -> None:
    p = point("p", (0, 0, 0), point_style="triad", line_style="guide", visual_state="hover")
    e = line("e", (0, 0, 0), (1, 0, 0), interaction="grabbable", point_style="axis", line_style="grabbed", visual_state="selected")
    assert p.metadata == {"point_style": "triad", "line_style": "guide", "visual_state": "hover"}
    assert e.metadata["point_style"] == "axis"
    assert e.metadata["line_style"] == "grabbed"
    assert e.metadata["visual_state"] == "selected"


def test_pass131_api_lab_can_place_all_styles_and_benchmark_them() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="test.pass131")
    lab.setup()
    lab.set_options(
        actor_kind="line",
        interaction="grabbable",
        point_style=LabPointStyle.TRANSLATE_ARROW.value,
        line_style=LabLineStyle.CONSTRUCTION.value,
        visual_state=LabVisualState.HOVER.value,
    )
    snap = lab.add_from_options()
    actor = next(actor for actor in ctx.selection.actors(owner_tool="test.pass131") if actor.id.startswith("api_lab:line_") and actor.metadata.get("line_style") == "construction")
    assert actor.metadata["point_style"] == "translate_arrow"
    assert actor.metadata["visual_state"] == "hover"
    assert snap.lines >= 3

    report = lab.run_benchmark(iterations=40)
    assert report.ok
    assert any(case.name == "API native style resolution" for case in report.cases)
    assert "tool_api.styles" in report.to_markdown()


def test_pass131_diagnostic_panel_exposes_all_native_style_enums() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    runner = Path("src/laserprog_studio/tool_core/diagnostic/runner.py").read_text(encoding="utf-8")

    assert "point_style" in source
    assert "line_style" in source
    assert "visual_state" in source
    assert "Translate arrow" in source
    assert "Construction" in source
    assert "api_lab_set_options" in controller and "point_style" in controller
    assert "point_style" in runner and "visual_state" in runner


def test_pass131_runner_full_validation_includes_native_style_resolution() -> None:
    runner = CoreDiagRunner()
    runner.run_full_api_validation()
    assert runner.last_api_test_report is not None and runner.last_api_test_report.ok
    assert runner.last_api_test_report.total == 14
    assert runner.last_api_lab_benchmark is not None and runner.last_api_lab_benchmark.ok
    assert any(case.name == "API native style resolution" for case in runner.last_api_lab_benchmark.cases)
