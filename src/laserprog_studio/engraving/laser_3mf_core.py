#!/usr/bin/env python3
"""
3MF GUI -> images for laser engraver/cutter.

Features:
- select a .3mf file
- auto-generate 3 views:
  1) orthographic top-down preview with union by color
  2) black/white laser image: green = outline, red = fill
  3) thickness labels placed at the center of zones
- save each image with a button
- tune offsets/margins: outline, fill, stroke width, DPI, etc.

Dependencies:
    pip install numpy shapely pillow

Run:
    python laser_3mf_gui.py

Prototype convention:
- dominant green material/color -> black outline
- dominant red material/color   -> black fill
- ignore / other colors       -> visible in preview, ignored for laser.
"""

from __future__ import annotations

import json
import shutil
import tkinter as tk
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

CORE_NS = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
MAT_NS = "{http://schemas.microsoft.com/3dmanufacturing/material/2015/02}"

PRESET_DIR_NAME = "presets"
PRESET_FILE_SUFFIX = ".json"
PRESET_TYPE = "laser_3mf_gui_parameters"
PRESET_VERSION = 1
DEFAULT_PRESET_NAME = "default"

class EngravingRole(str, Enum):
    OUTLINE = "outline"
    FILL = "fill"
    IGNORE = "ignore"


ENGRAVING_ROLE_OUTLINE = EngravingRole.OUTLINE.value
ENGRAVING_ROLE_FILL = EngravingRole.FILL.value
ENGRAVING_ROLE_IGNORE = EngravingRole.IGNORE.value
ENGRAVING_ROLE_COLORS = {
    ENGRAVING_ROLE_OUTLINE: "#00C853",
    ENGRAVING_ROLE_FILL: "#E53935",
    ENGRAVING_ROLE_IGNORE: "#B8B8B8",
}
SUPPORTED_ENGRAVING_ROLES = tuple(role.value for role in EngravingRole)


# -----------------------------
# Data
# -----------------------------

@dataclass
class MeshObject:
    object_id: str
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=float))
    triangles: np.ndarray = field(default_factory=lambda: np.zeros((0, 3), dtype=int))
    triangle_colors: List[str] = field(default_factory=list)
    components: List[Tuple[str, np.ndarray]] = field(default_factory=list)
    color: str = "#B0B0B0FF"


@dataclass
class Instance2D:
    name: str
    color: str
    footprint: Polygon | MultiPolygon
    height: float


@dataclass
class RenderConfig:
    dpi: int = 220
    normal_z_threshold: float = 0.5
    page_margin_ratio: float = 0.08
    contour_width_mm: float = 0.12
    contour_margin_mm: float = 0.0
    fill_margin_mm: float = 0.0
    fill_edge_width_mm: float = 0.02
    label_font_size_px: int = 22
    min_output_px: int = 700
    max_display_px: int = 900


# -----------------------------
# 3MF parsing
# -----------------------------

def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag

