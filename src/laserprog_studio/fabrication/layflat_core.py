# -*- coding: utf-8 -*-
"""Tool: 3MF lay-flat and packing.

v9: lay-flat + triangle winding/topology repair.
By default, two parts that only touch are NOT merged.
Parts are oriented flat, placed on the ground, packed, then triangles are reoriented
outwards to avoid 3D Builder issues.
"""

from __future__ import annotations

import json
import re
import tkinter as tk
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from laserprog_studio.domain.work_model import WorkMesh

TOOL_ID = "layflat_arranger"
TOOL_NAME = "Lay flat / packing 3MF"

DEFAULT_SETTINGS = {
    "input_path": "",
    "use_loaded_model": False,
    "output_name": "layflat_parts",
    "output_dir": "",
    "spacing_mm": 5.0,
    "fusion_mode": "overlap",  # overlap | none | touch
    "minimum_overlap_mm": 0.01,
    "touch_tolerance_mm": 0.05,
    # Agencement : none | max_length | max_depth
    "packing_constraint": "max_length",
    "max_length_mm": 300.0,
    "max_depth_mm": 200.0,
    "allow_xy_rotation": True,
}

DEFAULT_COLOR = "#B8B8B8"
FUSION_LABELS = {
    "overlap": "overlap - overlap only",
    "none": "none - no merge",
    "touch": "touch - contact/tolerance",
}

PACKING_LABELS = {
    "none": "Free - no constraint",
    "max_length": "Max length X",
    "max_depth": "Max depth Y",
}


def safe_filename(name: str) -> str:
    name = name.strip() or "layflat_parts"
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)
    return name.strip("._") or "layflat_parts"


def fmt(v: float) -> str:
    if abs(v) < 1e-9:
        v = 0.0
    return f"{v:.6f}".rstrip("0").rstrip(".")


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_color(value: str | None) -> str:
    if not value:
        return DEFAULT_COLOR
    value = value.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.upper()
    if re.fullmatch(r"#[0-9a-fA-F]{8}", value):
        return value[:7].upper()
    return DEFAULT_COLOR


def parse_transform(transform: str | None) -> tuple[float, ...]:
    """3MF transform = 12 values: 3x4 affine matrix.
    x' = x*m0 + y*m3 + z*m6 + m9, etc.
    """
    if not transform:
        return (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
    vals = [float(x) for x in transform.replace(",", " ").split()]
    if len(vals) != 12:
        return (1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
    return tuple(vals)


def apply_transform(v: tuple[float, float, float], m: tuple[float, ...]) -> tuple[float, float, float]:
    x, y, z = v
    return (
        x * m[0] + y * m[3] + z * m[6] + m[9],
        x * m[1] + y * m[4] + z * m[7] + m[10],
        x * m[2] + y * m[5] + z * m[8] + m[11],
    )


@dataclass
class MeshObject:
    name: str
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]
    color: str = DEFAULT_COLOR
    source_object_id: str = ""

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


@dataclass
class PieceGroup:
    name: str
    objects: list[MeshObject] = field(default_factory=list)
    vertices: list[tuple[float, float, float]] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)
    color: str = DEFAULT_COLOR
    flat_width: float = 0.0
    flat_depth: float = 0.0
    flat_height: float = 0.0

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


class AutoSaveSettings:
    def __init__(self, path: Path, defaults: dict) -> None:
        self.path = path
        self.defaults = defaults.copy()
        self.data = self.defaults.copy()
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except Exception:
                pass
        else:
            self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")


def compose_transform(a: tuple[float, ...], b: tuple[float, ...]) -> tuple[float, ...]:
    """Compose two 3MF transforms.

    Result applies b first, then a: out(v) = apply_transform(apply_transform(v, b), a).
    3MF transform fields are stored as:
      x' = x*m0 + y*m3 + z*m6 + m9
      y' = x*m1 + y*m4 + z*m7 + m10
      z' = x*m2 + y*m5 + z*m8 + m11
    """
    # Convert to 4x4 row-vector style matrix, compose, convert back.
    A = [
        [a[0], a[1], a[2], 0.0],
        [a[3], a[4], a[5], 0.0],
        [a[6], a[7], a[8], 0.0],
        [a[9], a[10], a[11], 1.0],
    ]
    B = [
        [b[0], b[1], b[2], 0.0],
        [b[3], b[4], b[5], 0.0],
        [b[6], b[7], b[8], 0.0],
        [b[9], b[10], b[11], 1.0],
    ]
    # row-vector convention: v * B * A
    C = [[sum(B[i][k] * A[k][j] for k in range(4)) for j in range(4)] for i in range(4)]
    return (C[0][0], C[0][1], C[0][2], C[1][0], C[1][1], C[1][2], C[2][0], C[2][1], C[2][2], C[3][0], C[3][1], C[3][2])


