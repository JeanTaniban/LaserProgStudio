# -*- coding: utf-8 -*-
from __future__ import annotations

import math


def texture_rotation_point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    abx = float(bx) - float(ax)
    aby = float(by) - float(ay)
    apx = float(px) - float(ax)
    apy = float(py) - float(ay)
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return math.hypot(apx, apy)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
    cx = float(ax) + t * abx
    cy = float(ay) + t * aby
    return math.hypot(float(px) - cx, float(py) - cy)


def texture_vec3_add(a, b):
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def texture_vec3_scale(v, s: float):
    return (float(v[0]) * float(s), float(v[1]) * float(s), float(v[2]) * float(s))
