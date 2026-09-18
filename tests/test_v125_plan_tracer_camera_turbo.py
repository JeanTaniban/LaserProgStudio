from __future__ import annotations

import time
from types import MethodType, SimpleNamespace

import numpy as np
import pytest

from laserprog_studio.application.camera_motion_diagnostics import CameraState
from laserprog_studio.application.projected_drawing_2d import (
    ProjectedDrawingOverlay2D,
    _BatchKey,
    _BatchVisual,
    _HandleVisual,
    _TextVisual,
)
from laserprog_studio.rendering.render_scheduler import CentralRenderScheduler
from laserprog_studio.tool_api.projected_drawing import ProjectedHandle, ProjectedText


class _Modified:
    def __init__(self) -> None:
        self.calls = 0

    def Modified(self) -> None:
        self.calls += 1


class _TextActor:
    def __init__(self) -> None:
        self.position = None

    def SetDisplayPosition(self, x: int, y: int) -> None:
        self.position = (int(x), int(y))


class _ProjectionCamera:
    def GetWindowCenter(self):
        return (0.0, 0.0)

    def GetViewShear(self):
        return (0.0, 0.0, 1.0)


class _ProjectionRenderer:
    def __init__(self) -> None:
        self.camera = _ProjectionCamera()

    def GetActiveCamera(self):
        return self.camera

    def GetOrigin(self):
        return (0, 0)

    def GetSize(self):
        return (1000, 800)


def _camera_state(*, focal=(0.0, 0.0, 0.0), scale=10.0) -> CameraState:
    return CameraState(
        position=(focal[0], focal[1], 10.0),
        focal_point=focal,
        view_up=(0.0, 1.0, 0.0),
        parallel_scale=scale,
        view_angle=30.0,
        parallel_projection=True,
    )


def test_parallel_camera_affine_scales_batches_but_preserves_handle_pixel_size() -> None:
    overlay = ProjectedDrawingOverlay2D.__new__(ProjectedDrawingOverlay2D)
    overlay._diagnostic_metrics = {}
    overlay._last_projection_viewport = (0.0, 0.0, 1000.0, 800.0)
    overlay._parallel_camera_affine = MethodType(lambda self, _previous, _current: (2.0, 500.0, 400.0, 10.0, -20.0), overlay)

    points = _Modified()
    polydata = _Modified()
    vtk_data = _Modified()
    batch_array = np.asarray(((400.0, 300.0, 0.0), (600.0, 500.0, 0.0)), dtype=np.float64)
    key = _BatchKey(0, "lines", "#FFFFFF", 1.0, 1.0)
    overlay._visuals = {
        key: _BatchVisual(
            key=key,
            actor=object(),
            mapper=object(),
            polydata=polydata,
            points=points,
            cells=object(),
            display_array=batch_array,
            vtk_display_data=vtk_data,
        )
    }

    handle_points = _Modified()
    handle_polydata = _Modified()
    handle_vtk_data = _Modified()
    handle_array = np.asarray(((95.0, 100.0, 0.0), (105.0, 100.0, 0.0)), dtype=np.float64)
    handle = ProjectedHandle(id="h", position=(0.0, 0.0, 0.0))
    overlay._handle_visuals = {
        "h": _HandleVisual(
            primitive=handle,
            actor=object(),
            mapper=object(),
            polydata=handle_polydata,
            points=handle_points,
            line_cells=object(),
            poly_cells=object(),
            display_array=handle_array,
            vtk_display_data=handle_vtk_data,
            display_center=(100.0, 100.0),
        )
    }

    text_actor = _TextActor()
    overlay._text_visuals = {
        "t": _TextVisual(
            primitive=ProjectedText(id="t", text="T", position=(0.0, 0.0, 0.0)),
            actor=text_actor,
            display_anchor=(200.0, 150.0),
            display_position=(200.0, 150.0),
        )
    }

    assert overlay._apply_parallel_camera_affine(_camera_state(), _camera_state(scale=5.0)) is True
    assert np.allclose(batch_array[:, :2], np.asarray(((310.0, 180.0), (710.0, 580.0))))
    # Handle center follows the affine transform, while its 10 px diameter stays 10 px.
    assert overlay._handle_visuals["h"].display_center == pytest.approx((-290.0, -220.0))
    assert np.linalg.norm(handle_array[1, :2] - handle_array[0, :2]) == pytest.approx(10.0)
    assert text_actor.position == (-90, -120)
    assert overlay._diagnostic_metrics["last_projection_backend"] == "parallel_affine"


def test_parallel_camera_affine_formula_matches_pan_and_zoom_geometry() -> None:
    overlay = ProjectedDrawingOverlay2D.__new__(ProjectedDrawingOverlay2D)
    overlay.owner = SimpleNamespace(plotter=SimpleNamespace(renderer=_ProjectionRenderer()))
    overlay._last_projection_viewport = (0.0, 0.0, 1000.0, 800.0)

    transform = overlay._parallel_camera_affine(
        _camera_state(focal=(0.0, 0.0, 0.0), scale=10.0),
        _camera_state(focal=(1.0, 2.0, 0.0), scale=5.0),
    )

    assert transform == pytest.approx((2.0, 500.0, 400.0, -80.0, -160.0))


def test_render_scheduler_allows_120_hz_budget_for_plan_trace_camera() -> None:
    owner = SimpleNamespace(
        active_tool="plan_trace",
        _creator_camera_navigation_active=True,
        _camera_zoom_burst_until=time.monotonic() + 1.0,
    )
    scheduler = CentralRenderScheduler(owner, SimpleNamespace(), min_interval_ms=33.0, interactive_min_interval_ms=16.0)
    assert scheduler._effective_min_interval_ms("camera") == pytest.approx(8.0)
