from __future__ import annotations

from types import SimpleNamespace

import pytest

from laserprog_studio.app_context import AppContext
from laserprog_studio.application.boolean_controller import BooleanController
from laserprog_studio.boolean_ops import BooleanEmptyResult, boolean_difference, is_closed_triangle_mesh
from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _rectangle_sketch(x0: float, y0: float, width: float, height: float) -> SketchDocument:
    sketch = SketchDocument()
    point_ids = [
        sketch.add_point((x0, y0)).id,
        sketch.add_point((x0 + width, y0)).id,
        sketch.add_point((x0 + width, y0 + height)).id,
        sketch.add_point((x0, y0 + height)).id,
    ]
    for a, b in zip(point_ids, point_ids[1:] + point_ids[:1]):
        sketch.add_line(a, b)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=True,
            split_curves_at_vertices=True,
            solve_faces=True,
        )
    )
    return sketch


def _plan_tracer_volume(x0: float, y0: float, width: float, height: float, depth: float = 10.0):
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = make_locked_plane("top", depth=0.0)
    tool._state.sketch = _rectangle_sketch(x0, y0, width, height)
    tool._state.extrusion_depth = depth
    return tool._build_apply_mesh()


def _box(*, size_x: float, size_y: float, size_z: float, pos_x: float, pos_y: float, pos_z: float):
    return build_box(
        PrimitiveBuildRequest(
            primitive_id="box",
            values={
                "size_x": size_x,
                "size_y": size_y,
                "size_z": size_z,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "pos_z": pos_z,
            },
            name_index=1,
        )
    )


def test_plan_tracer_volume_is_boolean_ready_against_primitive() -> None:
    cutter = _plan_tracer_volume(8.0, 8.0, 18.0, 18.0)
    target = _box(size_x=40.0, size_y=40.0, size_z=12.0, pos_x=20.0, pos_y=20.0, pos_z=6.0)

    result = boolean_difference(target, cutter, cutter_margin_mm=0.0)

    assert is_closed_triangle_mesh(result.vertices, result.triangles) == (True, 0, 0)
    assert len(result.triangles) > 0


def test_two_plan_tracer_volumes_can_be_subtracted() -> None:
    target = _plan_tracer_volume(0.0, 0.0, 40.0, 30.0)
    cutter = _plan_tracer_volume(10.0, 8.0, 15.0, 12.0)

    result = boolean_difference(target, cutter, cutter_margin_mm=0.0)

    assert is_closed_triangle_mesh(result.vertices, result.triangles) == (True, 0, 0)
    assert len(result.triangles) > 0


def test_complete_plan_tracer_subtraction_is_classified_as_consumed_target() -> None:
    cutter = _plan_tracer_volume(0.0, 0.0, 40.0, 30.0)
    target = _box(size_x=10.0, size_y=10.0, size_z=5.0, pos_x=20.0, pos_y=15.0, pos_z=2.5)

    with pytest.raises(BooleanEmptyResult, match="consumed the complete target"):
        boolean_difference(target, cutter, cutter_margin_mm=0.0)


class _MessageBox:
    @staticmethod
    def information(*_args, **_kwargs):
        return None

    @staticmethod
    def warning(*_args, **_kwargs):
        return None

    @staticmethod
    def critical(*_args, **_kwargs):
        return None


class _Owner:
    TOOL_NONE = "none"

    def __init__(self, meshes):
        self._meshes = list(meshes)
        self.selected_indices = [0]
        self.active_index = 0
        self.active_tool = self.TOOL_NONE
        self.project_preferences = SimpleNamespace(laser=SimpleNamespace(boolean_subtract_margin_mm=0.0))
        self._boolean_job_active = False
        self.logs = []

    def current_meshes(self):
        return self._meshes

    def _selected_transform_indices(self):
        return list(self.selected_indices)

    def has_preview(self):
        return False

    def ui_log(self, text):
        self.logs.append(str(text))


def _context(owner) -> AppContext:
    return AppContext(
        owner=owner,
        selection=SelectionState(),
        transform=TransformState(),
        tool=ToolState(),
        preview=PreviewState(),
        layout=UiLayoutState(),
        render=RenderState(),
        clipboard=ClipboardState(),
    )


def test_subtract_touching_removes_a_target_consumed_by_plan_tracer_cutter(monkeypatch) -> None:
    cutter = _plan_tracer_volume(0.0, 0.0, 40.0, 30.0)
    target = _box(size_x=10.0, size_y=10.0, size_z=5.0, pos_x=20.0, pos_y=15.0, pos_z=2.5)
    owner = _Owner([cutter, target])
    controller = BooleanController(_context(owner))
    captured = {}

    monkeypatch.setattr("laserprog_studio.application.boolean_controller._qmessagebox", lambda: _MessageBox)
    monkeypatch.setattr(controller, "blocked_message", lambda: False)
    monkeypatch.setattr(controller, "touching_mesh_indices", lambda _cutter_index, _meshes: [1])

    def run_now(*, key, description, worker):
        captured["result"] = worker()

    monkeypatch.setattr(controller, "_run_boolean_job", run_now)

    controller.subtract_touching()

    result = captured["result"]
    assert len(result.meshes) == 1
    assert result.meshes[0].name == cutter.name
    assert result.selected_indices == [0]
    assert result.active_index == 0
    assert "removed=[1]" in result.reason