def parse_transform(transform: Optional[str]) -> np.ndarray:
    """Parse a 3MF transform (12 values) into a 4x4 matrix."""
    if not transform:
        return np.eye(4)
    vals = [float(v) for v in transform.split()]
    if len(vals) != 12:
        raise ValueError(f"Invalid 3MF transform ({len(vals)} values): {transform}")

    # 3MF convention: 3x4 row-major. Rebuild a matrix suitable for column vectors.
    m00, m01, m02, m10, m11, m12, m20, m21, m22, m30, m31, m32 = vals
    return np.array(
        [
            [m00, m10, m20, m30],
            [m01, m11, m21, m31],
            [m02, m12, m22, m32],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


def apply_transform(vertices: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    homo = np.column_stack([vertices, np.ones(len(vertices))])
    return (matrix @ homo.T).T[:, :3]


def color_from_table(color_tables: Dict[str, List[str]], pid: Optional[str], pindex: int, fallback: str) -> str:
    if pid in color_tables and 0 <= pindex < len(color_tables[pid]):
        return color_tables[pid][pindex]
    return fallback


def read_3mf_model(path: Path) -> Tuple[Dict[str, MeshObject], List[Tuple[str, np.ndarray]]]:
    with zipfile.ZipFile(path, "r") as zf:
        model_name = next((n for n in zf.namelist() if n.endswith(".model")), None)
        if model_name is None:
            raise RuntimeError("The 3MF file does not contain a .model file.")
        root = ET.fromstring(zf.read(model_name))

    resources = root.find(f"{CORE_NS}resources")
    if resources is None:
        raise RuntimeError("3MF is missing the <resources> section.")

    color_tables: Dict[str, List[str]] = {}
    for child in list(resources):
        table_id = child.attrib.get("id")
        if not table_id:
            continue
        child_kind = local_name(child.tag).lower()
        if child_kind == "basematerials":
            # Be tolerant: LaserProg and several 3MF writers use the material
            # namespace for basematerials, while some readers expect the core
            # namespace. Local-name parsing keeps both variants compatible.
            color_tables[table_id] = [
                base.attrib.get("displaycolor", "#B0B0B0FF")
                for base in list(child)
                if local_name(base.tag).lower() == "base"
            ]
        elif child_kind == "colorgroup":
            color_tables[table_id] = [
                color.attrib.get("color", "#B0B0B0FF")
                for color in list(child)
                if local_name(color.tag).lower() == "color"
            ]

    objects: Dict[str, MeshObject] = {}
    for obj in resources.findall(f"{CORE_NS}object"):
        oid = obj.attrib["id"]
        obj_pid = obj.attrib.get("pid")
        obj_pindex = int(obj.attrib.get("pindex", "0"))
        obj_color = color_from_table(color_tables, obj_pid, obj_pindex, "#B0B0B0FF")

        mesh_object = MeshObject(object_id=oid, color=obj_color)
        mesh = obj.find(f"{CORE_NS}mesh")
        if mesh is not None:
            verts_node = mesh.find(f"{CORE_NS}vertices")
            tris_node = mesh.find(f"{CORE_NS}triangles")
            verts: List[List[float]] = []
            tris: List[List[int]] = []
            tri_colors: List[str] = []

            if verts_node is not None:
                for v in verts_node.findall(f"{CORE_NS}vertex"):
                    verts.append([float(v.attrib["x"]), float(v.attrib["y"]), float(v.attrib["z"])])

            if tris_node is not None:
                for t in tris_node.findall(f"{CORE_NS}triangle"):
                    tris.append([int(t.attrib["v1"]), int(t.attrib["v2"]), int(t.attrib["v3"])])

                    # Per-triangle color if available. In 3MF, p1/p2/p3 may differ.
                    # For this laser pipeline, use p1 as the dominant triangle color.
                    tri_pid = t.attrib.get("pid", obj_pid)
                    tri_pindex = int(t.attrib.get("p1", t.attrib.get("pindex", str(obj_pindex))))
                    tri_colors.append(color_from_table(color_tables, tri_pid, tri_pindex, obj_color))

            mesh_object.vertices = np.array(verts, dtype=float)
            mesh_object.triangles = np.array(tris, dtype=int)
            mesh_object.triangle_colors = tri_colors

        comps = obj.find(f"{CORE_NS}components")
        if comps is not None:
            for comp in comps.findall(f"{CORE_NS}component"):
                mesh_object.components.append((comp.attrib["objectid"], parse_transform(comp.attrib.get("transform"))))

        objects[oid] = mesh_object

    build_items: List[Tuple[str, np.ndarray]] = []
    build = root.find(f"{CORE_NS}build")
    if build is not None:
        for item in build.findall(f"{CORE_NS}item"):
            build_items.append((item.attrib["objectid"], parse_transform(item.attrib.get("transform"))))

    return objects, build_items


def resolve_object(
    objects: Dict[str, MeshObject],
    object_id: str,
    matrix: np.ndarray,
) -> List[Tuple[str, np.ndarray, np.ndarray, List[str], str]]:
    obj = objects[object_id]
    out: List[Tuple[str, np.ndarray, np.ndarray, List[str], str]] = []

    if len(obj.triangles):
        out.append((object_id, apply_transform(obj.vertices, matrix), obj.triangles, obj.triangle_colors, obj.color))

    for child_id, child_matrix in obj.components:
        out.extend(resolve_object(objects, child_id, matrix @ child_matrix))

    return out


# -----------------------------
# 2D geometry
# -----------------------------

def normalize_color(c: str) -> str:
    c = c.strip()
    if not c.startswith("#"):
        return "#B0B0B0"
    return c[:7]


def color_kind(c: str) -> str:
    """Exporter role convention: green = outline, red = fill, other = ignore."""
    s = normalize_color(c).lower()
    try:
        r, g, b = int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)
    except Exception:
        return ENGRAVING_ROLE_IGNORE
    if g > r and g > b:
        return ENGRAVING_ROLE_OUTLINE
    if r > g and r > b:
        return ENGRAVING_ROLE_FILL
    return ENGRAVING_ROLE_IGNORE


def iter_polygons(geom) -> Iterable[Polygon]:
    if geom is None or geom.is_empty:
        return
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon):
        yield from geom.geoms
    else:
        try:
            yield from geom.geoms
        except AttributeError:
            return


def safe_buffer(geom, offset_mm: float):
    if geom is None or geom.is_empty or abs(offset_mm) < 1e-12:
        return geom
    out = geom.buffer(offset_mm, join_style=2, mitre_limit=5.0)
    if out.is_empty:
        return geom
    return out


def footprint_from_top_triangles(
    vertices: np.ndarray,
    triangles: np.ndarray,
    triangle_colors: List[str],
    normal_z_threshold: float,
    fallback_color: str,
) -> Dict[str, Polygon | MultiPolygon]:
    polys_by_color: Dict[str, List[Polygon]] = {}

    for i, tri in enumerate(triangles):
        p = vertices[tri]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        norm = np.linalg.norm(n)
        if norm == 0:
            continue
        n = n / norm
        if n[2] < normal_z_threshold:
            continue

        poly = Polygon([(float(x), float(y)) for x, y, _z in p])
        if poly.is_valid and poly.area > 1e-9:
            color = triangle_colors[i] if i < len(triangle_colors) else fallback_color
            polys_by_color.setdefault(normalize_color(color), []).append(poly)

    merged: Dict[str, Polygon | MultiPolygon] = {}
    for color, polys in polys_by_color.items():
        if polys:
            merged[color] = unary_union(polys)
    return merged


def load_instances(path: Path, cfg: RenderConfig) -> List[Instance2D]:
    objects, build_items = read_3mf_model(path)
    instances: List[Instance2D] = []

    for root_id, matrix in build_items:
        for oid, vertices, triangles, triangle_colors, fallback_color in resolve_object(objects, root_id, matrix):
            by_color = footprint_from_top_triangles(
                vertices,
                triangles,
                triangle_colors,
                cfg.normal_z_threshold,
                fallback_color,
            )
            if not by_color:
                continue
            height = float(vertices[:, 2].max() - vertices[:, 2].min())
            for color, footprint in by_color.items():
                if footprint is not None and not footprint.is_empty:
                    instances.append(Instance2D(oid, color, footprint, height))

    return instances


def union_by_color(instances: List[Instance2D]) -> List[Tuple[str, Polygon | MultiPolygon]]:
    groups: Dict[str, List[Polygon | MultiPolygon]] = {}
    for inst in instances:
        groups.setdefault(normalize_color(inst.color), []).append(inst.footprint)

    def sort_key(item):
        color, _ = item
        return {"ignore": 0, "other": 0, "outline": 1, "fill": 2}.get(color_kind(color), 0)

    merged = []
    for color, geoms in sorted(groups.items(), key=sort_key):
        merged.append((color, unary_union(geoms)))
    return merged


def union_by_operation(instances: List[Instance2D], kind_name: str):
    geoms = [inst.footprint for inst in instances if color_kind(inst.color) == kind_name]
    if not geoms:
        return None
    return unary_union(geoms)

def union_by_height(instances: List[Instance2D], precision: int = 3) -> List[Tuple[float, Polygon | MultiPolygon]]:
    """Merge footprints with the same thickness for the thickness view."""
    groups: Dict[float, List[Polygon | MultiPolygon]] = {}
    for inst in instances:
        if inst.footprint is None or inst.footprint.is_empty:
            continue
        height = round(float(inst.height), precision)
        groups.setdefault(height, []).append(inst.footprint)

    merged: List[Tuple[float, Polygon | MultiPolygon]] = []
    for height in sorted(groups.keys(), reverse=True):
        geom = unary_union(groups[height])
        if geom is not None and not geom.is_empty:
            merged.append((height, geom))
    return merged


# -----------------------------
# Pillow rendering
# -----------------------------

def global_bounds(instances: List[Instance2D]) -> Tuple[float, float, float, float]:
    bounds = [inst.footprint.bounds for inst in instances if inst.footprint is not None and not inst.footprint.is_empty]
    if not bounds:
        raise RuntimeError("No valid 2D geometry.")
    minx = min(b[0] for b in bounds)
    miny = min(b[1] for b in bounds)
    maxx = max(b[2] for b in bounds)
    maxy = max(b[3] for b in bounds)
    return minx, miny, maxx, maxy


class CanvasTransform:
    def __init__(self, bounds: Tuple[float, float, float, float], cfg: RenderConfig):
        minx, miny, maxx, maxy = bounds
        w_mm = max(maxx - minx, 1e-6)
        h_mm = max(maxy - miny, 1e-6)
        margin = max(w_mm, h_mm) * cfg.page_margin_ratio

        self.minx = minx - margin
        self.miny = miny - margin
        self.maxx = maxx + margin
        self.maxy = maxy + margin

        physical_scale = cfg.dpi / 25.4
        out_w = int(round((self.maxx - self.minx) * physical_scale))
        out_h = int(round((self.maxy - self.miny) * physical_scale))

        # Avoid tiny images for small tests.
        scale_boost = max(1.0, cfg.min_output_px / max(out_w, out_h, 1))
        self.scale = physical_scale * scale_boost
        self.width = max(10, int(round((self.maxx - self.minx) * self.scale)))
        self.height = max(10, int(round((self.maxy - self.miny) * self.scale)))

    def pt(self, xy: Tuple[float, float]) -> Tuple[int, int]:
        x, y = xy
        px = int(round((x - self.minx) * self.scale))
        py = int(round((self.maxy - y) * self.scale))
        return px, py

    def mm_to_px(self, mm: float) -> int:
        return max(1, int(round(mm * self.scale)))


def color_to_rgb(c: str) -> Tuple[int, int, int]:
    s = normalize_color(c)
    try:
        return int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)
    except Exception:
        return 176, 176, 176


