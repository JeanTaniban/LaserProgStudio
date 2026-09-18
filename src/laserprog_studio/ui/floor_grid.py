# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from .floor_grid_model import floor_grid_layers


_FLOOR_GRID_ACTOR_NAMES = (
    "floor_grid_minor",
    "floor_grid_major",
    "floor_grid_axis_x",
    "floor_grid_axis_y",
    "floor_grid_origin",
    "floor_grid_labels",
    "floor_grid",
)

_LASER_AREA_ACTOR_NAMES = (
    "laser_engraving_area_minor",
    "laser_engraving_area_major",
    "laser_engraving_area_frame",
    "laser_engraving_area",
)


class UIFloorGridLayer:

    def initialize_empty_viewport_guides(self, render: bool = False) -> bool:
        """Initialize viewport guides even before any mesh exists.

        The previous grid refresh path was mostly reached through scene rebuilds.
        On a brand-new empty project that meant the VTK viewport could stay as a
        white canvas until the first object was added.  Startup and empty-scene
        tools call this method to create the workplane, background and camera
        without waiting for a mesh actor.
        """
        try:
            plotter = getattr(self, "plotter", None)
            if plotter is None:
                return False
            try:
                plotter.set_background("#F3F6FA")
            except Exception:
                pass
            if bool(getattr(self, "show_floor_grid", False)):
                self._update_floor_grid_actor(render=False)
            else:
                self._update_laser_area_actor(render=False)
            if not list(self.current_meshes()):
                try:
                    plotter.view_isometric()
                except Exception:
                    pass
                try:
                    plotter.reset_camera()
                except Exception:
                    pass
            if render:
                try:
                    plotter.render()
                except Exception:
                    pass
            return True
        except Exception:
            log_exception("initialize_empty_viewport_guides")
            return False
    def set_floor_grid_visible(self, visible: bool) -> None:
        self.show_floor_grid = bool(visible)
        try:
            if hasattr(self, "btn_floor_grid"):
                self.btn_floor_grid.blockSignals(True)
                self.btn_floor_grid.setChecked(self.show_floor_grid)
                self.btn_floor_grid.blockSignals(False)
            self._update_floor_grid_actor(render=True)
            self.ui_log(f"[DISPLAY] floor_grid={self.show_floor_grid}")
        except Exception:
            log_exception("set_floor_grid_visible")

    def _floor_grid_actor_items(self, actor: Any) -> list[Any]:
        if actor is None:
            return []
        if isinstance(actor, dict):
            return [a for a in actor.values() if a is not None]
        if isinstance(actor, (list, tuple, set)):
            return [a for a in actor if a is not None]
        return [actor]

    def _remove_floor_grid_actor(self) -> None:
        actor = getattr(self, "floor_grid_actor", None)
        for item in self._floor_grid_actor_items(actor):
            try:
                self.plotter.remove_actor(item, render=False)
            except Exception:
                pass
        for name in _FLOOR_GRID_ACTOR_NAMES:
            try:
                self.plotter.remove_actor(name, render=False)
            except Exception:
                pass
        self.floor_grid_actor = None

    def _polydata_from_grid_lines(self, lines: list[Any]):
        if not lines:
            return None
        import numpy as np
        import pyvista as pv

        points = []
        vtk_lines = []
        for a, b in lines:
            i = len(points)
            points.extend([a, b])
            vtk_lines.extend([2, i, i + 1])
        return pv.PolyData(np.asarray(points, dtype=float), lines=np.asarray(vtk_lines, dtype=np.int_))

    def _build_floor_grid_polydata(self, meshes: list[Any]):
        bounds = scene_bounds(meshes)
        step = max(float(getattr(self, "floor_grid_step", 10.0)), 0.1)
        plan, layers = floor_grid_layers(bounds, requested_step=step)
        return {name: self._polydata_from_grid_lines(lines) for name, lines in layers.items()}, plan

    def _add_floor_grid_labels(self, plan: dict[str, Any]):
        """World floor grid labels are intentionally disabled.

        The grid/axis lines remain useful orientation guides, but the former
        "O  0,0", "+X" and "+Y" point-label actors cluttered the scene
        and could overlap tool gizmos near the model. Keep the cleanup actor
        name for backwards compatibility, but never create the label actor.
        """
        return None

    def _laser_preferences(self):
        prefs = getattr(self, "project_preferences", None)
        if prefs is None:
            try:
                from ..services.project_preferences import load_project_preferences

                prefs = load_project_preferences()
                self.project_preferences = prefs
            except Exception:
                prefs = None
        return getattr(prefs, "laser", None)

    def _remove_laser_area_actor(self) -> None:
        actor = getattr(self, "laser_area_actor", None)
        for item in self._floor_grid_actor_items(actor):
            try:
                self.plotter.remove_actor(item, render=False)
            except Exception:
                pass
        for name in _LASER_AREA_ACTOR_NAMES:
            try:
                self.plotter.remove_actor(name, render=False)
            except Exception:
                pass
        self.laser_area_actor = None

    def _laser_area_layers(self) -> dict[str, list[Any]]:
        laser = self._laser_preferences()
        if laser is None:
            return {"minor": [], "major": [], "frame": []}
        try:
            sx = max(float(getattr(laser, "machine_area_x_mm", 400.0)), 1.0)
            sy = max(float(getattr(laser, "machine_area_y_mm", 300.0)), 1.0)
        except Exception:
            sx, sy = 400.0, 300.0
        z = 0.006
        xmin, xmax = -sx * 0.5, sx * 0.5
        ymin, ymax = -sy * 0.5, sy * 0.5
        layers: dict[str, list[Any]] = {"minor": [], "major": [], "frame": []}
        def add(layer: str, a, b) -> None:
            layers[layer].append(((float(a[0]), float(a[1]), float(a[2])), (float(b[0]), float(b[1]), float(b[2]))))
        add("frame", (xmin, ymin, z + 0.004), (xmax, ymin, z + 0.004))
        add("frame", (xmax, ymin, z + 0.004), (xmax, ymax, z + 0.004))
        add("frame", (xmax, ymax, z + 0.004), (xmin, ymax, z + 0.004))
        add("frame", (xmin, ymax, z + 0.004), (xmin, ymin, z + 0.004))
        step = 10.0
        major = 50.0
        import math
        for i in range(int(math.ceil(xmin / step)), int(math.floor(xmax / step)) + 1):
            x = float(i) * step
            if abs(x - xmin) < 1e-6 or abs(x - xmax) < 1e-6:
                continue
            layer = "major" if abs((x / major) - round(x / major)) < 1e-6 else "minor"
            add(layer, (x, ymin, z), (x, ymax, z))
        for i in range(int(math.ceil(ymin / step)), int(math.floor(ymax / step)) + 1):
            y = float(i) * step
            if abs(y - ymin) < 1e-6 or abs(y - ymax) < 1e-6:
                continue
            layer = "major" if abs((y / major) - round(y / major)) < 1e-6 else "minor"
            add(layer, (xmin, y, z), (xmax, y, z))
        return layers

    def _update_laser_area_actor(self, render: bool = False) -> None:
        try:
            self._remove_laser_area_actor()
            laser = self._laser_preferences()
            if laser is None or not bool(getattr(laser, "show_machine_area", False)):
                if render:
                    self.plotter.render()
                return
            layers = self._laser_area_layers()
            actors: dict[str, Any] = {}
            styles = {
                "minor": dict(color="#6B7280", line_width=0.8, opacity=0.18, tubes=False),
                "major": dict(color="#93A4B8", line_width=1.0, opacity=0.30, tubes=False),
                "frame": dict(color="#88C0D0", line_width=2.2, opacity=0.92, tubes=True),
            }
            for layer_name in ("minor", "major", "frame"):
                poly = self._polydata_from_grid_lines(layers.get(layer_name, []))
                if poly is None:
                    continue
                style = styles[layer_name]
                actors[layer_name] = self.plotter.add_mesh(
                    poly,
                    color=style["color"],
                    line_width=style["line_width"],
                    name=f"laser_engraving_area_{layer_name}",
                    pickable=False,
                    lighting=False,
                    render_lines_as_tubes=bool(style["tubes"]),
                    render=False,
                )
                try:
                    prop = actors[layer_name].GetProperty()
                    prop.SetOpacity(float(style["opacity"]))
                    prop.SetAmbient(1.0)
                    prop.SetDiffuse(0.0)
                except Exception:
                    pass
            self.laser_area_actor = actors
            if render:
                self.plotter.render()
        except Exception:
            log_exception("update_laser_area_actor")

    def _update_floor_grid_actor(self, render: bool = False) -> None:
        try:
            self._remove_floor_grid_actor()
            if not bool(getattr(self, "show_floor_grid", False)):
                self._update_laser_area_actor(render=False)
                if render:
                    self.plotter.render()
                return
            polys, plan = self._build_floor_grid_polydata(self.current_meshes())
            actors: dict[str, Any] = {}
            styles = {
                "minor": dict(color="#7E8797", line_width=1.0, opacity=0.24, tubes=False),
                "major": dict(color="#A7B0C2", line_width=1.4, opacity=0.48, tubes=False),
                "axis_x": dict(color="#EF6B6B", line_width=2.4, opacity=0.92, tubes=True),
                "axis_y": dict(color="#60D394", line_width=2.4, opacity=0.92, tubes=True),
                "origin": dict(color="#F4F7FF", line_width=2.1, opacity=0.96, tubes=True),
            }
            for layer_name in ("minor", "major", "axis_x", "axis_y", "origin"):
                poly = polys.get(layer_name)
                if poly is None:
                    continue
                style = styles[layer_name]
                actors[layer_name] = self.plotter.add_mesh(
                    poly,
                    color=style["color"],
                    line_width=style["line_width"],
                    name=f"floor_grid_{layer_name}",
                    pickable=False,
                    lighting=False,
                    render_lines_as_tubes=bool(style["tubes"]),
                    render=False,
                )
                try:
                    prop = actors[layer_name].GetProperty()
                    prop.SetOpacity(float(style["opacity"]))
                    prop.SetAmbient(1.0)
                    prop.SetDiffuse(0.0)
                except Exception:
                    pass
            # Intentionally no point labels on the global origin/axes: the
            # colored grid axes already provide orientation without adding text
            # that competes visually with editing gizmos.
            self.floor_grid_actor = actors
            self._update_laser_area_actor(render=False)
            self._sync_mesh_list_selection()
            if render:
                self.plotter.render()
        except Exception:
            log_exception("update_floor_grid_actor")
