# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from .result import OperationResult


@dataclass(frozen=True)
class ReliefAnchor:
    mesh_index: int
    point: tuple[float, float, float]
    normal: tuple[float, float, float]


def _vec_sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _vec_cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _vec_dot(a, b) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _vec_len(a) -> float:
    return math.sqrt(max(_vec_dot(a, a), 0.0))


def _vec_norm(a, fallback=(0.0, 0.0, 1.0)):
    length = _vec_len(a)
    if length <= 1e-12:
        return tuple(float(v) for v in fallback)
    return (float(a[0]) / length, float(a[1]) / length, float(a[2]) / length)


def _basis_from_normal(normal: tuple[float, float, float], rotation_deg: float = 0.0):
    w = _vec_norm(normal)
    world_up = (0.0, 0.0, 1.0)
    if abs(_vec_dot(w, world_up)) > 0.92:
        world_up = (0.0, 1.0, 0.0)
    u = _vec_norm(_vec_cross(world_up, w), fallback=(1.0, 0.0, 0.0))
    v = _vec_norm(_vec_cross(w, u), fallback=(0.0, 1.0, 0.0))
    angle = math.radians(float(rotation_deg))
    ca, sa = math.cos(angle), math.sin(angle)
    ru = (u[0] * ca + v[0] * sa, u[1] * ca + v[1] * sa, u[2] * ca + v[2] * sa)
    rv = (-u[0] * sa + v[0] * ca, -u[1] * sa + v[1] * ca, -u[2] * sa + v[2] * ca)
    return _vec_norm(ru), _vec_norm(rv), w


def triangle_normal(mesh: Any, triangle_index: int) -> tuple[float, float, float]:
    try:
        tri = getattr(mesh, "triangles", [])[int(triangle_index)]
        verts = getattr(mesh, "vertices", [])
        a, b, c = verts[int(tri[0])], verts[int(tri[1])], verts[int(tri[2])]
        return _vec_norm(_vec_cross(_vec_sub(b, a), _vec_sub(c, a)))
    except Exception:
        return (0.0, 0.0, 1.0)


def _polydata_to_arrays(poly) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    try:
        pts = poly.GetPoints()
        if pts is None:
            return [], []
        for i in range(int(pts.GetNumberOfPoints())):
            p = pts.GetPoint(i)
            vertices.append((float(p[0]), float(p[1]), float(p[2])))
        for cid in range(int(poly.GetNumberOfCells())):
            cell = poly.GetCell(cid)
            ids = cell.GetPointIds()
            n = int(ids.GetNumberOfIds())
            if n == 3:
                triangles.append((int(ids.GetId(0)), int(ids.GetId(1)), int(ids.GetId(2))))
    except Exception:
        return vertices, triangles
    return vertices, triangles





def _normalize_font_name(font_family: Any | None) -> str:
    """Return a stable family name from Creator inspector/Qt values.

    Qt widgets can send either a plain family string or a QFont-like object.
    Keeping this coercion in geometry code prevents a font-combo event from
    reaching the text engine as ``<QFont ...>`` and failing in the preview path.
    """
    if font_family is None:
        return ""
    family_getter = getattr(font_family, "family", None)
    if callable(family_getter):
        try:
            value = family_getter()
            if value:
                return str(value).strip()
        except Exception:
            pass
    value = str(font_family or "").strip()
    # Defensive cleanup for repr-like values emitted by some test/adaptor stubs.
    for prefix in ("QFont(", "<PySide6.QtGui.QFont"):
        if value.startswith(prefix):
            return ""
    return value.strip('\\\"\' ')


def _polygon_signed_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        area += float(x1) * float(y2) - float(x2) * float(y1)
    return 0.5 * area


def _dedupe_ring(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for x, y in points:
        pt = (float(x), float(y))
        if not cleaned or abs(cleaned[-1][0] - pt[0]) > 1e-7 or abs(cleaned[-1][1] - pt[1]) > 1e-7:
            cleaned.append(pt)
    if len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) <= 1e-7 and abs(cleaned[0][1] - cleaned[-1][1]) <= 1e-7:
        cleaned.pop()
    return cleaned