def read_3mf_meshes(path: Path) -> list[MeshObject]:
    """Read meshes from a 3MF file.

    Compatible with files generated by this toolbox and with files re-saved by
    Microsoft 3D Builder. 3D Builder often wraps real mesh objects inside
    component objects; this reader resolves those components recursively and
    applies all transforms.
    """
    with zipfile.ZipFile(path, "r") as zf:
        model_name = "3D/3dmodel.model"
        if model_name not in zf.namelist():
            candidates = [n for n in zf.namelist() if n.lower().endswith(".model")]
            if not candidates:
                raise ValueError("No .model file found in the 3MF.")
            model_name = candidates[0]
        xml_data = zf.read(model_name)

    root = ET.fromstring(xml_data)

    material_colors: dict[tuple[str, str], str] = {}
    for elem in root.iter():
        if local_name(elem.tag) == "basematerials":
            pid = elem.attrib.get("id", "")
            index = 0
            for child in list(elem):
                if local_name(child.tag) == "base":
                    material_colors[(pid, str(index))] = parse_color(child.attrib.get("displaycolor"))
                    index += 1

    objects_by_id: dict[str, ET.Element] = {}
    for elem in root.iter():
        if local_name(elem.tag) == "object":
            oid = elem.attrib.get("id")
            if oid:
                objects_by_id[oid] = elem

    def direct_child(parent: ET.Element, child_name: str) -> ET.Element | None:
        return next((c for c in list(parent) if local_name(c.tag) == child_name), None)

    def mesh_from_object(oid: str, transform: tuple[float, ...], name_prefix: str, seen: set[str]) -> list[MeshObject]:
        if oid in seen:
            return []
        obj = objects_by_id.get(oid)
        if obj is None:
            return []

        # Case 1: real mesh object.
        mesh_elem = direct_child(obj, "mesh")
        if mesh_elem is not None:
            vertices_elem = direct_child(mesh_elem, "vertices")
            triangles_elem = direct_child(mesh_elem, "triangles")
            if vertices_elem is None or triangles_elem is None:
                return []

            vertices: list[tuple[float, float, float]] = []
            for v in list(vertices_elem):
                if local_name(v.tag) != "vertex":
                    continue
                raw = (float(v.attrib.get("x", "0")), float(v.attrib.get("y", "0")), float(v.attrib.get("z", "0")))
                vertices.append(apply_transform(raw, transform))

            triangles: list[tuple[int, int, int]] = []
            color = DEFAULT_COLOR

            # Fallback color can be stored on object-level pid/pindex in some 3MF variants.
            obj_pid = obj.attrib.get("pid")
            obj_pindex = obj.attrib.get("pindex")
            if obj_pid is not None and obj_pindex is not None:
                color = material_colors.get((obj_pid, obj_pindex), color)

            for t in list(triangles_elem):
                if local_name(t.tag) != "triangle":
                    continue
                try:
                    triangles.append((int(t.attrib["v1"]), int(t.attrib["v2"]), int(t.attrib["v3"])))
                except KeyError:
                    continue
                if color == DEFAULT_COLOR:
                    pid = t.attrib.get("pid")
                    p1 = t.attrib.get("p1") or t.attrib.get("p2") or t.attrib.get("p3")
                    if pid is not None and p1 is not None:
                        color = material_colors.get((pid, p1), color)

            if vertices and triangles:
                name = obj.attrib.get("name") or f"object_{oid}"
                return [MeshObject(f"{name_prefix}{name}", vertices, triangles, color, oid)]
            return []

        # Case 2: component object. This is what 3D Builder tends to create.
        components_elem = direct_child(obj, "components")
        if components_elem is not None:
            out: list[MeshObject] = []
            for idx, comp in enumerate(list(components_elem), start=1):
                if local_name(comp.tag) != "component":
                    continue
                child_oid = comp.attrib.get("objectid")
                if not child_oid:
                    continue
                child_transform = parse_transform(comp.attrib.get("transform"))
                combined = compose_transform(transform, child_transform)
                out.extend(mesh_from_object(child_oid, combined, f"{name_prefix}component_{oid}_{idx}_", seen | {oid}))
            return out

        return []

    build_items: list[tuple[str, tuple[float, ...]]] = []
    for elem in root.iter():
        if local_name(elem.tag) == "item":
            oid = elem.attrib.get("objectid")
            if oid:
                build_items.append((oid, parse_transform(elem.attrib.get("transform"))))

    if not build_items:
        # Fallback: expose every standalone mesh object. Avoid component wrappers here.
        build_items = [(oid, parse_transform(None)) for oid, obj in objects_by_id.items() if direct_child(obj, "mesh") is not None]

    meshes: list[MeshObject] = []
    for item_index, (oid, transform) in enumerate(build_items, start=1):
        item_meshes = mesh_from_object(oid, transform, f"item_{item_index}_", set())
        for j, mesh in enumerate(item_meshes, start=1):
            mesh.name = f"{mesh.name}_{j}"
            meshes.append(mesh)

    if not meshes:
        raise ValueError(
            "No readable mesh found in the 3MF. The file may contain only unresolved components or an exotic 3MF flavor."
        )
    return meshes

