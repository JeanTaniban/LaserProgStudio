# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class TransformGeometryLayer:
    def _gizmo_axis_definitions(self) -> dict[str, tuple[tuple[float, float, float], str]]:
        return {
            "x": ((1.0, 0.0, 0.0), "#ff4b4b"),
            "y": ((0.0, 1.0, 0.0), "#42d66d"),
            "z": ((0.0, 0.0, 1.0), "#4f91ff"),
        }

    def _axis_plane_basis(self, axis: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Return two stable basis vectors perpendicular to a world axis."""
        axis = (axis or "").lower()
        if axis == "x":
            return (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
        if axis == "y":
            return (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)

    @staticmethod
    def _normalized_axis_tuple(value: Any, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
        try:
            import numpy as np

            vec = np.asarray(value, dtype=float)
            if vec.shape[0] < 3:
                return fallback
            vec = vec[:3]
            n = float(np.linalg.norm(vec))
            if not np.isfinite(n) or n <= 1.0e-12:
                return fallback
            vec = vec / n
            return (float(vec[0]), float(vec[1]), float(vec[2]))
        except Exception:
            return fallback

    def _local_scale_axis_definitions_for_mesh(self, mesh: Any) -> dict[str, tuple[tuple[float, float, float], str]]:
        """Return colored local X/Y/Z scale axes for a mesh.

        Translation and rotation intentionally keep using world axes. Scale uses
        the stored object rotation so handles and bounds frame follow the part
        orientation.  Some generated meshes, such as the right-click primitive
        board, are baked directly as oriented vertices instead of carrying a
        transform quaternion.  Those meshes store their real local frame in
        metadata; prefer that explicit frame so the Scale handles and rectangle
        are built from the same basis as the actual board.
        """
        colors = {"x": "#ff4b4b", "y": "#42d66d", "z": "#4f91ff"}
        try:
            metadata = getattr(mesh, "metadata", {}) or {}
            board = metadata.get("primitive_board") if isinstance(metadata, dict) else None
            if isinstance(board, dict):
                world_axes = self._gizmo_axis_definitions()
                u = self._normalized_axis_tuple(board.get("u_axis"), world_axes["x"][0])
                v = self._normalized_axis_tuple(board.get("v_axis"), world_axes["y"][0])
                n = self._normalized_axis_tuple(board.get("normal"), world_axes["z"][0])
                return {"x": (u, colors["x"]), "y": (v, colors["y"]), "z": (n, colors["z"])}
        except Exception:
            pass
        try:
            import numpy as np
            mat = self._quat_to_matrix(self._mesh_rotation_quat(mesh))
            axes: dict[str, tuple[tuple[float, float, float], str]] = {}
            for i, key in enumerate(("x", "y", "z")):
                vec = np.asarray(mat[:, i], dtype=float)
                n = float(np.linalg.norm(vec))
                if n <= 1e-12:
                    vec = np.asarray(self._gizmo_axis_definitions()[key][0], dtype=float)
                else:
                    vec = vec / n
                axes[key] = ((float(vec[0]), float(vec[1]), float(vec[2])), colors[key])
            return axes
        except Exception:
            return self._gizmo_axis_definitions()

    def _oriented_bounds_for_mesh(self, mesh: Any) -> tuple[tuple[float, float, float, float, float, float], tuple[float, float, float], dict[str, tuple[tuple[float, float, float], str]]]:
        """Return local-axis bounds, world center, and local axes for scale tools."""
        try:
            import numpy as np
            axes = self._local_scale_axis_definitions_for_mesh(mesh)
            pts = np.asarray(mesh.vertices, dtype=float)
            if pts.size == 0:
                b = mesh_bounds(mesh)
                return b, mesh_center(mesh), axes
            ax = np.asarray(axes["x"][0], dtype=float)
            ay = np.asarray(axes["y"][0], dtype=float)
            az = np.asarray(axes["z"][0], dtype=float)
            coords = np.column_stack((pts @ ax, pts @ ay, pts @ az))
            mins = coords.min(axis=0)
            maxs = coords.max(axis=0)
            mids = (mins + maxs) * 0.5
            center = ax * mids[0] + ay * mids[1] + az * mids[2]
            bounds = (float(mins[0]), float(maxs[0]), float(mins[1]), float(maxs[1]), float(mins[2]), float(maxs[2]))
            return bounds, (float(center[0]), float(center[1]), float(center[2])), axes
        except Exception:
            b = mesh_bounds(mesh)
            return b, mesh_center(mesh), self._gizmo_axis_definitions()

    def _local_scale_point_to_world(self, coords: tuple[float, float, float], axes: dict[str, tuple[tuple[float, float, float], str]]) -> tuple[float, float, float]:
        try:
            import numpy as np
            p = (
                np.asarray(axes["x"][0], dtype=float) * float(coords[0])
                + np.asarray(axes["y"][0], dtype=float) * float(coords[1])
                + np.asarray(axes["z"][0], dtype=float) * float(coords[2])
            )
            return (float(p[0]), float(p[1]), float(p[2]))
        except Exception:
            return (float(coords[0]), float(coords[1]), float(coords[2]))

    def _scale_frame_specs_to_world(self, frame_specs: Any, axes: dict[str, tuple[tuple[float, float, float], str]]):
        """Convert adaptive frame specs from local-axis coordinates to world points.

        ``_adaptive_scale_frame_specs`` works in the same projected local space as
        ``_oriented_bounds_for_selection``.  The native Transform Gizmo API,
        however, expects world-space line endpoints.  Sending local coordinates
        directly is harmless for an unrotated cube but places the rectangle far
        from baked-oriented meshes such as primitive boards.
        """
        converted = []
        for handle, p0, p1, color in tuple(frame_specs or ()):  # defensive for tests and old callers
            converted.append((str(handle), self._local_scale_point_to_world(p0, axes), self._local_scale_point_to_world(p1, axes), str(color)))
        return tuple(converted)

    def _adaptive_scale_frame_specs(self, local_bounds: tuple[float, float, float, float, float, float], axes: dict[str, tuple[tuple[float, float, float], str]], length: float):
        """Return bounds-frame edge specs for the scale gizmo.

        The frame is drawn in the local face that is most perpendicular to the
        current camera direction. This keeps the rectangle usable when the user
        looks at the part from the side: instead of becoming edge-on, it switches
        to the visible local XZ or YZ face.
        """
        try:
            import numpy as np
            axis_keys = ("x", "y", "z")
            axis_vecs = {k: np.asarray(axes[k][0], dtype=float) for k in axis_keys}
            for key in axis_keys:
                n = float(np.linalg.norm(axis_vecs[key]))
                if not np.isfinite(n) or n < 1e-12:
                    axis_vecs[key] = np.asarray(self._gizmo_axis_definitions()[key][0], dtype=float)
                else:
                    axis_vecs[key] = axis_vecs[key] / n

            # _camera_forward_vector points from camera to focal point. For choosing
            # the visible face we need the direction from the part toward the camera.
            to_camera = -np.asarray(self._camera_forward_vector(), dtype=float)
            n_cam = float(np.linalg.norm(to_camera))
            if not np.isfinite(n_cam) or n_cam < 1e-12:
                to_camera = np.asarray((0.0, 0.0, 1.0), dtype=float)
            else:
                to_camera = to_camera / n_cam

            normal_axis = max(axis_keys, key=lambda k: abs(float(np.dot(axis_vecs[k], to_camera))))
            plane_axes = [k for k in axis_keys if k != normal_axis]
            bounds_by_axis = {
                "x": (float(local_bounds[0]), float(local_bounds[1])),
                "y": (float(local_bounds[2]), float(local_bounds[3])),
                "z": (float(local_bounds[4]), float(local_bounds[5])),
            }
            colors = {k: axes.get(k, (None, "#ffffff"))[1] for k in axis_keys}
            pad = max(float(length) * 0.055, self._gizmo_visible_epsilon())
            face_offset = max(float(length) * 0.035, self._gizmo_visible_epsilon())

            normal_dot = float(np.dot(axis_vecs[normal_axis], to_camera))
            normal_min, normal_max = bounds_by_axis[normal_axis]
            normal_coord = normal_max + face_offset if normal_dot >= 0.0 else normal_min - face_offset

            a, b = plane_axes
            a_min, a_max = bounds_by_axis[a]
            b_min, b_max = bounds_by_axis[b]
            a_min_p, a_max_p = a_min - pad, a_max + pad
            b_min_p, b_max_p = b_min - pad, b_max + pad

            def point(a_val: float, b_val: float) -> tuple[float, float, float]:
                coords = {
                    normal_axis: normal_coord,
                    a: float(a_val),
                    b: float(b_val),
                }
                return (float(coords["x"]), float(coords["y"]), float(coords["z"]))

            return [
                (f"{a}_min", point(a_min_p, b_min_p), point(a_min_p, b_max_p), colors[a]),
                (f"{a}_max", point(a_max_p, b_min_p), point(a_max_p, b_max_p), colors[a]),
                (f"{b}_min", point(a_min_p, b_min_p), point(a_max_p, b_min_p), colors[b]),
                (f"{b}_max", point(a_min_p, b_max_p), point(a_max_p, b_max_p), colors[b]),
            ]
        except Exception:
            xmin, xmax, ymin, ymax, _zmin, zmax = [float(v) for v in local_bounds]
            eps = self._gizmo_visible_epsilon()
            pad = max(float(length) * 0.055, eps)
            z = zmax + max(float(length) * 0.035, eps)
            return [
                ("x_min", (xmin - pad, ymin - pad, z), (xmin - pad, ymax + pad, z), "#ff4b4b"),
                ("x_max", (xmax + pad, ymin - pad, z), (xmax + pad, ymax + pad, z), "#ff4b4b"),
                ("y_min", (xmin - pad, ymin - pad, z), (xmax + pad, ymin - pad, z), "#42d66d"),
                ("y_max", (xmin - pad, ymax + pad, z), (xmax + pad, ymax + pad, z), "#42d66d"),
            ]

    def _gizmo_visible_epsilon(self) -> float:
        """Small numeric floor only; it must not become a visual size floor."""
        return 1.0e-6

    def _camera_visible_height_at(self, point: tuple[float, float, float]) -> float:
        """Return world-space visible height at a point depth.

        The transform gizmo must follow the camera framing. Do not clamp this to
        mesh size or a large absolute value, otherwise the gizmo stops shrinking
        when the user zooms in and becomes visually huge.
        """
        eps = self._gizmo_visible_epsilon()
        try:
            import numpy as np
            cam = self.plotter.camera
            if bool(cam.GetParallelProjection()):
                return max(2.0 * float(cam.GetParallelScale()), eps)
            pos = np.array(cam.GetPosition(), dtype=float)
            _, _, forward = self._camera_basis()
            depth = float(np.dot(np.array(point, dtype=float) - pos, forward))
            if depth <= eps:
                depth = float(np.linalg.norm(np.array(point, dtype=float) - pos))
            view_angle = math.radians(float(cam.GetViewAngle() or 30.0))
            return max(2.0 * depth * math.tan(view_angle / 2.0), eps)
        except Exception:
            try:
                return max(bounds_size(scene_bounds(self.current_meshes())) * 0.16, eps)
            except Exception:
                return 1.0

    def _gizmo_length_at(self, center: tuple[float, float, float], meshes: list[Any] | None = None) -> float:
        """Size axes/rings from the camera framing only.

        A previous version used mesh-size and absolute-size floors. That made the
        gizmo stop shrinking after zooming in. Keep only an epsilon floor so VTK
        primitives never receive zero dimensions.
        """
        try:
            visible_height = self._camera_visible_height_at(center)
            return max(visible_height * 0.16, self._gizmo_visible_epsilon())
        except Exception:
            return 1.0

    def _add_gizmo_label(self, axis: str, center: tuple[float, float, float], vec: tuple[float, float, float], length: float, color: str) -> None:
        """Add a colored 3D axis label in the foreground gizmo layer."""
        try:
            import pyvista as pv
            label_height = max(length * 0.18, self._gizmo_visible_epsilon())
            label_depth = max(length * 0.018, self._gizmo_visible_epsilon())
            text = pv.Text3D(axis.upper(), depth=label_depth, height=label_height)
            pos = (
                center[0] + vec[0] * length * 1.08,
                center[1] + vec[1] * length * 1.08,
                center[2] + vec[2] * length * 1.08,
            )
            text.translate(pos, inplace=True)
            self._add_overlay_mesh_actor(text, key=f"label_{axis}", axis=None, color=color, pickable=False)
        except Exception:
            pass

    def _make_rotation_ring_mesh(self, center: tuple[float, float, float], axis: str, radius: float, tube_radius: float):
        """Create a thick circle mesh in the plane perpendicular to a world axis."""
        import numpy as np
        import pyvista as pv
        b1, b2 = self._axis_plane_basis(axis)
        c = np.asarray(center, dtype=float)
        u = np.asarray(b1, dtype=float)
        v = np.asarray(b2, dtype=float)
        samples = 144
        angles = np.linspace(0.0, 2.0 * math.pi, samples, endpoint=False)
        pts = np.asarray([c + math.cos(t) * radius * u + math.sin(t) * radius * v for t in angles], dtype=float)
        poly = pv.PolyData(pts)
        poly.lines = np.hstack(([samples + 1], np.arange(samples, dtype=np.int64), [0]))
        try:
            return poly.tube(radius=tube_radius, n_sides=18, capping=True)
        except TypeError:
            return poly.tube(radius=tube_radius)

    def _make_tube_line_mesh(self, p0: tuple[float, float, float], p1: tuple[float, float, float], radius: float, *, samples: int = 2):
        """Create a pickable thick line from two 3D points."""
        import numpy as np
        import pyvista as pv
        pts = np.asarray([p0, p1], dtype=float)
        poly = pv.PolyData(pts)
        poly.lines = np.asarray([2, 0, 1], dtype=np.int64)
        try:
            return poly.tube(radius=float(radius), n_sides=14, capping=True)
        except TypeError:
            return poly.tube(radius=float(radius))

    def _make_scale_box_handle(self, center: tuple[float, float, float], size: float):
        """Create a compact cube handle used by the Scale gizmo."""
        import pyvista as pv
        try:
            return pv.Cube(center=center, x_length=size, y_length=size, z_length=size)
        except TypeError:
            s = float(size) * 0.5
            return pv.Box(bounds=(center[0] - s, center[0] + s, center[1] - s, center[1] + s, center[2] - s, center[2] + s))

    def _logical_axis_from_handle(self, handle: str | None) -> str | None:
        """Return x/y/z for a gizmo handle id such as 'x', 'x_min', or 'scale_edge_x_max'."""
        h = (handle or "").lower().strip()
        if h in {"x", "y", "z"}:
            return h
        if h in {"x_min", "x_max", "y_min", "y_max", "z_min", "z_max"}:
            return h[0]
        if h.startswith("scale_edge_"):
            return self._logical_axis_from_handle(h.replace("scale_edge_", "", 1))
        if h.startswith("scale_") and h.endswith("_handle"):
            parts = h.split("_")
            if len(parts) >= 2:
                return self._logical_axis_from_handle(parts[1])
        return None

    def _scale_handle_is_frame_edge(self, handle: str | None) -> bool:
        h = (handle or "").lower().strip()
        if h.startswith("scale_edge_"):
            h = h.replace("scale_edge_", "", 1)
        return h in {"x_min", "x_max", "y_min", "y_max", "z_min", "z_max"}

    def _scale_edge_side(self, handle: str | None) -> str | None:
        h = (handle or "").lower().strip()
        if h.startswith("scale_edge_"):
            h = h.replace("scale_edge_", "", 1)
        if h.endswith("_min"):
            return "min"
        if h.endswith("_max"):
            return "max"
        return None

    def _scale_vertices_along_axis(self, vertices: list[tuple[float, float, float]], pivot: tuple[float, float, float], axis: str, factor: float) -> list[tuple[float, float, float]]:
        """Scale vertices along one world axis around a pivot point."""
        vec = self._gizmo_axis_definitions().get((axis or "").lower(), ((0.0, 0.0, 0.0), "#ffffff"))[0]
        return self._scale_vertices_along_vector(vertices, pivot, vec, factor)

    def _scale_vertices_along_vector(self, vertices: list[tuple[float, float, float]], pivot: tuple[float, float, float], axis_vector: tuple[float, float, float], factor: float) -> list[tuple[float, float, float]]:
        """Scale vertices along an arbitrary axis around a fixed pivot plane."""
        try:
            import numpy as np
            factor = max(0.001, float(factor))
            axis = np.asarray(axis_vector, dtype=float)
            n = float(np.linalg.norm(axis))
            if n <= 1e-12:
                return list(vertices)
            axis = axis / n
            p = np.asarray(pivot, dtype=float)
            pts = np.asarray(vertices, dtype=float)
            rel = pts - p
            distances = rel @ axis
            scaled = pts + np.outer(distances * (factor - 1.0), axis)
            return [tuple(row) for row in scaled.tolist()]
        except Exception:
            return list(vertices)

    def _world_to_display(self, point: tuple[float, float, float]) -> tuple[float, float, float]:
        ren = self.plotter.renderer
        ren.SetWorldPoint(float(point[0]), float(point[1]), float(point[2]), 1.0)
        ren.WorldToDisplay()
        x, y, z = ren.GetDisplayPoint()
        return float(x), float(y), float(z)
