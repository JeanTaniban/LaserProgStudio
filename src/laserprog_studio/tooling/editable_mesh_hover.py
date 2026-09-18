# -*- coding: utf-8 -*-
"""Shared yellow edge hover preview for reopenable Creator meshes.

Plan Tracer 2D established the UX convention that an editable generated mesh is
outlined in yellow before it is clicked.  This helper keeps the same convention
available to other Creator tools without duplicating renderer-specific code.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from laserprog_studio.tool_api import projected_drawing as draw2d


@dataclass(frozen=True, slots=True)
class EditableHoverMesh:
    object_id: str
    mesh: Any


class EditableMeshHoverPreview:
    """Render one lightweight yellow outline group for an editable scene source.

    The preview is owner-scoped, non-selectable, and updated only when the
    hovered editable group changes.  A group may contain several meshes, which
    is useful for a Mechanical Motion assembly made of multiple generated parts.
    """

    def __init__(
        self,
        owner_tool: str,
        primitive_prefix: str,
        *,
        metadata_role: str,
        color: str = "#FFD54F",
    ) -> None:
        self.owner_tool = str(owner_tool)
        self.primitive_prefix = str(primitive_prefix)
        self.metadata_role = str(metadata_role)
        self.color = str(color)
        self._group_key: str | None = None
        self._primitive_ids: tuple[str, ...] = ()

    @property
    def group_key(self) -> str | None:
        return self._group_key

    @property
    def visible(self) -> bool:
        return bool(self._group_key and self._primitive_ids)

    def reset(self) -> None:
        """Forget cached renderer state after a tool-wide cleanup/reopen."""

        self._group_key = None
        self._primitive_ids = ()

    @staticmethod
    def _mesh_geometry(mesh: Any) -> tuple[tuple[tuple[float, float, float], ...], tuple[tuple[int, int, int], ...]] | None:
        try:
            raw_vertices = getattr(mesh, "vertices", ())
            raw_triangles = getattr(mesh, "triangles", ())
            vertices = tuple(tuple(float(value) for value in point) for point in raw_vertices)
            triangles = tuple(tuple(int(value) for value in cell) for cell in raw_triangles)
        except Exception:
            return None
        if len(vertices) < 3 or not triangles:
            return None
        return vertices, triangles

    def show(
        self,
        ctx: Any,
        *,
        group_key: str,
        meshes: Iterable[EditableHoverMesh],
        render: bool = True,
    ) -> bool:
        """Show the editable group, returning whether its visual state changed."""

        key = str(group_key or "").strip()
        candidates = tuple(meshes)
        if not key or not candidates:
            return self.hide(ctx, render=render)

        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        if key == self._group_key and self._primitive_ids:
            existing = tuple(registry.get(primitive_id) for primitive_id in self._primitive_ids)
            if all(item is not None and bool(getattr(item, "visible", True)) for item in existing):
                return False

        primitives: list[Any] = []
        primitive_ids: list[str] = []
        for index, candidate in enumerate(candidates):
            geometry = self._mesh_geometry(candidate.mesh)
            if geometry is None:
                continue
            vertices, triangles = geometry
            primitive_id = f"{self.primitive_prefix}:{index}"
            primitive_ids.append(primitive_id)
            primitives.append(
                draw2d.triangle_mesh(
                    primitive_id,
                    vertices,
                    triangles,
                    fill_color=self.color,
                    fill_opacity=0.035,
                    outline_color=self.color,
                    outline_width_px=5.0,
                    outline_opacity=0.92,
                    layer=55,
                    metadata={
                        "editable_hover_role": self.metadata_role,
                        "source_object_id": str(candidate.object_id),
                        "editable_group_key": key,
                        "projected_drawing_only": True,
                        "projected_no_selection_actor": True,
                    },
                )
            )

        if not primitives:
            return self.hide(ctx, render=render)

        old_ids = self._primitive_ids
        with registry.batch():
            if old_ids:
                registry.remove_many(old_ids, render=False)
            registry.add_many(tuple(primitives), replace=True, render=False)
        self._group_key = key
        self._primitive_ids = tuple(primitive_ids)
        if render:
            registry.render(render=True)
        return True

    def hide(self, ctx: Any, *, render: bool = True) -> bool:
        """Remove the yellow hover preview without touching other tool overlays."""

        had_visual = bool(self._group_key or self._primitive_ids)
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        if self._primitive_ids:
            try:
                registry.remove_many(self._primitive_ids, render=False)
            except Exception:
                pass
        self.reset()
        if render and had_visual:
            registry.render(render=True)
        return had_visual


__all__ = ["EditableHoverMesh", "EditableMeshHoverPreview"]