def _make_font_text_geometry(text: str, depth: float, font_family: str) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    """Build closed extruded text geometry from a real system font.

    This is deliberately optional and imported lazily: headless CI and portable
    builds can still fall back to VTK vector text, while the desktop app uses the
    same Qt font engine as the UI. The resulting mesh is a closed triangulated
    prism, so changing ``font_family`` changes the actual geometry, not just the
    metadata.
    """
    from PySide6.QtGui import QFont, QPainterPath
    from PySide6.QtWidgets import QApplication
    from shapely.geometry import Polygon
    from shapely.ops import triangulate

    if QApplication.instance() is None:
        raise ValueError("Qt font engine is not initialised.")

    font_name = _normalize_font_name(font_family)
    if not font_name or font_name.lower() in {"vtk vectortext", "vector text", "vtk"}:
        raise ValueError("No concrete system font selected.")

    font = QFont(font_name)
    font.setPointSizeF(100.0)
    try:
        font.setStyleStrategy(QFont.PreferOutline)
    except Exception:
        pass
    path = QPainterPath()
    path.addText(0.0, 0.0, font, text or "Texte")
    polygons = path.toSubpathPolygons()
    rings: list[list[tuple[float, float]]] = []
    for poly in polygons:
        ring = _dedupe_ring([(float(p.x()), float(-p.y())) for p in poly])
        if len(ring) >= 3 and abs(_polygon_signed_area(ring)) > 1e-6:
            rings.append(ring)
    if not rings:
        raise ValueError(f"Could not extract outlines for font {font_name!r}.")
    point_count = sum(len(ring) for ring in rings)
    if len(rings) > 512 or point_count > 12000:
        raise ValueError(f"Font outline for {font_name!r} is too complex for live preview.")

    ring_polys = []
    for ring in rings:
        try:
            poly = Polygon(ring)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if not poly.is_empty and poly.area > 1e-6:
                ring_polys.append((ring, poly, abs(float(poly.area))))
        except Exception:
            continue
    if not ring_polys:
        raise ValueError(f"Could not polygonize font {font_name!r}.")

    ring_polys.sort(key=lambda item: item[2], reverse=True)
    depths: list[int] = []
    for _ring, poly, _area in ring_polys:
        parent_count = 0
        probe = poly.representative_point()
        for _other_ring, other_poly, other_area in ring_polys:
            if other_area <= _area:
                continue
            try:
                if other_poly.contains(probe):
                    parent_count += 1
            except Exception:
                pass
        depths.append(parent_count)

    outline_polys: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]], Polygon]] = []
    for i, (ring, poly, _area) in enumerate(ring_polys):
        if depths[i] % 2 != 0:
            continue
        holes: list[list[tuple[float, float]]] = []
        for j, (hole_ring, hole_poly, _hole_area) in enumerate(ring_polys):
            if depths[j] != depths[i] + 1:
                continue
            try:
                if poly.contains(hole_poly.representative_point()):
                    holes.append(hole_ring)
            except Exception:
                pass
        try:
            solid = Polygon(ring, holes)
            if not solid.is_valid:
                solid = solid.buffer(0)
            if not solid.is_empty and solid.area > 1e-6:
                outline_polys.append((ring, holes, solid))
        except Exception:
            continue
    if not outline_polys:
        raise ValueError(f"Could not build filled glyphs for font {font_name!r}.")

    vertices: list[tuple[float, float, float]] = []
    index: dict[tuple[float, float, float], int] = {}
    z0 = 0.0
    z1 = max(float(depth), 0.001)

    def vid(x: float, y: float, z: float) -> int:
        key = (round(float(x), 6), round(float(y), 6), round(float(z), 6))
        existing = index.get(key)
        if existing is not None:
            return existing
        index[key] = len(vertices)
        vertices.append((float(x), float(y), float(z)))
        return index[key]

    triangles: list[tuple[int, int, int]] = []

    def orient_ring(ring: list[tuple[float, float]], *, ccw: bool) -> list[tuple[float, float]]:
        is_ccw = _polygon_signed_area(ring) > 0.0
        return list(ring if is_ccw == ccw else reversed(ring))

    for outer, holes, solid in outline_polys:
        # Top and bottom caps are triangulated through shapely so real glyph
        # holes remain holes instead of being bridged by naive fans.
        for tri in triangulate(solid):
            try:
                if not solid.covers(tri.representative_point()) and not solid.contains(tri.centroid):
                    continue
                coords = list(tri.exterior.coords)[:3]
                if len(coords) != 3:
                    continue
                a, b, c = [(float(x), float(y)) for x, y in coords]
                if abs(_polygon_signed_area([a, b, c])) <= 1e-9:
                    continue
                top = (vid(a[0], a[1], z1), vid(b[0], b[1], z1), vid(c[0], c[1], z1))
                bottom = (vid(c[0], c[1], z0), vid(b[0], b[1], z0), vid(a[0], a[1], z0))
                triangles.append(top)
                triangles.append(bottom)
            except Exception:
                continue
        # Side walls: outer boundary and holes both need vertical quads.
        for ring, ccw in [(outer, True), *[(hole, False) for hole in holes]]:
            oriented = orient_ring(_dedupe_ring(ring), ccw=ccw)
            if len(oriented) < 3:
                continue
            for p1, p2 in zip(oriented, oriented[1:] + oriented[:1]):
                a0 = vid(p1[0], p1[1], z0)
                b0 = vid(p2[0], p2[1], z0)
                a1 = vid(p1[0], p1[1], z1)
                b1 = vid(p2[0], p2[1], z1)
                triangles.append((a0, b0, b1))
                triangles.append((a0, b1, a1))

    if not vertices or not triangles:
        raise ValueError(f"Could not generate 3D text for font {font_name!r}.")
    return vertices, triangles

