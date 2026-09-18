# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController


class TextureGizmoRenderService(OwnerDelegatingController):
    """Migrated TEX gizmo responsibility extracted from TextureGizmoController."""

    def _make_texture_rotation_ring_mesh(self, center, normal, radius: float, tube_radius: float):
        import numpy as np
        import pyvista as pv

        c = np.asarray(center, dtype=float)
        _n, u, v = self._texture_rotation_ring_basis(normal)
        samples = 144
        angles = np.linspace(0.0, 2.0 * math.pi, samples, endpoint=False)
        pts = np.asarray([c + math.cos(t) * float(radius) * u + math.sin(t) * float(radius) * v for t in angles], dtype=float)
        poly = pv.PolyData(pts)
        poly.lines = np.hstack(([samples + 1], np.arange(samples, dtype=np.int64), [0]))
        try:
            return poly.tube(radius=float(tube_radius), n_sides=18, capping=True)
        except TypeError:
            return poly.tube(radius=float(tube_radius))

    def _make_texture_move_center_mesh(self, center, radius: float):
        import pyvista as pv

        try:
            return pv.Sphere(radius=float(radius), center=tuple(float(v) for v in center), theta_resolution=24, phi_resolution=12)
        except Exception:
            return pv.Sphere(radius=float(radius), center=tuple(float(v) for v in center))

    def update_texture_rotation_gizmo(self, render: bool = True) -> None:
        """Show one rotation ring for the active TEX decal."""
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                return
            if not self.has_preview():
                return
            try:
                self._clear_gizmo_actors()
            except Exception:
                pass
            target = self._texture_rotation_target()
            if target is None:
                return
            _idx, _mesh, center, normal = target
            radius_px = float(getattr(self, "_texture_rotation_gizmo_screen_radius_px", 82.0) or 82.0)
            radius = self._texture_rotation_world_radius_for_screen(center, radius_px=radius_px)
            tube = self._texture_rotation_world_radius_for_screen(center, radius_px=7.5)
            self._texture_rotation_gizmo_radius_world = float(radius)
            self._texture_rotation_gizmo_pick_radius_px = 44.0
            self._texture_move_gizmo_pick_radius_px = 34.0
            self._texture_rotation_gizmo_ring_center = tuple(float(v) for v in center)
            self._texture_rotation_gizmo_ring_normal = tuple(float(v) for v in normal)
            ring = self._make_texture_rotation_ring_mesh(center, normal, radius, tube)
            self._add_overlay_mesh_actor(ring, key="texture_rotation_ring", axis="texrot", color="#FFB000", pickable=True)
            center_radius = self._texture_rotation_world_radius_for_screen(center, radius_px=12.0)
            center_mesh = self._make_texture_move_center_mesh(center, center_radius)
            self._add_overlay_mesh_actor(center_mesh, key="texture_move_center", axis="texmove", color="#00D4FF", pickable=True)
            self.ui_log(
                f"[TEXTURE_GIZMO] visible target={_idx} center=({center[0]:.3f},{center[1]:.3f},{center[2]:.3f}) "
                f"radius_px={radius_px:.1f} radius_world={radius:.4f} tube_px=7.5 center_handle_px=12.0"
            )
            if render:
                self.plotter.render()
        except Exception:
            log_exception("update_texture_rotation_gizmo")

