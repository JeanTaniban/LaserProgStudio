"""Incremental Projected Drawing renderer for Cloth.

Document geometry and the surface preview are revision-driven.  The high
frequency cursor path uses the official Plan 2D cursor API and updates only the
cursor/rubber-band primitives, so moving the mouse no longer rebuilds every
panel and every curve.
"""
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import plan2d, projected_drawing as draw2d

from .drawing import ClothDrawingController
from .geometry_trace import ClothGeometryTraceController
from .interaction import ClothInteractionState, ClothUxStage
from .mesh_builder import build_cloth_surface_mesh, triangulate_simple_polygon
from .models import ClothCurveRole, ClothPatchFunction, ClothSession
from .selection import logical_patch_group
from .topology import curve_patch_incidence, patch_frame, sample_curve, sample_patch_boundary


_CURVE_COLORS = {
    ClothCurveRole.BOUNDARY: "#55B7FF",
    ClothCurveRole.FOLD: "#FFAD5C",
    ClothCurveRole.SEAM: "#68D391",
    ClothCurveRole.CONSTRUCTION: "#8B98A7",
}
_CURSOR_ID = "cloth:cursor"
_STATIC_PREFIXES = (
    "cloth:surface",
    "cloth:curve:",
    "cloth:point:",
    "cloth:hovered_reference_face",
    "cloth:source:",
    "cloth:join:",
    "cloth:flat_preview",
)


