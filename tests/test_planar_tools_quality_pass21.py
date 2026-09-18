# -*- coding: utf-8 -*-
from __future__ import annotations

import math

import pytest

from laserprog_studio.planar_tools import (
    PlanarPolygonDraft,
    VentPathDraft,
    VentSectionKind,
    dedupe_consecutive_points,
    make_extruded_polygon_mesh,
    make_locked_plane,
    polygon_self_intersections,
    validate_polygon_for_extrusion,
)


def test_pass21_polygon_validation_rejects_self_intersection() -> None:
    bow_tie = [(0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)]
    result = validate_polygon_for_extrusion(bow_tie, closed=True, extrusion_depth=5.0)
    assert result.ok is False
    assert "self-intersecting" in result.message()
    assert polygon_self_intersections(bow_tie)


def test_pass21_planar_drafts_ignore_consecutive_duplicate_points() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=4.0)
    draft.add_point_plane((0.0, 0.0))
    draft.add_point_plane((0.0, 0.0), min_spacing=0.1)
    draft.add_point_plane((10.0, 0.0))
    draft.add_point_plane((10.0, 10.0))
    assert len(draft.points) == 3
    assert draft.close_polygon() is True
    mesh = make_extruded_polygon_mesh(draft)
    assert len(mesh.vertices) == 6


def test_pass21_mesh_generation_refuses_invalid_trace() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=5.0)
    for point in ((0.0, 0.0), (10.0, 10.0), (0.0, 10.0), (10.0, 0.0)):
        draft.add_point_plane(point)
    draft.close_polygon()
    with pytest.raises(ValueError, match="self-intersecting"):
        make_extruded_polygon_mesh(draft)


def test_pass21_rectangle_vent_dimensions_drive_area() -> None:
    draft = VentPathDraft(make_locked_plane("front"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 5.0
    draft.section.area = 100.0
    assert draft.section_dimensions() == (20.0, 5.0)
    assert math.isclose(draft.section.area, 100.0)


def test_pass21_dedupe_removes_duplicate_closure_point() -> None:
    assert dedupe_consecutive_points([(0, 0), (1, 0), (1, 1), (0, 0)]) == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
