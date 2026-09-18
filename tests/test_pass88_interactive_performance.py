from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


def test_display_lod_keeps_vertices_and_reduces_triangles() -> None:
    from laserprog_studio.rendering.display_lod import make_display_lod_mesh

    mesh = SimpleNamespace(
        name="dense",
        color="#aaaaaa",
        vertices=[(float(i), 0.0, 0.0) for i in range(300_010)],
        triangles=[(i, i + 1, i + 2) for i in range(0, 300_000, 3)],
        uvs=None,
        texture_projections=[],
    )
    display, info = make_display_lod_mesh(mesh, threshold=1_000, target=500)
    assert info.enabled is True
    assert display.vertices is mesh.vertices
    assert len(display.vertices) == len(mesh.vertices)
    assert len(display.triangles) < len(mesh.triangles)
    assert info.displayed_triangles == len(display.triangles)


def test_incremental_renderer_uses_display_lod_before_polydata() -> None:
    source = (STUDIO / "rendering" / "incremental_scene.py").read_text(encoding="utf-8")
    assert "from .display_lod import make_display_lod_mesh" in source
    assert "display_mesh, lod_info = make_display_lod_mesh" in source
    assert "workmesh_to_polydata(display_mesh)" in source
    assert "[LOD] Display LOD" in source


def test_background_task_manager_is_composed_and_shutdown() -> None:
    runtime = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    camera = (STUDIO / "controllers" / "camera.py").read_text(encoding="utf-8")
    manager = (STUDIO / "application" / "background_tasks.py").read_text(encoding="utf-8")
    assert "BackgroundTaskManager" in runtime
    assert "self.background_task_manager = BackgroundTaskManager" in runtime
    assert "manager.shutdown()" in camera
    assert "ThreadPoolExecutor" in manager
    assert "QTimer" in manager


def test_boolean_operations_run_through_worker() -> None:
    source = (STUDIO / "application" / "boolean_controller.py").read_text(encoding="utf-8")
    assert "task_manager_for" in source
    assert "_run_boolean_job" in source
    assert "[BOOLEAN][WORKER]" in source
    assert "_boolean_job_active" in source
    assert "worker receives" in source


def test_modifier_previews_are_debounced_and_backgrounded() -> None:
    source = (STUDIO / "application" / "modifier_preview_controller.py").read_text(encoding="utf-8")
    simplify_source = (STUDIO / "tooling" / "simplify_tool.py").read_text(encoding="utf-8")
    hollow_source = (STUDIO / "tooling" / "hollow_tool.py").read_text(encoding="utf-8")
    assert "ctx.operations.simplify" in simplify_source
    assert "ButtonRow" in simplify_source
    assert "ctx.operations.hollow" in hollow_source
    assert "ButtonRow" in hollow_source
    assert "def _schedule_relief_preview" in source
    assert "def _schedule_extrude_down_preview(self, *, delay_ms: int = 240)" in source
    assert "def _schedule_hollow_preview" not in source
    assert source.count("task_manager_for(self.owner).run") >= 1
    assert "Computing preview in background" in source


def test_acoustic_diffuser_preview_runs_through_creator_jobs() -> None:
    source = (STUDIO / "tooling" / "acoustic_diffuser_tool.py").read_text(encoding="utf-8")
    assert "ctx.jobs.start" in source
    assert "ctx.operations.acoustic_diffuser" in source
    assert "Computing acoustic diffuser preview" in source
