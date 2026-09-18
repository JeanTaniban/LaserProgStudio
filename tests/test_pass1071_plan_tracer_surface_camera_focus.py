# -*- coding: utf-8 -*-
from __future__ import annotations

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_api import plan2d
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tooling.plan_trace_2d.snap import PlanTrace2DSnapService


class _OwnerWithFocus:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def align_camera_to_plan_surface(self, **kwargs):
        self.calls.append(dict(kwargs))


def test_plan2d_surface_camera_alignment_accepts_focus_bounds_for_object_framing() -> None:
    ctx = ToolContext()
    owner = _OwnerWithFocus()
    ctx.owner = owner
    plane = make_locked_plane("top", depth=3.0)
    bounds = (10.0, 210.0, -20.0, 80.0, 0.0, 30.0)

    assert plan2d.align_camera_to_plan_surface(ctx, plane, anchor_world=(20.0, 30.0, 3.0), focus_bounds=bounds) is True

    assert owner.calls
    assert owner.calls[-1]["focus_bounds"] == bounds
    assert owner.calls[-1]["origin"] == (20.0, 30.0, 3.0)


def test_plan_tracer_surface_pick_uses_clicked_object_bounds_for_camera_zoom() -> None:
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    service = PlanTrace2DSnapService(tool)
    mesh = WorkMesh(
        "large_board",
        [(10.0, -20.0, 0.0), (210.0, -20.0, 0.0), (210.0, 80.0, 30.0), (10.0, 80.0, 30.0)],
        [(0, 1, 2), (0, 2, 3)],
    )
    ctx.document.bind(type("Doc", (), {"meshes": [mesh]})())

    pick = type("Pick", (), {"object_index": 0, "object_id": getattr(mesh, "mesh_id", "")})()

    assert service._picked_object_bounds(ctx, pick) == (10.0, 210.0, -20.0, 80.0, 0.0, 30.0)


def test_plan_tracer_snap_passes_picked_object_bounds_to_surface_camera_api() -> None:
    source = __import__("pathlib").Path("src/laserprog_studio/tooling/plan_trace_2d/snap.py").read_text(encoding="utf-8")
    assert "focus_bounds=self._picked_object_bounds(ctx, picked)" in source
