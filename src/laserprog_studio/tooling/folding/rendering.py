# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import projected_drawing as draw2d

from .geometry import (
    build_folding_frame,
    control_points,
    hinge_boundary_segments,
    hinge_handle_point,
    sample_curve,
    shape_control_fractions,
    shape_handle_normals,
    shape_handle_points,
)
from .models import FoldingFixedSide, FoldingMode, FoldingPhase, FoldingSession


class FoldingRenderer:
    def __init__(self, owner_tool: str, session: FoldingSession) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session

    @staticmethod
    def _mesh_geometry(mesh: Any) -> tuple[tuple[tuple[float, float, float], ...], tuple[tuple[int, int, int], ...]] | None:
        try:
            vertices = tuple(tuple(float(v) for v in point) for point in getattr(mesh, "vertices", ()))
            triangles = tuple(tuple(int(v) for v in tri) for tri in getattr(mesh, "triangles", ()))
        except Exception:
            return None
        if len(vertices) < 3 or not triangles:
            return None
        return vertices, triangles

    @staticmethod
    def _face_mesh(primitive_id: str, vertices: tuple[tuple[float, float, float], ...], *, selected: bool) -> Any | None:
        if len(vertices) != 3:
            return None
        color = "#66C7FF" if selected else "#FFD54F"
        return draw2d.triangle_mesh(
            primitive_id,
            vertices,
            ((0, 1, 2),),
            fill_color=color,
            fill_opacity=0.16 if selected else 0.13,
            outline_color=color,
            outline_width_px=3.0 if selected else 4.0,
            outline_opacity=0.98,
            layer=62 if selected else 66,
            metadata={
                "folding_role": "selected_face" if selected else "hovered_face",
                "projected_drawing_only": True,
                "projected_no_selection_actor": True,
            },
        )

    def _living_hinge_primitives(self) -> tuple[Any, ...]:
        session = self.session
        curve = session.curve
        plane = session.plane
        if plane is None or not curve.complete:
            return ()
        primitives: list[Any] = []
        try:
            frame = build_folding_frame(plane, curve)
            curve_points = sample_curve(plane, curve, count=64)
            handle = hinge_handle_point(plane, curve)
            primitives.append(draw2d.polyline("folding:curve", curve_points, color="#4FC3F7", width_px=3.2, opacity=0.98, layer=66))
            primitives.append(
                draw2d.handle(
                    "folding:angle",
                    handle,
                    shape="diamond",
                    direction=frame.normal,
                    color="#4AA7FF",
                    size_px=18.0,
                    constraint="free",
                    layer=76,
                    metadata={"folding_role": "angle_handle"},
                )
            )
            shape_points = shape_handle_points(plane, curve)
            shape_normals = shape_handle_normals(plane, curve)
            fractions = shape_control_fractions(curve)
            for index, (point, direction, fraction) in enumerate(zip(shape_points, shape_normals, fractions), start=1):
                baseline = tuple(
                    float(frame.start[axis_index]) + float(frame.axis[axis_index]) * frame.length_mm * float(fraction)
                    for axis_index in range(3)
                )
                primitives.extend(
                    (
                        draw2d.line(
                            f"folding:shape:guide:{index}",
                            baseline,
                            point,
                            color="#B99CFF",
                            width_px=1.2,
                            opacity=0.48,
                            layer=63,
                        ),
                        draw2d.handle(
                            f"folding:shape:{index}",
                            point,
                            shape="ring",
                            direction=direction,
                            color="#B388FF",
                            size_px=14.0,
                            constraint="free",
                            layer=75,
                            metadata={"folding_role": "shape_handle", "shape_index": index - 1},
                        ),
                    )
                )
            # Invisible aliases keep old diagnostics/tests and saved actor references
            # harmlessly compatible without reintroducing the two-handle UI.
            primitives.extend(
                (
                    draw2d.point("folding:control:1", handle, size_px=1.0, opacity=0.0, visible=False, hit_radius_px=1.0, metadata={"folding_role": "legacy_alias"}),
                    draw2d.point("folding:control:2", handle, size_px=1.0, opacity=0.0, visible=False, hit_radius_px=1.0, metadata={"folding_role": "legacy_alias"}),
                )
            )
            if session.source_mesh is not None:
                start_line, end_line = hinge_boundary_segments(getattr(session.source_mesh, "vertices", ()) or (), plane, curve)
                primitives.extend(
                    (
                        draw2d.line("folding:hinge:start", start_line[0], start_line[1], color="#74F3A5", width_px=3.0, opacity=0.95, layer=65),
                        draw2d.line("folding:hinge:end", end_line[0], end_line[1], color="#FFB36B", width_px=3.0, opacity=0.95, layer=65),
                    )
                )
            fixed_at_start = curve.normalized_fixed_side() == FoldingFixedSide.START.value
            fixed_anchor = frame.start if fixed_at_start else frame.end
            moving_anchor = frame.end if fixed_at_start else frame.start
            primitives.extend(
                (
                    draw2d.text("folding:fixed:label", "FIXED", fixed_anchor, color="#CFFFE0", size_px=11, bold=True, anchor="bottom_left", offset_px=(8.0, -8.0), layer=72),
                    draw2d.text("folding:moving:label", "MOVING", moving_anchor, color="#FFE0C3", size_px=11, bold=True, anchor="bottom_left", offset_px=(8.0, -8.0), layer=72),
                )
            )
        except Exception:
            return ()
        return tuple(primitives)

    def _legacy_curve_primitives(self) -> tuple[Any, ...]:
        session = self.session
        curve = session.curve
        plane = session.plane
        if plane is None or not curve.complete:
            return ()
        primitives: list[Any] = []
        try:
            frame = build_folding_frame(plane, curve)
            c1, c2 = control_points(plane, curve)
            baseline_1 = tuple(float(frame.start[i]) + float(frame.axis[i]) * frame.length_mm / 3.0 for i in range(3))
            baseline_2 = tuple(float(frame.start[i]) + float(frame.axis[i]) * 2.0 * frame.length_mm / 3.0 for i in range(3))
            primitives.extend(
                (
                    draw2d.line("folding:baseline", frame.start, frame.end, color="#76879A", width_px=1.2, opacity=0.65, layer=58),
                    draw2d.line("folding:control:guide:1", baseline_1, c1, color="#6AB9FF", width_px=1.3, opacity=0.70, layer=60),
                    draw2d.line("folding:control:guide:2", baseline_2, c2, color="#6AB9FF", width_px=1.3, opacity=0.70, layer=60),
                    draw2d.polyline("folding:curve", sample_curve(plane, curve), color="#50B7FF", width_px=3.0, opacity=0.98, layer=64),
                    draw2d.handle("folding:control:1", c1, shape="diamond", direction=frame.bend_axis, color="#4AA7FF", size_px=18.0, constraint="free", layer=74, metadata={"folding_role": "control_1"}),
                    draw2d.handle("folding:control:2", c2, shape="diamond", direction=frame.bend_axis, color="#4AA7FF", size_px=18.0, constraint="free", layer=74, metadata={"folding_role": "control_2"}),
                )
            )
        except Exception:
            return ()
        return tuple(primitives)

    def _curve_primitives(self) -> tuple[Any, ...]:
        if str(self.session.curve.mode) == FoldingMode.LIVING_HINGE.value:
            return self._living_hinge_primitives()
        return self._legacy_curve_primitives()

    def sync_adjustment(self, ctx: Any, *, render: bool = True) -> None:
        """Update only the lightweight curve actors during interaction.

        The target mesh outline can contain tens of thousands of points. It is
        installed once by :meth:`sync`; angle drags then use the projected
        drawing incremental-update path and never resubmit that mesh.
        """

        if self.session.phase is not FoldingPhase.ADJUST_CURVE:
            self.sync(ctx, render=render)
            return
        primitives = self._curve_primitives()
        if not primitives:
            return
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        try:
            registry.update_many(primitives, render=render)
        except (KeyError, ValueError, TypeError):
            # First frame, backend reset, or topology migration: rebuild once.
            self.sync(ctx, render=render)

    def sync(self, ctx: Any, *, render: bool = True) -> None:
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        primitives: list[Any] = []
        session = self.session
        curve = session.curve

        if session.phase is not FoldingPhase.SELECT_MESH:
            for target_number, (object_id, _index, _name, mesh) in enumerate(session.target_rows()):
                geometry = self._mesh_geometry(mesh)
                if geometry is None:
                    continue
                vertices, triangles = geometry
                primitives.append(
                    draw2d.triangle_mesh(
                        "folding:target" if target_number == 0 else f"folding:target:{target_number + 1}",
                        vertices,
                        triangles,
                        fill_color="#4AA7FF",
                        fill_opacity=0.012,
                        outline_color="#4AA7FF",
                        outline_width_px=2.2,
                        outline_opacity=0.58,
                        layer=48,
                        metadata={
                            "folding_role": "target_mesh",
                            "source_object_id": str(object_id),
                            "folding_group_id": str(session.group_id or ""),
                            "projected_drawing_only": True,
                            "projected_no_selection_actor": True,
                        },
                    )
                )

        selected_face = self._face_mesh("folding:selected_face", session.selected_face_vertices, selected=True)
        if selected_face is not None:
            primitives.append(selected_face)
        hovered_face = self._face_mesh("folding:hovered_face", session.hovered_face_vertices, selected=False)
        if hovered_face is not None and session.phase is FoldingPhase.SELECT_FACE:
            primitives.append(hovered_face)

        if curve.start is not None:
            primitives.append(draw2d.point("folding:start", curve.start, color="#74F3A5", size_px=11.0, layer=70, metadata={"folding_role": "start"}))
        if curve.end is not None:
            primitives.append(draw2d.point("folding:end", curve.end, color="#FFB36B", size_px=11.0, layer=70, metadata={"folding_role": "end"}))

        if session.hover_point is not None and session.phase is FoldingPhase.PLACE_END and curve.start is not None:
            primitives.append(draw2d.line("folding:pending_interval", curve.start, session.hover_point, color="#FFD54F", width_px=2.2, opacity=0.82, layer=64))

        if session.phase is FoldingPhase.ADJUST_CURVE:
            primitives.extend(self._curve_primitives())
        registry.replace_all(tuple(primitives), render=render)

    def clear(self, ctx: Any, *, render: bool = True) -> None:
        ctx.projected_drawing.for_tool(self.owner_tool).clear(render=render)


__all__ = ["FoldingRenderer"]
