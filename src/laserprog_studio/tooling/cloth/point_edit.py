# -*- coding: utf-8 -*-
"""Lightweight point dragging for the interactive Cloth editor.

This module owns the drag state and plane/snap calculations so the Creator
adapter remains focused on lifecycle and state-machine routing.  V1 deliberately
locks vertices shared by several panels: moving a hinge vertex requires a
multi-plane constraint solver and must not silently make panels non-planar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from laserprog_studio.planar_tools import clamp_world_point_to_plane
from laserprog_studio.tool_api.tracing import plane_from_origin_normal, point_plane_distance

from .interaction import ClothInteractionState
from .models import ClothDocument
from .picking import cloth_snap_targets
from .topology import patch_frame, patch_point_ids

Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ClothPointEditResult:
    handled: bool
    changed: bool = False
    message: str = ""


class ClothPointEditor:
    """Edit one non-shared Cloth point on its owning panel plane."""

    def __init__(self) -> None:
        self.point_id: str | None = None
        self.origin: Point3 | None = None
        self.plane: Any | None = None
        self.changed = False

    @property
    def active(self) -> bool:
        return self.point_id is not None

    def reset(self) -> None:
        self.point_id = None
        self.origin = None
        self.plane = None
        self.changed = False

    def begin(
        self,
        document: ClothDocument,
        interaction: ClothInteractionState,
        point_id: str,
        *,
        active_plane: Any | None,
        report: Callable[[str], None],
    ) -> bool:
        point = document.points.get(str(point_id))
        if point is None:
            return False
        owners = tuple(
            patch
            for patch in document.patches.values()
            if point.id in patch_point_ids(document, patch)
        )
        if len(owners) > 1:
            interaction.message = "Shared fold vertices are locked in Cloth V1. Move a free panel vertex instead."
            interaction.hovered_point_id = point.id
            report(interaction.message)
            return False
        if owners:
            frame = patch_frame(document, owners[0])
            if frame is None:
                report("This panel no longer defines a valid editing plane.")
                return False
            plane = plane_from_origin_normal(frame.origin, frame.normal)
        else:
            plane = active_plane
        if plane is None:
            report("This point does not have a valid local editing plane.")
            return False
        self.point_id = point.id
        self.origin = tuple(float(value) for value in point.position)
        self.plane = plane
        self.changed = False
        interaction.hovered_point_id = point.id
        interaction.cursor_world = point.position
        interaction.message = "Drag the point on its panel plane; release to validate."
        return True

    def move(
        self,
        ctx: Any,
        event: Any,
        document: ClothDocument,
        interaction: ClothInteractionState,
        *,
        owner_tool: str,
        smart_snap: bool,
        snap_tolerance_px: float,
        render_preview: Callable[[], None],
    ) -> ClothPointEditResult:
        point_id = self.point_id
        if point_id is None:
            return ClothPointEditResult(False)
        position = self._event_position(ctx, event)
        if position is None:
            return ClothPointEditResult(True, self.changed, "Moving Cloth point…")
        if smart_snap:
            position = self._snap_position(
                ctx,
                event,
                document,
                interaction,
                point_id,
                position,
                owner_tool=owner_tool,
                snap_tolerance_px=snap_tolerance_px,
            )
        else:
            interaction.cursor_snap_label = "Free"
        previous = document.points[point_id].position
        moved_now = position != previous
        if moved_now:
            document.move_point(point_id, position)
        self.changed = self.changed or position != self.origin
        interaction.cursor_world = position
        interaction.hovered_point_id = point_id
        interaction.message = "Moving Cloth point…"
        if moved_now:
            render_preview()
        return ClothPointEditResult(True, self.changed, interaction.message)

    def finish(
        self,
        ctx: Any,
        event: Any,
        document: ClothDocument,
        interaction: ClothInteractionState,
        *,
        owner_tool: str,
        smart_snap: bool,
        snap_tolerance_px: float,
        render_preview: Callable[[], None],
    ) -> ClothPointEditResult:
        if not self.active:
            return ClothPointEditResult(False)
        self.move(
            ctx,
            event,
            document,
            interaction,
            owner_tool=owner_tool,
            smart_snap=smart_snap,
            snap_tolerance_px=snap_tolerance_px,
            render_preview=render_preview,
        )
        point_id = self.point_id
        changed = self.changed
        self.reset()
        message = "Point moved. The panel and flat pattern were updated." if changed else f"Point {point_id or ''} selected."
        return ClothPointEditResult(True, changed, message)

    def cancel(self, document: ClothDocument) -> ClothPointEditResult:
        if not self.active:
            return ClothPointEditResult(False)
        if self.point_id is not None and self.origin is not None:
            document.move_point(self.point_id, self.origin)
        self.reset()
        return ClothPointEditResult(True, False, "Point movement cancelled.")

    def _event_position(self, ctx: Any, event: Any) -> Point3 | None:
        if self.plane is None or getattr(event, "screen_pos", None) is None:
            return None
        try:
            hit = ctx.pick.plane_intersection(event.screen_pos, self.plane)
            if hit.hit and hit.world_pos is not None:
                return tuple(float(value) for value in hit.world_pos)
        except Exception:
            pass
        if getattr(event, "world_pos", None) is not None:
            return clamp_world_point_to_plane(self.plane, event.world_pos)
        return None

    def _snap_position(
        self,
        ctx: Any,
        event: Any,
        document: ClothDocument,
        interaction: ClothInteractionState,
        point_id: str,
        position: Point3,
        *,
        owner_tool: str,
        snap_tolerance_px: float,
    ) -> Point3:
        try:
            incident_curve_ids = {
                curve.id for curve in document.curves.values() if point_id in curve.point_ids
            }
            targets = tuple(
                target
                for target in cloth_snap_targets(document, owner_tool=owner_tool, plane=self.plane)
                if point_id not in str(getattr(target, "source_id", ""))
                and str(getattr(target, "metadata", {}).get("cloth_curve_id", "")) not in incident_curve_ids
            )
            result = ctx.snap.smart(
                position,
                event.screen_pos,
                ctx,
                extra_targets=targets,
                max_distance_px=snap_tolerance_px,
            )
            if result.snapped and point_plane_distance(self.plane, result.position) <= 0.5:
                interaction.cursor_snap_label = str(result.metadata.get("snap_label") or result.label or "Snap")
                return clamp_world_point_to_plane(self.plane, result.position)
        except Exception:
            pass
        interaction.cursor_snap_label = "Free"
        return position


__all__ = ["ClothPointEditResult", "ClothPointEditor"]