def axis_overlap_amount(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    return min(a_max, b_max) - max(a_min, b_min)


def bounds_touch(a: tuple[float, float, float, float, float, float], b: tuple[float, float, float, float, float, float], tol: float) -> bool:
    return not (
        a[3] < b[0] - tol or b[3] < a[0] - tol or
        a[4] < b[1] - tol or b[4] < a[1] - tol or
        a[5] < b[2] - tol or b[5] < a[2] - tol
    )


def bounds_overlap_strict(a: tuple[float, float, float, float, float, float], b: tuple[float, float, float, float, float, float], minimum_overlap: float) -> bool:
    return (
        axis_overlap_amount(a[0], a[3], b[0], b[3]) > minimum_overlap and
        axis_overlap_amount(a[1], a[4], b[1], b[4]) > minimum_overlap and
        axis_overlap_amount(a[2], a[5], b[2], b[5]) > minimum_overlap
    )


def group_objects(meshes: list[MeshObject], mode: str, tol: float, minimum_overlap: float) -> list[list[MeshObject]]:
    n = len(meshes)
    if mode == "none":
        return [[m] for m in meshes]

    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    bounds = [m.bounds() for m in meshes]
    for i in range(n):
        for j in range(i + 1, n):
            should_group = bounds_touch(bounds[i], bounds[j], tol) if mode == "touch" else bounds_overlap_strict(bounds[i], bounds[j], minimum_overlap)
            if should_group:
                union(i, j)

    groups: dict[int, list[MeshObject]] = {}
    for i, mesh in enumerate(meshes):
        groups.setdefault(find(i), []).append(mesh)
    return list(groups.values())


def merge_group(meshes: list[MeshObject], index: int) -> PieceGroup:
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    color = meshes[0].color if meshes else DEFAULT_COLOR
    for mesh in meshes:
        offset = len(vertices)
        vertices.extend(mesh.vertices)
        triangles.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.triangles)
    name = "+".join(m.name for m in meshes[:3])
    if len(meshes) > 3:
        name += f"_et_{len(meshes)-3}_autres"
    return PieceGroup(name=f"piece_{index}_{name}", objects=meshes, vertices=vertices, triangles=triangles, color=color)


def _permutation_parity(axes: tuple[int, int, int]) -> int:
    """Return +1 for a direct permutation, -1 for a mirrored permutation."""
    inv = 0
    vals = list(axes)
    for i in range(3):
        for j in range(i + 1, 3):
            if vals[i] > vals[j]:
                inv += 1
    return -1 if inv % 2 else 1


def _triangle_normal(a, b, c) -> tuple[float, float, float]:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    return (
        uy * vz - uz * vy,
        uz * vx - ux * vz,
        ux * vy - uy * vx,
    )