def draw_filled_polygon(draw: ImageDraw.ImageDraw, poly: Polygon, tr: CanvasTransform, fill, outline=None, width=1):
    exterior = [tr.pt((x, y)) for x, y in poly.exterior.coords]
    draw.polygon(exterior, fill=fill)
    if outline is not None:
        draw.line(exterior, fill=outline, width=width, joint="curve")
    for interior in poly.interiors:
        hole = [tr.pt((x, y)) for x, y in interior.coords]
        draw.polygon(hole, fill="white")
        if outline is not None:
            draw.line(hole, fill=outline, width=width, joint="curve")


def draw_outline_polygon(draw: ImageDraw.ImageDraw, poly: Polygon, tr: CanvasTransform, outline="black", width=1):
    exterior = [tr.pt((x, y)) for x, y in poly.exterior.coords]
    draw.line(exterior, fill=outline, width=width, joint="curve")
    for interior in poly.interiors:
        hole = [tr.pt((x, y)) for x, y in interior.coords]
        draw.line(hole, fill=outline, width=width, joint="curve")


def load_font(size_px: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size_px)
    return ImageFont.load_default()


def render_top_down(instances: List[Instance2D], cfg: RenderConfig) -> Image.Image:
    tr = CanvasTransform(global_bounds(instances), cfg)
    img = Image.new("RGB", (tr.width, tr.height), "white")
    draw = ImageDraw.Draw(img)
    edge_px = tr.mm_to_px(0.10)

    # Union before drawing: no internal borders between overlapping/touching parts of the same color.
    for color, geom in union_by_color(instances):
        fill = color_to_rgb(color)
        for poly in iter_polygons(geom):
            draw_filled_polygon(draw, poly, tr, fill=fill, outline="black", width=edge_px)
    return img


