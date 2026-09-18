"""Transform-only gizmo API.

This module deliberately lives beside the generic ``gizmos`` package, not inside
its public contract.  Application Transform needs world-scaled axes and optional centre
handles; Creator tools such as Plan Tracer depend on the historical unit-sized
``ctx.gizmos.translate/rotate/scale`` semantics.  Keeping the two managers
separate prevents Transform UI changes from mutating every tool in the app.
"""
from __future__ import annotations

from .gizmos.manager import GizmoManager, GizmoManipulator, Point3


class TransformGizmoManager(GizmoManager):
    """Dedicated manager for the main application's Transform tool.

    It extends the persistent handle manager with world-space axis lengths and
    local axis vectors.  No generic Creator tool should use this manager.
    """

    def translate(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        axes: tuple[str, ...] = ("x", "y", "z"),
        radius_px: int = 14,
        axis_length: float = 1.0,
        axis_vectors: dict[str, Point3] | None = None,
        include_center: bool = True,
        center_selectable: bool = True,
    ) -> GizmoManipulator:
        handle_ids: list[str] = []
        offsets = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
        vectors = axis_vectors or {}
        length = max(0.0, float(axis_length))
        for axis in axes:
            axis_key = str(axis).lower()
            vec = vectors.get(axis_key, offsets.get(axis_key, (0.0, 0.0, 0.0)))
            try:
                dx, dy, dz = (float(vec[0]), float(vec[1]), float(vec[2]))
            except Exception:
                dx, dy, dz = offsets.get(axis_key, (0.0, 0.0, 0.0))
            handle_id = f"{id}:{axis_key}"
            self.upsert_handle(
                id=handle_id,
                owner_tool=owner_tool,
                position=(float(origin[0]) + dx * length, float(origin[1]) + dy * length, float(origin[2]) + dz * length),
                radius_px=radius_px,
                base_radius_px=radius_px,
                kind=f"translate:{axis_key}",
                style_id="translate_arrow",
            )
            handle_ids.append(handle_id)
        if include_center:
            center_id = f"{id}:center"
            center_radius = max(8, int(radius_px * 0.8))
            self.upsert_handle(
                id=center_id,
                owner_tool=owner_tool,
                position=origin,
                radius_px=center_radius,
                base_radius_px=center_radius,
                kind="translate:center",
                style_id="solid",
                selectable=bool(center_selectable),
            )
            handle_ids.append(center_id)
        return GizmoManipulator(
            id=id,
            owner_tool=owner_tool,
            kind="translate",
            handle_ids=tuple(handle_ids),
            origin=origin,
            metadata={"axis_length": length, "axes": tuple(str(a).lower() for a in axes)},
        )

    def rotate(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        axes: tuple[str, ...] = ("x", "y", "z"),
        radius_px: int = 13,
        axis_length: float = 1.0,
        axis_vectors: dict[str, Point3] | None = None,
    ) -> GizmoManipulator:
        handle_ids: list[str] = []
        offsets = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}
        vectors = axis_vectors or {}
        length = max(0.0, float(axis_length))
        for axis in axes:
            axis_key = str(axis).lower()
            vec = vectors.get(axis_key, offsets.get(axis_key, (0.0, 0.0, 0.0)))
            try:
                dx, dy, dz = (float(vec[0]), float(vec[1]), float(vec[2]))
            except Exception:
                dx, dy, dz = offsets.get(axis_key, (0.0, 0.0, 0.0))
            handle_id = f"{id}:rotate:{axis_key}"
            self.upsert_handle(
                id=handle_id,
                owner_tool=owner_tool,
                position=(float(origin[0]) + dx * length, float(origin[1]) + dy * length, float(origin[2]) + dz * length),
                radius_px=radius_px,
                base_radius_px=radius_px,
                kind=f"rotate:{axis_key}",
                style_id="ring",
            )
            handle_ids.append(handle_id)
        return GizmoManipulator(
            id=id,
            owner_tool=owner_tool,
            kind="rotate",
            handle_ids=tuple(handle_ids),
            origin=origin,
            metadata={"axis_length": length, "axes": tuple(str(a).lower() for a in axes)},
        )

    def scale(
        self,
        *,
        id: str,
        owner_tool: str,
        origin: Point3 = (0.0, 0.0, 0.0),
        axes: tuple[str, ...] = ("x", "y", "z", "uniform"),
        radius_px: int = 13,
        axis_length: float = 1.0,
        axis_vectors: dict[str, Point3] | None = None,
    ) -> GizmoManipulator:
        handle_ids: list[str] = []
        offsets = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0), "uniform": (0.75, 0.75, 0.75)}
        vectors = axis_vectors or {}
        length = max(0.0, float(axis_length))
        for axis in axes:
            axis_key = str(axis).lower()
            vec = vectors.get(axis_key, offsets.get(axis_key, (0.0, 0.0, 0.0)))
            try:
                dx, dy, dz = (float(vec[0]), float(vec[1]), float(vec[2]))
            except Exception:
                dx, dy, dz = offsets.get(axis_key, (0.0, 0.0, 0.0))
            handle_id = f"{id}:scale:{axis_key}"
            self.upsert_handle(
                id=handle_id,
                owner_tool=owner_tool,
                position=(float(origin[0]) + dx * length, float(origin[1]) + dy * length, float(origin[2]) + dz * length),
                radius_px=radius_px,
                base_radius_px=radius_px,
                kind=f"scale:{axis_key}",
                style_id="square",
            )
            handle_ids.append(handle_id)
        return GizmoManipulator(
            id=id,
            owner_tool=owner_tool,
            kind="scale",
            handle_ids=tuple(handle_ids),
            origin=origin,
            metadata={"axis_length": length, "axes": tuple(str(a).lower() for a in axes)},
        )
