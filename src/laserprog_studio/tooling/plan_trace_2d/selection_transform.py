# -*- coding: utf-8 -*-
"""Small, explicit state machine for Plan Tracer selection transforms.

Translation remains driven by Smart Snap. Holding Ctrl during an active drag
temporarily rotates the selection around the physically grabbed sketch point.
The rotation state is isolated here so selection topology, snapping and viewport
rendering do not accumulate mode-specific flags.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping

Point2 = tuple[float, float]


@dataclass(slots=True)
class SelectionTransformSession:
    point_ids: tuple[str, ...]
    pivot_point_id: str
    mode: str = "translate"
    rotation_start_screen: Point2 | None = None
    rotation_pivot_xy: Point2 | None = None
    rotation_start_positions: dict[str, Point2] = field(default_factory=dict)
    angle_rad: float = 0.0
    translation_screen_offset: Point2 = (0.0, 0.0)

    @property
    def rotating(self) -> bool:
        return self.mode == "rotate"

    def latch_rotation(
        self,
        *,
        screen_pos: Point2,
        positions: Mapping[str, Point2],
    ) -> bool:
        """Switch once from translation to rotation without changing geometry."""

        if self.rotating:
            return False
        pivot = positions.get(self.pivot_point_id)
        if pivot is None:
            return False
        self.mode = "rotate"
        self.rotation_start_screen = (float(screen_pos[0]), float(screen_pos[1]))
        self.rotation_pivot_xy = (float(pivot[0]), float(pivot[1]))
        self.rotation_start_positions = {
            str(point_id): (float(value[0]), float(value[1]))
            for point_id, value in positions.items()
            if str(point_id) in self.point_ids
        }
        self.angle_rad = 0.0
        return True

    def resume_translation(self, *, screen_pos: Point2, pivot_screen_pos: Point2) -> None:
        """Leave Ctrl-rotation without snapping the pivot to the raw cursor."""

        self.mode = "translate"
        self.translation_screen_offset = (
            float(pivot_screen_pos[0]) - float(screen_pos[0]),
            float(pivot_screen_pos[1]) - float(screen_pos[1]),
        )
        self.rotation_start_screen = None
        self.rotation_pivot_xy = None
        self.rotation_start_positions = {}
        self.angle_rad = 0.0

    def effective_translation_screen_pos(self, screen_pos: Point2) -> Point2:
        return (
            float(screen_pos[0]) + float(self.translation_screen_offset[0]),
            float(screen_pos[1]) + float(self.translation_screen_offset[1]),
        )

    def rotated_positions(self, screen_pos: Point2, *, degrees_per_pixel: float = 0.5) -> dict[str, Point2]:
        if not self.rotating or self.rotation_start_screen is None or self.rotation_pivot_xy is None:
            return {}
        # Horizontal mouse travel is deliberate: it works even though the grab
        # starts exactly on the pivot, where an angular cursor vector is undefined.
        dx = float(screen_pos[0]) - float(self.rotation_start_screen[0])
        angle = math.radians(float(degrees_per_pixel) * dx)
        self.angle_rad = angle
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        px, py = self.rotation_pivot_xy
        result: dict[str, Point2] = {}
        for point_id, (x, y) in self.rotation_start_positions.items():
            rx = float(x) - px
            ry = float(y) - py
            result[point_id] = (px + rx * cos_a - ry * sin_a, py + rx * sin_a + ry * cos_a)
        return result


__all__ = ["SelectionTransformSession"]
