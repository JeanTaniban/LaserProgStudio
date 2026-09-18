# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.planar_tools import PlanarToolConfig, snap_plane_point


def test_pass99_smart_snap_priority_preserves_endpoint_when_grid_is_on() -> None:
    snapped, label = snap_plane_point(
        (20.4, 0.3),
        PlanarToolConfig(grid_snap_enabled=True, smart_snap_enabled=True, grid_step=5.0, smart_snap_tolerance=5.0, smart_snap_priority=True),
        anchor_points=[(20.25, 0.25)],
    )

    assert snapped == (20.25, 0.25)
    assert label == "smart point"


def test_pass99_grid_snap_is_fallback_when_no_smart_hit_exists() -> None:
    snapped, label = snap_plane_point(
        (22.4, 7.6),
        PlanarToolConfig(grid_snap_enabled=True, smart_snap_enabled=True, grid_step=5.0, smart_snap_tolerance=1.0, smart_snap_priority=True),
        anchor_points=[(100.0, 100.0)],
    )

    assert snapped == (20.0, 10.0)
    assert label == "grid 5"


def test_pass99_plan_trace_handles_are_large_optimized_old_style_gizmos() -> None:
    source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")

    assert "_cached_point_sphere" in source
    assert "theta_resolution=10 if lightweight else 18" in source
    assert "cloud.glyph" in source
    assert "render_points_as_spheres=True" in source
    assert "size=38.0 if lightweight else 42.0" in source


def test_pass99_interactive_drag_uses_partial_overlay_refresh() -> None:
    preview = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")
    controller = Path("src/laserprog_studio/application/planar_tool_controller.py").read_text(encoding="utf-8")

    assert "INTERACTIVE_PREVIEW_ACTOR_NAMES" in preview
    assert "interactive_only=bool(lightweight)" in preview
    assert "Full face" in controller
    assert "1.0 / 30.0" in controller
