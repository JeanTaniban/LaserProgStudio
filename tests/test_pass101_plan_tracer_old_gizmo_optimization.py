# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_pass101_plan_tracer_restores_old_mesh_gizmos_with_cached_templates() -> None:
    source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")

    assert "actual small 3D spheres" in source
    assert "cloud.glyph(geom=sphere" in source
    assert "_planar_point_sphere_cache" in source
    assert "phi_resolution=6 if lightweight else 10" in source


def test_pass101_interactive_old_gizmos_stay_batched_and_lightweight() -> None:
    source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")

    assert 'self._polylines_actor(polylines, name="plan_trace_element_lines"' in source
    assert 'self._point_actor(point_cloud, name="plan_trace_element_points"' in source
    assert "lightweight=lightweight" in source
    assert "size=40.0 if lightweight else 46.0" in source
