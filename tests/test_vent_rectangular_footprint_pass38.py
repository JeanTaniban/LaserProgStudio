# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh
from laserprog_studio.planar_tools.vent_preview_snap import corridor_bounds, corridor_outline_paths, rectangular_vent_footprint_geometries
from shapely.geometry import LineString


def _rect_draft() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.waypoints = [(0.0, 0.0), (60.0, 0.0), (120.0, 0.0)]
    return draft


def _span_at_x(mesh, x: float, *, tol: float = 1e-6) -> float:
    ys = [float(v[1]) for v in mesh.vertices if abs(float(v[0]) - float(x)) <= tol]
    assert ys, f"no mesh vertices at x={x}"
    return max(ys) - min(ys)


def _footprint_span_at_x(draft: VentPathDraft, x: float) -> float:
    outer, _inner = rectangular_vent_footprint_geometries(draft, draft.smoothed_centerline())
    cut = outer.intersection(LineString([(float(x), -1000.0), (float(x), 1000.0)]))
    bounds = cut.bounds
    return float(bounds[3] - bounds[1]) if bounds else 0.0


def test_pass38_preview_uses_unioned_corridor_outline_for_tight_curve() -> None:
    center = [(0.0, 0.0), (40.0, 0.0), (0.0, 8.0)]
    rings = corridor_outline_paths(center, 8.0)

    assert len(rings) >= 1
    assert len(rings[0]) >= 4
    bounds = corridor_bounds(center, 8.0)
    assert bounds is not None
    min_x, min_y, max_x, max_y = bounds
    assert min_x >= -8.1
    assert max_x <= 49.0
    assert min_y >= -8.1
    assert max_y <= 16.1


def test_pass38_rectangular_mesh_uses_same_footprint_model_and_ignores_legacy_only_walls() -> None:
    full = _rect_draft()
    legacy = _rect_draft()
    legacy.only_walls = True

    full_mesh = make_vent_path_mesh(full)
    legacy_mesh = make_vent_path_mesh(legacy)

    assert len(full_mesh.vertices) == len(legacy_mesh.vertices)
    assert len(full_mesh.triangles) == len(legacy_mesh.triangles)
    assert _span_at_x(full_mesh, 0.0) == 24.0
    assert _span_at_x(full_mesh, 120.0) == 24.0


def test_pass38_rectangular_flare_changes_footprint_end_widths() -> None:
    draft = _rect_draft()
    draft.flare_side = VentFlareSide.BOTH
    draft.flare_factor = 1.6
    draft.mark_end_flare_finalized(True)

    mesh = make_vent_path_mesh(draft)
    assert mesh.vertices

    assert _footprint_span_at_x(draft, 2.0) > _footprint_span_at_x(draft, 60.0)
    assert _footprint_span_at_x(draft, 118.0) > _footprint_span_at_x(draft, 60.0)
