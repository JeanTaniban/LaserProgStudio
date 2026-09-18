# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder


def test_pass109_painter_is_persistent_not_destructive() -> None:
    source = read_tool_core_diag_scene_runtime_source()

    render_body = source.split("def render_context", 1)[1]
    assert "rendered_persistent" in source
    assert "no clear/rebuild during interaction" in source
    assert "clear_tool_core_diag_scene(self.owner)" not in render_body
    assert "state.meshes" in source
    assert "SetVisibility" in source
    assert "copy_from" in source or "DeepCopy" in source


def test_pass109_hover_and_grab_update_handle_state_without_rebuilding_demo() -> None:
    runner = CoreDiagRunner()
    demo = HandleDemoBuilder(runner.ctx)
    demo.build_demo()
    stats_before = runner.backend_stats()

    demo.apply_hover("demo:1:grab")
    demo.apply_grabbed("demo:1:grab")
    demo.apply_hover(None)
    stats_after = runner.backend_stats()

    assert stats_after["created"] == stats_before["created"]
    assert stats_after["removed"] == stats_before["removed"]
    assert stats_after["full_renders"] >= stats_before["full_renders"]


def test_pass109_controller_does_not_rewrite_text_report_on_every_pointer_move() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    move_body = source.split("def handle_pointer_move", 1)[1].split("def handle_pointer_release", 1)[0]

    assert "_render_demo_scene()" in move_body
    assert "_write_report" not in move_body
