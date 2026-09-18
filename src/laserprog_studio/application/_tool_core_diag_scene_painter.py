# -*- coding: utf-8 -*-
"""Persistent PyVista renderer for Tool Core diagnostic and Creator UI scenes."""
from __future__ import annotations

from math import cos, pi, sin, sqrt
from typing import Any
import time

from ..mesh_ops import parse_hex_color, workmesh_to_polydata
from ..studio_log import log_exception
from ..tool_core.gizmos import (
    get_point_style,
    plotter_axis_locked_billboard_basis,
    plotter_pixel_radius_to_world,
    visual_state_for_flags,
)
from ..tool_core.preview import PreviewKind, TextLabel
from ._tool_core_diag_scene_state import _ACTOR_PREFIX, _DiagActorState, _state

from ._preview_face_triangulation import _triangulate_preview_face_points


def _diag(stage: str, owner: Any = None, ctx: Any = None, owner_tool: str = "", **payload: Any) -> None:
    try:
        from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

        record_projected_overlay_event(f"diag_scene.{stage}", owner=owner, ctx=ctx, owner_tool=str(owner_tool or ""), **payload)
    except Exception:
        pass



class ToolCoreDiagScenePainter:
    """Draws tool-core diagnostic handles/previews in the live PyVista viewport.

    The key rule is no clear/rebuild during interaction. Handles, guide rings,
    crosses and line batches are persistent actors. Hover/grab updates only
    mutate existing PolyData and actor visibility, so the user never sees the
    whole overlay disappear for a frame.
    """

    def __init__(
        self,
        owner: Any,
        *,
        owner_tool: str = "tool_core_diag",
        actor_prefix: str = _ACTOR_PREFIX,
        state_attr: str = "_tool_core_diag_scene_state",
        actor_names_attr: str = "_tool_core_diag_actor_names",
        guide_kind_prefixes: tuple[str, ...] = ("demo_grab", "style_grab", "api_lab_"),
        draw_guides_for_all: bool = False,
    ) -> None:
        self.owner = owner
        self.owner_tool = str(owner_tool)
        self.actor_prefix = str(actor_prefix)
        self.state_attr = str(state_attr)
        self.actor_names_attr = str(actor_names_attr)
        self.guide_kind_prefixes = tuple(str(prefix) for prefix in guide_kind_prefixes)
        self.draw_guides_for_all = bool(draw_guides_for_all)

    def render_context(self, ctx: Any, *, render: bool = True) -> dict[str, int | str]:
        total_started = time.perf_counter()
        profiler = getattr(ctx, "profiler", None)
        perf_owner = "".join(ch if ch.isalnum() else "_" for ch in self.owner_tool).strip("_") or "unknown"
        perf_prefix = f"creator_ui.{perf_owner}"
        plotter = getattr(self.owner, "plotter", None)
        _diag("render_context.start", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, render=bool(render), has_plotter=plotter is not None, actor_prefix=self.actor_prefix)
        if plotter is None:
            _diag("render_context.no_plotter", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool)
            return {"status": "no_plotter"}
        try:
            import numpy as np
            import pyvista as pv
        except Exception as exc:  # pragma: no cover - optional GUI dependency
            _diag("render_context.import_exception", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, error_type=type(exc).__name__, message=str(exc)[:300])
            log_exception("tool_core_diag_scene_import")
            return {"status": "missing_pyvista"}

        state = _state(self.owner, self.state_attr)
        actor_names_before = len(state.actor_names)
        collect_started = time.perf_counter()
        handles = list(ctx.gizmos.handles(owner_tool=self.owner_tool))
        previews = list(ctx.preview.items(owner_tool=self.owner_tool))
        collect_ms = (time.perf_counter() - collect_started) * 1000.0
        _diag("render_context.collected", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, handles=len(handles), previews=len(previews), state_actor_names=len(state.actor_names), actor_names_before=actor_names_before)
        build_started = time.perf_counter()

        used_names: set[str] = set()
        next_handle_refs: dict[str, list[tuple[str, int, int]]] = {}
        next_handle_positions: dict[str, tuple[float, float, float]] = {}
        next_preview_refs: dict[str, list[tuple[str, int, int]]] = {}
        handle_groups: dict[tuple[str, str, int, tuple[float, float, float, float]], list[tuple[str, tuple[float, float, float]]]] = {}
        guide_groups: dict[tuple[str, str], tuple[list[tuple[float, float, float]], list[int], Any, float]] = {}
        guide_ref_ranges: dict[tuple[str, str], dict[str, list[tuple[int, int]]]] = {}
        # Some OpenGL/VTK drivers clamp GL point size or ignore updates for
        # point sprites. Minimal dots therefore use tiny persistent filled
        # geometry discs, not raw point primitives, while still behaving like
        # one simple point in the tool API.
        minimal_dot_groups: dict[
            tuple[str, str, int, tuple[float, float, float, float]],
            tuple[list[tuple[float, float, float]], list[int], tuple[float, float, float, float]],
        ] = {}
        minimal_dot_ref_ranges: dict[tuple[str, str, int, tuple[float, float, float, float]], dict[str, list[tuple[int, int]]]] = {}

        def add_polyline(
            store_points: list[tuple[float, float, float]],
            store_cells: list[int],
            points: list[tuple[float, float, float]] | tuple[tuple[float, float, float], ...],
            *,
            closed: bool = False,
        ) -> tuple[int, int] | None:
            if len(points) < 2:
                return None
            start = len(store_points)
            pts = [tuple(float(v) for v in point) for point in points]
            if closed and pts[0] != pts[-1]:
                pts.append(pts[0])
            store_points.extend(pts)
            store_cells.extend([len(pts), *range(start, start + len(pts))])
            return start, len(pts)

        def guide_store(kind: str, style_id: str, color: Any, line_width: float) -> tuple[list[tuple[float, float, float]], list[int]]:
            # Guides are split by style/color once, then kept as persistent actors.
            # This avoids the old white-on-white issue without returning to an
            # actor-per-handle model.
            key = (kind, str(style_id))
            if key not in guide_groups:
                guide_groups[key] = ([], [], color, float(line_width))
            return guide_groups[key][0], guide_groups[key][1]

        axis_basis = plotter_axis_locked_billboard_basis(plotter)

        def add_handle_guides(handle: Any) -> None:
            kind = str(getattr(handle, "kind", ""))
            if not self.draw_guides_for_all and not any(kind.startswith(prefix) for prefix in self.guide_kind_prefixes):
                return
            style_id = str(getattr(handle, "style_id", "solid"))
            style = get_point_style(style_id)
            guide_shape = style.guide_shape
            center = tuple(float(v) for v in handle.position)
            if getattr(style, "geometry_dot", False):
                state_name = visual_state_for_flags(
                    selectable=bool(handle.selectable),
                    hover=bool(handle.hover),
                    grabbed=bool(getattr(handle, "grabbed", False)),
                    selected=bool(handle.selected),
                    visible=bool(handle.visible),
                ).value
                rgba = tuple(float(v) for v in handle.color)
                key = (style_id, state_name, int(handle.radius_px), rgba)
                if key not in minimal_dot_groups:
                    minimal_dot_groups[key] = ([], [], rgba)
                dot_points, dot_faces, _rgba = minimal_dot_groups[key]
                # Radius is in screen pixels converted to world units on the
                # nearest cardinal view plane.  This gives a real controllable
                # dot even when GL point-size support is limited.
                # The diagnostic sliders drive handle.radius_px directly.  Do
                # not clamp this back to a large value here, otherwise the
                # minimal dot cannot be tuned precisely.
                dot_scale = plotter_pixel_radius_to_world(plotter, center, max(1.5, float(handle.radius_px)))
                dot_radius = max(0.015, float(dot_scale.world_radius))
                sides = 18
                start = len(dot_points)
                dot_points.append(axis_basis.point(center, 0.0, 0.0, 0.08))
                for idx in range(sides):
                    angle = 2.0 * pi * idx / float(sides)
                    dot_points.append(axis_basis.point(center, cos(angle) * dot_radius, sin(angle) * dot_radius, 0.08))
                dot_faces.extend([sides + 1, start, *range(start + 1, start + 1 + sides)])
                minimal_dot_ref_ranges.setdefault(key, {}).setdefault(str(handle.id), []).append((start, sides + 1))
                return
            if guide_shape == "none":
                return
            scale = plotter_pixel_radius_to_world(plotter, center, max(6.0, float(handle.radius_px) * 0.68))
            radius = max(0.08, float(scale.world_radius))
            if getattr(handle, "grabbed", False):
                radius *= 1.15
            elif getattr(handle, "hover", False):
                radius *= 1.08

            def pnt(u_offset: float, v_offset: float, n_offset: float = 0.05) -> tuple[float, float, float]:
                return axis_basis.point(center, float(u_offset), float(v_offset), float(n_offset))

            def add_polyline_uv(
                store_points: list[tuple[float, float, float]],
                store_cells: list[int],
                uv_points: list[tuple[float, float]] | tuple[tuple[float, float], ...],
                *,
                closed: bool = False,
                n_offset: float = 0.05,
            ) -> tuple[int, int] | None:
                return add_polyline(store_points, store_cells, [pnt(u, v, n_offset) for u, v in uv_points], closed=closed)

            def arrowhead(
                store_points: list[tuple[float, float, float]],
                store_cells: list[int],
                tip_uv: tuple[float, float],
                direction: tuple[float, float],
                *,
                size: float,
            ) -> None:
                dx, dy = direction
                mag = max((dx * dx + dy * dy) ** 0.5, 1.0e-9)
                ux, uy = dx / mag, dy / mag
                px, py = -uy, ux
                back = (tip_uv[0] - ux * size, tip_uv[1] - uy * size)
                left = (back[0] + px * size * 0.52, back[1] + py * size * 0.52)
                right = (back[0] - px * size * 0.52, back[1] - py * size * 0.52)
                add_polyline_uv(store_points, store_cells, [left, tip_uv, right])

            def record_guide(kind_name: str, range_value: tuple[int, int] | None) -> None:
                if range_value is not None:
                    guide_ref_ranges.setdefault((kind_name, style_id), {}).setdefault(str(handle.id), []).append(range_value)

            if guide_shape == "ring":
                circle = [(cos(2.0 * pi * i / 32.0) * radius, sin(2.0 * pi * i / 32.0) * radius) for i in range(33)]
                pts, cells = guide_store("ring", style_id, style.ring_color[:3], 2.4)
                record_guide("ring", add_polyline_uv(pts, cells, circle, closed=True))
            elif guide_shape == "diamond":
                diamond = [(0.0, radius), (radius, 0.0), (0.0, -radius), (-radius, 0.0)]
                pts, cells = guide_store("ring", style_id, style.ring_color[:3], 2.4)
                record_guide("ring", add_polyline_uv(pts, cells, diamond, closed=True))
            elif guide_shape == "square":
                side = radius / sqrt(2.0)
                square = [(-side, -side), (side, -side), (side, side), (-side, side)]
                pts, cells = guide_store("ring", style_id, style.ring_color[:3], 2.4)
                record_guide("ring", add_polyline_uv(pts, cells, square, closed=True))
            elif guide_shape == "minimal":
                # Minimal is a plain persistent point/dot only.  No square, no
                # ring and no crosshair are drawn here; state feedback comes
                # from the core point actor color/size updated in place.
                return
            elif guide_shape == "arrow":
                pts, cells = guide_store("arrow", style_id, style.cross_color[:3], 3.0)
                tip = (radius * 1.65, 0.0)
                shoulder = (radius * 0.70, 0.0)
                tail = (-radius * 1.00, 0.0)
                record_guide("arrow", add_polyline_uv(pts, cells, [tail, shoulder, tip]))
                before = len(pts)
                arrowhead(pts, cells, tip, (1.0, 0.0), size=radius * 0.54)
                record_guide("arrow", (before, len(pts) - before) if len(pts) > before else None)
            elif guide_shape == "translate_axis":
                pts, cells = guide_store("translate_axis", style_id, style.cross_color[:3], 3.5)
                tip = (radius * 1.95, 0.0)
                tail = (-radius * 1.15, 0.0)
                record_guide("translate_axis", add_polyline_uv(pts, cells, [tail, tip]))
                before = len(pts)
                arrowhead(pts, cells, tip, (1.0, 0.0), size=radius * 0.68)
                record_guide("translate_axis", (before, len(pts) - before) if len(pts) > before else None)
                # Small base tick, like a transform-axis grab handle, makes the
                # direction readable without adding a heavy mesh/cone actor.
                record_guide("translate_axis", add_polyline_uv(pts, cells, [(tail[0], -radius * 0.36), (tail[0], radius * 0.36)]))
            elif guide_shape == "axis":
                pts, cells = guide_store("axis", style_id, style.cross_color[:3], 2.7)
                x_tip = (radius * 1.35, 0.0)
                y_tip = (0.0, radius * 1.35)
                record_guide("axis", add_polyline_uv(pts, cells, [(-radius, 0.0), x_tip]))
                record_guide("axis", add_polyline_uv(pts, cells, [(0.0, -radius), y_tip]))
                before = len(pts)
                arrowhead(pts, cells, x_tip, (1.0, 0.0), size=radius * 0.42)
                arrowhead(pts, cells, y_tip, (0.0, 1.0), size=radius * 0.42)
                record_guide("axis", (before, len(pts) - before) if len(pts) > before else None)
            elif guide_shape == "chevron":
                pts, cells = guide_store("chevron", style_id, style.cross_color[:3], 2.8)
                record_guide("chevron", add_polyline_uv(pts, cells, [(-radius * 1.0, -radius * 0.65), (0.0, 0.0), (-radius * 1.0, radius * 0.65)]))
                record_guide("chevron", add_polyline_uv(pts, cells, [(radius * 0.15, -radius * 0.65), (radius * 1.15, 0.0), (radius * 0.15, radius * 0.65)]))
            elif guide_shape == "triad":
                pts, cells = guide_store("triad", style_id, style.cross_color[:3], 2.7)
                for angle in (0.0, (2.0 * pi) / 3.0, (4.0 * pi) / 3.0):
                    dx, dy = cos(angle), sin(angle)
                    tip = (dx * radius * 1.35, dy * radius * 1.35)
                    record_guide("triad", add_polyline_uv(pts, cells, [(0.0, 0.0), tip]))
                    before = len(pts)
                    arrowhead(pts, cells, tip, (dx, dy), size=radius * 0.38)
                    record_guide("triad", (before, len(pts) - before) if len(pts) > before else None)

            if guide_shape == "target":
                arm = radius * 0.70
                pts, cells = guide_store("cross", style_id, style.cross_color[:3], 2.4)
                record_guide("cross", add_polyline_uv(pts, cells, [(-arm, 0.0), (arm, 0.0)]))
                record_guide("cross", add_polyline_uv(pts, cells, [(0.0, -arm), (0.0, arm)]))

        for handle in handles:
            if not handle.visible:
                continue
            next_handle_positions[str(handle.id)] = tuple(float(v) for v in handle.position)
            state_name = visual_state_for_flags(
                selectable=bool(handle.selectable),
                hover=bool(handle.hover),
                grabbed=bool(getattr(handle, "grabbed", False)),
                selected=bool(handle.selected),
                visible=bool(handle.visible),
            ).value
            style_id = str(getattr(handle, "style_id", "solid"))
            style = get_point_style(style_id)
            rgba = tuple(float(v) for v in handle.color)
            if getattr(style, "draw_core", True) and not getattr(style, "geometry_dot", False):
                key = (style_id, state_name, int(handle.radius_px), rgba)
                handle_groups.setdefault(key, []).append((str(handle.id), tuple(float(v) for v in handle.position)))
                next_handle_positions[str(handle.id)] = tuple(float(v) for v in handle.position)
            add_handle_guides(handle)

        fallback_colors = {
            "default": "deepskyblue",
            "fixed": "lightsteelblue",
            "grabbable": "dodgerblue",
            "hover": "cyan",
            "grabbed": "orange",
            "selected": "gold",
            "snap": "greenyellow",
            "stress": "dodgerblue",
        }
        def color_key(value: Any) -> str:
            try:
                values = tuple(float(v) for v in value)
            except Exception:
                return str(value).replace("#", "hex").replace(" ", "_").replace(",", "_").replace("(", "").replace(")", "").replace(":", "_")
            return "rgba" + "_".join(str(int(max(0.0, min(1.0, component)) * 255.0 + 0.5)) for component in values[:4])

        for (style_id, state_name, size, rgba), entries in handle_groups.items():
            points = [point for _handle_id, point in entries]
            safe_style = str(style_id).replace(":", "_")
            safe_state = state_name.replace(":", "_")
            safe_color = color_key(rgba)
            name = f"{self.actor_prefix}handles_{safe_style}_{safe_state}_{size}_{safe_color}"
            color = tuple(rgba[:3]) if len(rgba) >= 3 else fallback_colors.get(state_name, "deepskyblue")
            opacity = float(rgba[3]) if len(rgba) >= 4 else 1.0
            self._upsert_points_actor(
                plotter,
                pv,
                np,
                state,
                name,
                points,
                color=color,
                opacity=opacity,
                point_size=float(size),
            )
            for index, (handle_id, _point) in enumerate(entries):
                next_handle_refs.setdefault(handle_id, []).append((name, index, 1))
            used_names.add(name)

        line_cells: list[int] = []
        line_points: list[tuple[float, float, float]] = []
        styled_line_groups: dict[tuple[str, float], tuple[list[tuple[float, float, float]], list[int]]] = {}
        preview_ref_ranges: dict[tuple[str, float] | tuple[str, str], dict[str, list[tuple[int, int]]]] = {}
        face_count = 0
        labels: list[str] = []
        label_points: list[tuple[float, float, float]] = []

        for item in previews:
            if not item.visible:
                continue
            kind = item.kind
            if kind in {PreviewKind.LINE, PreviewKind.POLYLINE, PreviewKind.ARC, PreviewKind.CIRCLE}:
                payload = item.payload if isinstance(item.payload, dict) else {}
                color = payload.get("color")
                line_width = float(payload.get("line_width", 3.0))
                style_id = payload.get("style_id", payload.get("line_style"))
                if not color and style_id:
                    try:
                        from ..tool_api.styles import line_style

                        style = line_style(str(style_id))
                        color = style.color
                        line_width = float(style.width_px)
                    except Exception:
                        color = None
                if color:
                    key = (str(color), line_width)
                    points_store, cells_store = styled_line_groups.setdefault(key, ([], []))
                    ref = add_polyline(points_store, cells_store, item.points, closed=(kind == PreviewKind.CIRCLE))
                    if ref is not None:
                        preview_ref_ranges.setdefault(key, {}).setdefault(str(item.id), []).append(ref)
                else:
                    ref = add_polyline(line_points, line_cells, item.points, closed=(kind == PreviewKind.CIRCLE))
                    if ref is not None:
                        preview_ref_ranges.setdefault(("default", "line_batch"), {}).setdefault(str(item.id), []).append(ref)
            elif kind == PreviewKind.FACE and len(item.points) >= 3:
                pts = [tuple(float(v) for v in point) for point in item.points]
                name = f"{self.actor_prefix}face_{face_count}"
                payload = item.payload if isinstance(item.payload, dict) else {}
                holes = tuple(tuple(tuple(float(v) for v in point) for point in hole) for hole in (payload.get("holes", ()) or ()) if len(hole) >= 3)
                triangulated = _triangulate_preview_face_points(tuple(pts), holes)
                if triangulated is not None:
                    mesh_points, mesh_faces = triangulated
                    mesh = pv.PolyData(np.asarray(mesh_points, dtype=float), faces=np.asarray(mesh_faces, dtype=int))
                else:
                    faces = [len(pts), *range(len(pts))]
                    mesh = pv.PolyData(np.asarray(pts, dtype=float), faces=np.asarray(faces, dtype=int))
                face_color = str(payload.get("face_color") or payload.get("color") or "#80B7DA")
                face_opacity = float(payload.get("face_opacity", payload.get("opacity", 0.32)))
                self._upsert_mesh_actor(plotter, state, name, mesh, color=face_color, opacity=face_opacity)
                used_names.add(name)
                line_payload = payload.get("outline_payload") if isinstance(payload.get("outline_payload"), dict) else payload
                outline_color = line_payload.get("color") if isinstance(line_payload, dict) else None
                outline_width = float(line_payload.get("line_width", 3.0)) if isinstance(line_payload, dict) else 3.0
                if outline_color:
                    key = (str(outline_color), outline_width)
                    points_store, cells_store = styled_line_groups.setdefault(key, ([], []))
                    add_polyline(points_store, cells_store, pts, closed=True)
                else:
                    add_polyline(line_points, line_cells, pts, closed=True)
                for hole in holes:
                    hole_pts = [tuple(float(v) for v in point) for point in hole]
                    if len(hole_pts) >= 3:
                        add_polyline(line_points, line_cells, hole_pts, closed=True)
                face_count += 1
            elif kind == PreviewKind.MESH and item.payload is not None:
                try:
                    preview_payload = item.payload
                    meta = getattr(preview_payload, "metadata", {}) or {}
                    visual = meta.get("tool_core_preview") if isinstance(meta, dict) else None
                    visual = visual if isinstance(visual, dict) else {}
                    mesh = workmesh_to_polydata(preview_payload)
                    name = f"{self.actor_prefix}mesh_{str(item.id).replace(':', '_').replace('.', '_')}"
                    color = str(visual.get("color") or getattr(preview_payload, "color", "#FFD54F") or "#FFD54F")
                    kwargs: dict[str, Any] = {
                        "color": color,
                        "opacity": float(visual.get("opacity", 0.55)),
                    }
                    style = str(visual.get("style") or "surface").strip().lower()
                    if style:
                        kwargs["style"] = style
                    if visual.get("line_width") is not None:
                        kwargs["line_width"] = float(visual.get("line_width") or 1.0)
                    try:
                        kwargs["render_lines_as_tubes"] = False
                    except Exception:
                        pass
                    self._upsert_mesh_actor(plotter, state, name, mesh, **kwargs)
                    used_names.add(name)
                except Exception:
                    log_exception("tool_core_diag_scene_preview_mesh")
            elif kind == PreviewKind.TEXT and isinstance(item.payload, TextLabel):
                labels.append(item.payload.text)
                label_points.append(tuple(float(v) for v in item.payload.position))

        # Pass108 named these groups grab_rings/grab_crosses.  Pass111 keeps
        # that persistent-guide contract but splits them by style color.
        for (guide_kind, guide_style), (points, cells, color, line_width) in guide_groups.items():
            guide_actor_kind = "grab_rings" if guide_kind == "ring" else "grab_crosses" if guide_kind in {"cross", "minimal"} else guide_kind
            name = f"{self.actor_prefix}guide_{guide_actor_kind}_{guide_style}"
            self._upsert_lines_actor(plotter, pv, np, state, name, points, cells, color=color, line_width=line_width)
            for handle_id, ranges in guide_ref_ranges.get((guide_kind, guide_style), {}).items():
                for start, count in ranges:
                    next_handle_refs.setdefault(handle_id, []).append((name, start, count))
            used_names.add(name)
        for (style_id, state_name, size, rgba), (points, faces, dot_rgba) in minimal_dot_groups.items():
            safe_style = str(style_id).replace(":", "_")
            safe_state = str(state_name).replace(":", "_")
            safe_color = color_key(rgba)
            name = f"{self.actor_prefix}dotdisc_{safe_style}_{safe_state}_{size}_{safe_color}"
            mesh = pv.PolyData(np.asarray(points if points else [(0.0, 0.0, 0.0)], dtype=float))
            if faces:
                mesh.faces = np.asarray(faces, dtype=int)
            self._upsert_mesh_actor(
                plotter,
                state,
                name,
                mesh,
                color=tuple(float(v) for v in dot_rgba[:3]),
                opacity=float(dot_rgba[3]) if len(dot_rgba) >= 4 else 1.0,
            )
            self._set_actor_visible(state, name, bool(points and faces))
            for handle_id, ranges in minimal_dot_ref_ranges.get((style_id, state_name, size, rgba), {}).items():
                for start, count in ranges:
                    next_handle_refs.setdefault(handle_id, []).append((name, start, count))
            used_names.add(name)
        for (color, line_width), (points, cells) in styled_line_groups.items():
            safe_color = str(color).replace("#", "hex").replace(" ", "_").replace(",", "_").replace("(", "").replace(")", "")
            name = f"{self.actor_prefix}line_batch_{safe_color}_{int(float(line_width) * 10)}"
            self._upsert_lines_actor(plotter, pv, np, state, name, points, cells, color=color, line_width=float(line_width))
            for item_id, ranges in preview_ref_ranges.get((color, line_width), {}).items():
                for start, count in ranges:
                    next_preview_refs.setdefault(item_id, []).append((name, start, count))
            used_names.add(name)
        default_line_name = f"{self.actor_prefix}line_batch"
        self._upsert_lines_actor(plotter, pv, np, state, default_line_name, line_points, line_cells, color="#263445", line_width=3.0)
        for item_id, ranges in preview_ref_ranges.get(("default", "line_batch"), {}).items():
            for start, count in ranges:
                next_preview_refs.setdefault(item_id, []).append((default_line_name, start, count))
        used_names.add(default_line_name)

        if labels and label_points:
            # Labels are deliberately static in this demo. Text actors are slow,
            # so we create/update them only when the signature changes.
            signature = tuple((str(label), tuple(float(v) for v in point)) for label, point in zip(labels, label_points))
            name = f"{self.actor_prefix}labels"
            if name in state.actor_names and not self._plotter_has_actor(plotter, name, state.actors.get(name)):
                self._forget_actor_cache(state, name)
            if signature != state.label_signature or name not in state.actor_names:
                if name in state.actor_names:
                    try:
                        plotter.remove_actor(name, render=False)
                    except Exception:
                        pass
                    state.actor_names.discard(name)
                    state.actors.pop(name, None)
                    state.meshes.pop(name, None)
                try:
                    actor = plotter.add_point_labels(
                        np.asarray(label_points, dtype=float),
                        labels,
                        name=name,
                        font_size=13,
                        point_size=0,
                        shape=None,
                        always_visible=True,
                        pickable=False,
                        render=False,
                    )
                    state.actors[name] = actor
                    state.actor_names.add(name)
                    state.label_signature = signature
                except Exception:
                    log_exception("tool_core_diag_scene_labels")
            self._set_actor_visible(state, name, True)
            used_names.add(name)

        # Hide stale dynamic actors instead of removing them. This prevents the
        # one-frame disappearance that was visible when hover/grab state changed.
        for name in list(state.actor_names):
            if not name.startswith(self.actor_prefix):
                continue
            if name == f"{self.actor_prefix}labels":
                if not labels:
                    self._set_actor_visible(state, name, False)
                continue
            if name not in used_names:
                self._set_actor_visible(state, name, False)

        state.handle_point_refs = next_handle_refs
        state.handle_positions = next_handle_positions
        state.preview_point_refs = next_preview_refs
        try:
            setattr(self.owner, self.actor_names_attr, sorted(state.actor_names))
        except Exception:
            pass
        build_ms = (time.perf_counter() - build_started) * 1000.0
        render_ms = 0.0
        if render:
            render_started = time.perf_counter()
            try:
                plotter.render()
            except Exception:
                pass
            render_ms = (time.perf_counter() - render_started) * 1000.0
        total_ms = (time.perf_counter() - total_started) * 1000.0
        try:
            if profiler is not None:
                profiler.record_timing(f"{perf_prefix}.collect", collect_ms)
                profiler.record_timing(f"{perf_prefix}.build_batches", build_ms)
                if render:
                    profiler.record_timing(f"{perf_prefix}.render", render_ms)
                profiler.record_timing(f"{perf_prefix}.total", total_ms)
                profiler.set_value(f"{perf_prefix}.handles", len(handles))
                profiler.set_value(f"{perf_prefix}.previews", len(previews))
                profiler.set_value(f"{perf_prefix}.actors", len(state.actor_names))
                profiler.set_value(f"{perf_prefix}.actors_new_last", max(0, len(state.actor_names) - actor_names_before))
                profiler.set_value(f"{perf_prefix}.handle_batches", len(handle_groups) + len(minimal_dot_groups))
                profiler.set_value(f"{perf_prefix}.core_point_instances", sum(len(entries) for entries in handle_groups.values()))
                profiler.set_value(f"{perf_prefix}.minimal_dot_instances", sum(len(ranges) for groups in minimal_dot_ref_ranges.values() for ranges in groups.values()))
                profiler.set_value(f"{perf_prefix}.minimal_dot_vertices", sum(len(values[0]) for values in minimal_dot_groups.values()))
                profiler.set_value(f"{perf_prefix}.guide_batches", len(guide_groups))
                profiler.set_value(f"{perf_prefix}.guide_vertices", sum(len(values[0]) for values in guide_groups.values()))
                profiler.set_value(f"{perf_prefix}.line_batches", len(styled_line_groups) + 1)
                profiler.set_value(f"{perf_prefix}.line_vertices", len(line_points) + sum(len(values[0]) for values in styled_line_groups.values()) + sum(len(values[0]) for values in guide_groups.values()))
                profiler.set_value(f"{perf_prefix}.faces", face_count)
                profiler.set_value(f"{perf_prefix}.labels", len(labels))
        except Exception:
            pass
        result = {
            "status": "rendered_persistent",
            "actors": len(state.actor_names),
            "actors_new": max(0, len(state.actor_names) - actor_names_before),
            "handles": len(handles),
            "previews": len(previews),
            "labels": len(labels),
            "faces": face_count,
        }
        _diag(
            "render_context.done",
            owner=self.owner,
            ctx=ctx,
            owner_tool=self.owner_tool,
            result=result,
            used_names_count=len(used_names),
            used_names_sample=sorted(used_names)[:24],
            state_actor_names_count=len(state.actor_names),
            state_actor_names_sample=sorted(state.actor_names)[:24],
            handle_refs=len(state.handle_point_refs),
            preview_refs=len(state.preview_point_refs),
        )
        return result


    def fast_update_context(
        self,
        ctx: Any,
        *,
        handle_ids: tuple[str, ...] = (),
        preview_ids: tuple[str, ...] = (),
        render: bool = True,
    ) -> bool:
        """Mutate cached point arrays for drag without rebuilding the scene.

        A preceding full ``render_context`` records which ranges in the batched
        PyVista meshes belong to each handle/preview.  During a drag we update
        only those ranges, which is the missing fast path for Creator UI motifs.
        """

        fast_started = time.perf_counter()
        profiler = getattr(ctx, "profiler", None)
        perf_owner = "".join(ch if ch.isalnum() else "_" for ch in self.owner_tool).strip("_") or "unknown"
        perf_prefix = f"creator_ui.{perf_owner}"
        plotter = getattr(self.owner, "plotter", None)
        _diag("fast_update_context.start", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, handle_ids=tuple(str(value) for value in handle_ids), preview_ids=tuple(str(value) for value in preview_ids), render=bool(render), has_plotter=plotter is not None)
        if plotter is None:
            _diag("fast_update_context.no_plotter", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool)
            return False
        state = _state(self.owner, self.state_attr)
        changed = False
        touched_points = 0

        direct_handle = getattr(ctx.gizmos, "handle", None)
        handles_by_id = None if callable(direct_handle) else {str(handle.id): handle for handle in ctx.gizmos.handles(owner_tool=self.owner_tool)}
        for handle_id in tuple(str(value) for value in handle_ids):
            handle = direct_handle(handle_id, owner_tool=self.owner_tool) if callable(direct_handle) else handles_by_id.get(handle_id)
            old_pos = state.handle_positions.get(handle_id)
            refs = state.handle_point_refs.get(handle_id, [])
            if handle is None or old_pos is None or not refs:
                _diag("fast_update_context.handle_skip", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, handle_id=handle_id, has_handle=handle is not None, has_old_pos=old_pos is not None, refs=len(refs))
                continue
            new_pos = tuple(float(v) for v in handle.position)
            delta = (new_pos[0] - old_pos[0], new_pos[1] - old_pos[1], new_pos[2] - old_pos[2])
            if abs(delta[0]) + abs(delta[1]) + abs(delta[2]) <= 1.0e-12:
                continue
            for mesh_name, start, count in refs:
                if not self._plotter_has_actor(plotter, mesh_name, state.actors.get(mesh_name)):
                    _diag("fast_update_context.handle_actor_missing", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, handle_id=handle_id, mesh_name=mesh_name)
                    return False
                mesh = state.meshes.get(mesh_name)
                if mesh is None:
                    _diag("fast_update_context.handle_mesh_missing", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, handle_id=handle_id, mesh_name=mesh_name)
                    return False
                try:
                    pts = mesh.points
                    pts[int(start): int(start) + int(count), 0] += delta[0]
                    pts[int(start): int(start) + int(count), 1] += delta[1]
                    pts[int(start): int(start) + int(count), 2] += delta[2]
                    mesh.points = pts
                    mesh.Modified()
                    touched_points += int(count)
                    changed = True
                except Exception:
                    return False
            state.handle_positions[handle_id] = new_pos

        preview_items = {str(item.id): item for item in ctx.preview.items(owner_tool=self.owner_tool)}
        for item_id in tuple(str(value) for value in preview_ids):
            item = preview_items.get(item_id)
            refs = state.preview_point_refs.get(item_id, [])
            if item is None or not refs:
                continue
            src_points = [tuple(float(v) for v in point) for point in getattr(item, "points", ())]
            for mesh_name, start, count in refs:
                if not self._plotter_has_actor(plotter, mesh_name, state.actors.get(mesh_name)):
                    _diag("fast_update_context.preview_actor_missing", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, item_id=item_id, mesh_name=mesh_name)
                    return False
                mesh = state.meshes.get(mesh_name)
                if mesh is None:
                    _diag("fast_update_context.preview_mesh_missing", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, item_id=item_id, mesh_name=mesh_name)
                    return False
                pts = list(src_points)
                if int(count) == len(pts) + 1 and pts:
                    pts.append(pts[0])
                if int(count) != len(pts):
                    return False
                try:
                    mesh.points[int(start): int(start) + int(count)] = pts
                    mesh.Modified()
                    touched_points += int(count)
                    changed = True
                except Exception:
                    return False

        render_ms = 0.0
        if changed and render:
            render_started = time.perf_counter()
            try:
                plotter.render()
            except Exception:
                pass
            render_ms = (time.perf_counter() - render_started) * 1000.0
        try:
            if profiler is not None:
                profiler.record_timing(f"{perf_prefix}.fast_update", (time.perf_counter() - fast_started) * 1000.0)
                if changed and render:
                    profiler.record_timing(f"{perf_prefix}.fast_update_render", render_ms)
                profiler.increment(f"{perf_prefix}.fast_update_calls", 1)
                if not changed:
                    profiler.increment(f"{perf_prefix}.fast_update_misses", 1)
                profiler.set_value(f"{perf_prefix}.fast_update_touched_points_last", touched_points)
                profiler.set_value(f"{perf_prefix}.fast_update_handles_requested", len(tuple(handle_ids)))
                profiler.set_value(f"{perf_prefix}.fast_update_previews_requested", len(tuple(preview_ids)))
        except Exception:
            pass
        _diag("fast_update_context.done", owner=self.owner, ctx=ctx, owner_tool=self.owner_tool, changed=bool(changed), touched_points=int(touched_points), state_actor_names=len(state.actor_names), handle_refs=len(state.handle_point_refs), preview_refs=len(state.preview_point_refs))
        return changed


    @staticmethod
    def _update_points_actor_style(actor: Any, *, color: Any, opacity: float, point_size: float) -> None:
        """Update point visual properties without recreating the actor.

        Hover/grab feedback may move a handle between state groups, but a group
        actor can already exist from a previous state.  Updating the property in
        place guarantees the current Tool Core palette is applied even after a
        style pass, and avoids the tempting but destructive remove/add path.
        """
        if actor is None:
            return
        try:
            prop = actor.GetProperty()
        except Exception:
            prop = getattr(actor, "prop", None)
        if prop is None:
            return
        try:
            prop.SetColor(float(color[0]), float(color[1]), float(color[2]))
        except Exception:
            try:
                prop.color = color
            except Exception:
                pass
        try:
            prop.SetOpacity(float(opacity))
        except Exception:
            try:
                prop.opacity = float(opacity)
            except Exception:
                pass
        try:
            prop.SetPointSize(float(point_size))
        except Exception:
            try:
                prop.point_size = float(point_size)
            except Exception:
                pass

    @staticmethod
    def _plotter_has_actor(plotter: Any, name: str, actor: Any | None) -> bool:
        """Return whether a cached Creator UI actor is still attached.

        PyVista scene rebuilds can clear or replace renderer actors without
        going through ``ToolCoreDiagScenePainter``.  The painter keeps a small
        Python cache so it can update meshes in place; after such a rebuild the
        cache can say "actor exists" while the live viewport no longer owns
        that actor.  Treat that state as detached and recreate the actor on the
        next full render.
        """

        if actor is None:
            return False
        actors = getattr(plotter, "actors", None)
        if isinstance(actors, dict):
            live = actors.get(name)
            return live is actor or live is not None
        # Some tests/fakes expose no actor map.  In that case the safest answer
        # is that the cached actor is usable.
        return True

    @staticmethod
    def _forget_actor_cache(state: _DiagActorState, name: str) -> None:
        state.actor_names.discard(name)
        state.actors.pop(name, None)
        state.meshes.pop(name, None)
        state.handle_point_refs.pop(name, None)
        state.preview_point_refs.pop(name, None)

    @staticmethod
    def _set_actor_visible(state: _DiagActorState, name: str, visible: bool) -> None:
        actor = state.actors.get(name)
        if actor is None:
            return
        try:
            actor.SetVisibility(bool(visible))
        except Exception:
            try:
                actor.visibility = bool(visible)
            except Exception:
                pass

    def _upsert_points_actor(
        self,
        plotter: Any,
        pv: Any,
        np: Any,
        state: _DiagActorState,
        name: str,
        points: list[tuple[float, float, float]],
        *,
        color: Any,
        opacity: float,
        point_size: float,
    ) -> None:
        pts = np.asarray(points if points else [(0.0, 0.0, 0.0)], dtype=float)
        if name in state.actor_names and not self._plotter_has_actor(plotter, name, state.actors.get(name)):
            _diag("points_actor.cache_detached", owner=self.owner, owner_tool=self.owner_tool, name=name)
            self._forget_actor_cache(state, name)
        if name not in state.actor_names:
            mesh = pv.PolyData(pts)
            _diag("points_actor.create", owner=self.owner, owner_tool=self.owner_tool, name=name, point_count=len(points), visible=bool(points))
            actor = plotter.add_mesh(
                mesh,
                name=name,
                render_points_as_spheres=True,
                point_size=point_size,
                color=color,
                opacity=opacity,
                pickable=False,
                render=False,
            )
            state.meshes[name] = mesh
            state.actors[name] = actor
            state.actor_names.add(name)
        else:
            _diag("points_actor.update", owner=self.owner, owner_tool=self.owner_tool, name=name, point_count=len(points), visible=bool(points))
            self._replace_polydata_points(state.meshes.get(name), pts)
            self._update_points_actor_style(state.actors.get(name), color=color, opacity=opacity, point_size=point_size)
        self._set_actor_visible(state, name, bool(points))

    def _upsert_lines_actor(
        self,
        plotter: Any,
        pv: Any,
        np: Any,
        state: _DiagActorState,
        name: str,
        points: list[tuple[float, float, float]],
        cells: list[int],
        *,
        color: str,
        line_width: float,
    ) -> None:
        if points and cells:
            mesh = pv.PolyData(np.asarray(points, dtype=float))
            mesh.lines = np.asarray(cells, dtype=int)
        else:
            mesh = pv.PolyData(np.asarray([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)], dtype=float))
            mesh.lines = np.asarray([2, 0, 1], dtype=int)
        self._upsert_mesh_actor(plotter, state, name, mesh, color=color, line_width=line_width)
        self._set_actor_visible(state, name, bool(points and cells))

    def _upsert_mesh_actor(self, plotter: Any, state: _DiagActorState, name: str, mesh: Any, **kwargs: Any) -> None:
        if name in state.actor_names and not self._plotter_has_actor(plotter, name, state.actors.get(name)):
            _diag("mesh_actor.cache_detached", owner=self.owner, owner_tool=self.owner_tool, name=name)
            self._forget_actor_cache(state, name)
        if name not in state.actor_names:
            try:
                point_count = int(getattr(mesh, "n_points", len(getattr(mesh, "points", ()) or ())))
            except Exception:
                point_count = -1
            _diag("mesh_actor.create", owner=self.owner, owner_tool=self.owner_tool, name=name, point_count=point_count, kwargs=kwargs)
            actor = plotter.add_mesh(mesh, name=name, pickable=False, render=False, **kwargs)
            state.meshes[name] = mesh
            state.actors[name] = actor
            state.actor_names.add(name)
            return
        old_mesh = state.meshes.get(name)
        try:
            point_count = int(getattr(mesh, "n_points", len(getattr(mesh, "points", ()) or ())))
        except Exception:
            point_count = -1
        _diag("mesh_actor.update", owner=self.owner, owner_tool=self.owner_tool, name=name, point_count=point_count, kwargs=kwargs)
        self._copy_polydata(old_mesh, mesh)
        self._update_mesh_actor_style(state.actors.get(name), **kwargs)
        self._set_actor_visible(state, name, True)

    @staticmethod
    def _update_mesh_actor_style(actor: Any, **kwargs: Any) -> None:
        if actor is None:
            return
        try:
            prop = actor.GetProperty()
        except Exception:
            prop = getattr(actor, "prop", None)
        if prop is None:
            return
        color = kwargs.get("color")
        if color is not None:
            try:
                if isinstance(color, str):
                    prop.SetColor(*parse_hex_color(color))
                else:
                    prop.SetColor(float(color[0]), float(color[1]), float(color[2]))
            except Exception:
                try:
                    prop.color = color
                except Exception:
                    pass
        if "opacity" in kwargs:
            try:
                prop.SetOpacity(float(kwargs["opacity"]))
            except Exception:
                try:
                    prop.opacity = float(kwargs["opacity"])
                except Exception:
                    pass
        if "line_width" in kwargs:
            try:
                prop.SetLineWidth(float(kwargs["line_width"]))
            except Exception:
                try:
                    prop.line_width = float(kwargs["line_width"])
                except Exception:
                    pass

    @staticmethod
    def _replace_polydata_points(mesh: Any, points: Any) -> None:
        if mesh is None:
            return
        try:
            mesh.points = points
            mesh.Modified()
        except Exception:
            try:
                mesh.SetPoints(points)
                mesh.Modified()
            except Exception:
                pass

    @staticmethod
    def _copy_polydata(target: Any, source: Any) -> None:
        if target is None:
            return
        try:
            target.copy_from(source)
            target.Modified()
        except Exception:
            try:
                target.DeepCopy(source)
                target.Modified()
            except Exception:
                pass
