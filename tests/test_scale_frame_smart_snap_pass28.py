# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from laserprog_studio.snapping import find_smart_scale_edge_snap


@dataclass
class DummyMesh:
    vertices: list[tuple[float, float, float]]


def box_vertices(x0: float, x1: float, y0: float = 0.0, y1: float = 10.0, z0: float = 0.0, z1: float = 10.0):
    return [
        (x, y, z)
        for x in (x0, x1)
        for y in (y0, y1)
        for z in (z0, z1)
    ]


def test_scale_frame_max_edge_snaps_to_target_min_contact() -> None:
    moving = DummyMesh(box_vertices(0.0, 19.55))
    target = DummyMesh(box_vertices(20.0, 30.0))

    snap = find_smart_scale_edge_snap(
        meshes=[moving, target],
        moving_index=0,
        moving_indices={0},
        proposed_vertices=moving.vertices,
        axis="x",
        axis_vector=(1.0, 0.0, 0.0),
        dragged_anchor="max",
        tolerance=1.0,
    )

    assert snap.mode == "smart"
    assert snap.candidate is not None
    assert snap.candidate.kind == "contact"
    assert snap.candidate.moving_anchor == "max"
    assert snap.candidate.target_anchor == "min"
    assert abs(snap.correction - 0.45) < 1e-9


def test_scale_frame_min_edge_snaps_to_target_max_contact() -> None:
    moving = DummyMesh(box_vertices(10.35, 30.0))
    target = DummyMesh(box_vertices(0.0, 10.0))

    snap = find_smart_scale_edge_snap(
        meshes=[target, moving],
        moving_index=1,
        moving_indices={1},
        proposed_vertices=moving.vertices,
        axis="x",
        axis_vector=(1.0, 0.0, 0.0),
        dragged_anchor="min",
        tolerance=1.0,
    )

    assert snap.mode == "smart"
    assert snap.candidate is not None
    assert snap.candidate.kind == "contact"
    assert snap.candidate.moving_anchor == "min"
    assert snap.candidate.target_anchor == "max"
    assert abs(snap.correction + 0.35) < 1e-9


def test_scale_frame_snap_projects_on_local_axis_vector() -> None:
    # Same concept as the X test, but with a local axis pointing along world Y.
    moving = DummyMesh(box_vertices(0.0, 10.0, 0.0, 19.8))
    target = DummyMesh(box_vertices(0.0, 10.0, 20.0, 30.0))

    snap = find_smart_scale_edge_snap(
        meshes=[moving, target],
        moving_index=0,
        moving_indices={0},
        proposed_vertices=moving.vertices,
        axis="y",
        axis_vector=(0.0, 1.0, 0.0),
        dragged_anchor="max",
        tolerance=0.5,
    )

    assert snap.mode == "smart"
    assert abs(snap.correction - 0.2) < 1e-9


def test_scale_frame_snap_ignores_axis_cube_handles_in_transform_drag() -> None:
    source = Path("src/laserprog_studio/controllers/transform_drag.py").read_text(encoding="utf-8")
    assert "find_smart_scale_edge_snap" in source
    assert "_scale_handle_is_frame_edge(self._drag_axis)" in source
    assert "The X/Y/Z cube handles stay free-form" in source
