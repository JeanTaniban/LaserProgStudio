# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import time
from dataclasses import replace
from typing import Any

from laserprog_studio.tool_api.styles import get_point_style, visual_state_for_flags
from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_api.projected_drawing import (
    ProjectedDragConstraint,
    ProjectedHandleShape,
    ProjectedInteraction,
)
from laserprog_studio.tool_api.visual import OverlayFieldSpec, OverlayWindowSpec
from laserprog_studio.geometry_ops.texture_projection_vector import _normalize_rotation_deg

from ._texture_projection_constants import (
    HANDLE_MOVE,
    HANDLE_ROTATE,
    HANDLE_SCALE,
    HANDLE_STRETCH_U_NEG,
    HANDLE_STRETCH_U_POS,
    HANDLE_STRETCH_V_NEG,
    HANDLE_STRETCH_V_POS,
    OVERLAY_ID,
)
from ._texture_projection_geometry import (
    Vec3,
    basis_from_normal,
    display_to_world_at_depth,
    display_to_world_on_plane,
    mesh_center,
    mesh_span,
    screen_pos,
    signed_angle_between_on_plane,
    vadd,
    vdot,
    vnorm,
    vscale,
    vsub,
    vec3_or_none,
)


_PREVIEW_FRAME_ID = "frame"
_PREVIEW_RING_ID = "rotation_ring"
_PREVIEW_CROSS_U_ID = "cross_u"
_PREVIEW_CROSS_V_ID = "cross_v"
_PREVIEW_LABEL_ID = "label"
_FAST_PREVIEW_IDS = (
    _PREVIEW_FRAME_ID,
    _PREVIEW_RING_ID,
    _PREVIEW_CROSS_U_ID,
    _PREVIEW_CROSS_V_ID,
    _PREVIEW_LABEL_ID,
)

# Texture placement is often used on busy engraved/wood grain previews.  Keep
# the widgets screen-locked like the rest of the Creator API, but make this
# tool's handles deliberately larger than the generic 13 px default so they
# stay easy to see and grab without changing the texture scale itself.
_TEXTURE_HANDLE_BASE_RADIUS_PX = 18
_TEXTURE_HANDLE_HIT_RADIUS_PX = 20.0
_TEXTURE_HANDLE_PICK_RADIUS_PX = 22.0
_TEXTURE_FRAME_LINE_WIDTH_PX = 4.5
_TEXTURE_RING_LINE_WIDTH_PX = 5.5
_TEXTURE_CROSS_LINE_WIDTH_PX = 4.0

_TEXTURE_HANDLE_IDS = {
    HANDLE_MOVE,
    HANDLE_ROTATE,
    HANDLE_SCALE,
    HANDLE_STRETCH_U_NEG,
    HANDLE_STRETCH_U_POS,
    HANDLE_STRETCH_V_NEG,
    HANDLE_STRETCH_V_POS,
}

_STRETCH_HANDLES = {
    HANDLE_STRETCH_U_NEG: ("stretch_u_neg", "texstretch_u"),
    HANDLE_STRETCH_U_POS: ("stretch_u_pos", "texstretch_u"),
    HANDLE_STRETCH_V_NEG: ("stretch_v_neg", "texstretch_v"),
    HANDLE_STRETCH_V_POS: ("stretch_v_pos", "texstretch_v"),
}


def _color_hex(value: Any, fallback: str = "#4AA7FF") -> str:
    """Convert Creator RGBA tuples or hex strings to projected-drawing hex."""

    if isinstance(value, str):
        text = value.strip()
        if len(text) == 7 and text.startswith("#"):
            return text.upper()
    try:
        r, g, b = tuple(float(component) for component in tuple(value)[:3])
        return "#%02X%02X%02X" % (
            max(0, min(255, int(round(r * 255)))),
            max(0, min(255, int(round(g * 255)))),
            max(0, min(255, int(round(b * 255)))),
        )
    except Exception:
        return fallback