def _closed_mesh_edge_report(triangles: list[tuple[int, int, int]]) -> tuple[int, int]:
    from collections import Counter

    edges: Counter[tuple[int, int]] = Counter()
    for a, b, c in triangles:
        for x, y in ((a, b), (b, c), (c, a)):
            if int(x) == int(y):
                continue
            edge = (int(x), int(y)) if int(x) < int(y) else (int(y), int(x))
            edges[edge] += 1
    boundary = sum(1 for count in edges.values() if count == 1)
    nonmanifold = sum(1 for count in edges.values() if count > 2)
    return boundary, nonmanifold

def _make_vtk_text_polydata(text: str, depth: float):
    import vtk

    src = vtk.vtkVectorText()
    src.SetText(text or "Texte")

    extrude = vtk.vtkLinearExtrusionFilter()
    extrude.SetInputConnection(src.GetOutputPort())
    extrude.SetExtrusionTypeToVectorExtrusion()
    extrude.SetVector(0.0, 0.0, 1.0)
    extrude.SetScaleFactor(max(float(depth), 0.001))
    extrude.CappingOn()

    tri1 = vtk.vtkTriangleFilter()
    tri1.SetInputConnection(extrude.GetOutputPort())

    clean1 = vtk.vtkCleanPolyData()
    clean1.SetInputConnection(tri1.GetOutputPort())

    # Some VTK vector-text glyphs contain tiny open boundaries after extrusion.
    # They render correctly but fail later in ADD/SUB manifold booleans. Filling
    # holes and normalising orientation keeps Relief/SUB objects usable as real
    # closed cutter/union volumes.
    fill = vtk.vtkFillHolesFilter()
    fill.SetInputConnection(clean1.GetOutputPort())
    fill.SetHoleSize(1000000.0)

    tri2 = vtk.vtkTriangleFilter()
    tri2.SetInputConnection(fill.GetOutputPort())

    normals = vtk.vtkPolyDataNormals()
    normals.SetInputConnection(tri2.GetOutputPort())
    normals.ConsistencyOn()
    normals.AutoOrientNormalsOn()
    normals.SplittingOff()

    clean2 = vtk.vtkCleanPolyData()
    clean2.SetInputConnection(normals.GetOutputPort())
    clean2.Update()
    return clean2.GetOutput()


