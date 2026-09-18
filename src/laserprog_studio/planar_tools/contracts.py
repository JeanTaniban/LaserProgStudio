# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class PlanarEditMode(str, Enum):
    """Common edit modes for locked-plane drawing tools.

    The names intentionally match the future UI button labels: ADD, MOD, SUPP,
    RST.  Keeping the enum here avoids each future tool inventing its own
    slightly different mode strings.
    """

    ADD = "ADD"
    MOD = "MOD"
    SUPP = "SUPP"
    RST = "RST"


class FixedPlanarView(str, Enum):
    """Orthographic camera views supported by locked planar tools."""

    TOP = "top"
    BOTTOM = "bottom"
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class VentSectionKind(str, Enum):
    ROUND = "round"
    RECTANGLE = "rectangle"


class VentFlareSide(str, Enum):
    """Which end of an audio vent receives a widened anti-chuff opening."""

    NONE = "none"
    START = "start"
    END = "end"
    BOTH = "both"


AxisName = Literal["x", "y", "z"]
Vec3 = tuple[float, float, float]
Vec2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class PlanePoint:
    """2D point in a locked drawing plane."""

    u: float
    v: float

    def as_tuple(self) -> Vec2:
        return (float(self.u), float(self.v))


@dataclass(frozen=True, slots=True)
class WorldPoint:
    """3D point in Studio world coordinates."""

    x: float
    y: float
    z: float

    def as_tuple(self) -> Vec3:
        return (float(self.x), float(self.y), float(self.z))


@dataclass(frozen=True, slots=True)
class LockedPlaneSpec:
    """Geometry contract for a view-locked planar tool.

    `normal` is the constant-depth direction.  `depth` is the dot product of a
    world point with that normal.  Every point emitted by the tool is clamped to
    this depth until the tool ends.
    """

    view: FixedPlanarView
    normal: Vec3
    u_axis: Vec3
    v_axis: Vec3
    depth: float = 0.0

    @property
    def view_name(self) -> str:
        return self.view.value

    def with_depth(self, depth: float) -> "LockedPlaneSpec":
        return LockedPlaneSpec(self.view, self.normal, self.u_axis, self.v_axis, float(depth))


@dataclass(frozen=True, slots=True)
class PlanarToolConfig:
    """Shared UI-independent settings for future planar tools."""

    grid_snap_enabled: bool = False
    smart_snap_enabled: bool = True
    grid_step: float = 5.0
    smart_snap_tolerance: float = 2.0
    grid_origin: Vec2 | None = None
    # Default preserves the expected behaviour for existing planar tools.  Plan tracer sets
    # this to True so smart endpoint coincidence is not destroyed by grid snap.
    smart_snap_priority: bool = False
