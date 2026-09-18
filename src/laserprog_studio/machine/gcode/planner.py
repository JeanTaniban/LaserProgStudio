# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from shapely.geometry import LineString, MultiLineString, Polygon

from .models import Point2D, Toolpath


_COORD_GRID_MM = 0.001
_AREA_EPSILON_MM2 = 1.0e-8


@dataclass(frozen=True, slots=True)
class GCodeGeometryTransform:
    """Real-size XY transform shared by G-code exports.

    ``flip_y`` defaults to true to mirror the Falcon SVG export visual frame:
    X grows right, Y grows downward on the 2D job canvas.  This keeps SVG and
    G-code previews comparable.  Users can still place the job with machine
    origin controls in the sender.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    page_margin_ratio: float = 0.0
    flip_y: bool = True

    @classmethod
    def from_bounds(cls, bounds: tuple[float, float, float, float], page_margin_ratio: float = 0.0, flip_y: bool = True) -> "GCodeGeometryTransform":
        min_x, min_y, max_x, max_y = (float(v) for v in bounds)
        width = max(max_x - min_x, 1.0e-6)
        height = max(max_y - min_y, 1.0e-6)
        margin = max(width, height) * max(0.0, float(page_margin_ratio))
        return cls(min_x - margin, min_y - margin, max_x + margin, max_y + margin, max(0.0, float(page_margin_ratio)), bool(flip_y))

    @property
    def width_mm(self) -> float:
        return float(self.max_x - self.min_x)

    @property
    def height_mm(self) -> float:
        return float(self.max_y - self.min_y)

    def point(self, x: float, y: float) -> Point2D:
        px = _snap(float(x) - self.min_x)
        py_raw = self.max_y - float(y) if self.flip_y else float(y) - self.min_y
        return px, _snap(py_raw)


def _snap(value: float) -> float:
    return round(float(value) / _COORD_GRID_MM) * _COORD_GRID_MM


def signed_area(points: Iterable[Point2D]) -> float:
    pts = tuple(points)
    if len(pts) < 3:
        return 0.0
    return 0.5 * sum(
        pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
        for i in range(len(pts))
    )


def clean_ring_points(coords: Iterable[tuple[float, float]], transform: GCodeGeometryTransform) -> tuple[Point2D, ...]:
    raw = list(coords)
    if len(raw) < 4:
        return ()
    tol = max(_COORD_GRID_MM * 0.5, 1.0e-9)
    tol_sq = tol * tol
    points: list[Point2D] = []
    for x, y in raw:
        p = transform.point(float(x), float(y))
        if points and (points[-1][0] - p[0]) ** 2 + (points[-1][1] - p[1]) ** 2 <= tol_sq:
            continue
        points.append(p)
    if len(points) > 1 and (points[0][0] - points[-1][0]) ** 2 + (points[0][1] - points[-1][1]) ** 2 <= tol_sq:
        points.pop()
    if len(points) < 3:
        return ()

    changed = True
    while changed and len(points) > 3:
        changed = False
        cleaned: list[Point2D] = []
        count = len(points)
        for i, current in enumerate(points):
            previous = points[(i - 1) % count]
            following = points[(i + 1) % count]
            ax, ay = current[0] - previous[0], current[1] - previous[1]
            bx, by = following[0] - current[0], following[1] - current[1]
            cross = ax * by - ay * bx
            dot = ax * bx + ay * by
            scale = max(abs(ax) + abs(ay), abs(bx) + abs(by), 1.0)
            if abs(cross) <= 1.0e-9 * scale * scale and dot >= -tol_sq:
                changed = True
                continue
            cleaned.append(current)
        if len(cleaned) < 3 or len(cleaned) == len(points):
            break
        points = cleaned
    if len(points) < 3 or abs(signed_area(points)) <= _AREA_EPSILON_MM2:
        return ()
    return tuple(points)


def ring_signature(points: tuple[Point2D, ...]) -> tuple[Point2D, ...]:
    if len(points) < 3:
        return ()

    def canonical(seq: tuple[Point2D, ...]) -> tuple[Point2D, ...]:
        start = min(range(len(seq)), key=lambda i: (seq[i][0], seq[i][1], i))
        return tuple(seq[start:] + seq[:start])

    return min(canonical(points), canonical(tuple(reversed(points))))


def iter_polygons(geom):
    if geom is None or getattr(geom, "is_empty", True):
        return
    if isinstance(geom, Polygon):
        yield geom
        return
    try:
        for item in geom.geoms:
            if isinstance(item, Polygon):
                yield item
            else:
                yield from iter_polygons(item)
    except Exception:
        return


def outline_toolpaths(geom, transform: GCodeGeometryTransform) -> list[Toolpath]:
    """Return cut paths small/interior first to reduce freed-piece drift."""
    seen: set[tuple[Point2D, ...]] = set()
    candidates: list[tuple[float, tuple[Point2D, ...], str]] = []
    for poly in iter_polygons(_clean_geometry(geom)):
        for ring, note in [(r, "hole") for r in poly.interiors] + [(poly.exterior, "outer")]:
            points = clean_ring_points(ring.coords, transform)
            signature = ring_signature(points)
            if not signature or signature in seen:
                continue
            seen.add(signature)
            candidates.append((abs(signed_area(points)), points, note))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [Toolpath("cut", points, closed=True, note=note) for _area, points, note in candidates]


def hatch_toolpaths(geom, transform: GCodeGeometryTransform, spacing_mm: float) -> list[Toolpath]:
    """Generate simple horizontal hatch engraving segments for fill geometry."""
    geom = _clean_geometry(geom)
    if geom is None or getattr(geom, "is_empty", True):
        return []
    spacing = max(float(spacing_mm), 0.01)
    minx, miny, maxx, maxy = geom.bounds
    paths: list[Toolpath] = []
    y = math.floor(float(miny) / spacing) * spacing
    row_index = 0
    while y <= maxy + spacing * 0.5:
        line = LineString([(minx - spacing, y), (maxx + spacing, y)])
        inter = geom.intersection(line)
        segments = _line_segments(inter)
        if row_index % 2:
            segments = [(b, a) for a, b in reversed(segments)]
        for start, end in segments:
            p0 = transform.point(*start)
            p1 = transform.point(*end)
            if _distance_sq(p0, p1) > 1.0e-8:
                paths.append(Toolpath("engrave", (p0, p1), closed=False, note="hatch"))
        y += spacing
        row_index += 1
    return paths


def _line_segments(geom) -> list[tuple[Point2D, Point2D]]:
    if geom is None or getattr(geom, "is_empty", True):
        return []
    segments: list[tuple[Point2D, Point2D]] = []
    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) >= 2:
            segments.append(((float(coords[0][0]), float(coords[0][1])), (float(coords[-1][0]), float(coords[-1][1]))))
    elif isinstance(geom, MultiLineString):
        for part in geom.geoms:
            segments.extend(_line_segments(part))
    else:
        try:
            for part in geom.geoms:
                segments.extend(_line_segments(part))
        except Exception:
            pass
    segments.sort(key=lambda seg: (seg[0][1], seg[0][0], seg[1][0]))
    return segments


def _clean_geometry(geom):
    if geom is None or getattr(geom, "is_empty", True):
        return geom
    try:
        if not bool(getattr(geom, "is_valid", True)):
            geom = geom.buffer(0)
        if geom is not None and not getattr(geom, "is_empty", True):
            geom = geom.buffer(0)
    except Exception:
        pass
    return geom


def _distance_sq(a: Point2D, b: Point2D) -> float:
    return (float(a[0]) - float(b[0])) ** 2 + (float(a[1]) - float(b[1])) ** 2