def make_text_relief_mesh(
    *,
    text: str,
    anchor_point: tuple[float, float, float],
    normal: tuple[float, float, float],
    size_mm: float = 12.0,
    depth_mm: float = 1.5,
    rotation_deg: float = 0.0,
    mode: str = "relief",
    align: str = "center",
    font_family: Any | None = None,
    color: str | None = None,
) -> Any:
    """Create a separate 3D text WorkMesh oriented on a picked surface.

    A selected system font now changes the actual glyph outlines. VTK vector text
    remains the fallback for portable/headless environments or when the previous
    ``VTK VectorText`` sentinel is selected.
    """
    from laserprog_studio.domain.work_model import WorkMesh

    text = str(text or "Texte")
    depth = max(float(depth_mm), 0.001)
    requested_font = _normalize_font_name(font_family)
    if requested_font and requested_font.lower() not in {"vtk vectortext", "vector text", "vtk"}:
        try:
            vertices, triangles = _make_font_text_geometry(text, depth, requested_font)
        except Exception:
            poly = _make_vtk_text_polydata(text, depth)
            vertices, triangles = _polydata_to_arrays(poly)
    else:
        poly = _make_vtk_text_polydata(text, depth)
        vertices, triangles = _polydata_to_arrays(poly)
    if not vertices or not triangles:
        raise ValueError("Could not generate 3D text.")
    boundary_edges, nonmanifold_edges = _closed_mesh_edge_report(triangles)
    if boundary_edges or nonmanifold_edges:
        raise ValueError(
            "The generated text volume is not closed. "
            f"boundary_edges={boundary_edges}, nonmanifold_edges={nonmanifold_edges}"
        )

    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]
    zs = [p[2] for p in vertices]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z = min(zs)
    height = max(max_y - min_y, 1e-9)
    scale = max(float(size_mm), 0.001) / height

    if align == "left":
        ox = min_x
    elif align == "right":
        ox = max_x
    else:
        ox = (min_x + max_x) * 0.5
    oy = (min_y + max_y) * 0.5

    u, v, w = _basis_from_normal(normal, rotation_deg)
    sign = -1.0 if str(mode).lower() in {"cut", "subtract", "cut", "engraved", "negative", "inset"} else 1.0
    # Tiny offset prevents z-fighting in the preview. In subtract mode the solid is
    # pushed inward, making it usable as a future subtract/cut body.
    eps = 0.02
    ax, ay, az = [float(c) for c in anchor_point]
    out_vertices: list[tuple[float, float, float]] = []
    for x, y, z in vertices:
        lx = (float(x) - ox) * scale
        ly = (float(y) - oy) * scale
        lz = (float(z) - min_z) * scale
        px = ax + u[0] * lx + v[0] * ly + w[0] * (sign * lz + eps)
        py = ay + u[1] * lx + v[1] * ly + w[1] * (sign * lz + eps)
        pz = az + u[2] * lx + v[2] * ly + w[2] * (sign * lz + eps)
        out_vertices.append((float(px), float(py), float(pz)))

    name = f"Relief - {text[:24]}"
    mesh_color = color or ("#E06A2E" if sign < 0.0 else "#F2C14E")
    mesh = WorkMesh(name=name, vertices=out_vertices, triangles=triangles, color=mesh_color)
    try:
        mesh.material = {"relief_text": text, "font_family": requested_font or "VTK VectorText", "mode": mode}
    except Exception:
        pass
    return mesh


def add_text_relief_preview(meshes: list[Any], anchor: ReliefAnchor, **kwargs) -> OperationResult:
    out = copy.deepcopy(list(meshes))
    if not (0 <= int(anchor.mesh_index) < len(out)):
        return OperationResult.failure("Relief target part not found.", warnings=())
    try:
        text_mesh = make_text_relief_mesh(anchor_point=anchor.point, normal=anchor.normal, **kwargs)
        out.append(text_mesh)
        return OperationResult.success(out, warnings=("Relief added as a separate object. Use ADD/SUB to merge or subtract it.",))
    except Exception as exc:
        return OperationResult.failure(str(exc), warnings=())


__all__ = ["ReliefAnchor", "add_text_relief_preview", "make_text_relief_mesh", "triangle_normal"]