class TextureProjectorRuntime:
    """Interactive viewport runtime for the texture projection creator tool.

    The projector has two update paths:

    * structural/full render: declare handles, frame, ring and overlay;
    * drag fast path: mutate only the current handle/preview positions and the
      active actor texture coordinates, then defer the expensive scene rebuild to
      mouse release.

    This mirrors the Creator API guidance used by Plan Tracer and the Gizmo
    catalog: no scene-cache rebuild, overlay resync or mesh-preview regeneration
    inside the mouse-move loop.
    """

    def __init__(self, tool: Any) -> None:
        self.tool = tool
        self._drag: dict[str, Any] | None = None

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            out = float(value)
            return out if math.isfinite(out) else float(default)
        except Exception:
            return float(default)

    @staticmethod
    def _wrap_delta_radians(delta: float) -> float:
        while delta > math.pi:
            delta -= 2.0 * math.pi
        while delta < -math.pi:
            delta += 2.0 * math.pi
        return delta

    @staticmethod
    def _unit_plane_vector(origin: Vec3, point: Vec3 | None) -> Vec3 | None:
        if point is None:
            return None
        vec = vsub(tuple(float(v) for v in point), tuple(float(v) for v in origin))
        if math.sqrt(max(vdot(vec, vec), 0.0)) <= 1e-8:
            return None
        return vnorm(vec)

    @staticmethod
    def _plane_distance(origin: Vec3, point: Vec3 | None) -> float | None:
        if point is None:
            return None
        vec = vsub(tuple(float(v) for v in point), tuple(float(v) for v in origin))
        dist = math.sqrt(max(vdot(vec, vec), 0.0))
        return dist if math.isfinite(dist) and dist > 1e-8 else None

    @staticmethod
    def _rotate_plane_basis(u_axis: Vec3, v_axis: Vec3, rotation_deg: float) -> tuple[Vec3, Vec3]:
        """Rotate an existing texture basis by the bitmap rotation value."""
        try:
            u = vnorm(tuple(float(v) for v in u_axis), fallback=(1.0, 0.0, 0.0))
            v = vnorm(tuple(float(v) for v in v_axis), fallback=(0.0, 1.0, 0.0))
            a = math.radians(float(rotation_deg))
            ca, sa = math.cos(a), math.sin(a)
            ru = vnorm((u[0] * ca + v[0] * sa, u[1] * ca + v[1] * sa, u[2] * ca + v[2] * sa), fallback=u)
            rv = vnorm((-u[0] * sa + v[0] * ca, -u[1] * sa + v[1] * ca, -u[2] * sa + v[2] * ca), fallback=v)
            return ru, rv
        except Exception:
            return tuple(float(v) for v in u_axis), tuple(float(v) for v in v_axis)

    @staticmethod
    def _origin_active(values: dict[str, Any], *, seed_face_index: int | None) -> bool:
        if seed_face_index is not None:
            return True
        value = values.get("projection_origin_active", False)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _ui_radius_world(self, ctx: Any, origin: Vec3, pixel_radius: float = 82.0) -> float:
        """Return a camera-sized world radius for the TEX viewport controls.

        The texture footprint itself can grow with the ``scale`` value, but the
        manipulation UI must not.  Point handles are already screen-locked by the
        Creator API; the drawn rotation circle and handle positions need the same
        camera/FOV-aware conversion.
        """
        owner = getattr(ctx, "owner", None)
        plotter = getattr(owner, "plotter", None) if owner is not None else None
        try:
            result = draw2d.world_radius_for_screen_pixels(
                plotter,
                tuple(float(v) for v in origin),
                float(pixel_radius),
                fallback_world_per_px=0.05,
            )
            if math.isfinite(float(result)) and float(result) > 1.0e-9:
                return float(result)
        except Exception:
            pass
        # Conservative non-camera fallback used by unit tests and headless owners.
        return max(float(pixel_radius) * 0.05, 0.25)

    @staticmethod
    def _angle_delta_deg(a: float, b: float) -> float:
        """Smallest signed delta from candidate ``b`` to value ``a``."""
        delta = float(a) - float(b)
        while delta > 180.0:
            delta -= 360.0
        while delta < -180.0:
            delta += 360.0
        return delta

    def _painted_face_points(self, state: dict[str, Any]) -> list[Vec3]:
        """Return the target points used for snap/clamp helpers.

        For a clicked face, use the coplanar face group selected by coverage.
        Otherwise fall back to all mesh vertices, which gives a predictable bounds
        based behaviour for the first pass requested by the user.
        """
        mesh = state.get("mesh")
        params = state.get("params")
        vertices = [tuple(float(x) for x in v) for v in (getattr(mesh, "vertices", None) or ())]
        if not vertices or params is None:
            return []
        seed = getattr(params, "seed_face_index", None)
        if seed is None:
            return vertices
        try:
            from laserprog_studio.geometry_ops.texture_projection_faces import _selected_face_ids_for_anchor

            triangles = list(getattr(mesh, "triangles", []) or [])
            face_ids = _selected_face_ids_for_anchor(
                mesh,
                seed_face_index=int(seed),
                normal=tuple(float(v) for v in state.get("normal", (0.0, 0.0, 1.0))),
                coverage_angle_deg=float(getattr(params, "coverage_angle_deg", 35.0)),
            )
            ids: set[int] = set()
            for face_id in face_ids or [int(seed)]:
                if 0 <= int(face_id) < len(triangles):
                    ids.update(int(i) for i in triangles[int(face_id)])
            if ids:
                return [vertices[i] for i in sorted(ids) if 0 <= i < len(vertices)]
        except Exception:
            pass
        return vertices

    def _move_constraint_for_state(self, state: dict[str, Any]) -> dict[str, Any] | None:
        """Build a cheap bounds constraint that keeps the texture centre on face."""
        try:
            points = self._painted_face_points(state)
            if len(points) < 2:
                return None
            normal = vnorm(tuple(float(v) for v in state.get("normal", (0.0, 0.0, 1.0))))
            u_axis, v_axis, _w = basis_from_normal(normal, 0.0)
            ref = points[0]
            coords = [(vdot(vsub(p, ref), u_axis), vdot(vsub(p, ref), v_axis)) for p in points]
            us = [c[0] for c in coords]
            vs = [c[1] for c in coords]
            if max(us) - min(us) <= 1.0e-9 or max(vs) - min(vs) <= 1.0e-9:
                return None
            return {
                "ref": ref,
                "u": u_axis,
                "v": v_axis,
                "normal": normal,
                "plane_w": vdot(vsub(tuple(float(x) for x in state.get("origin", ref)), ref), normal),
                "min_u": min(us),
                "max_u": max(us),
                "min_v": min(vs),
                "max_v": max(vs),
            }
        except Exception:
            return None

    @staticmethod
    def _clamp_origin_to_constraint(origin: Vec3, constraint: dict[str, Any] | None) -> Vec3:
        if not constraint:
            return tuple(float(v) for v in origin)
        try:
            ref = tuple(float(v) for v in constraint["ref"])
            u_axis = tuple(float(v) for v in constraint["u"])
            v_axis = tuple(float(v) for v in constraint["v"])
            normal = tuple(float(v) for v in constraint["normal"])
            rel = vsub(tuple(float(v) for v in origin), ref)
            u = max(float(constraint["min_u"]), min(float(constraint["max_u"]), vdot(rel, u_axis)))
            v = max(float(constraint["min_v"]), min(float(constraint["max_v"]), vdot(rel, v_axis)))
            w = float(constraint.get("plane_w", vdot(rel, normal)))
            return vadd(vadd(vadd(ref, vscale(u_axis, u)), vscale(v_axis, v)), vscale(normal, w))
        except Exception:
            return tuple(float(v) for v in origin)

    def _rotation_snap_candidates_for_state(self, state: dict[str, Any]) -> list[tuple[float, str]]:
        """Angles worth snapping to: common angles + projected bounds axes."""
        candidates: list[tuple[float, str]] = []
        # Remarkable angles.  15° steps include 30/45/60/90 without making the
        # interaction feel locked everywhere.
        for angle in range(-360, 361, 15):
            candidates.append((float(angle), f"{angle}°"))
        try:
            normal = vnorm(tuple(float(v) for v in state.get("normal", (0.0, 0.0, 1.0))))
            base_u = vnorm(tuple(float(v) for v in state.get("base_u", (1.0, 0.0, 0.0))), fallback=(1.0, 0.0, 0.0))
            base_v = vnorm(tuple(float(v) for v in state.get("base_v", (0.0, 1.0, 0.0))), fallback=(0.0, 1.0, 0.0))
            mesh = state.get("mesh")
            vertices = [tuple(float(x) for x in v) for v in (getattr(mesh, "vertices", None) or ())]
            spans = (1.0, 1.0, 1.0)
            if vertices:
                xs = [p[0] for p in vertices]
                ys = [p[1] for p in vertices]
                zs = [p[2] for p in vertices]
                spans = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
            world_axes = [((1.0, 0.0, 0.0), spans[0], "bounds X"), ((0.0, 1.0, 0.0), spans[1], "bounds Y"), ((0.0, 0.0, 1.0), spans[2], "bounds Z")]
            for axis, span, label in world_axes:
                if float(span) <= 1.0e-9:
                    continue
                # Project the bound axis into the painted plane.
                in_plane = vsub(axis, vscale(normal, vdot(axis, normal)))
                length = math.sqrt(max(vdot(in_plane, in_plane), 0.0))
                if length <= 1.0e-6:
                    continue
                in_plane = vscale(in_plane, 1.0 / length)
                angle = math.degrees(math.atan2(vdot(in_plane, base_v), vdot(in_plane, base_u)))
                candidates.append((angle, label))
                candidates.append((angle + 90.0, f"{label} +90°"))
        except Exception:
            pass
        # Keep the list small and deterministic.
        unique: dict[tuple[int, str], tuple[float, str]] = {}
        for angle, label in candidates:
            norm_angle = self._angle_delta_deg(float(angle), 0.0)
            key = (int(round(norm_angle * 100.0)), str(label))
            unique[key] = (norm_angle, str(label))
        return list(unique.values())

    def _snap_rotation(self, raw_deg: float, candidates: list[tuple[float, str]], *, threshold_deg: float = 4.0) -> tuple[float, str | None]:
        try:
            raw = float(raw_deg)
            best: tuple[float, float, str] | None = None
            for base, label in candidates:
                candidate = float(base) + 360.0 * round((raw - float(base)) / 360.0)
                # Do not swallow tiny intentional drags around the current 0°
                # orientation.  Snapping to 0° is useful after a real rotation,
                # but the first few pixels must still produce visible feedback.
                if abs(self._angle_delta_deg(candidate, 0.0)) <= 1.0e-6 and abs(raw) <= float(threshold_deg):
                    continue
                delta = self._angle_delta_deg(raw, candidate)
                score = abs(delta)
                if best is None or score < best[0]:
                    best = (score, candidate, str(label))
            if best is not None and best[0] <= float(threshold_deg):
                return float(best[1]), best[2]
        except Exception:
            pass
        return float(raw_deg), None

    def _scale_snap_candidates_for_state(self, state: dict[str, Any]) -> list[tuple[float, str]]:
        """Return scale values that fit the current rotated texture frame to the painted bounds."""
        try:
            points = self._painted_face_points(state)
            if len(points) < 2:
                return []
            origin = tuple(float(v) for v in state.get("origin", (0.0, 0.0, 0.0)))
            # Use the *rotated* image axes.  This is the important part: fitting a
            # 45° image against a rectangular face needs the face extent measured
            # in that 45° frame, not in the unrotated mesh bounds frame.
            u_axis = tuple(float(v) for v in state.get("u", (1.0, 0.0, 0.0)))
            v_axis = tuple(float(v) for v in state.get("v", (0.0, 1.0, 0.0)))
            coords = [(vdot(vsub(p, origin), u_axis), vdot(vsub(p, origin), v_axis)) for p in points]
            us = [c[0] for c in coords]
            vs = [c[1] for c in coords]
            face_w = max(us) - min(us)
            face_h = max(vs) - min(vs)
            if face_w <= 1.0e-9 or face_h <= 1.0e-9:
                return []

            current_scale = max(float(getattr(state.get("params"), "scale", 1.0) or 1.0), 1.0e-9)
            tile_w = float(state.get("tile_width", 0.0) or 0.0)
            tile_h = float(state.get("tile_height", 0.0) or 0.0)
            if tile_w <= 1.0e-9 or tile_h <= 1.0e-9:
                # Fallback for non-anchored projections: infer the unscaled frame
                # dimensions from the current visible frame.
                tile_w = 2.0 * float(state.get("half_w", 0.0) or 0.0) / current_scale
                tile_h = 2.0 * float(state.get("half_h", 0.0) or 0.0) / current_scale
            if tile_w <= 1.0e-9 or tile_h <= 1.0e-9:
                return []

            # Face-anchored square images start as a fit-inside tile, so on a
            # rectangular board the stored tile can be the short side (for
            # example 10x10 on a 20x10 face).  Scale snapping, however, should
            # answer the user question "what scale makes the current rotated
            # square image fit/cover this face?"  Use the unrotated painted-face
            # bounds as the square tile's canonical side; otherwise a 45° snap on
            # a 20x10 face doubles the useful value and feels broken.
            if abs(tile_w - tile_h) <= max(tile_w, tile_h, 1.0) * 1.0e-6:
                try:
                    base_u = vnorm(tuple(float(v) for v in state.get("base_u", u_axis)), fallback=u_axis)
                    base_v = vnorm(tuple(float(v) for v in state.get("base_v", v_axis)), fallback=v_axis)
                    base_coords = [(vdot(vsub(p, origin), base_u), vdot(vsub(p, origin), base_v)) for p in points]
                    bus = [c[0] for c in base_coords]
                    bvs = [c[1] for c in base_coords]
                    base_w = max(bus) - min(bus)
                    base_h = max(bvs) - min(bvs)
                    canonical_square_side = max(tile_w, tile_h, base_w, base_h)
                    if math.isfinite(canonical_square_side) and canonical_square_side > 1.0e-9:
                        tile_w = canonical_square_side
                        tile_h = canonical_square_side
                except Exception:
                    pass

            fit_w = face_w / max(tile_w, 1.0e-9)
            fit_h = face_h / max(tile_h, 1.0e-9)
            values = [
                (fit_w, "fit width"),
                (fit_h, "fit height"),
                (min(fit_w, fit_h), "fit inside"),
                (max(fit_w, fit_h), "cover bounds"),
            ]
            out: list[tuple[float, str]] = []
            seen: set[tuple[int, str]] = set()
            for value, label in values:
                value = float(value)
                if not math.isfinite(value) or value <= 0.0:
                    continue
                # Keep semantically different snap labels even when their numeric
                # value is equal.  A square rotated over a rectangle can have
                # identical width/height candidates, and the UI/tests still need
                # to know both snaps exist.
                key = (int(round(value * 100000.0)), str(label))
                if key in seen:
                    continue
                seen.add(key)
                out.append((value, label))
            return out
        except Exception:
            return []

    @staticmethod
    def _snap_scale(raw_scale: float, candidates: list[tuple[float, str]], *, relative_threshold: float = 0.055) -> tuple[float, str | None]:
        try:
            raw = max(float(raw_scale), 1.0e-9)
            best: tuple[float, float, str] | None = None
            for candidate, label in candidates:
                candidate = max(float(candidate), 1.0e-9)
                score = abs(raw - candidate) / max(candidate, 1.0e-9)
                if best is None or score < best[0]:
                    best = (score, candidate, str(label))
            if best is not None and best[0] <= float(relative_threshold):
                return float(best[1]), best[2]
        except Exception:
            pass
        return float(raw_scale), None

    def state(self, ctx: Any) -> dict[str, Any] | None:
        values = dict(ctx.inspector.values()) if ctx.inspector.panel is not None else {}
        try:
            target = int(values.get("target_index", -1))
        except Exception:
            target = -1
        meshes = list(ctx.document.meshes(include_preview=False))
        if not (0 <= target < len(meshes)):
            selected = tuple(ctx.scene_selection.selected_indices())
            if selected:
                target = int(selected[-1])
        if not (0 <= target < len(meshes)):
            return None
        mesh = meshes[target]
        params = self.tool.params_from_context(ctx)
        active_origin = self._origin_active(values, seed_face_index=params.seed_face_index)
        stored_origin = vec3_or_none(values.get("projection_origin")) if active_origin else None
        origin = params.projection_origin or stored_origin or mesh_center(mesh)
        normal = params.projection_normal or (vec3_or_none(values.get("projection_normal")) if active_origin else None) or (0.0, 0.0, 1.0)
        origin = tuple(float(v) for v in origin)
        normal = vnorm(tuple(float(v) for v in normal))
        span = mesh_span(mesh)
        scale = max(float(params.scale or 1.0), 0.001)
        stretch_u = max(float(getattr(params, "stretch_u", 1.0) or 1.0), 0.001)
        stretch_v = max(float(getattr(params, "stretch_v", 1.0) or 1.0), 0.001)
        texture_radius = max(span * 0.30 * scale * max(stretch_u, stretch_v), 1.0e-6)
        base_u: Vec3 | None = None
        base_v: Vec3 | None = None
        tile_w = 0.0
        tile_h = 0.0

        # When a face is clicked, use the same edit frame as the actual UV/decal
        # generator.  The previous viewport frame used a generic normal basis and
        # a mesh_span*0.30 heuristic: snap scale was therefore unrelated to the
        # real texture dimensions and could appear rotated by the triangle diagonal.
        if params.seed_face_index is not None and str(params.projection_mode or "planar").lower() == "planar":
            try:
                from laserprog_studio.geometry_ops.texture_projection_faces import _texture_anchor_frame_for_mesh

                frame = _texture_anchor_frame_for_mesh(mesh, params)
                if frame is not None:
                    frame_origin, frame_normal, frame_u, frame_v, frame_tile_w, frame_tile_h = frame
                    origin = tuple(float(v) for v in frame_origin)
                    normal = vnorm(tuple(float(v) for v in frame_normal))
                    base_u = vnorm(tuple(float(v) for v in frame_u), fallback=(1.0, 0.0, 0.0))
                    base_v = vnorm(tuple(float(v) for v in frame_v), fallback=(0.0, 1.0, 0.0))
                    tile_w = max(float(frame_tile_w), 1.0e-9)
                    tile_h = max(float(frame_tile_h), 1.0e-9)
                    texture_radius = max(max(tile_w * stretch_u, tile_h * stretch_v) * 0.5 * scale, 1.0e-6)
            except Exception:
                base_u = None
                base_v = None

        # Viewport UI radius is independent from texture scale.  Only the camera
        # projection/FOV changes it, so the handles stay easy to grab.
        radius = self._ui_radius_world(ctx, origin, pixel_radius=82.0)
        if base_u is not None and base_v is not None:
            u_axis, v_axis = self._rotate_plane_basis(base_u, base_v, _normalize_rotation_deg(params.rotation_deg))
            w_axis = normal
        else:
            u_axis, v_axis, w_axis = basis_from_normal(normal, _normalize_rotation_deg(params.rotation_deg))
        aspect = 1.0
        try:
            iw = float(params.image_width or 0.0)
            ih = float(params.image_height or 0.0)
            if iw > 0.0 and ih > 0.0:
                aspect = max(0.05, min(20.0, iw / ih))
        except Exception:
            aspect = 1.0
        if tile_w > 1.0e-9 and tile_h > 1.0e-9:
            half_w = max(tile_w * scale * stretch_u * 0.5, 1.0e-6)
            half_h = max(tile_h * scale * stretch_v * 0.5, 1.0e-6)
        elif aspect >= 1.0:
            half_w = texture_radius
            half_h = max(texture_radius / aspect, texture_radius * 0.18)
            tile_w = max(2.0 * half_w / (scale * stretch_u), 1.0e-9)
            tile_h = max(2.0 * half_h / (scale * stretch_v), 1.0e-9)
        else:
            half_w = max(texture_radius * aspect, texture_radius * 0.18)
            half_h = texture_radius
            tile_w = max(2.0 * half_w / (scale * stretch_u), 1.0e-9)
            tile_h = max(2.0 * half_h / (scale * stretch_v), 1.0e-9)
        return {
            "target": int(target),
            "mesh": mesh,
            "params": params,
            "origin": origin,
            "normal": w_axis,
            "u": u_axis,
            "v": v_axis,
            "base_u": base_u or u_axis,
            "base_v": base_v or v_axis,
            "radius": radius,
            "texture_radius": texture_radius,
            "half_w": half_w,
            "half_h": half_h,
            "tile_width": tile_w,
            "tile_height": tile_h,
            "stretch_u": stretch_u,
            "stretch_v": stretch_v,
            "origin_active": active_origin,
        }

    def points(self, state: dict[str, Any]) -> dict[str, Any]:
        origin = state["origin"]
        u = state["u"]
        v = state["v"]
        radius = float(state["radius"])
        half_w = float(state["half_w"])
        half_h = float(state["half_h"])
        rotate_handle = vadd(origin, vscale(v, max(half_h, radius) * 1.22))
        scale_handle = vadd(origin, vscale(u, max(half_w, radius) * 1.22))
        stretch_u_neg = vadd(origin, vscale(u, -half_w))
        stretch_u_pos = vadd(origin, vscale(u, half_w))
        stretch_v_neg = vadd(origin, vscale(v, -half_h))
        stretch_v_pos = vadd(origin, vscale(v, half_h))
        corners = (
            vadd(vadd(origin, vscale(u, -half_w)), vscale(v, -half_h)),
            vadd(vadd(origin, vscale(u, half_w)), vscale(v, -half_h)),
            vadd(vadd(origin, vscale(u, half_w)), vscale(v, half_h)),
            vadd(vadd(origin, vscale(u, -half_w)), vscale(v, half_h)),
            vadd(vadd(origin, vscale(u, -half_w)), vscale(v, -half_h)),
        )
        ring = tuple(
            vadd(origin, vadd(vscale(u, math.cos(2.0 * math.pi * step / 96.0) * radius), vscale(v, math.sin(2.0 * math.pi * step / 96.0) * radius)))
            for step in range(97)
        )
        cross_u = (vadd(origin, vscale(u, -radius * 0.18)), vadd(origin, vscale(u, radius * 0.18)))
        cross_v = (vadd(origin, vscale(v, -radius * 0.18)), vadd(origin, vscale(v, radius * 0.18)))
        return {"move": origin, "rotate": rotate_handle, "scale": scale_handle, "stretch_u_neg": stretch_u_neg, "stretch_u_pos": stretch_u_pos, "stretch_v_neg": stretch_v_neg, "stretch_v_pos": stretch_v_pos, "frame": corners, "ring": ring, "cross_u": cross_u, "cross_v": cross_v}

    def _actor_metadata(self, kind: str, style_id: str, label: str) -> dict[str, Any]:
        return {
            "kind": kind,
            "label": label,
            "semantic": "texture_projector_handle",
            # Expose the handles to the native Creator API interaction refresh.
            "motif_family": "texture_projector",
            "motif_kind": "handle",
            "point_style": style_id,
            "line_style": "grabbable",
            "visual_state": "auto",
            "base_radius_px": _TEXTURE_HANDLE_BASE_RADIUS_PX,
            "kind_suffix": kind,
            "api_ui_visible": True,
        }

    def _handle_specs(self, state: dict[str, Any]) -> tuple[tuple[str, Vec3, str, str, str], ...]:
        pts = self.points(state)
        return (
            (HANDLE_MOVE, pts["move"], "texture_projector:move", "target", "Move texture"),
            (HANDLE_ROTATE, pts["rotate"], "texture_projector:rotate", "ring", "Rotate texture"),
            (HANDLE_SCALE, pts["scale"], "texture_projector:scale", "square", "Scale texture proportionally"),
            (HANDLE_STRETCH_U_NEG, pts["stretch_u_neg"], "texture_projector:stretch_u_neg", "square", "Stretch width"),
            (HANDLE_STRETCH_U_POS, pts["stretch_u_pos"], "texture_projector:stretch_u_pos", "square", "Stretch width"),
            (HANDLE_STRETCH_V_NEG, pts["stretch_v_neg"], "texture_projector:stretch_v_neg", "square", "Stretch height"),
            (HANDLE_STRETCH_V_POS, pts["stretch_v_pos"], "texture_projector:stretch_v_pos", "square", "Stretch height"),
        )

    def _preview_primitives(self, state: dict[str, Any]) -> tuple[Any, ...]:
        pts = self.points(state)
        owner = self.tool.id
        frame_id = f"{owner}:{_PREVIEW_FRAME_ID}"
        ring_id = f"{owner}:{_PREVIEW_RING_ID}"
        cross_u_id = f"{owner}:{_PREVIEW_CROSS_U_ID}"
        cross_v_id = f"{owner}:{_PREVIEW_CROSS_V_ID}"
        label_id = f"{owner}:{_PREVIEW_LABEL_ID}"
        return (
            draw2d.polyline(
                frame_id,
                pts["frame"],
                color="#46A6FF",
                width_px=_TEXTURE_FRAME_LINE_WIDTH_PX,
                layer=18,
                interaction=ProjectedInteraction.FIXED,
                metadata={"role": "texture_projector_frame", "projected_no_selection_actor": True},
            ),
            draw2d.polyline(
                ring_id,
                pts["ring"],
                color="#FFB23F",
                width_px=_TEXTURE_RING_LINE_WIDTH_PX,
                layer=17,
                interaction=ProjectedInteraction.FIXED,
                metadata={"role": "texture_projector_rotation_ring", "projected_no_selection_actor": True},
            ),
            draw2d.line(
                cross_u_id,
                pts["cross_u"][0],
                pts["cross_u"][1],
                color="#91E085",
                width_px=_TEXTURE_CROSS_LINE_WIDTH_PX,
                layer=19,
                interaction=ProjectedInteraction.FIXED,
                metadata={"role": "texture_projector_cross_u", "projected_no_selection_actor": True},
            ),
            draw2d.line(
                cross_v_id,
                pts["cross_v"][0],
                pts["cross_v"][1],
                color="#91E085",
                width_px=_TEXTURE_CROSS_LINE_WIDTH_PX,
                layer=19,
                interaction=ProjectedInteraction.FIXED,
                metadata={"role": "texture_projector_cross_v", "projected_no_selection_actor": True},
            ),
            draw2d.text(
                label_id,
                "Texture placement",
                vadd(state["origin"], vscale(state["normal"], 0.6)),
                color="#E8F1F8",
                size_px=13,
                anchor="bottom",
                layer=42,
                metadata={"role": "texture_projector_label", "projected_no_selection_actor": True},
            ),
        )

    def _show_projector_preview(self, ctx: Any, state: dict[str, Any], *, mark_dirty: bool = False, render: bool = False) -> tuple[str, ...]:
        primitives = self._preview_primitives(state)
        registry = ctx.projected_drawing.for_tool(self.tool.id)
        registry.add_many(primitives, replace=True, render=render)
        dirty = tuple(str(item.id) for item in primitives)
        if mark_dirty:
            try:
                current = tuple(getattr(ctx.selection.state, "dirty_visual_preview_ids", ()) or ())
                ctx.selection.state.dirty_visual_preview_ids = tuple(dict.fromkeys((*current, *dirty)))
            except Exception:
                pass
        return dirty

    def render_declarations(self, ctx: Any, *, clear_previews: bool = True, sync_overlay: bool = True, rebuild_snap: bool = True) -> dict[str, Any] | None:
        state = self.state(ctx)
        registry = ctx.projected_drawing.for_tool(self.tool.id)
        # Do not clear the whole projected registry before rebuilding: that would
        # unregister selection actors momentarily and lose hover/grab state during
        # a style-only refresh. Stale primitives are reconciled after add_many.
        if state is None:
            registry.clear(render=False)
            ctx.overlay.close_tool_windows(self.tool.id, include_persistent=False)
            return None

        hover_id = getattr(ctx.selection.state, "hover_id", None)
        grabbed = set(getattr(ctx.selection.state, "grabbed_ids", ()) or ())
        selected = set(getattr(ctx.selection, "ids", lambda: ())() or ())

        def flags(actor_id: str) -> tuple[bool, bool, bool]:
            return actor_id == hover_id, actor_id in grabbed, actor_id in selected

        projected: list[Any] = list(self._preview_primitives(state))
        for actor_id, position, kind, style_id, label in self._handle_specs(state):
            hover, grabbed_flag, selected_flag = flags(actor_id)
            style = get_point_style(style_id)
            visual_state = visual_state_for_flags(selectable=True, hover=hover, grabbed=grabbed_flag, selected=selected_flag)
            shape = {
                "target": ProjectedHandleShape.TARGET,
                "ring": ProjectedHandleShape.RING,
                "square": ProjectedHandleShape.SQUARE,
            }.get(str(style_id), ProjectedHandleShape.SOLID)
            direction = state["v"] if actor_id in {HANDLE_ROTATE, HANDLE_STRETCH_V_NEG, HANDLE_STRETCH_V_POS} else state["u"] if actor_id in {HANDLE_SCALE, HANDLE_STRETCH_U_NEG, HANDLE_STRETCH_U_POS} else state["normal"]
            projected.append(
                draw2d.handle(
                    actor_id,
                    position,
                    shape=shape,
                    direction=direction,
                    size_px=float(style.radius_for(_TEXTURE_HANDLE_BASE_RADIUS_PX, visual_state)),
                    line_width_px=3.0,
                    color=_color_hex(style.color_for(visual_state)),
                    hover_color=_color_hex(getattr(style, "hover_color", style.color_for(visual_state))),
                    selected_color=_color_hex(getattr(style, "selected_color", style.color_for(visual_state))),
                    grabbed_color=_color_hex(getattr(style, "grabbed_color", style.color_for(visual_state))),
                    layer=34,
                    interaction=ProjectedInteraction.GRABBABLE,
                    constraint=ProjectedDragConstraint.FREE,
                    hit_radius_px=_TEXTURE_HANDLE_HIT_RADIUS_PX,
                    metadata=self._actor_metadata(kind, style_id, label),
                )
            )
        with registry.batch():
            registry.add_many(projected, replace=True, render=False)
            existing = {str(item.id) for item in registry.items()}
            wanted = {str(item.id) for item in projected}
            stale = tuple(item_id for item_id in existing if item_id not in wanted)
            if stale:
                registry.remove_many(stale, render=False)
        if sync_overlay:
            params = state["params"]
            ctx.overlay.show_window(
                OverlayWindowSpec(
                    id=OVERLAY_ID,
                    title="Texture placement",
                    owner_tool=self.tool.id,
                    overlay_kind="palette",
                    anchor="viewport_top_right",
                    width_px=310,
                    persistent=False,
                    movable=True,
                    fields=[
                        OverlayFieldSpec("tex_ui_hint", "Handles", "center = move · ring = rotate · square = scale · edges = stretch", kind="info"),
                        OverlayFieldSpec("tex_ui_rotate", "Rotation", f"{float(params.rotation_deg):.1f}°", kind="number"),
                        OverlayFieldSpec("tex_ui_scale", "Scale", f"{float(params.scale):.3g} · U×{float(getattr(params, 'stretch_u', 1.0)):.3g} V×{float(getattr(params, 'stretch_v', 1.0)):.3g}", kind="number"),
                        OverlayFieldSpec("tex_ui_snap", "Snap", str((self._drag or {}).get("snap_label") or "15° · bounds · fit"), kind="info"),
                        OverlayFieldSpec("tex_ui_target", "Target", f"#{int(state['target']):02d}", kind="info"),
                    ],
                )
            )
        if rebuild_snap:
            try:
                ctx.scene_cache.rebuild(ctx, scope="snap")
            except Exception:
                pass
        return state

    def render(self, ctx: Any, *, render: bool = True) -> None:
        self.render_declarations(ctx)
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui

                render_creator_viewport_ui(owner, ctx, self.tool.id, render=render)
            except Exception:
                if render:
                    try:
                        ctx.request_full_render()
                    except Exception:
                        pass

    def handle_from_kind(self, kind: str | None) -> str:
        kind_value = str(kind or "").lower()
        if kind_value in {HANDLE_MOVE.lower(), "move", "texmove", "texture_projector:move"}:
            return HANDLE_MOVE
        if kind_value in {HANDLE_SCALE.lower(), "scale", "texscale", "texture_projector:scale"}:
            return HANDLE_SCALE
        if kind_value in {HANDLE_STRETCH_U_NEG.lower(), "stretch_u_neg", "texstretch_u", "texture_projector:stretch_u_neg"}:
            return HANDLE_STRETCH_U_NEG
        if kind_value in {HANDLE_STRETCH_U_POS.lower(), "stretch_u_pos", "texture_projector:stretch_u_pos"}:
            return HANDLE_STRETCH_U_POS
        if kind_value in {HANDLE_STRETCH_V_NEG.lower(), "stretch_v_neg", "texstretch_v", "texture_projector:stretch_v_neg"}:
            return HANDLE_STRETCH_V_NEG
        if kind_value in {HANDLE_STRETCH_V_POS.lower(), "stretch_v_pos", "texture_projector:stretch_v_pos"}:
            return HANDLE_STRETCH_V_POS
        return HANDLE_ROTATE

    def axis_from_handle_id(self, handle_id: str) -> str:
        if handle_id == HANDLE_MOVE:
            return "texmove"
        if handle_id == HANDLE_SCALE:
            return "texscale"
        if handle_id in {HANDLE_STRETCH_U_NEG, HANDLE_STRETCH_U_POS}:
            return "texstretch_u"
        if handle_id in {HANDLE_STRETCH_V_NEG, HANDLE_STRETCH_V_POS}:
            return "texstretch_v"
        return "texrot"

    def handle_screen_positions(self, ctx: Any) -> dict[str, Vec3]:
        state = self.state(ctx)
        owner = getattr(ctx, "owner", None)
        if state is None or owner is None:
            return {}
        pts = self.points(state)
        out: dict[str, Vec3] = {}
        for handle_id, key in (
            (HANDLE_MOVE, "move"),
            (HANDLE_ROTATE, "rotate"),
            (HANDLE_SCALE, "scale"),
            (HANDLE_STRETCH_U_NEG, "stretch_u_neg"),
            (HANDLE_STRETCH_U_POS, "stretch_u_pos"),
            (HANDLE_STRETCH_V_NEG, "stretch_v_neg"),
            (HANDLE_STRETCH_V_POS, "stretch_v_pos"),
        ):
            screen = screen_pos(owner, pts[key])
            if screen is not None:
                out[handle_id] = screen
        return out

    def _qt_world_to_screen(self, ctx: Any):
        """Return a Qt-space world-to-screen projector for manual TEX picks."""

        owner = getattr(ctx, "owner", None)
        if owner is not None and callable(getattr(owner, "_world_to_display", None)):
            def _project(point: Vec3) -> tuple[float, float]:
                x, y_vtk, _depth = owner._world_to_display(tuple(float(v) for v in point))
                height = None
                try:
                    plotter = getattr(owner, "plotter", None)
                    raw_height = getattr(plotter, "height", None)
                    height = float(raw_height() if callable(raw_height) else raw_height)
                except Exception:
                    height = None
                y = float(height) - float(y_vtk) if height is not None and height > 0.0 else float(y_vtk)
                return (float(x), y)
            return _project
        viewport = getattr(ctx, "viewport", None)
        projector = getattr(viewport, "world_to_screen", None)
        return projector if callable(projector) else None

    def pick_handle(self, ctx: Any, qx: float, qy: float) -> tuple[str, str] | None:
        """Pick a Texture Projection handle in Qt screen space.

        The Creator API selection manager is the source of truth because it uses
        the same Qt-space projection as native drag/hover.  A small manual
        fallback remains for unit contexts created without selection actors, but
        it uses :func:`screen_pos`, which now returns Qt-style Y coordinates.
        """

        try:
            projector = self._qt_world_to_screen(ctx)
            selection = getattr(ctx, "selection", None)
            if callable(projector) and selection is not None:
                hit = selection.hit_test((float(qx), float(qy)), projector, owner_tool=self.tool.id, selectable_only=True)
                handle_id = None if hit is None else str(getattr(hit, "actor_id", "") or "")
                if handle_id in _TEXTURE_HANDLE_IDS:
                    try:
                        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                        audit.increment("texture_projection.handle_pick.native_hit")
                        audit.set_value("texture_projection.handle_pick.last_distance_px", f"{float(getattr(hit, 'distance_px', 0.0)):.3f}")
                    except Exception:
                        pass
                    return ("gizmo", self.axis_from_handle_id(handle_id))
        except Exception:
            pass

        handles = self.handle_screen_positions(ctx)
        if not handles:
            return None
        best: tuple[str, float] | None = None
        for handle_id, (sx, sy, _depth) in handles.items():
            dist = math.hypot(float(qx) - sx, float(qy) - sy)
            if best is None or dist < best[1]:
                best = (handle_id, dist)
        if best is not None:
            try:
                from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                audit.set_value("texture_projection.handle_pick.manual_best", f"{best[0]}:{best[1]:.3f}px")
            except Exception:
                pass
            if best[1] <= _TEXTURE_HANDLE_PICK_RADIUS_PX:
                try:
                    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                    audit.increment("texture_projection.handle_pick.manual_hit")
                except Exception:
                    pass
                return ("gizmo", self.axis_from_handle_id(best[0]))
        try:
            from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

            audit.increment("texture_projection.handle_pick.miss")
        except Exception:
            pass
        return None

    def hover_handle(self, ctx: Any, qx: float, qy: float) -> bool:
        picked = self.pick_handle(ctx, qx, qy)
        handle_id: str | None = None
        if picked is not None:
            _kind, axis = picked
            if axis == "texmove":
                handle_id = HANDLE_MOVE
            elif axis == "texscale":
                handle_id = HANDLE_SCALE
            elif axis == "texstretch_u":
                handle_id = HANDLE_STRETCH_U_POS
            elif axis == "texstretch_v":
                handle_id = HANDLE_STRETCH_V_POS
            elif axis == "texrot":
                handle_id = HANDLE_ROTATE
        current = getattr(ctx.selection.state, "hover_id", None)
        if current != handle_id:
            try:
                ctx.selection.set_hover(handle_id)
            except Exception:
                pass
            self.render(ctx, render=True)
            return True
        return handle_id is not None

    def _axis_from_kind_or_handle(self, kind: str | None) -> str:
        raw = str(kind or "texrot").lower()
        if raw in {"texmove", "texrot", "texscale", "texstretch_u", "texstretch_v"}:
            return raw
        if raw.startswith("texture_") or raw in {HANDLE_MOVE.lower(), HANDLE_ROTATE.lower(), HANDLE_SCALE.lower(), HANDLE_STRETCH_U_NEG.lower(), HANDLE_STRETCH_U_POS.lower(), HANDLE_STRETCH_V_NEG.lower(), HANDLE_STRETCH_V_POS.lower(), "move", "rotate", "scale", "stretch_u_neg", "stretch_u_pos", "stretch_v_neg", "stretch_v_pos"}:
            return self.axis_from_handle_id(self.handle_from_kind(raw))
        return "texrot"

    def start_drag(self, ctx: Any, qx: float, qy: float, *, kind: str = "texrot") -> bool:
        state = self.state(ctx)
        owner = getattr(ctx, "owner", None)
        if state is None or owner is None:
            return False
        axis = self._axis_from_kind_or_handle(kind)
        origin_screen = screen_pos(owner, state["origin"])
        if origin_screen is None:
            return False
        angle0 = math.atan2(float(qy) - origin_screen[1], float(qx) - origin_screen[0])
        dist0 = max(math.hypot(float(qx) - origin_screen[0], float(qy) - origin_screen[1]), 1.0)
        plane_hit0 = display_to_world_on_plane(owner, qx, qy, state["origin"], state["normal"])
        world0 = plane_hit0 or display_to_world_at_depth(owner, qx, qy, origin_screen[2])
        params = state["params"]
        self._drag = {
            "axis": axis,
            "target": state["target"],
            "start_q": (float(qx), float(qy)),
            "center_q": origin_screen,
            "last_angle": angle0,
            "start_dist": dist0,
            "start_rotation": float(params.rotation_deg),
            "current_rotation": float(params.rotation_deg),
            "start_scale": float(params.scale),
            "start_stretch_u": float(getattr(params, "stretch_u", 1.0)),
            "start_stretch_v": float(getattr(params, "stretch_v", 1.0)),
            "start_u_axis": state.get("u"),
            "start_v_axis": state.get("v"),
            "start_half_w": float(state.get("half_w", 1.0)),
            "start_half_h": float(state.get("half_h", 1.0)),
            "start_origin": state["origin"],
            "start_normal": state["normal"],
            "start_world": world0,
            "start_plane_hit": plane_hit0,
            "start_plane_vector": self._unit_plane_vector(state["origin"], plane_hit0),
            "start_plane_distance": self._plane_distance(state["origin"], plane_hit0),
            "seed_face_index": params.seed_face_index,
            "origin_active": bool(state.get("origin_active")),
            "dirty": False,
            "last_update": None,
            "last_render_time": 0.0,
            "move_constraint": self._move_constraint_for_state(state),
            "rotation_snap_candidates": self._rotation_snap_candidates_for_state(state),
            "scale_snap_candidates": self._scale_snap_candidates_for_state(state),
            "snap_label": None,
        }
        try:
            owner._texture_rotation_gizmo_pressed = True
            owner._texture_rotation_gizmo_drag_active = True
            owner._texture_rotation_gizmo_press_pos = (float(qx), float(qy))
        except Exception:
            pass
        try:
            ctx.selection.clear()
            handle_id = self.handle_from_kind(axis)
            ctx.selection.select(handle_id, replace=True)
            ctx.selection.begin_grab(handle_id, (float(qx), float(qy)), state["origin"])
        except Exception:
            pass
        self.render(ctx, render=True)
        return True

    def _compute_drag_update(self, ctx: Any, qx: float, qy: float) -> dict[str, Any] | None:
        drag = self._drag
        if not drag:
            return None
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return None
        axis = str(drag.get("axis", "texrot"))
        normal = tuple(float(v) for v in drag.get("start_normal", (0.0, 0.0, 1.0)))
        origin = tuple(float(v) for v in drag.get("start_origin", (0.0, 0.0, 0.0)))
        update: dict[str, Any] = {
            "target_index": int(drag.get("target", -1)),
        }
        seed_face = drag.get("seed_face_index")
        if seed_face is not None:
            update["seed_face_index"] = int(seed_face)
        if axis == "texrot":
            plane_hit = display_to_world_on_plane(owner, qx, qy, origin, normal)
            start_vec = drag.get("start_plane_vector")
            current_vec = self._unit_plane_vector(origin, plane_hit)
            angle_delta = None
            if start_vec is not None and current_vec is not None:
                angle_delta = signed_angle_between_on_plane(start_vec, current_vec, normal)
            if angle_delta is not None:
                # Geometric path: the cursor ray is intersected with the actual
                # texture plane, then measured in that local plane.  This keeps the
                # handle glued to the mouse even when the camera sees the texture as
                # a projected ellipse or from the opposite side.
                current = float(drag.get("start_rotation", 0.0)) + math.degrees(float(angle_delta))
            else:
                cx, cy, _depth = drag["center_q"]
                angle = math.atan2(float(qy) - float(cy), float(qx) - float(cx))
                previous = float(drag.get("last_angle", angle))
                delta = self._wrap_delta_radians(angle - previous)
                current = float(drag.get("current_rotation", drag.get("start_rotation", 0.0))) - math.degrees(delta)
                drag["last_angle"] = angle
            current, snap_label = self._snap_rotation(float(current), list(drag.get("rotation_snap_candidates", []) or []))
            drag["snap_label"] = f"rotation → {snap_label}" if snap_label else None
            current = _normalize_rotation_deg(current)
            drag["current_rotation"] = current
            update["rotation_deg"] = current
        elif axis == "texscale":
            plane_hit = display_to_world_on_plane(owner, qx, qy, origin, normal)
            start_plane_distance = drag.get("start_plane_distance")
            current_plane_distance = self._plane_distance(origin, plane_hit)
            if start_plane_distance is not None and current_plane_distance is not None:
                ratio = float(current_plane_distance) / max(float(start_plane_distance), 1e-8)
            else:
                cx, cy, _depth = drag["center_q"]
                dist = max(math.hypot(float(qx) - float(cx), float(qy) - float(cy)), 1.0)
                ratio = dist / max(float(drag["start_dist"]), 1.0)
            raw_scale = max(0.001, min(100000.0, float(drag["start_scale"]) * float(ratio)))
            snapped_scale, snap_label = self._snap_scale(raw_scale, list(drag.get("scale_snap_candidates", []) or []))
            drag["snap_label"] = f"scale → {snap_label}" if snap_label else None
            update["scale"] = max(0.001, min(100000.0, float(snapped_scale)))
        elif axis in {"texstretch_u", "texstretch_v"}:
            plane_hit = display_to_world_on_plane(owner, qx, qy, origin, normal)
            if plane_hit is not None:
                rel = vsub(tuple(float(v) for v in plane_hit), origin)
                if axis == "texstretch_u":
                    u_axis = tuple(float(v) for v in (drag.get("start_u_axis") or (1.0, 0.0, 0.0)))
                    start_half = max(float(drag.get("start_half_w", 1.0)), 1.0e-8)
                    ratio = max(abs(vdot(rel, u_axis)) / start_half, 0.001)
                    update["stretch_u"] = max(0.001, min(100000.0, float(drag.get("start_stretch_u", 1.0)) * ratio))
                    drag["snap_label"] = "stretch width"
                else:
                    v_axis = tuple(float(v) for v in (drag.get("start_v_axis") or (0.0, 1.0, 0.0)))
                    start_half = max(float(drag.get("start_half_h", 1.0)), 1.0e-8)
                    ratio = max(abs(vdot(rel, v_axis)) / start_half, 0.001)
                    update["stretch_v"] = max(0.001, min(100000.0, float(drag.get("start_stretch_v", 1.0)) * ratio))
                    drag["snap_label"] = "stretch height"
            else:
                cx, cy, _depth = drag["center_q"]
                dist = max(math.hypot(float(qx) - float(cx), float(qy) - float(cy)), 1.0)
                ratio = dist / max(float(drag["start_dist"]), 1.0)
                if axis == "texstretch_u":
                    update["stretch_u"] = max(0.001, min(100000.0, float(drag.get("start_stretch_u", 1.0)) * ratio))
                else:
                    update["stretch_v"] = max(0.001, min(100000.0, float(drag.get("start_stretch_v", 1.0)) * ratio))
        else:
            _cx, _cy, depth = drag["center_q"]
            current_world = display_to_world_on_plane(owner, qx, qy, origin, normal)
            start_world = drag.get("start_plane_hit")
            if current_world is None:
                current_world = display_to_world_at_depth(owner, qx, qy, depth)
                start_world = drag.get("start_world")
            if current_world is not None and start_world is not None:
                delta = vsub(current_world, start_world)
                # Keep the handle on the picked surface plane: remove normal drift.
                delta = vsub(delta, vscale(normal, vdot(delta, normal)))
                origin = vadd(origin, delta)
                clamped_origin = self._clamp_origin_to_constraint(origin, drag.get("move_constraint"))
                if clamped_origin != origin:
                    drag["snap_label"] = "center clamped to face"
                else:
                    drag["snap_label"] = None
                origin = clamped_origin
                update["projection_origin"] = origin
                update["projection_origin_active"] = True
                drag["origin_active"] = True
        if axis in {"texrot", "texscale", "texstretch_u", "texstretch_v"} and bool(drag.get("origin_active", False)):
            update["projection_origin"] = origin
            update["projection_origin_active"] = True
        update["projection_normal"] = normal
        return update

    def _drag_render_allowed(self, *, min_interval: float = 1.0 / 60.0) -> bool:
        """Coalesce very dense mouse-move bursts to one visible frame budget."""
        drag = self._drag
        if drag is None:
            return True
        try:
            now = time.monotonic()
            last = float(drag.get("last_render_time", 0.0) or 0.0)
            if now - last < float(min_interval):
                return False
            drag["last_render_time"] = now
            return True
        except Exception:
            return True

    def _set_actor_uvs_fast(self, ctx: Any, idx: int, mesh: Any) -> bool:
        """Mutate one existing VTK/PyVista actor's texture coordinates in place.

        PyVista exposes texture coordinates as active texture coordinates on the
        dataset.  Replacing only this array is cheap compared with rebuilding the
        preview meshes and recreating actors while the mouse is moving.
        """
        try:
            owner = getattr(ctx, "owner", None)
            if owner is None:
                return False
            uvs = getattr(mesh, "uvs", None)
            if uvs is None:
                return False
            # Prefer the historical window helper when present: it already knows
            # how to find the scene actor maps and keep texture visibility stable.
            helper = getattr(owner, "_texture_projection_set_actor_uvs_fast", None)
            if callable(helper):
                try:
                    if bool(helper(int(idx), mesh)):
                        return True
                except Exception:
                    pass
            actor = getattr(owner, "actors_by_index", {}).get(int(idx)) if isinstance(getattr(owner, "actors_by_index", None), dict) else None
            mapper = actor.GetMapper() if actor is not None and hasattr(actor, "GetMapper") else None
            dataset = mapper.GetInput() if mapper is not None and hasattr(mapper, "GetInput") else None
            if dataset is None and isinstance(getattr(owner, "polydata_by_index", None), dict):
                dataset = getattr(owner, "polydata_by_index", {}).get(int(idx))
            if dataset is None:
                return False
            n_points = int(dataset.GetNumberOfPoints()) if hasattr(dataset, "GetNumberOfPoints") else len(getattr(mesh, "vertices", []))
            if len(uvs) != n_points:
                return False
            try:
                import numpy as np

                if hasattr(dataset, "active_texture_coordinates"):
                    dataset.active_texture_coordinates = np.asarray(uvs, dtype=float)
            except Exception:
                pass
            try:
                from vtkmodules.vtkCommonCore import vtkFloatArray

                tcoords = vtkFloatArray()
                tcoords.SetName("Texture Coordinates")
                tcoords.SetNumberOfComponents(2)
                tcoords.SetNumberOfTuples(int(n_points))
                for i, (u, v) in enumerate(uvs):
                    tcoords.SetTuple2(int(i), float(u), float(v))
                dataset.GetPointData().SetTCoords(tcoords)
            except Exception:
                return False
            try:
                dataset.Modified()
            except Exception:
                pass
            try:
                if mapper is not None:
                    mapper.Modified()
            except Exception:
                pass
            try:
                from laserprog_studio.rendering.textures import actor_has_texture, apply_texture_to_actor, configure_actor_for_texture_visibility

                if actor is not None:
                    if actor_has_texture(actor):
                        configure_actor_for_texture_visibility(actor)
                    else:
                        apply_texture_to_actor(owner, actor, mesh, reason="creator_tex_live_drag")
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _projection_source_index(self, update: dict[str, Any], fallback: int) -> int:
        try:
            return int(update.get("target_index", fallback))
        except Exception:
            return int(fallback)

    def _find_live_texture_mesh(self, ctx: Any, state: dict[str, Any], update: dict[str, Any]) -> tuple[int, Any] | None:
        """Return the preview mesh/actor that actually owns the edited texture."""
        try:
            from laserprog_studio.geometry_ops.texture_projection_decal import _is_texture_decal, _decal_source_name

            preview_meshes = list(ctx.document.meshes(include_preview=True))
            if not preview_meshes:
                return None
            params = state["params"]
            target = self._projection_source_index(update, int(state.get("target", -1)))
            # Attach-to-mesh edits the real source mesh. The unchecked mode edits
            # the separate lifted decal patch.
            if getattr(params, "seed_face_index", None) is None or bool(getattr(params, "attach_to_mesh", False)):
                if 0 <= target < len(preview_meshes):
                    return target, preview_meshes[target]
                return None
            base_meshes = list(ctx.document.meshes(include_preview=False))
            source_name = ""
            if 0 <= target < len(base_meshes):
                source_name = str(getattr(base_meshes[target], "name", "") or "")
            seed = getattr(params, "seed_face_index", None)
            best: tuple[int, Any] | None = None
            for i, mesh in enumerate(preview_meshes):
                if not _is_texture_decal(mesh):
                    continue
                if source_name and str(_decal_source_name(mesh) or "") != source_name:
                    continue
                if seed is not None:
                    try:
                        if int(getattr(mesh, "texture_decal_source_face")) == int(seed):
                            return int(i), mesh
                    except Exception:
                        pass
                if best is None:
                    best = (int(i), mesh)
            return best
        except Exception:
            return None

    def _update_live_texture_uvs(self, ctx: Any, state: dict[str, Any], update: dict[str, Any], *, render: bool = False) -> bool:
        """Update bitmap placement during drag without rebuilding preview meshes."""
        try:
            target = self._find_live_texture_mesh(ctx, state, update)
            if target is None:
                return False
            idx, mesh = target
            params = state["params"]
            scale_value = float(update.get("scale", getattr(params, "scale", 1.0)))
            stretch_u_value = float(update.get("stretch_u", getattr(params, "stretch_u", 1.0)))
            stretch_v_value = float(update.get("stretch_v", getattr(params, "stretch_v", 1.0)))
            rotation_value = _normalize_rotation_deg(float(update.get("rotation_deg", getattr(params, "rotation_deg", 0.0))))
            offset_u_value = float(update.get("offset_u", getattr(params, "offset_u", 0.0)))
            offset_v_value = float(update.get("offset_v", getattr(params, "offset_v", 0.0)))
            origin = update.get("projection_origin", state.get("origin"))
            if origin is not None:
                origin = tuple(float(v) for v in origin)
            from laserprog_studio.geometry_ops.texture_projection_decal import _is_texture_decal

            if _is_texture_decal(mesh):
                from laserprog_studio.geometry_ops.texture_projection_vector import _dot, _sub, _uv_from_plane_coords

                origin = origin or tuple(float(v) for v in getattr(mesh, "texture_decal_origin"))
                u_axis = tuple(float(v) for v in getattr(mesh, "texture_decal_u_axis"))
                v_axis = tuple(float(v) for v in getattr(mesh, "texture_decal_v_axis"))
                tile_w = float(getattr(mesh, "texture_decal_tile_width", 1.0) or 1.0)
                tile_h = float(getattr(mesh, "texture_decal_tile_height", 1.0) or 1.0)
                uvs: list[tuple[float, float]] = []
                for point in list(getattr(mesh, "vertices", []) or []):
                    p = tuple(float(v) for v in point)
                    rel = _sub(p, origin)
                    uvs.append(
                        _uv_from_plane_coords(
                            _dot(rel, u_axis),
                            _dot(rel, v_axis),
                            tile_w=tile_w,
                            tile_h=tile_h,
                            scale=scale_value,
                            rotation_deg=rotation_value,
                            offset_u=offset_u_value,
                            offset_v=offset_v_value,
                            stretch_u=stretch_u_value,
                            stretch_v=stretch_v_value,
                        )
                    )
                mesh.uvs = uvs
                try:
                    setattr(mesh, "texture_decal_origin", origin)
                except Exception:
                    pass
            else:
                from laserprog_studio.geometry_ops.texture_projection_faces import _store_texture_edit_frame
                from laserprog_studio.geometry_ops.texture_projection_operations import compute_anchor_attached_coverage_uvs
                from laserprog_studio.geometry_ops.texture_projection_uv import compute_projected_uvs

                projection_origin = origin if origin is not None else getattr(params, "projection_origin", None)
                masked_uvs = None
                if getattr(params, "seed_face_index", None) is not None and bool(getattr(params, "attach_to_mesh", False)):
                    masked_uvs = compute_anchor_attached_coverage_uvs(
                        mesh,
                        params,
                        projection_origin=projection_origin,
                        scale=scale_value,
                        stretch_u=stretch_u_value,
                        stretch_v=stretch_v_value,
                        rotation_deg=rotation_value,
                        offset_u=offset_u_value,
                        offset_v=offset_v_value,
                    )
                if masked_uvs is not None:
                    mesh.uvs = masked_uvs
                else:
                    mesh.uvs = compute_projected_uvs(
                        mesh,
                        projection_mode=params.projection_mode,
                        scale=scale_value,
                        stretch_u=stretch_u_value,
                        stretch_v=stretch_v_value,
                        rotation_deg=rotation_value,
                        offset_u=offset_u_value,
                        offset_v=offset_v_value,
                        preserve_aspect=bool(params.preserve_aspect),
                        image_width=params.image_width,
                        image_height=params.image_height,
                        seed_face_index=params.seed_face_index,
                        projection_origin=projection_origin,
                        projection_normal=params.projection_normal,
                        coverage_angle_deg=float(params.coverage_angle_deg),
                    )
                try:
                    _store_texture_edit_frame(mesh, params)
                except Exception:
                    pass
            try:
                projections = list(getattr(mesh, "texture_projections", []) or [])
                if projections:
                    proj = projections[0]
                    for name, value in (
                        ("scale", scale_value),
                        ("stretch_u", stretch_u_value),
                        ("stretch_v", stretch_v_value),
                        ("rotation_deg", rotation_value),
                        ("offset_u", offset_u_value),
                        ("offset_v", offset_v_value),
                        ("repeat", bool(params.repeat)),
                        ("coverage_angle_deg", float(params.coverage_angle_deg)),
                        ("seed_face_index", params.seed_face_index),
                        ("projection_mode", params.projection_mode),
                    ):
                        try:
                            setattr(proj, name, value)
                        except Exception:
                            pass
                    mesh.texture_projections = projections
            except Exception:
                pass
            ok = self._set_actor_uvs_fast(ctx, int(idx), mesh)
            if render and ok:
                owner = getattr(ctx, "owner", None)
                plotter = getattr(owner, "plotter", None) if owner is not None else None
                render_fn = getattr(plotter, "render", None)
                if callable(render_fn):
                    try:
                        render_fn()
                    except Exception:
                        pass
            return bool(ok or getattr(ctx.document, "has_preview", False))
        except Exception:
            return False

    def _apply_fast_drag_update(self, ctx: Any, update: dict[str, Any], *, render: bool = True) -> dict[str, Vec3]:
        try:
            ctx.inspector.update_values(update, notify=False)
        except Exception:
            pass
        state = self.state(ctx)
        if state is None:
            return {}
        pts = self.points(state)
        positions = {
            HANDLE_MOVE: pts["move"],
            HANDLE_ROTATE: pts["rotate"],
            HANDLE_SCALE: pts["scale"],
            HANDLE_STRETCH_U_NEG: pts["stretch_u_neg"],
            HANDLE_STRETCH_U_POS: pts["stretch_u_pos"],
            HANDLE_STRETCH_V_NEG: pts["stretch_v_neg"],
            HANDLE_STRETCH_V_POS: pts["stretch_v_pos"],
        }
        registry = ctx.projected_drawing.for_tool(self.tool.id)
        with registry.batch():
            try:
                registry.update_positions(positions, render=False)
            except Exception:
                # If a test calls the drag path before the declarations exist,
                # rebuild the projected tool UI once instead of falling back to
                # the removed preview/gizmo API.
                self.render_declarations(ctx, clear_previews=True, sync_overlay=False, rebuild_snap=False)
                try:
                    registry.update_positions(positions, render=False)
                except Exception:
                    pass
            self._show_projector_preview(ctx, state, mark_dirty=True, render=False)
        self._update_live_texture_uvs(ctx, state, update, render=False)
        try:
            current = tuple(getattr(ctx.selection.state, "dirty_visual_handle_ids", ()) or ())
            ctx.selection.state.dirty_visual_handle_ids = tuple(dict.fromkeys((*current, *positions.keys())))
        except Exception:
            pass
        render_now = bool(render and self._drag_render_allowed())
        if render_now:
            owner = getattr(ctx, "owner", None)
            if owner is not None:
                try:
                    ctx.projected_drawing.for_tool(self.tool.id).render(render=True)
                except Exception:
                    try:
                        ctx.request_light_render()
                    except Exception:
                        pass
            else:
                try:
                    ctx.request_light_render()
                except Exception:
                    pass
        drag = self._drag
        if drag is not None:
            drag["dirty"] = True
            drag["last_update"] = dict(update)
        return positions

    def update_drag(self, ctx: Any, qx: float, qy: float, *, source: str = "direct") -> bool:  # noqa: ARG002
        if not self._drag:
            return False
        update = self._compute_drag_update(ctx, qx, qy)
        if not update:
            return False
        self._apply_fast_drag_update(ctx, update, render=True)
        return True

    def resolve_drag_positions(self, ctx: Any, event: Any) -> dict[str, Any] | None:
        """Native Creator API drag resolver for TEX handles.

        It updates the projector frame in place and returns only the grabbed
        handle replacement to the native runtime. The expensive mesh projection
        is committed once in :meth:`finish_drag`.
        """

        screen_pos = getattr(event, "screen_pos", None)
        if screen_pos is None:
            return None
        grabbed = tuple(str(value) for value in getattr(ctx.selection.state, "grabbed_ids", ()) or ())
        texture_handles = tuple(handle_id for handle_id in grabbed if handle_id in {HANDLE_MOVE, HANDLE_ROTATE, HANDLE_SCALE, HANDLE_STRETCH_U_NEG, HANDLE_STRETCH_U_POS, HANDLE_STRETCH_V_NEG, HANDLE_STRETCH_V_POS})
        if not texture_handles:
            return None
        handle_id = texture_handles[-1]
        qx, qy = float(screen_pos[0]), float(screen_pos[1])
        if not self._drag:
            if not self.start_drag(ctx, qx, qy, kind=self.axis_from_handle_id(handle_id)):
                return None
        update = self._compute_drag_update(ctx, qx, qy)
        if not update:
            return None
        positions = self._apply_fast_drag_update(ctx, update, render=False)
        actor = ctx.selection.actor(handle_id)
        if actor is None or handle_id not in positions:
            return None
        return {handle_id: replace(actor, points=(positions[handle_id],))}

    def reset_for_new_anchor(self, ctx: Any) -> None:
        """Clear transient projector UI before placing/reloading a face anchor."""
        self._drag = None
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            for name, value in (
                ("_texture_rotation_gizmo_pressed", False),
                ("_texture_rotation_gizmo_drag_active", False),
                ("_texture_rotation_gizmo_press_pos", None),
            ):
                try:
                    setattr(owner, name, value)
                except Exception:
                    pass
        try:
            ctx.selection.end_grab()
        except Exception:
            pass
        try:
            ctx.selection.clear()
        except Exception:
            pass
        try:
            ctx.projected_drawing.for_tool(self.tool.id).clear(render=False)
        except Exception:
            pass
        try:
            ctx.overlay.close_tool_windows(self.tool.id, include_persistent=False)
        except Exception:
            pass

    def on_native_interaction_result(self, ctx: Any, event: Any, result: Any) -> None:
        action = str(getattr(result, "action", "") or "")
        screen_pos = getattr(event, "screen_pos", None)
        if action in {"grab", "select"} and screen_pos is not None:
            hit = getattr(result, "hit", None)
            handle_id = str(getattr(hit, "actor_id", "") or "")
            if handle_id in _TEXTURE_HANDLE_IDS:
                self.start_drag(ctx, float(screen_pos[0]), float(screen_pos[1]), kind=self.axis_from_handle_id(handle_id))
        elif action == "release":
            self.finish_drag(ctx)

    def _commit_drag_preview(self, ctx: Any, drag: dict[str, Any]) -> None:
        update = dict(drag.get("last_update") or {})
        target = update.get("target_index", drag.get("target", -1))
        try:
            target_i = int(target)
        except Exception:
            return
        seed = update.get("seed_face_index", drag.get("seed_face_index"))
        origin = update.get("projection_origin")
        normal = update.get("projection_normal", drag.get("start_normal"))
        # The inspector already owns rotation/scale/origin-active values.  The
        # preview operation below is the single heavy operation after the drag.
        try:
            self.tool.preview_index(
                ctx,
                target_i,
                seed_face_index=None if seed is None else int(seed),
                projection_origin=origin,
                projection_normal=normal,
            )
        except Exception:
            self.render(ctx, render=True)

    def finish_drag(self, ctx: Any) -> bool:
        if not self._drag:
            return False
        drag = dict(self._drag)
        self._drag = None
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            for name, value in (
                ("_texture_rotation_gizmo_pressed", False),
                ("_texture_rotation_gizmo_drag_active", False),
                ("_texture_rotation_gizmo_press_pos", None),
            ):
                try:
                    setattr(owner, name, value)
                except Exception:
                    pass
        try:
            ctx.selection.end_grab()
            ctx.selection.clear()
        except Exception:
            pass
        if bool(drag.get("dirty", False)):
            self._commit_drag_preview(ctx, drag)
        else:
            self.render(ctx, render=True)
        return True


__all__ = ["TextureProjectorRuntime"]
