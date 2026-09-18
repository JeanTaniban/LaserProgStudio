# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from ..studio_log import log_exception


def _rgb_from_hex(color: str) -> tuple[float, float, float]:
    text = str(color or "#FFFFFF").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    try:
        if len(text) == 6:
            return (int(text[0:2], 16) / 255.0, int(text[2:4], 16) / 255.0, int(text[4:6], 16) / 255.0)
    except Exception:
        pass
    return (1.0, 1.0, 1.0)


@dataclass
class PlanarGizmoActorRecord:
    actor: object
    mapper: object
    polydata: object
    points: object
    sphere: object
    radius: float
    lightweight: bool
    name: str


class PlanarGizmoActorCache:
    """Persistent VTK glyph actors for Plan tracer edit handles.

    The important performance rule is: never rebuild the sphere glyph mesh on
    every mouse move.  ``vtkGlyph3DMapper`` instances remain in the renderer and
    only their ``vtkPoints`` input is updated in place.
    """

    def __init__(self) -> None:
        self._records: dict[str, PlanarGizmoActorRecord] = {}

    def names(self) -> set[str]:
        return set(self._records)

    def hide_all(self, names: Iterable[str] | None = None) -> None:
        wanted = set(str(n) for n in names) if names is not None else None
        for name, record in list(self._records.items()):
            if wanted is not None and name not in wanted:
                continue
            try:
                record.actor.SetVisibility(False)
            except Exception:
                pass

    def draw_points(
        self,
        plotter: object,
        *,
        name: str,
        points: Sequence[tuple[float, float, float]],
        color: str,
        radius: float,
        lightweight: bool,
        ambient: float,
        diffuse: float,
        specular: float,
    ) -> bool:
        if plotter is None or not points:
            self.hide_all([name])
            return True
        try:
            record = self._records.get(str(name))
            if record is None:
                record = self._create_record(str(name), float(radius), bool(lightweight))
                self._records[str(name)] = record
                self._add_actor(plotter, str(name), record.actor)
            self._sync_radius(record, float(radius), bool(lightweight))
            self._sync_points(record, points)
            prop = record.actor.GetProperty()
            prop.SetColor(*_rgb_from_hex(color))
            prop.SetAmbient(float(ambient))
            prop.SetDiffuse(float(diffuse))
            prop.SetSpecular(float(specular))
            try:
                prop.SetInterpolationToPhong()
            except Exception:
                pass
            record.actor.SetVisibility(True)
            try:
                record.actor.SetPickable(False)
            except Exception:
                pass
            return True
        except Exception:
            log_exception(f"planar_gizmo_cache_draw_{name}")
            self._records.pop(str(name), None)
            return False

    def _create_record(self, name: str, radius: float, lightweight: bool) -> PlanarGizmoActorRecord:
        from vtkmodules.vtkCommonCore import vtkPoints
        from vtkmodules.vtkCommonDataModel import vtkPolyData
        from vtkmodules.vtkFiltersSources import vtkSphereSource
        from vtkmodules.vtkRenderingCore import vtkActor, vtkGlyph3DMapper

        points = vtkPoints()
        points.SetDataTypeToFloat()
        polydata = vtkPolyData()
        polydata.SetPoints(points)

        sphere = vtkSphereSource()
        sphere.SetRadius(float(radius))
        theta, phi = self._resolution(lightweight)
        sphere.SetThetaResolution(theta)
        sphere.SetPhiResolution(phi)
        sphere.Update()

        mapper = vtkGlyph3DMapper()
        mapper.SetInputData(polydata)
        mapper.SetSourceConnection(sphere.GetOutputPort())
        mapper.ScalingOff()
        mapper.OrientOff()
        mapper.SetScalarVisibility(False)
        try:
            mapper.SetCullingAndLOD(True)
            mapper.SetNumberOfLOD(2)
            mapper.SetLODDistanceAndTargetReduction(0, 0.0, 0.0)
            mapper.SetLODDistanceAndTargetReduction(1, 700.0, 0.65)
        except Exception:
            pass

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.SetVisibility(False)
        actor.SetPickable(False)
        return PlanarGizmoActorRecord(actor, mapper, polydata, points, sphere, float(radius), bool(lightweight), name)

    def _add_actor(self, plotter: object, name: str, actor: object) -> None:
        add_actor = getattr(plotter, "add_actor", None)
        if callable(add_actor):
            # PyVista has gained parameters over time.  Prefer the fastest path
            # when available, but stay compatible with older local installs.
            for kwargs in (
                {"name": name, "render": False, "pickable": False, "remove_existing_actor": False},
                {"name": name, "render": False, "pickable": False},
                {"name": name, "render": False},
                {"name": name},
            ):
                try:
                    add_actor(actor, **kwargs)
                    return
                except TypeError:
                    continue
        renderer = getattr(plotter, "renderer", None)
        add = getattr(renderer, "AddActor", None)
        if callable(add):
            add(actor)

    def _sync_radius(self, record: PlanarGizmoActorRecord, radius: float, lightweight: bool) -> None:
        if abs(float(radius) - float(record.radius)) <= max(0.001, float(record.radius) * 0.03) and bool(lightweight) == bool(record.lightweight):
            return
        record.sphere.SetRadius(float(radius))
        theta, phi = self._resolution(lightweight)
        record.sphere.SetThetaResolution(theta)
        record.sphere.SetPhiResolution(phi)
        record.sphere.Modified()
        record.radius = float(radius)
        record.lightweight = bool(lightweight)

    def _sync_points(self, record: PlanarGizmoActorRecord, points: Sequence[tuple[float, float, float]]) -> None:
        n = len(points)
        record.points.SetNumberOfPoints(int(n))
        for i, p in enumerate(points):
            record.points.SetPoint(int(i), float(p[0]), float(p[1]), float(p[2]))
        # This is the cheap path: mutate the existing VTK input and notify the
        # pipeline.  No actor removal, no ``cloud.glyph(...)`` mesh rebuild.
        record.points.Modified()
        record.polydata.Modified()

    @staticmethod
    def _resolution(lightweight: bool) -> tuple[int, int]:
        return (8, 5) if bool(lightweight) else (14, 8)