def _signed_volume(vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]]) -> float:
    """Signed volume of a closed mesh. Positive = coherent outward winding."""
    if not vertices or not triangles:
        return 0.0
    # Translate toward the local origin to improve numeric stability.
    ox = min(v[0] for v in vertices)
    oy = min(v[1] for v in vertices)
    oz = min(v[2] for v in vertices)
    vol = 0.0
    for ia, ib, ic in triangles:
        ax, ay, az = vertices[ia][0] - ox, vertices[ia][1] - oy, vertices[ia][2] - oz
        bx, by, bz = vertices[ib][0] - ox, vertices[ib][1] - oy, vertices[ib][2] - oz
        cx, cy, cz = vertices[ic][0] - ox, vertices[ic][1] - oy, vertices[ic][2] - oz
        vol += (
            ax * (by * cz - bz * cy)
            - ay * (bx * cz - bz * cx)
            + az * (bx * cy - by * cx)
        ) / 6.0
    return vol


def repair_triangle_winding(piece: PieceGroup) -> None:
    """Repair winding topologically.

    Old method: normal/mesh center test. It fails on parts with
    holes or concave shapes: some faces keep the same direction as their
    neighbor, which 3D Builder reports as an invalid object.

    Nouvelle methode :
    1. Propagation par aretes partagees : deux neighboring triangles doivent parcourir
       leur arete commune en sens oppose.
    2. For each connected component, then force a positive signed volume.
    """
    if not piece.vertices or not piece.triangles:
        return

    triangles = list(piece.triangles)
    edge_to_faces: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    # stored value: (face_index, edge_start, edge_end) with the current face direction
    for fi, (a, b, c) in enumerate(triangles):
        for u, v in ((a, b), (b, c), (c, a)):
            edge_to_faces.setdefault(tuple(sorted((u, v))), []).append((fi, u, v))

    adjacency: dict[int, list[tuple[int, bool]]] = {i: [] for i in range(len(triangles))}
    for _edge, faces in edge_to_faces.items():
        if len(faces) != 2:
            # Bord ouvert ou non-manifold : on ignore ici. 3D Builder pourra encore
            # repair, but do not break the file.
            continue
        (f1, u1, v1), (f2, u2, v2) = faces
        same_direction = (u1 == u2 and v1 == v2)
        # If both faces see the edge in the same direction, one of them must be reversed.
        adjacency[f1].append((f2, same_direction))
        adjacency[f2].append((f1, same_direction))

    flip = [False] * len(triangles)
    visited = [False] * len(triangles)
    components: list[list[int]] = []

    for start in range(len(triangles)):
        if visited[start]:
            continue
        stack = [start]
        visited[start] = True
        comp: list[int] = []
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt, same_direction in adjacency[cur]:
                required_flip = flip[cur] ^ same_direction
                if not visited[nxt]:
                    flip[nxt] = required_flip
                    visited[nxt] = True
                    stack.append(nxt)
        components.append(comp)

    repaired = []
    for i, (a, b, c) in enumerate(triangles):
        repaired.append((a, c, b) if flip[i] else (a, b, c))

    # Force outward winding only for genuinely closed manifold components.
    # A signed volume is not a reliable orientation test for an open sheet;
    # applying it there can reverse the user-visible side of the object.
    for comp in components:
        comp_set = set(comp)
        component_edge_counts: dict[tuple[int, int], int] = {}
        for face_index in comp:
            a, b, c = repaired[face_index]
            for u, v in ((a, b), (b, c), (c, a)):
                edge = tuple(sorted((u, v)))
                component_edge_counts[edge] = component_edge_counts.get(edge, 0) + 1
        is_closed_manifold = bool(component_edge_counts) and all(count == 2 for count in component_edge_counts.values())
        if not is_closed_manifold:
            continue
        comp_tris = [repaired[i] for i in comp_set]
        if _signed_volume(piece.vertices, comp_tris) < 0:
            for i in comp_set:
                a, b, c = repaired[i]
                repaired[i] = (a, c, b)

    piece.triangles = repaired


