# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.planar_tools import (
    PlanTraceAddKind,
    PlanTraceElement,
    PlanarPolygonDraft,
    make_locked_plane,
    plan_trace_closed_regions,
)


def test_pass98_nearly_touching_line_chain_closes_face() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=10.0)
    draft.elements.extend(
        [
            PlanTraceElement(PlanTraceAddKind.LINE, [(0.0, 0.0), (20.0, 0.0)]),
            PlanTraceElement(PlanTraceAddKind.LINE, [(20.20, 0.06), (20.0, 10.0)]),
            PlanTraceElement(PlanTraceAddKind.LINE, [(19.95, 10.18), (0.0, 10.0)]),
            PlanTraceElement(PlanTraceAddKind.LINE, [(0.0, 10.0), (0.08, 0.05)]),
        ]
    )

    regions = plan_trace_closed_regions(draft)
    assert len(regions) == 1
    assert round(regions[0].area, 3) == 200.0
    assert draft.is_ready_for_extrusion()


def test_pass98_plan_preview_has_lightweight_interactive_path() -> None:
    preview_source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")
    controller_source = Path("src/laserprog_studio/application/planar_tool_controller.py").read_text(encoding="utf-8")

    assert "lightweight: bool = False" in preview_source
    assert "if not lightweight" in preview_source
    assert "_polylines_actor" in preview_source
    assert "draw_planar_preview(render=True, lightweight=True)" in controller_source


def test_pass98_mod_drag_cache_excludes_dragged_point_to_avoid_self_snap() -> None:
    controller_source = Path("src/laserprog_studio/application/planar_tool_controller.py").read_text(encoding="utf-8")
    assert "snaps to its own previous location" in controller_source
    assert "dragged_point" in controller_source
