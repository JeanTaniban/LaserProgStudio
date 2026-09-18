from __future__ import annotations

import math

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.mesh_repair import offset_mesh_uniform_by_face_planes
from laserprog_studio.services.project_preferences import ProjectPreferences, LaserEngravingPreferences, coerce_project_preferences


def _box_mesh(size_x: float, size_y: float, size_z: float, *, angle_deg: float = 0.0) -> WorkMesh:
    hx, hy, hz = size_x / 2.0, size_y / 2.0, size_z / 2.0
    verts = [
        (-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
        (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz),
    ]
    if abs(angle_deg) > 1e-9:
        a = math.radians(angle_deg)
        ca, sa = math.cos(a), math.sin(a)
        verts = [(x * ca - y * sa, x * sa + y * ca, z) for x, y, z in verts]
    tris = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh(name="cutter", vertices=[tuple(map(float, p)) for p in verts], triangles=tris)


def _extent_on_axis(mesh: WorkMesh, axis: tuple[float, float, float]) -> float:
    ax, ay, az = axis
    dots = [float(x) * ax + float(y) * ay + float(z) * az for x, y, z in mesh.vertices]
    return max(dots) - min(dots)


def test_subtract_margin_preference_accepts_positive_zero_and_negative_values() -> None:
    prefs = coerce_project_preferences({"laser": {"boolean_subtract_margin_mm": "-0.25"}})
    assert prefs.laser.boolean_subtract_margin_mm == -0.25
    assert ProjectPreferences().laser.boolean_subtract_margin_mm == 0.0
    assert LaserEngravingPreferences(boolean_subtract_margin_mm=0.35).boolean_subtract_margin_mm == 0.35


def test_uniform_offset_grows_rectangular_cutter_by_same_margin_on_all_axes() -> None:
    mesh = _box_mesh(200.0, 20.0, 6.0)
    grown = offset_mesh_uniform_by_face_planes(mesh, margin_mm=0.4)
    assert math.isclose(_extent_on_axis(grown, (1.0, 0.0, 0.0)), 200.8, abs_tol=1e-6)
    assert math.isclose(_extent_on_axis(grown, (0.0, 1.0, 0.0)), 20.8, abs_tol=1e-6)
    assert math.isclose(_extent_on_axis(grown, (0.0, 0.0, 1.0)), 6.8, abs_tol=1e-6)


def test_uniform_offset_shrinks_rectangular_cutter_with_negative_margin() -> None:
    mesh = _box_mesh(200.0, 20.0, 6.0)
    shrunk = offset_mesh_uniform_by_face_planes(mesh, margin_mm=-0.4)
    assert math.isclose(_extent_on_axis(shrunk, (1.0, 0.0, 0.0)), 199.2, abs_tol=1e-6)
    assert math.isclose(_extent_on_axis(shrunk, (0.0, 1.0, 0.0)), 19.2, abs_tol=1e-6)
    assert math.isclose(_extent_on_axis(shrunk, (0.0, 0.0, 1.0)), 5.2, abs_tol=1e-6)


def test_uniform_offset_is_not_world_bounds_scaling_for_rotated_rectangle() -> None:
    angle = math.radians(37.0)
    local_u = (math.cos(angle), math.sin(angle), 0.0)
    local_v = (-math.sin(angle), math.cos(angle), 0.0)
    mesh = _box_mesh(80.0, 12.0, 4.0, angle_deg=37.0)
    grown = offset_mesh_uniform_by_face_planes(mesh, margin_mm=0.5)
    assert math.isclose(_extent_on_axis(grown, local_u), 81.0, abs_tol=1e-6)
    assert math.isclose(_extent_on_axis(grown, local_v), 13.0, abs_tol=1e-6)
    assert math.isclose(_extent_on_axis(grown, (0.0, 0.0, 1.0)), 5.0, abs_tol=1e-6)
