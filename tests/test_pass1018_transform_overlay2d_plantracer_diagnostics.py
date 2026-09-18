# -*- coding: utf-8 -*-
from pathlib import Path


def test_transform_uses_true_foreground_actor2d_backend() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_overlay_2d.py").read_text(encoding="utf-8")
    assert "vtkActor2D" in source
    assert "vtkPolyDataMapper2D" in source
    assert "SetDisplayLocationToForeground" in source
    assert "vtkCommand.StartEvent" in source
    assert "screen_space_overlay = True" in source
    assert "AddActor2D" in source
    for forbidden in ("vtkSphereSource", "vtkConeSource", "vtkCylinderSource", "pv.Sphere(", "pv.Cone(", ".tube("):
        assert forbidden not in source


def test_transform_overlay2d_has_camera_facing_arrows_and_shared_picking() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_overlay_2d.py").read_text(encoding="utf-8")
    api = Path("src/laserprog_studio/application/transform_gizmo_api.py").read_text(encoding="utf-8")
    assert "_choose_display_sign" in source
    assert "facing > 0.14" in source
    assert "display_signs" in source
    assert "def pick(" in source
    assert "renderer.pick(px, py" in api
    assert "native_transform_drag_basis" in api


def test_plan_tracer_report_includes_creator_ui_breakdown() -> None:
    painter = Path("src/laserprog_studio/application/_tool_core_diag_scene_painter.py").read_text(encoding="utf-8")
    overlay = Path("src/laserprog_studio/tooling/plan_trace_2d/overlay.py").read_text(encoding="utf-8")
    actors = Path("src/laserprog_studio/tool_api/plan2d/actors.py").read_text(encoding="utf-8")
    for token in (
        "build_batches",
        "fast_update_misses",
        "minimal_dot_vertices",
        "guide_vertices",
        "line_vertices",
        "fast_update_touched_points_last",
    ):
        assert token in painter
    assert '"creator_ui."' in overlay
    assert "plan2d.actor_visuals." in actors
    assert 'path_name = "fast_drag"' in actors
    assert 'else "full_interaction"' in actors
