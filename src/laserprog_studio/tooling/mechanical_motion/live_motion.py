# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin, sqrt
from typing import Any, Mapping

from .kinematics import mesh_motion_transforms, solve_kinematics
from .models import Point3
from .session import MechanicalSession


@dataclass(slots=True)
class _ActorBaseline:
    actor: Any
    user_matrix: Any | None
    mesh_id: str
    shaft_id: str
    rack_id: str


def _unit_axis(axis: Point3) -> Point3:
    x, y, z = (float(axis[0]), float(axis[1]), float(axis[2]))
    length = sqrt(x * x + y * y + z * z)
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return (x / length, y / length, z / length)


def _rotation_affine(center: Point3, axis: Point3, angle_deg: float) -> tuple[tuple[float, ...], ...]:
    """Return a row-major 4x4 rotation around one arbitrary world axis."""

    x, y, z = _unit_axis(axis)
    angle = radians(float(angle_deg) % 360.0)
    c = cos(angle)
    s = sin(angle)
    one = 1.0 - c
    rotation = (
        (c + x * x * one, x * y * one - z * s, x * z * one + y * s),
        (y * x * one + z * s, c + y * y * one, y * z * one - x * s),
        (z * x * one - y * s, z * y * one + x * s, c + z * z * one),
    )
    cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
    tx = cx - (rotation[0][0] * cx + rotation[0][1] * cy + rotation[0][2] * cz)
    ty = cy - (rotation[1][0] * cx + rotation[1][1] * cy + rotation[1][2] * cz)
    tz = cz - (rotation[2][0] * cx + rotation[2][1] * cy + rotation[2][2] * cz)
    return (
        (rotation[0][0], rotation[0][1], rotation[0][2], tx),
        (rotation[1][0], rotation[1][1], rotation[1][2], ty),
        (rotation[2][0], rotation[2][1], rotation[2][2], tz),
        (0.0, 0.0, 0.0, 1.0),
    )


def _translation_affine(translation: Point3) -> tuple[tuple[float, ...], ...]:
    dx, dy, dz = (float(value) for value in translation)
    return (
        (1.0, 0.0, 0.0, dx),
        (0.0, 1.0, 0.0, dy),
        (0.0, 0.0, 1.0, dz),
        (0.0, 0.0, 0.0, 1.0),
    )


def _motion_affine(center: Point3, axis: Point3, angle_deg: float, translation: Point3) -> tuple[tuple[float, ...], ...]:
    values = [list(row) for row in _rotation_affine(center, axis, angle_deg)]
    values[0][3] += float(translation[0])
    values[1][3] += float(translation[1])
    values[2][3] += float(translation[2])
    return tuple(tuple(row) for row in values)


def _vtk_matrix(values: tuple[tuple[float, ...], ...]) -> Any | None:
    try:
        import vtk

        matrix = vtk.vtkMatrix4x4()
        for row in range(4):
            for column in range(4):
                matrix.SetElement(row, column, float(values[row][column]))
        return matrix
    except Exception:
        return None


def _copy_vtk_matrix(value: Any | None) -> Any | None:
    if value is None:
        return None
    try:
        import vtk

        clone = vtk.vtkMatrix4x4()
        clone.DeepCopy(value)
        return clone
    except Exception:
        return value


def _compose(delta: Any, baseline: Any | None) -> Any:
    if baseline is None:
        return delta
    try:
        import vtk

        result = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Multiply4x4(delta, baseline, result)
        return result
    except Exception:
        return delta


