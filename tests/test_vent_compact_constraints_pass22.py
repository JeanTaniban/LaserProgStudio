# -*- coding: utf-8 -*-
from __future__ import annotations

import math

import pytest

from laserprog_studio.planar_tools import (
    VentPathDraft,
    VentSectionKind,
    clamp_vent_waypoint_candidate,
    make_locked_plane,
    make_vent_path_mesh,
    make_vent_clearance_policy,
)


def _rect_draft(*, compact: bool) -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 10.0
    draft.section.height = 5.0
    draft.section.area = 50.0
    draft.wall_thickness = 3.0
    draft.compact_wall_fusion = compact
    return draft


def test_pass22_rectangle_policy_keeps_spacing_metadata_for_reports() -> None:
    compact = make_vent_clearance_policy(section_kind="rectangle", section_width=10.0, wall_thickness=3.0, compact_wall_fusion=True)
    normal = make_vent_clearance_policy(section_kind="rectangle", section_width=10.0, wall_thickness=3.0, compact_wall_fusion=False)
    round_policy = make_vent_clearance_policy(section_kind="round", section_width=10.0, wall_thickness=3.0, compact_wall_fusion=True)

    assert math.isclose(compact.min_centerline_spacing, 13.0)
    assert math.isclose(normal.min_centerline_spacing, 16.0)
    assert math.isclose(round_policy.min_centerline_spacing, 16.0)
    assert compact.allows_shared_walls is True
    assert round_policy.allows_shared_walls is False


def test_pass22_close_parallel_passes_are_allowed_in_clean_preview_workflow() -> None:
    draft = _rect_draft(compact=True)
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0), (40.0, 12.0), (0.0, 12.0)]

    assert draft.validation_result().ok is True


def test_pass22_round_and_rectangle_share_the_same_simple_centerline_validation() -> None:
    rect = _rect_draft(compact=False)
    rect.waypoints = [(0.0, 0.0), (40.0, 0.0), (40.0, 13.0), (0.0, 13.0)]
    assert rect.validation_result().ok is True
    assert rect.clearance_policy().allows_shared_walls is True

    roundish = VentPathDraft(make_locked_plane("top"))
    roundish.section.kind = VentSectionKind.ROUND
    roundish.section.area = math.pi * 25.0
    roundish.wall_thickness = 3.0
    roundish.compact_wall_fusion = True
    roundish.waypoints = [(0.0, 0.0), (40.0, 0.0), (40.0, 13.0), (0.0, 13.0)]
    assert roundish.validation_result().ok is True


def test_pass22_candidate_on_existing_centerline_is_allowed_without_touch_safety() -> None:
    draft = _rect_draft(compact=True)
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0)]
    result = clamp_vent_waypoint_candidate(draft.waypoints, (20.0, 0.0), draft.clearance_policy(), anchor=draft.waypoints[-1])

    assert result.valid is True
    assert result.was_clamped is False
    assert result.point == (20.0, 0.0)
    assert result.message == ""


def test_pass22_mesh_generation_refuses_self_crossing_vent() -> None:
    draft = _rect_draft(compact=True)
    draft.waypoints = [(0.0, 0.0), (40.0, 40.0), (0.0, 40.0), (40.0, 0.0)]
    with pytest.raises(ValueError, match="self-intersects"):
        make_vent_path_mesh(draft)
