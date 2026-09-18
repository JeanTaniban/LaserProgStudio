# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, UiShowcaseBuilder
from laserprog_studio.tool_core.preview import PreviewKind, TextLabel


def test_pass105_preview_manager_supports_arc_circle_and_text_items() -> None:
    runner = CoreDiagRunner()
    ctx = runner.ctx

    ctx.preview.show_arc("arc", "tool_core_diag", [(0, 0, 0), (1, 1, 0)])
    ctx.preview.show_circle("circle", "tool_core_diag", [(0, 0, 0), (1, 0, 0), (0, 0, 0)])
    text = ctx.preview.show_text("label", "tool_core_diag", "dimension", (2, 2, 0), size_px=16)

    kinds = {item.kind for item in ctx.preview.items(owner_tool="tool_core_diag")}
    assert {PreviewKind.ARC, PreviewKind.CIRCLE, PreviewKind.TEXT}.issubset(kinds)
    assert isinstance(text.payload, TextLabel)
    assert text.payload.text == "dimension"
    assert text.payload.size_px == 16


def test_pass105_ui_showcase_builder_creates_complete_visual_scene() -> None:
    runner = CoreDiagRunner()
    showcase = UiShowcaseBuilder(runner.ctx)

    snapshot = showcase.build_full_showcase()

    assert snapshot.handles >= 90
    assert snapshot.previews >= 10
    assert snapshot.labels >= 8
    assert snapshot.overlay_buttons >= 5
    assert snapshot.drag_updates >= 60
    assert any("line, polyline, circle, arc" in note for note in snapshot.notes)


def test_pass105_runner_exposes_gui_showcase_scenarios() -> None:
    runner = CoreDiagRunner()

    handles = runner.run_ui_handles()
    primitives = runner.run_ui_primitives()
    text = runner.run_ui_text()
    stress = runner.run_ui_stress()
    all_ui = runner.run_ui_showcase()

    assert handles.handles >= 4
    assert primitives.previews >= 5
    assert text.previews >= 4
    assert stress.handles >= 160
    assert all_ui.handles >= 90
    assert "UI showcase" in "\n".join(runner.log)


def test_pass105_diagnostic_panel_exposes_gui_showcase_actions() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    for label in ["API Lab", "Add actor", "Delete selected", "Move selected", "Clear"]:
        assert label in source
    assert "run_api_lab_setup" in source
    assert "api_lab_clear" in source


def test_pass105_live_scene_painter_uses_batched_viewport_approach() -> None:
    source = read_tool_core_diag_scene_runtime_source()
    assert "render_points_as_spheres=True" in source
    assert "line_batch" in source
    assert "add_point_labels" in source
    assert "tool_core_diag_ui_" in source
    assert "clear_tool_core_diag_scene" in source


def test_pass105_doc_exists_and_describes_performance_rules() -> None:
    doc = Path("docs/archive/passes/pass105_tool_core_ui_showcase.md")
    text = doc.read_text(encoding="utf-8")
    assert "Batched primitives" in text
    assert "Position-only updates" in text
    assert "Text labels" in text