def _flat_orientation_frame(dims: list[float]) -> tuple[tuple[int, int, int], tuple[float, float, float]]:
    """Return a right-handed axis frame for lay-flat orientation.

    The historical implementation only permuted coordinates. Odd permutations
    have determinant -1 and therefore mirror the part. Reversing triangle
    winding repairs normals but cannot undo that geometric reflection.

    We keep the thin source axis mapped toward +Z and, when the selected axis
    permutation is odd, negate one in-plane output axis. The resulting transform
    always has determinant +1, so it is a proper rotation and preserves the
    object's handedness.
    """
    thin_axis = min(range(3), key=lambda i: dims[i])
    remaining = [i for i in range(3) if i != thin_axis]
    if dims[remaining[1]] > dims[remaining[0]]:
        remaining = [remaining[1], remaining[0]]
    axes = (remaining[0], remaining[1], thin_axis)
    parity = _permutation_parity(axes)
    # Keep Z positive so Lay Flat never chooses the opposite physical side.
    # Compensate an odd permutation with an in-plane sign only.
    signs = (1.0, float(parity), 1.0)
    return axes, signs


def orient_piece_flat(piece: PieceGroup) -> None:
    minx, miny, minz, maxx, maxy, maxz = piece.bounds()
    dims = [maxx - minx, maxy - miny, maxz - minz]
    axes, signs = _flat_orientation_frame(dims)

    oriented = []
    for v in piece.vertices:
        values = (v[0], v[1], v[2])
        oriented.append(
            (
                signs[0] * values[axes[0]],
                signs[1] * values[axes[1]],
                signs[2] * values[axes[2]],
            )
        )

    minx2 = min(x for x, _, _ in oriented)
    miny2 = min(y for _, y, _ in oriented)
    minz2 = min(z for _, _, z in oriented)
    normalized = [(x - minx2, y - miny2, z - minz2) for x, y, z in oriented]
    piece.vertices = normalized
    piece.flat_width = max(x for x, _, _ in normalized)
    piece.flat_depth = max(y for _, y, _ in normalized)
    piece.flat_height = max(z for _, _, z in normalized)
    repair_triangle_winding(piece)

def rotate_piece_xy_90(piece: PieceGroup) -> None:
    """Rotate an already flattened part by 90 degrees in the XY plane.

    ``(x, y, z) -> (y, width - x, z)`` is a proper rotation plus a
    translation (determinant +1). Triangle winding must therefore remain
    unchanged; reversing it here used to make open surfaces appear flipped.
    """
    w = piece.flat_width
    piece.vertices = [(vy, w - vx, vz) for vx, vy, vz in piece.vertices]
    piece.flat_width, piece.flat_depth = piece.flat_depth, piece.flat_width
    repair_triangle_winding(piece)


def _translate_piece(piece: PieceGroup, dx: float, dy: float) -> None:
    piece.vertices = [(vx + dx, vy + dy, vz) for vx, vy, vz in piece.vertices]


def _reset_piece_to_origin(piece: PieceGroup) -> None:
    minx, miny, minz, _maxx, _maxy, _maxz = piece.bounds()
    piece.vertices = [(vx - minx, vy - miny, vz - minz) for vx, vy, vz in piece.vertices]


def _piece_dims_after_rotation(piece: PieceGroup, rotated: bool) -> tuple[float, float]:
    return (piece.flat_depth, piece.flat_width) if rotated else (piece.flat_width, piece.flat_depth)


def pack_pieces_length_constrained(pieces: list[PieceGroup], spacing: float, max_length: float, allow_rotation: bool) -> list[PieceGroup]:
    """Row packing with X constraint.

    For each part, test existing rows, a new row,
    and optionally 90-degree rotation. Choose the placement that increases
    the total footprint the least. This is not a perfect solver, but it is
    significantly smarter than the old sequential placement.
    """
    if not pieces:
        return []
    max_length = max(max_length, max(min(p.flat_width, p.flat_depth) if allow_rotation else p.flat_width for p in pieces))
    ordered = sorted(pieces, key=lambda p: p.flat_width * p.flat_depth, reverse=True)
    rows: list[dict] = []

    for piece in ordered:
        best = None
        for rotated in ([False, True] if allow_rotation else [False]):
            w, d = _piece_dims_after_rotation(piece, rotated)
            if w > max_length + 1e-9:
                continue
            for ri, row in enumerate(rows):
                x0 = row["used"] + (spacing if row["used"] > 0 else 0.0)
                if x0 + w <= max_length + 1e-9:
                    new_h = max(row["height"], d)
                    total_depth = max((r["y"] + (new_h if i == ri else r["height"])) for i, r in enumerate(rows))
                    waste = max_length - (x0 + w)
                    score = (total_depth, new_h - row["height"], waste)
                    if best is None or score < best[0]:
                        best = (score, ri, x0, row["y"], rotated, w, d)
            y0 = 0.0 if not rows else max(r["y"] + r["height"] for r in rows) + spacing
            score = (y0 + d, d, max_length - w)
            if best is None or score < best[0]:
                best = (score, None, 0.0, y0, rotated, w, d)

        if best is None:
            w, d = piece.flat_width, piece.flat_depth
            y0 = 0.0 if not rows else max(r["y"] + r["height"] for r in rows) + spacing
            best = ((y0 + d, d, 0.0), None, 0.0, y0, False, w, d)

        _score, ri, x0, y0, rotated, w, d = best
        if rotated:
            rotate_piece_xy_90(piece)
        _reset_piece_to_origin(piece)
        _translate_piece(piece, x0, y0)
        if ri is None:
            rows.append({"y": y0, "height": d, "used": w})
        else:
            rows[ri]["height"] = max(rows[ri]["height"], d)
            rows[ri]["used"] = x0 + w
    return ordered