class ClothRenderer:
    def __init__(
        self,
        owner_tool: str,
        session: ClothSession,
        interaction: ClothInteractionState,
        drawing: ClothDrawingController,
        geometry_trace: ClothGeometryTraceController | None = None,
    ) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session
        self.interaction = interaction
        self.drawing = drawing
        self.geometry_trace = geometry_trace or ClothGeometryTraceController()
        self._surface_cache_document_id: int | None = None
        self._surface_cache_revision: int = -1
        self._surface_cache: Any | None = None
        self._static_signature: tuple[Any, ...] | None = None
        self._draft_signature: tuple[Any, ...] | None = None
        self._cursor_signature: tuple[Any, ...] | None = None

    def _surface_preview(self):
        document = self.session.document
        if not document.patches:
            self._surface_cache_document_id = id(document)
            self._surface_cache_revision = int(document.revision)
            self._surface_cache = None
            return None
        identity = id(document)
        revision = int(document.revision)
        if self._surface_cache_document_id != identity or self._surface_cache_revision != revision:
            self._surface_cache_document_id = identity
            self._surface_cache_revision = revision
            try:
                self._surface_cache = build_cloth_surface_mesh(document, name="Cloth preview")
            except Exception:
                self._surface_cache = None
        return self._surface_cache

    def sync(self, ctx: Any, *, render: bool = True) -> None:
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        static_changed = self._sync_static(registry)
        draft_changed = self._sync_draft(registry)
        cursor_changed = self._sync_cursor(ctx)
        if cursor_changed:
            plan2d.sync_plan_actor_visuals(
                ctx,
                owner_tool=self.owner_tool,
                changed_actor_ids=(_CURSOR_ID,),
                extra_preview_ids=("cloth:draft:rubber",) if draft_changed else (),
                position_only=not static_changed and not draft_changed,
                render=render,
            )
        elif static_changed or draft_changed:
            registry.sync_interaction_state(render=False)
            registry.render(render=render)

    def _sync_static(self, registry: Any) -> bool:
        document = self.session.document
        state = self.interaction
        selected_fold_curve_id = None
        if state.selected_fold_id and state.selected_fold_id in document.folds:
            selected_fold_curve_id = document.folds[state.selected_fold_id].curve_id
        signature = (
            id(document),
            int(document.revision),
            tuple(sorted(state.selected_curve_ids)),
            tuple(sorted(self.session.selected_point_ids)),
            tuple(sorted(self.session.selected_curve_ids)),
            tuple(sorted(self.session.selected_patch_ids)),
            selected_fold_curve_id,
            state.selected_pattern_curve_id,
            state.pattern_operation,
            state.hovered_curve_id,
            state.hovered_point_id,
            state.hovered_patch_id,
            tuple(state.hovered_patch_group_ids),
            tuple(state.hovered_face_vertices),
            self.session.edit_mode.value,
            id(state.flat_preview_mesh) if state.flat_preview_mesh is not None else None,
            int(self.geometry_trace.revision),
            tuple(getattr(item, "id", "") for item in state.join_proposals),
            int(state.join_proposal_index),
        )
        if signature == self._static_signature:
            return False
        self._static_signature = signature

        primitives: list[Any] = []
        surface = self._surface_preview()
        if surface is not None and surface.mesh is not None:
            primitives.append(
                draw2d.triangle_mesh(
                    "cloth:surface",
                    tuple(surface.mesh.vertices),
                    tuple(surface.mesh.triangles),
                    fill_color="#65C7F2",
                    fill_opacity=0.30,
                    outline_color="#8DD9F7",
                    outline_width_px=0.8,
                    outline_opacity=0.24,
                    layer=42,
                    metadata={"cloth_role": "surface_preview", "projected_no_selection_actor": True},
                )
            )

        # Function overlays remain visible independently of selection. Pattern
        # faces are violet; junction faces are orange. Normal textile keeps the
        # material/surface preview colour.
        for patch_id, patch in document.patches.items():
            if patch.function is ClothPatchFunction.TEXTILE:
                continue
            boundary = tuple(sample_patch_boundary(document, patch, arc_segments=24))
            frame = patch_frame(document, patch)
            if frame is None or len(boundary) < 3:
                continue
            triangles = tuple(triangulate_simple_polygon([frame.project(point) for point in boundary]))
            if not triangles:
                continue
            is_pattern = patch.function is ClothPatchFunction.PATTERN
            primitives.append(
                draw2d.triangle_mesh(
                    f"cloth:surface:function:{patch_id}",
                    boundary,
                    triangles,
                    fill_color="#A855F7" if is_pattern else "#F97316",
                    fill_opacity=0.28 if is_pattern else 0.30,
                    outline_color="#D8B4FE" if is_pattern else "#FDBA74",
                    outline_width_px=1.15,
                    outline_opacity=0.62,
                    layer=56,
                    metadata={"cloth_role": patch.function.value, "cloth_patch_id": patch_id, "projected_no_selection_actor": True},
                )
            )

        # Faces need an entity-level overlay because the normal surface preview
        # is one merged triangle mesh.  Keeping this separate also means face
        # selection never changes the generated Cloth mesh or its topology.
        selected_patches = set(self.session.selected_patch_ids)
        hover_group = set(state.hovered_patch_group_ids)
        if not hover_group and state.hovered_patch_id:
            hover_group.update(logical_patch_group(document, state.hovered_patch_id))
        highlighted_patches = selected_patches | hover_group
        for patch_id in sorted(value for value in highlighted_patches if value in document.patches):
            patch = document.patches[patch_id]
            boundary = tuple(sample_patch_boundary(document, patch, arc_segments=24))
            frame = patch_frame(document, patch)
            if frame is None or len(boundary) < 3:
                continue
            triangles = tuple(triangulate_simple_polygon([frame.project(point) for point in boundary]))
            if not triangles:
                continue
            selected = patch_id in selected_patches
            primitives.append(
                draw2d.triangle_mesh(
                    f"cloth:surface:selection:{patch_id}",
                    boundary,
                    triangles,
                    fill_color="#FBBF24" if selected else "#67E8F9",
                    fill_opacity=0.42 if selected else 0.24,
                    outline_color="#FDE68A" if selected else "#A5F3FC",
                    outline_width_px=1.0 if selected else 0.75,
                    outline_opacity=0.42 if selected else 0.28,
                    layer=64 if selected else 61,
                    metadata={"cloth_role": "patch_selection", "cloth_patch_id": patch_id, "projected_no_selection_actor": True},
                )
            )

        curve_incidence = curve_patch_incidence(document)
        patch_group_key = {
            patch_id: str(
                dict(patch.metadata or {}).get("cloth_logical_group_id")
                or dict(patch.metadata or {}).get("cloth_creation_group_id")
                or dict(patch.metadata or {}).get("cloth_join_proposal_id")
                or patch_id
            )
            for patch_id, patch in document.patches.items()
        }
        detailed_edges = state.stage is ClothUxStage.DRAW or self.session.edit_mode.value == "modify" or self.drawing.active
        for curve in document.curves.values():
            points = tuple(sample_curve(document, curve, arc_segments=32))
            if len(points) < 2:
                continue
            selected = (
                curve.id in state.selected_curve_ids
                or curve.id in self.session.selected_curve_ids
                or curve.id == selected_fold_curve_id
                or curve.id == state.selected_pattern_curve_id
            )
            hovered = curve.id == state.hovered_curve_id
            is_cut = bool(curve.metadata.get("cloth_user_cut") or curve.metadata.get("cloth_auto_cut") or curve.metadata.get("cloth_pattern_edge_kind") == "cut")
            curve_patches = tuple(value for value in curve_incidence.get(curve.id, ()) if value in document.patches)
            group_keys = {patch_group_key.get(value, value) for value in curve_patches}
            internal_same_group = len(curve_patches) >= 2 and len(group_keys) == 1
            selected_boundary = bool(selected_patches.intersection(curve_patches)) and not (
                internal_same_group and set(curve_patches).issubset(selected_patches)
            )
            base_color = "#F472B6" if is_cut else _CURVE_COLORS.get(curve.role, "#55B7FF")
            if selected or hovered:
                color = "#FFD54F"
                width = 3.2 if selected else 2.8
                opacity = 1.0
            elif selected_boundary:
                color = "#FDE68A"
                width = 2.2
                opacity = 0.94
            elif internal_same_group and not detailed_edges:
                color = "#7DD3FC"
                width = 0.55
                opacity = 0.16
            elif detailed_edges:
                color = base_color
                width = 2.2 if is_cut else 1.8 if curve.role is ClothCurveRole.FOLD else 1.45
                opacity = 0.86
            else:
                color = base_color
                width = 1.25 if is_cut or curve.role is ClothCurveRole.FOLD else 0.9
                opacity = 0.48
            primitives.append(
                draw2d.polyline(
                    f"cloth:curve:{curve.id}",
                    points,
                    color=color,
                    width_px=width,
                    opacity=opacity,
                    layer=66 if selected or hovered else 58,
                    metadata={
                        "cloth_role": curve.role.value,
                        "cloth_curve_id": curve.id,
                        "projected_no_selection_actor": True,
                    },
                )
            )

        if self.session.edit_mode.value == "modify" or self.drawing.active:
            for point in document.points.values():
                hovered = point.id == state.hovered_point_id
                selected = point.id in self.session.selected_point_ids
                primitives.append(
                    draw2d.point(
                        f"cloth:point:{point.id}",
                        point.position,
                        color="#FBBF24" if selected else "#FFD54F" if hovered else "#D9F1FF",
                        size_px=12.0 if selected else 11.0 if hovered else 7.0,
                        layer=72 if selected else 70 if hovered else 62,
                        metadata={"cloth_role": "point", "cloth_point_id": point.id},
                    )
                )

        if state.hovered_face_vertices and len(state.hovered_face_vertices) == 3:
            primitives.append(
                draw2d.triangle_mesh(
                    "cloth:hovered_reference_face",
                    tuple(state.hovered_face_vertices),
                    ((0, 1, 2),),
                    fill_color="#FFD54F",
                    fill_opacity=0.15,
                    outline_color="#FFD54F",
                    outline_width_px=4.0,
                    outline_opacity=0.98,
                    layer=68,
                    metadata={"cloth_role": "reference_face_hover", "projected_no_selection_actor": True},
                )
            )

        if self.session.edit_mode.value == "mesh_trace":
            selected_triangles = self.geometry_trace.selected_face_triangles()
            if selected_triangles:
                vertices: list[tuple[float, float, float]] = []
                triangles: list[tuple[int, int, int]] = []
                for triangle in selected_triangles:
                    base = len(vertices)
                    vertices.extend(triangle)
                    triangles.append((base, base + 1, base + 2))
                primitives.append(
                    draw2d.triangle_mesh(
                        "cloth:source:selected_faces",
                        tuple(vertices),
                        tuple(triangles),
                        fill_color="#22D3EE",
                        fill_opacity=0.22,
                        outline_color="#67E8F9",
                        outline_width_px=2.6,
                        outline_opacity=0.96,
                        layer=67,
                        metadata={"cloth_role": "source_face_selection", "projected_no_selection_actor": True},
                    )
                )
            hovered_triangles = self.geometry_trace.hovered_face_triangles()
            if hovered_triangles:
                vertices: list[tuple[float, float, float]] = []
                triangles: list[tuple[int, int, int]] = []
                for triangle in hovered_triangles:
                    base = len(vertices)
                    vertices.extend(triangle)
                    triangles.append((base, base + 1, base + 2))
                primitives.append(
                    draw2d.triangle_mesh(
                        "cloth:source:hovered_face",
                        tuple(vertices),
                        tuple(triangles),
                        fill_color="#A3E635",
                        fill_opacity=0.15,
                        outline_color="#D9F99D",
                        outline_width_px=2.2,
                        outline_opacity=0.86,
                        layer=69,
                        metadata={"cloth_role": "source_face_hover", "projected_no_selection_actor": True},
                    )
                )
            for index, (start, end) in enumerate(self.geometry_trace.selected_edge_segments()):
                primitives.append(
                    draw2d.line(
                        f"cloth:source:selected_edge:{index}",
                        start,
                        end,
                        color="#22D3EE",
                        width_px=4.0,
                        opacity=1.0,
                        layer=71,
                        metadata={"cloth_role": "source_edge_selection", "projected_no_selection_actor": True},
                    )
                )
            hovered_edge = self.geometry_trace.hovered_edge_segment()
            if hovered_edge is not None:
                primitives.append(
                    draw2d.line(
                        "cloth:source:hovered_edge",
                        hovered_edge[0],
                        hovered_edge[1],
                        color="#FDE047",
                        width_px=4.8,
                        opacity=1.0,
                        layer=72,
                        metadata={"cloth_role": "source_edge_hover", "projected_no_selection_actor": True},
                    )
                )
            # Show the strongest prediction before the user accepts it. This is
            # intentionally limited to directional continuation to avoid
            # flooding dense meshes with every connected edge.
            predictions = self.geometry_trace.predictions()
            if predictions.ruled_strip is not None:
                strip = predictions.ruled_strip
                vertices = tuple(
                    point
                    for pair in zip(strip.rail_a, strip.rail_b)
                    for point in pair
                )
                triangles = tuple(
                    triangle
                    for index in range(strip.segment_count)
                    for triangle in (
                        (2 * index, 2 * index + 2, 2 * index + 3),
                        (2 * index, 2 * index + 3, 2 * index + 1),
                    )
                )
                if triangles:
                    primitives.append(
                        draw2d.triangle_mesh(
                            "cloth:source:ruled_strip_prediction",
                            vertices,
                            triangles,
                            fill_color="#86EFAC",
                            fill_opacity=0.14,
                            outline_color="#BBF7D0",
                            outline_width_px=1.8,
                            outline_opacity=0.78,
                            layer=64,
                            metadata={"cloth_role": "source_ruled_strip_prediction", "projected_no_selection_actor": True},
                        )
                    )
                stride = max(1, len(strip.ribs) // 32)
                for index, (start, end) in enumerate(strip.ribs[::stride]):
                    primitives.append(
                        draw2d.line(
                            f"cloth:source:ruled_strip_rib:{index}",
                            start,
                            end,
                            color="#BBF7D0",
                            width_px=1.6,
                            opacity=0.72,
                            layer=66,
                            metadata={"cloth_role": "source_ruled_strip_rib", "projected_no_selection_actor": True},
                        )
                    )
            for plan_index, plan in enumerate(predictions.closable_faces[:64]):
                snapshot = self.geometry_trace.snapshots.get(plan.object_id)
                if snapshot is None:
                    continue
                vertices = tuple(
                    snapshot.vertices[vertex_index]
                    for face_index in plan.face_indices
                    for vertex_index in snapshot.triangles[face_index]
                )
                triangles = tuple(
                    (3 * index, 3 * index + 1, 3 * index + 2)
                    for index in range(len(plan.face_indices))
                )
                if triangles:
                    primitives.append(
                        draw2d.triangle_mesh(
                            f"cloth:source:face_closure:{plan_index}",
                            vertices,
                            triangles,
                            fill_color="#86EFAC" if plan.complete else "#FDBA74",
                            fill_opacity=0.12 if plan.complete else 0.08,
                            outline_color="#86EFAC" if plan.complete else "#FDBA74",
                            outline_width_px=1.4,
                            outline_opacity=0.45,
                            layer=63,
                            metadata={"cloth_role": "source_face_closure_prediction", "projected_no_selection_actor": True},
                        )
                    )
            for index, item in enumerate(predictions.closure_edges):
                snapshot = self.geometry_trace.snapshots.get(item.object_id)
                if snapshot is None:
                    continue
                start, end = snapshot.edge_vertices(item.edge)
                primitives.append(
                    draw2d.line(
                        f"cloth:source:closure_edge:{index}",
                        start,
                        end,
                        color="#FB923C",
                        width_px=3.4,
                        opacity=0.96,
                        layer=68,
                        metadata={"cloth_role": "source_face_missing_edge", "projected_no_selection_actor": True},
                    )
                )
            for index, item in enumerate(predictions.directional_edges):
                snapshot = self.geometry_trace.snapshots.get(item.object_id)
                if snapshot is None:
                    continue
                start, end = snapshot.edge_vertices(item.edge)
                primitives.append(
                    draw2d.line(
                        f"cloth:source:prediction:{index}",
                        start,
                        end,
                        color="#A5F3FC",
                        width_px=2.1,
                        opacity=0.72,
                        layer=65,
                        metadata={"cloth_role": "source_edge_prediction", "projected_no_selection_actor": True},
                    )
                )

        if state.join_proposals:
            index = max(0, min(int(state.join_proposal_index), len(state.join_proposals) - 1))
            proposal = state.join_proposals[index]
            preview_triangles = tuple(getattr(proposal, "triangle_preview", ()) or ())
            if preview_triangles:
                vertices: list[tuple[float, float, float]] = []
                triangles: list[tuple[int, int, int]] = []
                for triangle in preview_triangles:
                    base = len(vertices)
                    vertices.extend(triangle)
                    triangles.append((base, base + 1, base + 2))
                primitives.append(
                    draw2d.triangle_mesh(
                        "cloth:join:proposal",
                        tuple(vertices),
                        tuple(triangles),
                        fill_color="#34D399",
                        fill_opacity=0.18,
                        outline_color="#A7F3D0",
                        outline_width_px=2.4,
                        outline_opacity=0.94,
                        layer=69,
                        metadata={"cloth_role": "join_proposal", "projected_no_selection_actor": True},
                    )
                )

        if state.flat_preview_mesh is not None:
            flat_vertices, flat_triangles = self._offset_flat_preview(
                state.flat_preview_mesh,
                surface.mesh if surface and surface.mesh else None,
            )
            primitives.append(
                draw2d.triangle_mesh(
                    "cloth:flat_preview",
                    flat_vertices,
                    flat_triangles,
                    fill_color="#A7E5C0",
                    fill_opacity=0.22,
                    outline_color="#63D48D",
                    outline_width_px=2.2,
                    outline_opacity=0.92,
                    layer=50,
                    metadata={"cloth_role": "flat_preview", "projected_no_selection_actor": True},
                )
            )
            if flat_vertices:
                primitives.append(
                    draw2d.text(
                        "cloth:flat_preview:label",
                        "FLAT PATTERN PREVIEW",
                        flat_vertices[0],
                        color="#BFF5D1",
                        size_px=12,
                        bold=True,
                        anchor="bottom_left",
                        offset_px=(0.0, -12.0),
                        layer=72,
                    )
                )

        wanted = {str(item.id) for item in primitives}
        stale = tuple(
            str(item.id)
            for item in registry.items()
            if self._is_static_id(str(item.id)) and str(item.id) not in wanted
        )
        if stale:
            registry.remove_many(stale, render=False)
        if primitives:
            registry.add_many(tuple(primitives), replace=True, render=False)
        return True

    def _sync_draft(self, registry: Any) -> bool:
        pending = tuple(self.drawing.pending_world_points)
        cursor = self.interaction.cursor_world
        signature = (pending, cursor if pending else None)
        if signature == self._draft_signature:
            return False
        self._draft_signature = signature
        primitives: list[Any] = []
        for index, point in enumerate(pending):
            primitives.append(draw2d.point(f"cloth:draft:point:{index}", point, color="#FFE27A", size_px=10.0, layer=76))
        if len(pending) >= 2:
            primitives.append(draw2d.polyline("cloth:draft:path", pending, color="#FFE27A", width_px=2.3, opacity=0.95, layer=72))
        if pending and cursor is not None:
            primitives.append(draw2d.line("cloth:draft:rubber", pending[-1], cursor, color="#FFD54F", width_px=1.8, opacity=0.8, layer=74))

        wanted = {str(item.id) for item in primitives}
        stale = tuple(str(item.id) for item in registry.items() if str(item.id).startswith("cloth:draft:") and str(item.id) not in wanted)
        if stale:
            registry.remove_many(stale, render=False)
        if primitives:
            registry.add_many(tuple(primitives), replace=True, render=False)
        return True

    def _sync_cursor(self, ctx: Any) -> bool:
        state = self.interaction
        visible = state.cursor_world is not None and state.stage in {ClothUxStage.OPENING, ClothUxStage.DRAW}
        signature = (
            state.cursor_world if visible else None,
            state.cursor_snap_kind,
            state.cursor_snap_label,
            state.cursor_snapped,
        )
        if signature == self._cursor_signature:
            return False
        self._cursor_signature = signature
        if not visible:
            try:
                plan2d.hide_plan_cursor(ctx, owner_tool=self.owner_tool, cursor_id=_CURSOR_ID, render=False)
            except Exception:
                pass
            return True
        plan2d.register_plan_cursor(
            ctx,
            owner_tool=self.owner_tool,
            cursor_id=_CURSOR_ID,
            world_pos=state.cursor_world,
            visible=True,
            snap_kind=state.cursor_snap_kind,
            snap_label=state.cursor_snap_label,
            snapped=state.cursor_snapped,
        )
        return True

    @staticmethod
    def _is_static_id(value: str) -> bool:
        return any(value == prefix or value.startswith(prefix) for prefix in _STATIC_PREFIXES)

    def clear(self, ctx: Any, *, render: bool = True) -> None:
        self._surface_cache_document_id = None
        self._surface_cache_revision = -1
        self._surface_cache = None
        self._static_signature = None
        self._draft_signature = None
        self._cursor_signature = None
        ctx.projected_drawing.for_tool(self.owner_tool).clear(render=render)

    @staticmethod
    def _offset_flat_preview(flat_mesh: Any, folded_mesh: Any | None):
        vertices = [tuple(float(value) for value in point) for point in getattr(flat_mesh, "vertices", ())]
        triangles = tuple(tuple(int(value) for value in triangle) for triangle in getattr(flat_mesh, "triangles", ()))
        if not vertices:
            return (), triangles
        if folded_mesh is not None and getattr(folded_mesh, "vertices", None):
            folded_vertices = list(folded_mesh.vertices)
            max_x = max(point[0] for point in folded_vertices)
            min_x = min(point[0] for point in vertices)
            width = max(point[0] for point in vertices) - min_x
            offset_x = max_x - min_x + max(20.0, width * 0.15)
        else:
            offset_x = 30.0
        min_z = min(point[2] for point in vertices)
        return tuple((point[0] + offset_x, point[1], point[2] - min_z) for point in vertices), triangles


__all__ = ["ClothRenderer"]
