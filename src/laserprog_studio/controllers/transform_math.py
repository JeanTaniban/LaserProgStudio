# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class TransformMathLayer:
    @staticmethod
    def _normalize_angle_deg(angle: float) -> float:
        """Keep inspector rotation values stable and readable."""
        try:
            raw = float(angle)
            value = (raw + 180.0) % 360.0 - 180.0
            # Prefer displaying +180 when the positive half-turn is reached by a positive snap.
            if abs(value + 180.0) < 1e-9 and raw > 0.0:
                return 180.0
            if abs(value) < 1e-9:
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    def _normalize_euler_deg(self, values: tuple[float, float, float]) -> tuple[float, float, float]:
        return tuple(self._normalize_angle_deg(v) for v in values)  # type: ignore[return-value]

    @staticmethod
    def _quat_normalize(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        w, x, y, z = (float(q[0]), float(q[1]), float(q[2]), float(q[3]))
        n = math.sqrt(w * w + x * x + y * y + z * z)
        if n <= 1e-12:
            return (1.0, 0.0, 0.0, 0.0)
        return (w / n, x / n, y / n, z / n)

    @staticmethod
    def _quat_multiply(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        """Quaternion product. The result applies b first, then a."""
        aw, ax, ay, az = a
        bw, bx, by, bz = b
        return (
            aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
        )

    @staticmethod
    def _quat_inverse(q: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        w, x, y, z = q
        n2 = w * w + x * x + y * y + z * z
        if n2 <= 1e-12:
            return (1.0, 0.0, 0.0, 0.0)
        return (w / n2, -x / n2, -y / n2, -z / n2)

    def _quat_from_axis_angle_tuple(self, axis_vector: tuple[float, float, float], angle_rad: float) -> tuple[float, float, float, float]:
        import numpy as np
        axis = np.asarray(axis_vector, dtype=float)
        n = float(np.linalg.norm(axis))
        if n <= 1e-12:
            return (1.0, 0.0, 0.0, 0.0)
        axis = axis / n
        half = 0.5 * float(angle_rad)
        s = math.sin(half)
        return self._quat_normalize((math.cos(half), float(axis[0] * s), float(axis[1] * s), float(axis[2] * s)))

    def _quat_from_euler_xyz_deg(self, rx: float, ry: float, rz: float) -> tuple[float, float, float, float]:
        """Build a quaternion matching transform_vertices order: X, then Y, then Z."""
        qx = self._quat_from_axis_angle_tuple((1.0, 0.0, 0.0), math.radians(float(rx)))
        qy = self._quat_from_axis_angle_tuple((0.0, 1.0, 0.0), math.radians(float(ry)))
        qz = self._quat_from_axis_angle_tuple((0.0, 0.0, 1.0), math.radians(float(rz)))
        return self._quat_normalize(self._quat_multiply(qz, self._quat_multiply(qy, qx)))

    @staticmethod
    def _quat_to_matrix(q: tuple[float, float, float, float]):
        import numpy as np
        w, x, y, z = q
        return np.array([
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
            [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
            [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
        ], dtype=float)

    def _euler_xyz_deg_from_quat(self, q: tuple[float, float, float, float]) -> tuple[float, float, float]:
        """Return Euler angles for the X->Y->Z convention used by transform_vertices."""
        try:
            m = self._quat_to_matrix(self._quat_normalize(q))
            sy = max(-1.0, min(1.0, -float(m[2, 0])))
            ry = math.asin(sy)
            cy = math.cos(ry)
            if abs(cy) > 1e-8:
                rx = math.atan2(float(m[2, 1]), float(m[2, 2]))
                rz = math.atan2(float(m[1, 0]), float(m[0, 0]))
            else:
                # Gimbal fallback: keep Z stable and solve X from the remaining terms.
                rx = math.atan2(-float(m[1, 2]), float(m[1, 1]))
                rz = 0.0
            return self._normalize_euler_deg((math.degrees(rx), math.degrees(ry), math.degrees(rz)))
        except Exception:
            return (0.0, 0.0, 0.0)

    def _mesh_rotation_quat(self, mesh: Any) -> tuple[float, float, float, float]:
        try:
            q = getattr(mesh, "_lps_rotation_quat", None)
            if q is not None and len(q) == 4:
                return self._quat_normalize(tuple(float(v) for v in q))  # type: ignore[return-value]
            e = getattr(mesh, "_lps_rotation_euler_deg", None)
            if e is not None and len(e) == 3:
                return self._quat_from_euler_xyz_deg(float(e[0]), float(e[1]), float(e[2]))
        except Exception:
            pass
        return (1.0, 0.0, 0.0, 0.0)

    def _mesh_rotation_euler(self, mesh: Any) -> tuple[float, float, float]:
        try:
            e = getattr(mesh, "_lps_rotation_euler_deg", None)
            if e is not None and len(e) == 3:
                return self._normalize_euler_deg((float(e[0]), float(e[1]), float(e[2])))
        except Exception:
            pass
        q = self._mesh_rotation_quat(mesh)
        return self._euler_xyz_deg_from_quat(q)

    def _set_mesh_rotation_state(self, mesh: Any, quat: tuple[float, float, float, float], euler: tuple[float, float, float] | None = None) -> None:
        try:
            q = self._quat_normalize(quat)
            setattr(mesh, "_lps_rotation_quat", q)
            setattr(mesh, "_lps_rotation_euler_deg", self._normalize_euler_deg(euler if euler is not None else self._euler_xyz_deg_from_quat(q)))
        except Exception:
            pass

    def _rotate_vertices_by_quaternion_tuple(self, vertices: list[tuple[float, float, float]], center: tuple[float, float, float], quat: tuple[float, float, float, float]) -> list[tuple[float, float, float]]:
        try:
            import numpy as np
            q = self._quat_normalize(quat)
            c = np.asarray(center, dtype=float)
            pts = np.asarray(vertices, dtype=float) - c
            m = self._quat_to_matrix(q)
            rotated = pts @ m.T
            return [tuple(row) for row in (rotated + c).tolist()]
        except Exception:
            return list(vertices)

    def _qt_to_vtk_xy(self, qx: float, qy: float) -> tuple[float, float]:
        try:
            h = float(self.plotter.height())
        except Exception:
            h = 0.0
        return float(qx), h - float(qy)

    def _display_ray(self, vtk_x: float, vtk_y: float):
        """Return near point and normalized world ray for a display coordinate."""
        import numpy as np
        ren = self.plotter.renderer
        pts = []
        for z_depth in (0.0, 1.0):
            ren.SetDisplayPoint(float(vtk_x), float(vtk_y), float(z_depth))
            ren.DisplayToWorld()
            wx, wy, wz, ww = ren.GetWorldPoint()
            if not ww:
                ww = 1.0
            pts.append(np.array((float(wx) / float(ww), float(wy) / float(ww), float(wz) / float(ww)), dtype=float))
        direction = pts[1] - pts[0]
        norm = float(np.linalg.norm(direction))
        if norm <= 1e-12:
            return pts[0], np.array((0.0, 0.0, -1.0), dtype=float)
        return pts[0], direction / norm

    def _rotation_vector_from_qt(self, qx: float, qy: float, center: tuple[float, float, float], axis_vector: tuple[float, float, float]):
        """Return a stable unit vector in the rotation plane for a Qt mouse point.

        The old implementation used only a ray/plane intersection.  That becomes
        unstable when the rotation plane is nearly parallel to the camera ray, so
        some drags accumulated non-linear deltas or jumped to a fallback.  This
        version keeps the exact ray path when reliable and falls back to a
        screen-space least-squares projection onto the two projected plane basis
        vectors.
        """
        try:
            import numpy as np
            vtk_x, vtk_y = self._qt_to_vtk_xy(qx, qy)
            ray_origin, ray_dir = self._display_ray(vtk_x, vtk_y)
            c = np.asarray(center, dtype=float)
            n = np.asarray(axis_vector, dtype=float)
            n_norm = float(np.linalg.norm(n))
            if n_norm <= 1e-12:
                return None
            n = n / n_norm

            def screen_fallback():
                try:
                    # Build an orthonormal basis in the rotation plane.
                    ref = np.array((0.0, 0.0, 1.0), dtype=float)
                    if abs(float(np.dot(ref, n))) > 0.88:
                        ref = np.array((0.0, 1.0, 0.0), dtype=float)
                    u = np.cross(n, ref)
                    u = u / (float(np.linalg.norm(u)) or 1.0)
                    v = np.cross(n, u)
                    v = v / (float(np.linalg.norm(v)) or 1.0)
                    # Project a short world radius in both basis directions and
                    # solve mouse_delta ~= a * screen_u + b * screen_v.
                    length = max(float(getattr(self, "_drag_gizmo_length", 0.0) or 0.0), 1.0)
                    try:
                        length = max(length, float(getattr(self, "_gizmo_length_at", lambda *_: 1.0)(tuple(center), self.current_meshes())))
                    except Exception:
                        pass
                    pc = self._world_to_display(tuple(c.tolist()))
                    pu = self._world_to_display(tuple((c + u * length).tolist()))
                    pv = self._world_to_display(tuple((c + v * length).tolist()))
                    h = float(self.plotter.height())
                    center2 = np.array((float(pc[0]), h - float(pc[1])), dtype=float)
                    su = np.array((float(pu[0]), h - float(pu[1])), dtype=float) - center2
                    sv = np.array((float(pv[0]), h - float(pv[1])), dtype=float) - center2
                    d = np.array((float(qx), float(qy)), dtype=float) - center2
                    if float(np.linalg.norm(d)) < 1e-6:
                        return None
                    mat = np.column_stack((su, sv))
                    coeff, *_ = np.linalg.lstsq(mat, d, rcond=None)
                    vec = u * float(coeff[0]) + v * float(coeff[1])
                    norm = float(np.linalg.norm(vec))
                    if norm < 1e-8:
                        return None
                    return tuple((vec / norm).tolist())
                except Exception:
                    return None

            denom = float(np.dot(ray_dir, n))
            if abs(denom) >= 1e-5:
                t = float(np.dot(c - ray_origin, n) / denom)
                hit = ray_origin + ray_dir * t
                vec = hit - c
                vec = vec - n * float(np.dot(vec, n))
                norm = float(np.linalg.norm(vec))
                if norm >= 1e-8:
                    return tuple((vec / norm).tolist())
            return screen_fallback()
        except Exception:
            return None

    def _signed_angle_between(self, prev_vec: tuple[float, float, float], next_vec: tuple[float, float, float], axis_vector: tuple[float, float, float]) -> float:
        import numpy as np
        a = np.asarray(prev_vec, dtype=float)
        b = np.asarray(next_vec, dtype=float)
        n = np.asarray(axis_vector, dtype=float)
        a = a / (float(np.linalg.norm(a)) or 1.0)
        b = b / (float(np.linalg.norm(b)) or 1.0)
        n = n / (float(np.linalg.norm(n)) or 1.0)
        return float(math.atan2(float(np.dot(n, np.cross(a, b))), float(np.dot(a, b))))

    def _rotate_vertices_by_quaternion(self, vertices: list[tuple[float, float, float]], center: tuple[float, float, float], axis_vector: tuple[float, float, float], angle_rad: float) -> list[tuple[float, float, float]]:
        """Rotate vertices around a world axis using a normalized axis-angle quaternion."""
        try:
            import numpy as np
            c = np.asarray(center, dtype=float)
            axis = np.asarray(axis_vector, dtype=float)
            axis = axis / (float(np.linalg.norm(axis)) or 1.0)
            half = 0.5 * float(angle_rad)
            qw = math.cos(half)
            qv = axis * math.sin(half)
            pts = np.asarray(vertices, dtype=float) - c
            # Quaternion vector rotation: v' = v + qw * t + cross(qv, t), t = 2 * cross(qv, v).
            t = 2.0 * np.cross(qv, pts)
            rotated = pts + qw * t + np.cross(qv, t)
            return [tuple(row) for row in (rotated + c).tolist()]
        except Exception:
            # Fallback to input vertices rather than corrupting geometry.
            return list(vertices)

    def _snap_rotation_angle(self, angle_rad: float, base_angle_deg: float = 0.0) -> tuple[float, str | None, float | None]:
        """Snap a rotation drag to absolute inspector angles, then return the delta to apply.

        The mouse drag produces a delta angle. A relative snap would quantize that delta, which
        makes a part starting at 15 deg snap to 15/60/105 deg. The transform inspector expects
        absolute values, so rotation snap must quantize base + delta instead.
        """
        try:
            enabled, step_deg, tol_deg = self._rotation_snap_settings()
            raw_delta_deg = math.degrees(float(angle_rad))
            if not enabled:
                return float(angle_rad), None, None
            step_deg = max(abs(float(step_deg)), 1e-9)
            tol_deg = max(float(tol_deg), 0.0)
            base_deg = self._normalize_angle_deg(float(base_angle_deg))
            target_abs_deg = self._normalize_angle_deg(base_deg + raw_delta_deg)
            snapped_abs_deg = round(target_abs_deg / step_deg) * step_deg
            snapped_abs_deg = self._normalize_angle_deg(snapped_abs_deg)
            distance_deg = abs(self._normalize_angle_deg(target_abs_deg - snapped_abs_deg))
            if distance_deg <= tol_deg:
                snapped_delta_deg = self._normalize_angle_deg(snapped_abs_deg - base_deg)
                return math.radians(snapped_delta_deg), f"rot {snapped_abs_deg:.1f} deg", snapped_abs_deg
        except Exception:
            pass
        return float(angle_rad), None, None