def pack_pieces_depth_constrained(pieces: list[PieceGroup], spacing: float, max_depth: float, allow_rotation: bool) -> list[PieceGroup]:
    """Column packing with Y constraint."""
    if not pieces:
        return []
    max_depth = max(max_depth, max(min(p.flat_width, p.flat_depth) if allow_rotation else p.flat_depth for p in pieces))
    ordered = sorted(pieces, key=lambda p: p.flat_width * p.flat_depth, reverse=True)
    cols: list[dict] = []

    for piece in ordered:
        best = None
        for rotated in ([False, True] if allow_rotation else [False]):
            w, d = _piece_dims_after_rotation(piece, rotated)
            if d > max_depth + 1e-9:
                continue
            for ci, col in enumerate(cols):
                y0 = col["used"] + (spacing if col["used"] > 0 else 0.0)
                if y0 + d <= max_depth + 1e-9:
                    new_w = max(col["width"], w)
                    total_length = max((c["x"] + (new_w if i == ci else c["width"])) for i, c in enumerate(cols))
                    waste = max_depth - (y0 + d)
                    score = (total_length, new_w - col["width"], waste)
                    if best is None or score < best[0]:
                        best = (score, ci, col["x"], y0, rotated, w, d)
            x0 = 0.0 if not cols else max(c["x"] + c["width"] for c in cols) + spacing
            score = (x0 + w, w, max_depth - d)
            if best is None or score < best[0]:
                best = (score, None, x0, 0.0, rotated, w, d)

        if best is None:
            w, d = piece.flat_width, piece.flat_depth
            x0 = 0.0 if not cols else max(c["x"] + c["width"] for c in cols) + spacing
            best = ((x0 + w, w, 0.0), None, x0, 0.0, False, w, d)

        _score, ci, x0, y0, rotated, w, d = best
        if rotated:
            rotate_piece_xy_90(piece)
        _reset_piece_to_origin(piece)
        _translate_piece(piece, x0, y0)
        if ci is None:
            cols.append({"x": x0, "width": w, "used": d})
        else:
            cols[ci]["width"] = max(cols[ci]["width"], w)
            cols[ci]["used"] = y0 + d
    return ordered


def pack_pieces_free(pieces: list[PieceGroup], spacing: float, allow_rotation: bool) -> list[PieceGroup]:
    if not pieces:
        return []
    total_area = sum(max(0.001, p.flat_width * p.flat_depth) for p in pieces)
    biggest = max(max(p.flat_width, p.flat_depth) for p in pieces)
    target = max(biggest, (total_area ** 0.5) * 1.25)
    return pack_pieces_length_constrained(pieces, spacing, target, allow_rotation)


def pack_pieces(
    pieces: list[PieceGroup],
    spacing: float,
    packing_constraint: str,
    max_length: float,
    max_depth: float,
    allow_rotation: bool,
) -> list[PieceGroup]:
    for p in pieces:
        _reset_piece_to_origin(p)
    if packing_constraint == "max_depth":
        return pack_pieces_depth_constrained(pieces, spacing, max_depth, allow_rotation)
    if packing_constraint == "none":
        return pack_pieces_free(pieces, spacing, allow_rotation)
    return pack_pieces_length_constrained(pieces, spacing, max_length, allow_rotation)


