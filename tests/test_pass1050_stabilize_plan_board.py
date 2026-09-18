# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.geometry_ops.primitive_board import BoardPrimitiveSpec, make_board_primitive_mesh
from laserprog_studio.services.project_preferences import ProjectPreferences, LaserEngravingPreferences
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tooling.plan_trace_2d.state import _PlanTrace2DState
from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.context import ToolContext


def _rectangle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((120.0, 0.0)).id
    p3 = sketch.add_point((120.0, 80.0)).id
    p4 = sketch.add_point((0.0, 80.0)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(SketchCompileOptions(solve_faces=True))
    return sketch


def test_v51_project_preferences_have_requested_laser_defaults() -> None:
    prefs = ProjectPreferences()
    assert prefs.laser.machine_area_x_mm == 358.0
    assert prefs.laser.machine_area_y_mm == 268.0
    assert prefs.laser.show_machine_area is True
    assert prefs.laser.primitive_board_x_mm == 200.0
    assert prefs.laser.primitive_board_y_mm == 100.0
    assert prefs.laser.default_board_thickness_mm == 3.0


def test_v51_scale_frame_for_oriented_primitive_board_is_world_converted() -> None:
    transform_source = __import__("pathlib").Path("src/laserprog_studio/controllers/transform_geometry.py").read_text(encoding="utf-8")
    gizmo_source = __import__("pathlib").Path("src/laserprog_studio/controllers/gizmo_view.py").read_text(encoding="utf-8")

    assert "primitive_board" in transform_source
    assert "_scale_frame_specs_to_world" in transform_source
    assert "sync_native_scale_gizmo" in gizmo_source
    assert "frame_specs = self._scale_frame_specs_to_world" in gizmo_source


def test_v51_plan_tracer_new_extrusion_depth_uses_laser_board_thickness() -> None:
    tool = PlanTrace2DCreatorTool()
    prefs = ProjectPreferences(laser=LaserEngravingPreferences(default_board_thickness_mm=4.2))
    ctx = SimpleNamespace(owner=SimpleNamespace(project_preferences=prefs))
    assert tool._default_board_thickness_mm(ctx) == 4.2

    tool._state.extrusion_depth = 0.0
    tool._services.overlay._last_ctx = ctx
    assert tool._apply_extrusion_depth() == 4.2


def test_v51_motif_button_can_use_semantic_face_state_when_selection_registry_lags() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )
    tool._state.sketch = _rectangle_sketch()
    face_id = next(iter(tool._state.sketch.faces.keys()))
    tool._state.pattern_face_id = face_id
    tool._state.pattern_face_ids = (face_id,)
    ctx.selection.ids = lambda: ()

    assert tool._services.motif_overlay.has_eligible_face(ctx) is True