def render_laser_bw(instances: List[Instance2D], cfg: RenderConfig) -> Image.Image:
    tr = CanvasTransform(global_bounds(instances), cfg)
    img = Image.new("RGB", (tr.width, tr.height), "white")
    draw = ImageDraw.Draw(img)

    fill_geom = union_by_operation(instances, "fill")
    if fill_geom is not None and not fill_geom.is_empty:
        fill_geom = safe_buffer(fill_geom, cfg.fill_margin_mm)
        edge_px = tr.mm_to_px(cfg.fill_edge_width_mm)
        for poly in iter_polygons(fill_geom):
            draw_filled_polygon(draw, poly, tr, fill="black", outline="black", width=edge_px)

    outline_geom = union_by_operation(instances, "outline")
    if outline_geom is not None and not outline_geom.is_empty:
        outline_geom = safe_buffer(outline_geom, cfg.contour_margin_mm)
        contour_px = tr.mm_to_px(cfg.contour_width_mm)
        for poly in iter_polygons(outline_geom):
            draw_outline_polygon(draw, poly, tr, outline="black", width=contour_px)

    return img


def render_thickness(instances: List[Instance2D], cfg: RenderConfig) -> Image.Image:
    tr = CanvasTransform(global_bounds(instances), cfg)
    img = Image.new("RGB", (tr.width, tr.height), "white")
    draw = ImageDraw.Draw(img)
    font = load_font(cfg.label_font_size_px)
    contour_px = tr.mm_to_px(cfg.contour_width_mm)

    # Union before rendering: we do not want one outline per 3MF instance.
    # Merge same-height areas, then place one label per merged island.
    for height, geom in union_by_height(instances):
        for poly in iter_polygons(geom):
            draw_outline_polygon(draw, poly, tr, outline="black", width=contour_px)
            p = poly.representative_point()
            x, y = tr.pt((p.x, p.y))
            text = f"{height:.2f} mm"
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            pad = max(3, int(0.25 * th))
            box = [x - tw // 2 - pad, y - th // 2 - pad, x + tw // 2 + pad, y + th // 2 + pad]
            draw.rounded_rectangle(box, radius=pad, fill="white", outline="black", width=1)
            draw.text((x - tw // 2, y - th // 2), text, fill="black", font=font)

    return img



# -----------------------------
# SVG / vector export
# -----------------------------

_SVG_COORD_GRID_MM = 0.001
_SVG_AREA_EPSILON_MM2 = 1.0e-8


def _svg_number(value: float) -> str:
    """Compact, locale-independent number formatting for SVG coordinates."""
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def _snap_svg_coordinate(value: float) -> float:
    """Snap exported path coordinates to a laser-safe micron grid.

    Shapely/3MF triangulation can leave vertices that differ by a few floating
    point ulps.  Those micro-segments are invisible in a preview but can make a
    CAM importer optimise a cut path differently.  A 0.001 mm grid is far below
    diode-laser positioning repeatability while keeping files deterministic.
    """

    grid = float(_SVG_COORD_GRID_MM)
    if grid <= 0.0:
        return float(value)
    return round(float(value) / grid) * grid


def _svg_point(x: float, y: float, tr: CanvasTransform) -> Tuple[float, float]:
    """Convert model millimetres to the SVG canvas coordinate system."""
    return _snap_svg_coordinate(float(x) - tr.minx), _snap_svg_coordinate(tr.maxy - float(y))


def _signed_svg_area(points: Iterable[Tuple[float, float]]) -> float:
    pts = tuple((float(x), float(y)) for x, y in points)
    if len(pts) < 3:
        return 0.0
    return 0.5 * sum(
        pts[index][0] * pts[(index + 1) % len(pts)][1]
        - pts[(index + 1) % len(pts)][0] * pts[index][1]
        for index in range(len(pts))
    )


def _clean_svg_ring_points(ring, tr: CanvasTransform) -> Tuple[Tuple[float, float], ...]:
    """Return a simple SVG ring point list with no closing duplicate.

    Falcon Design Space is usually tolerant, but dense Plan Tracer motifs can
    export many tiny collinear segments after boolean repairs.  Keep corners,
    drop duplicated/zero-length segments and drop only genuinely collinear
    middle vertices.  This reduces repeated laser passes on the same line.
    """

    raw_coords = list(getattr(ring, "coords", ()) or ())
    if len(raw_coords) < 4:
        return ()
    points: List[Tuple[float, float]] = []
    tol = max(float(_SVG_COORD_GRID_MM) * 0.5, 1.0e-9)
    tol_sq = tol * tol
    for x, y in raw_coords:
        point = _svg_point(float(x), float(y), tr)
        if points and (points[-1][0] - point[0]) ** 2 + (points[-1][1] - point[1]) ** 2 <= tol_sq:
            continue
        points.append(point)
    if len(points) > 1 and (points[0][0] - points[-1][0]) ** 2 + (points[0][1] - points[-1][1]) ** 2 <= tol_sq:
        points.pop()
    if len(points) < 3:
        return ()

    changed = True
    while changed and len(points) > 3:
        changed = False
        cleaned: List[Tuple[float, float]] = []
        count = len(points)
        for index, current in enumerate(points):
            previous = points[(index - 1) % count]
            following = points[(index + 1) % count]
            ax = current[0] - previous[0]
            ay = current[1] - previous[1]
            bx = following[0] - current[0]
            by = following[1] - current[1]
            cross = ax * by - ay * bx
            dot = ax * bx + ay * by
            scale = max(abs(ax) + abs(ay), abs(bx) + abs(by), 1.0)
            # Only remove a point when it lies on a straight segment between its
            # neighbours.  Keep cusps and backtracking points because they can be
            # real motif details.
            if abs(cross) <= 1.0e-9 * scale * scale and dot >= -tol_sq:
                changed = True
                continue
            cleaned.append(current)
        if len(cleaned) < 3 or len(cleaned) == len(points):
            break
        points = cleaned
    if len(points) < 3 or abs(_signed_svg_area(points)) <= _SVG_AREA_EPSILON_MM2:
        return ()
    return tuple(points)


def _ring_svg_signature(points: Tuple[Tuple[float, float], ...]) -> Tuple[Tuple[float, float], ...]:
    """Return an orientation/rotation-insensitive signature for de-duplication."""

    if len(points) < 3:
        return ()

    def canonical(seq: Tuple[Tuple[float, float], ...]) -> Tuple[Tuple[float, float], ...]:
        start = min(range(len(seq)), key=lambda index: (seq[index][0], seq[index][1], index))
        return tuple(seq[start:] + seq[:start])

    forward = canonical(tuple(points))
    backward = canonical(tuple(reversed(points)))
    return min(forward, backward)


def _ring_points_to_svg_path(points: Tuple[Tuple[float, float], ...]) -> str:
    if len(points) < 3:
        return ""
    x0, y0 = points[0]
    parts = [f"M {_svg_number(x0)} {_svg_number(y0)}"]
    for sx, sy in points[1:]:
        parts.append(f"L {_svg_number(sx)} {_svg_number(sy)}")
    parts.append("Z")
    return " ".join(parts)


def _ring_to_svg_path(ring, tr: CanvasTransform) -> str:
    """Return one simple closed SVG path for a single ring.

    Falcon Design Space is more reliable when cut geometry is imported as plain
    independent path elements instead of one compound path with several
    subpaths.  Keep this helper intentionally conservative: absolute M/L/Z
    commands only, no transforms, no arcs, no relative commands.
    """
    return _ring_points_to_svg_path(_clean_svg_ring_points(ring, tr))


def _polygon_to_svg_path(poly: Polygon, tr: CanvasTransform) -> str:
    """Return one fill SVG path with subpaths for exterior + holes."""
    parts: List[str] = []
    rings = [poly.exterior, *list(poly.interiors)]
    for ring in rings:
        path = _ring_to_svg_path(ring, tr)
        if path:
            parts.append(path)
    return " ".join(parts)


def _clean_svg_geometry(geom):
    """Normalise polygonal geometry before SVG path extraction.

    Browser renderers are tolerant of tiny invalid slivers or self-touching
    rings, but laser CAM importers often are not.  ``buffer(0)`` is the safest
    Shapely repair available here because it does not introduce SVG-specific
    transforms and keeps the exported coordinates in millimetres.
    """
    if geom is None or getattr(geom, "is_empty", True):
        return geom
    try:
        if not bool(getattr(geom, "is_valid", True)):
            geom = geom.buffer(0)
        # A second no-op repair after import/union normalises GeometryCollections
        # and collapses sub-micron slivers created by triangle footprints.
        if geom is not None and not getattr(geom, "is_empty", True):
            geom = geom.buffer(0)
    except Exception:
        pass
    return geom


def _svg_paths_for_geometry(geom, tr: CanvasTransform) -> List[str]:
    paths: List[str] = []
    geom = _clean_svg_geometry(geom)
    if geom is None or geom.is_empty:
        return paths
    for poly in iter_polygons(geom):
        if poly is None or poly.is_empty:
            continue
        path = _polygon_to_svg_path(poly, tr)
        if path:
            paths.append(path)
    return paths


def _ring_area_mm2(ring) -> float:
    try:
        return abs(float(Polygon(list(ring.coords)).area))
    except Exception:
        return 0.0


def _svg_cut_paths_for_geometry(geom, tr: CanvasTransform) -> List[str]:
    """Return Falcon-safe cut paths as one SVG element per contour ring.

    Do not export cut geometry as compound paths.  A motif may contain many
    islands and holes; splitting every ring into its own closed path avoids
    importer ambiguity and gives CAM software a better chance to cut inner/small
    contours before larger outer contours.
    """
    candidates: List[Tuple[float, str, Tuple[Tuple[float, float], ...]]] = []
    seen: set[Tuple[Tuple[float, float], ...]] = set()
    geom = _clean_svg_geometry(geom)
    if geom is None or geom.is_empty:
        return []
    for poly in iter_polygons(geom):
        if poly is None or poly.is_empty:
            continue
        for ring in list(poly.interiors) + [poly.exterior]:
            points = _clean_svg_ring_points(ring, tr)
            if len(points) < 3:
                continue
            signature = _ring_svg_signature(points)
            if not signature or signature in seen:
                continue
            seen.add(signature)
            path = _ring_points_to_svg_path(points)
            if path:
                candidates.append((abs(_signed_svg_area(points)), path, signature))
    candidates.sort(key=lambda item: (item[0], item[2]))
    return [path for _area, path, _signature in candidates]


def export_falcon_svg(instances: List[Instance2D], cfg: RenderConfig, out: Path | str) -> Path:
    """Export a real-size SVG aimed at Falcon Design Space.

    The current PNG export rasterises the same data. This function keeps the
    geometry as vectors, in millimetres, so Falcon Design Space can import it
    as editable paths instead of tracing pixels.

    Color convention in the SVG:
    - green stroke: outline/cut vector paths;
    - red filled shapes: filled engraving/vector fill areas.
    """
    if not instances:
        raise RuntimeError("No 2D geometry to export.")

    out_path = Path(out)
    tr = CanvasTransform(global_bounds(instances), cfg)
    width_mm = float(tr.maxx - tr.minx)
    height_mm = float(tr.maxy - tr.miny)

    fill_geom = union_by_operation(instances, "fill")
    if fill_geom is not None and not fill_geom.is_empty:
        fill_geom = safe_buffer(fill_geom, cfg.fill_margin_mm)

    outline_geom = union_by_operation(instances, "outline")
    if outline_geom is not None and not outline_geom.is_empty:
        outline_geom = safe_buffer(outline_geom, cfg.contour_margin_mm)

    fill_paths = _svg_paths_for_geometry(fill_geom, tr)
    outline_paths = _svg_cut_paths_for_geometry(outline_geom, tr)

    if not fill_paths and not outline_paths:
        raise RuntimeError("No outline/fill geometry to export as SVG.")

    outline_width = max(float(cfg.contour_width_mm), 0.001)
    svg_lines: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            f'width="{_svg_number(width_mm)}mm" height="{_svg_number(height_mm)}mm" '
            f'viewBox="0 0 {_svg_number(width_mm)} {_svg_number(height_mm)}">'
        ),
        '  <title>LaserProg Studio - Falcon Design Space vector export</title>',
        '  <desc>Units are millimetres. Green strokes are plain closed outline/cut paths; red filled paths are filled engraving areas.</desc>',
        '  <metadata>{"generator":"LaserProg Studio","unit":"mm","target":"Falcon Design Space","outline":"green plain closed paths","fill":"red filled path","cut_path_mode":"one_svg_path_per_ring"}</metadata>',
    ]

    if fill_paths:
        svg_lines.append('  <g id="falcon_fill_engrave" fill="#E53935" stroke="none" fill-rule="evenodd">')
        for idx, path in enumerate(fill_paths, start=1):
            svg_lines.append(f'    <path id="fill_{idx:03d}" d="{path}"/>')
        svg_lines.append('  </g>')

    if outline_paths:
        svg_lines.append(
            f'  <g id="falcon_outline_cut" fill="none" stroke="#00C853" '
            f'stroke-width="{_svg_number(outline_width)}" stroke-linecap="round" stroke-linejoin="round">'
        )
        for idx, path in enumerate(outline_paths, start=1):
            svg_lines.append(f'    <path id="outline_{idx:03d}" d="{path}"/>')
        svg_lines.append('  </g>')

    svg_lines.append('</svg>')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(svg_lines) + "\n", encoding="utf-8")
    return out_path

# -----------------------------
# Tkinter interface - single window
# -----------------------------
