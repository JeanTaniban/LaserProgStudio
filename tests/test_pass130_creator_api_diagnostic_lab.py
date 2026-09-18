# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabInteraction
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.diagnostic.runner import CoreDiagRunner


def test_pass130_api_lab_supports_enum_actor_creation_selection_and_move() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="test.pass130")

    snap = lab.setup()
    assert snap.actors >= 6
    assert snap.lines >= 2

    lab.set_options(actor_kind=LabActorKind.LINE.value, interaction=LabInteraction.GRABBABLE.value, move="+X")
    after_add = lab.add_from_options()
    assert after_add.lines >= 3

    actor_id = lab.select_at((45.0, 0.0), lambda p: (float(p[0]), float(p[1])))
    assert actor_id is not None
    assert ctx.selection.ids() == (actor_id,)

    lab.begin_grab_if_possible(actor_id, (45.0, 0.0), (45.0, 0.0, 0.42))
    moved = lab.move_selected((3.0, 0.0, 0.0))
    lab.end_grab()
    assert moved >= 1
    assert ctx.selection.actor(actor_id).points[0][0] > 45.0

    deleted = lab.delete_selected()
    assert deleted.actors == after_add.actors - 1


def test_pass130_api_lab_benchmark_is_exposed_from_runner() -> None:
    runner = CoreDiagRunner()
    snapshot = runner.run_api_lab_benchmark(40)

    assert runner.last_api_lab_benchmark is not None
    assert runner.last_api_lab_benchmark.ok
    assert len(runner.last_api_lab_benchmark.cases) >= 5
    assert snapshot.profiler_values.get("diag.api_lab.benchmark") == 1
    markdown = runner.last_api_lab_benchmark.to_markdown()
    assert "Creator API Lab benchmark" in markdown
    assert "API smart snap query" in markdown


def test_pass130_diagnostic_panel_is_focused_on_creator_api_lab() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])

    assert "Creator API Lab" in source
    assert "actor_kind" in source
    assert "interaction" in source
    assert "move" in source
    assert "Add actor" in source
    assert "Delete selected" in source
    assert "Move selected" in source
    assert "Full validation" in source
    assert "run_api_lab_setup" in controller
    assert "run_full_api_validation" in controller


def test_pass130_full_runner_uses_creator_api_validation_path() -> None:
    runner = CoreDiagRunner()
    snapshot = runner.run_all()

    assert runner.last_api_test_report is not None and runner.last_api_test_report.ok
    assert runner.last_api_lab_benchmark is not None and runner.last_api_lab_benchmark.ok
    assert runner.last_bench_report is not None
    assert snapshot.profiler_values.get("diag.api_lab.benchmark") == 1
    assert any("All Creator API diagnostic scenarios completed" in entry for entry in runner.log)
