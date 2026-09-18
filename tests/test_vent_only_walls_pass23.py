# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh


def _rectangle_vent(*, only_walls: bool) -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.only_walls = only_walls
    draft.waypoints = [(0.0, 0.0), (60.0, 0.0)]
    return draft


def test_pass23_only_walls_is_effective_only_for_rectangle() -> None:
    rect = _rectangle_vent(only_walls=True)
    assert rect.uses_only_walls() is True

    roundish = VentPathDraft(make_locked_plane("top"))
    roundish.section.kind = VentSectionKind.ROUND
    roundish.section.area = 100.0
    roundish.wall_thickness = 2.0
    roundish.only_walls = True
    roundish.waypoints = [(0.0, 0.0), (60.0, 0.0)]
    assert roundish.uses_only_walls() is False


def test_pass23_rectangle_only_walls_is_legacy_and_does_not_change_new_evt_mesh() -> None:
    full = make_vent_path_mesh(_rectangle_vent(only_walls=False))
    walls_only = make_vent_path_mesh(_rectangle_vent(only_walls=True))

    # Pass 38 simplified EVT to one rectangular footprint mesh.  The old
    # Only-walls flag remains load-compatible but is no longer exposed in the
    # user workflow and should not create a second geometry path.
    assert len(walls_only.triangles) == len(full.triangles)
    assert len(walls_only.vertices) == len(full.vertices)


def test_pass23_round_vent_ignores_only_walls_flag() -> None:
    base = VentPathDraft(make_locked_plane("top"))
    base.section.kind = VentSectionKind.ROUND
    base.section.area = 100.0
    base.wall_thickness = 2.0
    base.waypoints = [(0.0, 0.0), (60.0, 0.0)]

    closed = make_vent_path_mesh(base)
    base.only_walls = True
    still_closed = make_vent_path_mesh(base)

    assert len(still_closed.triangles) == len(closed.triangles)
