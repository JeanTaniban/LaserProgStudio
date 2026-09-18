# -*- coding: utf-8 -*-
from __future__ import annotations

from ..app_context import AppContext
from ..studio_log import log_exception
from .action_controller import WindowController


class PlanarPickService(WindowController):
    """VTK picking helpers used by locked-plane tools.

    Keeping this out of ``PlanarToolController`` prevents the controller from
    mixing edit-state logic with low-level VTK picker details.
    """

    @classmethod
    def create(cls, context: AppContext) -> "PlanarPickService":
        return cls(context)

    def first_mesh_hit_from_qt_pos(self, qx: float, qy: float) -> tuple[float, float, float] | None:
        try:
            import vtk

            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.0008)
            try:
                picker.PickFromListOn()
                for actor in getattr(self.owner, "actors_by_index", {}).values():
                    picker.AddPickList(actor)
            except Exception:
                pass
            for vx, vy, _label in self.owner._qt_to_vtk_candidates(float(qx), float(qy)):
                picker.Pick(int(vx), int(vy), 0, self.owner.plotter.renderer)
                actor = picker.GetActor() or picker.GetViewProp()
                resolved = self.owner._resolve_picked_actor(actor)
                if resolved and resolved[0] == "mesh" and int(picker.GetCellId()) >= 0:
                    point = picker.GetPickPosition()
                    return (float(point[0]), float(point[1]), float(point[2]))
        except Exception:
            log_exception("planar_pick_first_hit")
        return None