def build_3mf_model_xml(pieces: list[PieceGroup]) -> str:
    import uuid

    core_ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    material_ns = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
    production_ns = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<model unit="millimeter" xml:lang="fr-FR" xmlns="{core_ns}" xmlns:m="{material_ns}" xmlns:p="{production_ns}">')
    lines.append('  <metadata name="Application">Laser Toolbox - Layflat Arranger</metadata>')
    lines.append('  <resources>')
    material_id = 1
    lines.append(f'    <m:basematerials id="{material_id}">')
    for piece in pieces:
        lines.append(f'      <m:base name="{escape(piece.name)}" displaycolor="{piece.color}"/>')
    lines.append('    </m:basematerials>')
    for index, piece in enumerate(pieces, start=1):
        material_index = index - 1
        lines.append(f'    <object id="{index}" name="{escape(piece.name)}" type="model" p:UUID="{uuid.uuid4()}">')
        lines.append('      <mesh>')
        lines.append('        <vertices>')
        for vx, vy, vz in piece.vertices:
            lines.append(f'          <vertex x="{fmt(vx)}" y="{fmt(vy)}" z="{fmt(vz)}"/>')
        lines.append('        </vertices>')
        lines.append('        <triangles>')
        for a, b, c in piece.triangles:
            lines.append(f'          <triangle v1="{a}" v2="{b}" v3="{c}" pid="{material_id}" p1="{material_index}" p2="{material_index}" p3="{material_index}"/>')
        lines.append('        </triangles>')
        lines.append('      </mesh>')
        lines.append('    </object>')
    lines.append('  </resources>')
    lines.append(f'  <build p:UUID="{uuid.uuid4()}">')
    for index, piece in enumerate(pieces, start=1):
        lines.append(f'    <item objectid="{index}" partnumber="{escape(piece.name)}" p:UUID="{uuid.uuid4()}"/>')
    lines.append('  </build>')
    lines.append('</model>')
    return "\n".join(lines)


def write_3mf(path: Path, pieces: list[PieceGroup]) -> None:
    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
'''
    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", build_3mf_model_xml(pieces))


def process_3mf(
    input_path: Path,
    spacing: float,
    tolerance: float,
    fusion_mode: str = "overlap",
    minimum_overlap: float = 0.01,
    packing_constraint: str = "max_length",
    max_length: float = 300.0,
    max_depth: float = 200.0,
    allow_rotation: bool = True,
) -> tuple[list[PieceGroup], str]:
    meshes = read_3mf_meshes(input_path)
    groups = group_objects(meshes, fusion_mode, tolerance, minimum_overlap)
    pieces = [merge_group(group, i + 1) for i, group in enumerate(groups)]
    for piece in pieces:
        orient_piece_flat(piece)
    pieces = pack_pieces(pieces, spacing, packing_constraint, max_length, max_depth, allow_rotation)

    total_w = total_d = 0.0
    if pieces:
        xs = [x for p in pieces for x, _, _ in p.vertices]
        ys = [y for p in pieces for _, y, _ in p.vertices]
        total_w = max(xs) - min(xs)
        total_d = max(ys) - min(ys)

    lines = [
        f"Source objects read: {len(meshes)}",
        f"Parts detected after grouping: {len(pieces)}",
        f"Mode regroupement : {fusion_mode}",
        f"Recouvrement minimal : {minimum_overlap:.3f} mm",
        f"Contact tolerance: {tolerance:.3f} mm",
        f"Espacement au sol : {spacing:.3f} mm",
        f"Packing constraint: {packing_constraint}",
        f"Longueur max X : {max_length:.3f} mm",
        f"Profondeur max Y : {max_depth:.3f} mm",
        f"XY rotation allowed: {'yes' if allow_rotation else 'no'}",
        f"Packed footprint: {total_w:.3f} x {total_d:.3f} mm",
        "",
    ]
    for p in pieces:
        lines.append(f"- {p.name}")
        lines.append(f"  source objects in this part: {len(p.objects)}")
        lines.append(f"  flat dimensions: {p.flat_width:.3f} x {p.flat_depth:.3f} x {p.flat_height:.3f} mm")
    return pieces, "\n".join(lines)