class MechanicalLiveMotionPreview:
    """Animate scene actors without rebuilding meshes or the whole viewport.

    The document preview remains the neutral source of truth. During Test only
    VTK actor matrices are changed. Apply, Cancel, exit and any normal preview
    rebuild restore the captured matrices, so animated poses never leak into the
    stored geometry or undo history.
    """

    def __init__(self, session: MechanicalSession) -> None:
        self.session = session
        self._baselines: dict[int, _ActorBaseline] = {}
        self._generation: int | None = None
        self._active = False

    @property
    def active(self) -> bool:
        return bool(self._active and self._baselines)

    def begin(self, ctx: Any) -> bool:
        # Re-entering Play while already in Test must keep the original neutral
        # baseline. Recapturing the currently rotated matrices would apply the
        # absolute angle twice on the next timer tick.
        if self._scene_is_current(ctx):
            return True
        owner = getattr(ctx, "owner", None)
        actors = getattr(owner, "actors_by_index", None) if owner is not None else None
        if not isinstance(actors, dict) or not actors:
            self._active = False
            self._baselines.clear()
            self._generation = None
            return False
        try:
            objects = ctx.document.objects(include_preview=True)
        except Exception:
            objects = ()
        zero_angles = {driver.id: 0.0 for driver in self.session.assembly.drivers.values()}
        zero_state = solve_kinematics(self.session.assembly, zero_angles)
        moving_shaft_ids = set(zero_state.shaft_angles_deg)
        moving_rack_ids = set(zero_state.rack_displacements_mm)
        moving_mesh_ids = {
            str(driver.target_mesh_id)
            for driver in self.session.assembly.drivers.values()
            if driver.target_mesh_id
        }
        for attachment in self.session.assembly.attachments.values():
            moving_mesh_ids.update(str(mesh_id) for mesh_id in attachment.target_mesh_ids if str(mesh_id))
        baselines: dict[int, _ActorBaseline] = {}
        for raw_index, actor in actors.items():
            index = int(raw_index)
            if actor is None or not callable(getattr(actor, "SetUserMatrix", None)):
                continue
            if not (0 <= index < len(objects)):
                continue
            mesh = objects[index].mesh
            mesh_id = str(getattr(mesh, "mesh_id", "") or objects[index].id)
            metadata = getattr(mesh, "metadata", None)
            metadata = metadata if isinstance(metadata, dict) else {}
            shaft_id = str(metadata.get("mechanical_shaft_id") or "")
            rack_id = str(metadata.get("mechanical_rack_id") or "")
            if shaft_id:
                if shaft_id not in moving_shaft_ids:
                    continue
            elif rack_id:
                if rack_id not in moving_rack_ids:
                    continue
            elif mesh_id not in moving_mesh_ids:
                continue
            try:
                current = actor.GetUserMatrix() if callable(getattr(actor, "GetUserMatrix", None)) else None
            except Exception:
                current = None
            baselines[index] = _ActorBaseline(
                actor=actor,
                user_matrix=_copy_vtk_matrix(current),
                mesh_id=mesh_id,
                shaft_id=shaft_id,
                rack_id=rack_id,
            )
        self._baselines = baselines
        self._generation = int(getattr(owner, "_scene_rebuild_generation", 0) or 0)
        self._active = bool(baselines)
        return self._active

    def _scene_is_current(self, ctx: Any) -> bool:
        owner = getattr(ctx, "owner", None)
        if owner is None or not self.active:
            return False
        generation = int(getattr(owner, "_scene_rebuild_generation", 0) or 0)
        actors = getattr(owner, "actors_by_index", None)
        return generation == self._generation and isinstance(actors, dict) and all(
            actors.get(index) is baseline.actor for index, baseline in self._baselines.items()
        )

    def end(self, ctx: Any, *, render: bool = False) -> None:
        if self._scene_is_current(ctx):
            for baseline in self._baselines.values():
                try:
                    baseline.actor.SetUserMatrix(baseline.user_matrix)
                except Exception:
                    pass
            if render:
                self._render(ctx)
        self._baselines.clear()
        self._generation = None
        self._active = False

    def update(self, ctx: Any, angles_deg: Mapping[str, float], *, render: bool = False) -> bool:
        if not self._scene_is_current(ctx) and not self.begin(ctx):
            return False
        plane = self.session.work_plane
        if plane is None:
            return False
        state = solve_kinematics(self.session.assembly, angles_deg)
        attached = mesh_motion_transforms(self.session.assembly, state)
        shaft_centers = self.session.shaft_centers()
        changed = False
        for baseline in self._baselines.values():
            center: Point3 | None = None
            angle = 0.0
            translation: Point3 = (0.0, 0.0, 0.0)
            if baseline.shaft_id and baseline.shaft_id in state.shaft_angles_deg:
                center = shaft_centers.get(baseline.shaft_id)
                angle = float(state.shaft_angles_deg.get(baseline.shaft_id, 0.0))
            elif baseline.rack_id and baseline.rack_id in state.rack_displacements_mm:
                from .rack_geometry import rack_axis

                rack = self.session.assembly.racks.get(baseline.rack_id)
                if rack is not None:
                    direction = rack_axis(rack)
                    distance = float(state.rack_displacements_mm.get(rack.id, 0.0))
                    translation = (direction[0] * distance, direction[1] * distance, direction[2] * distance)
            elif baseline.mesh_id in attached:
                transform = attached[baseline.mesh_id]
                center = transform.center
                angle = transform.angle_deg
                translation = transform.translation
            try:
                has_translation = any(abs(value) > 1.0e-12 for value in translation)
                if (center is None or abs(angle) <= 1.0e-12) and not has_translation:
                    baseline.actor.SetUserMatrix(baseline.user_matrix)
                else:
                    if center is None or abs(angle) <= 1.0e-12:
                        affine = _translation_affine(translation)
                    else:
                        affine = _motion_affine(center, plane.normal, angle, translation)
                    delta = _vtk_matrix(affine)
                    if delta is None:
                        return False
                    baseline.actor.SetUserMatrix(_compose(delta, baseline.user_matrix))
                changed = True
            except Exception:
                return False
        if changed and render:
            self._render(ctx)
        return changed

    @staticmethod
    def _render(ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        plotter = getattr(owner, "plotter", None) if owner is not None else None
        callback = getattr(plotter, "render", None)
        if callable(callback):
            try:
                callback()
            except Exception:
                pass


__all__ = ["MechanicalLiveMotionPreview"]
