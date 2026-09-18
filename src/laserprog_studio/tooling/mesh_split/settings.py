# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable
import math


def _clamp_float(value: Any, fallback: float, *, low: float, high: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(fallback)
    return max(float(low), min(float(high), number))


def normalize3(values: Iterable[float]) -> tuple[float, float, float]:
    xyz = list(values)[:3]
    if len(xyz) != 3:
        return (0.0, 0.0, 1.0)
    x, y, z = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return (x / length, y / length, z / length)


def normal_from_euler_xyz_deg(rx_deg: float, ry_deg: float, rz_deg: float) -> tuple[float, float, float]:
    """Return local Z transformed by XYZ Euler angles in degrees."""

    rx = math.radians(float(rx_deg))
    ry = math.radians(float(ry_deg))
    rz = math.radians(float(rz_deg))
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    # R = Rz * Ry * Rx, applied to local Z=(0, 0, 1).
    x0, y0, z0 = 0.0, -sx, cx
    x1, y1, z1 = cy * x0 + sy * z0, y0, -sy * x0 + cy * z0
    x2, y2, z2 = cz * x1 - sz * y1, sz * x1 + cz * y1, z1
    return normalize3((x2, y2, z2))


@dataclass(frozen=True, slots=True)
class SplitPlaneSettings:
    """Validated user-facing settings for the Split Mesh tool."""

    preset_id: str = "center_z"
    offset_mm: float = 0.0
    rx_deg: float = 0.0
    ry_deg: float = 0.0
    rz_deg: float = 0.0
    plane_size_mm: float = 120.0
    tolerance: float = 0.00001

    @property
    def normal(self) -> tuple[float, float, float]:
        return normal_from_euler_xyz_deg(self.rx_deg, self.ry_deg, self.rz_deg)

    @property
    def summary(self) -> str:
        nx, ny, nz = self.normal
        return f"offset {self.offset_mm:g} mm · normal ({nx:.2f}, {ny:.2f}, {nz:.2f}) · tol {self.tolerance:g}"


def split_settings_from_values(values: dict[str, Any]) -> SplitPlaneSettings:
    return SplitPlaneSettings(
        preset_id=str(values.get("split_preset", values.get("preset_id", "center_z")) or "center_z"),
        offset_mm=_clamp_float(values.get("offset_mm", 0.0), 0.0, low=-1_000_000.0, high=1_000_000.0),
        rx_deg=_clamp_float(values.get("rx_deg", 0.0), 0.0, low=-360.0, high=360.0),
        ry_deg=_clamp_float(values.get("ry_deg", 0.0), 0.0, low=-360.0, high=360.0),
        rz_deg=_clamp_float(values.get("rz_deg", 0.0), 0.0, low=-360.0, high=360.0),
        plane_size_mm=_clamp_float(values.get("plane_size_mm", 120.0), 120.0, low=1.0, high=1_000_000.0),
        tolerance=_clamp_float(values.get("tolerance", 0.00001), 0.00001, low=0.00000001, high=10.0),
    )


__all__ = ["SplitPlaneSettings", "normal_from_euler_xyz_deg", "normalize3", "split_settings_from_values"]
