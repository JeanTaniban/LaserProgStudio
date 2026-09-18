# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import WorkMesh

from .image_mask_relief_loading import _load_height_map
from .image_mask_relief_types import MaskReliefResult, MaskReliefStats

_Q_SCALE = 1_000_000.0


def _build_grayscale_heightfield_mesh(
    path: str | Path,
    *,
    max_height_mm: float,
    pixel_size_mm: float,
    invert: bool,
    max_grid_size: int,
    name: str,
    color: str,
) -> MaskReliefResult:
    """Grayscale raster pipeline: continuous heightfield mesh from raster cells."""

    pixel = max(1e-6, float(pixel_size_mm))
    heights, source_size, downsampled = _load_height_map(
        path,
        max_height_mm=max_height_mm,
        invert=bool(invert),
        binary=False,
        max_grid_size=int(max_grid_size),
    )
    rows = len(heights)
    cols = len(heights[0]) if rows else 0
    if rows <= 0 or cols <= 0:
        raise ValueError("Image vide ou illisible.")

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    vertex_scope = [0]
    vertex_index: dict[tuple[int, int, int, int], int] = {}

    def q(value: float) -> int:
        return int(round(float(value) * _Q_SCALE))

    def vertex(x: float, y: float, z: float) -> int:
        key = (int(vertex_scope[0]), q(x), q(y), q(z))
        idx = vertex_index.get(key)
        if idx is not None:
            return idx
        idx = len(vertices)
        vertex_index[key] = idx
        vertices.append((float(x), float(y), float(z)))
        return idx

    active = sum(1 for row in heights for h in row if float(h) > 0.0)
    total_w = cols * pixel
    total_h = rows * pixel
    x_origin = -total_w / 2.0
    y_origin = -total_h / 2.0
    active_cells = {(r, c) for r in range(rows) for c in range(cols) if float(heights[r][c]) > 0.0}

    def grid_xy(r_node: int, c_node: int) -> tuple[float, float]:
        return (x_origin + float(c_node) * pixel, y_origin + float(rows - r_node) * pixel)

    visited: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []
    for start_cell in sorted(active_cells):
        if start_cell in visited:
            continue
        stack = [start_cell]
        visited.add(start_cell)
        comp: set[tuple[int, int]] = set()
        while stack:
            rr, cc = stack.pop()
            comp.add((rr, cc))
            for nr, nc in ((rr - 1, cc), (rr + 1, cc), (rr, cc - 1), (rr, cc + 1)):
                if (nr, nc) in active_cells and (nr, nc) not in visited:
                    visited.add((nr, nc))
                    stack.append((nr, nc))
        components.append(comp)

    for component_id, component in enumerate(components, start=1):
        vertex_scope[0] = int(component_id)
        cells = sorted(component)
        corner_offsets = {
            "nw": (0, 0),
            "ne": (0, 1),
            "se": (1, 1),
            "sw": (1, 0),
        }
        parent: dict[tuple[int, int, str], tuple[int, int, str]] = {}

        def corner_key(r: int, c: int, name: str) -> tuple[int, int, str]:
            return (int(r), int(c), str(name))

        for r, c in cells:
            for name_key in corner_offsets:
                k = corner_key(r, c, name_key)
                parent[k] = k

        def find(k: tuple[int, int, str]) -> tuple[int, int, str]:
            root = parent[k]
            if root != k:
                root = find(root)
                parent[k] = root
            return root

        def union(a: tuple[int, int, str], b: tuple[int, int, str]) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for r, c in cells:
            if (r, c + 1) in component:  # east shared edge
                union(corner_key(r, c, "ne"), corner_key(r, c + 1, "nw"))
                union(corner_key(r, c, "se"), corner_key(r, c + 1, "sw"))
            if (r + 1, c) in component:  # south shared edge
                union(corner_key(r, c, "sw"), corner_key(r + 1, c, "nw"))
                union(corner_key(r, c, "se"), corner_key(r + 1, c, "ne"))

        groups: dict[tuple[int, int, str], list[tuple[int, int, str]]] = {}
        for k in list(parent):
            groups.setdefault(find(k), []).append(k)

        def new_vertex(x: float, y: float, z: float) -> int:
            idx = len(vertices)
            vertices.append((float(x), float(y), float(z)))
            return idx

        top_vertex_by_root: dict[tuple[int, int, str], int] = {}
        bottom_vertex_by_root: dict[tuple[int, int, str], int] = {}
        for root, members in groups.items():
            r0, c0, name0 = members[0]
            dr, dc = corner_offsets[name0]
            node = (r0 + dr, c0 + dc)
            vals = [float(heights[r][c]) for r, c, _name in members if float(heights[r][c]) > 0.0]
            z = float(sum(vals) / len(vals)) if vals else 0.0
            x, y = grid_xy(node[0], node[1])
            top_vertex_by_root[root] = new_vertex(x, y, z)
            bottom_vertex_by_root[root] = new_vertex(x, y, 0.0)

        def top_corner(r: int, c: int, name_key: str) -> int:
            return top_vertex_by_root[find(corner_key(r, c, name_key))]

        def bottom_corner(r: int, c: int, name_key: str) -> int:
            return bottom_vertex_by_root[find(corner_key(r, c, name_key))]

        def add_tri(a: int, b: int, c: int) -> None:
            if len({int(a), int(b), int(c)}) == 3:
                triangles.append((int(a), int(b), int(c)))

        def add_quad_idx(a: int, b: int, c: int, d: int) -> None:
            if len({int(a), int(b), int(c), int(d)}) < 4:
                return
            triangles.append((int(a), int(b), int(c)))
            triangles.append((int(a), int(c), int(d)))

        for r, c in cells:
            h = float(heights[r][c])
            nw = top_corner(r, c, "nw")
            ne = top_corner(r, c, "ne")
            se = top_corner(r, c, "se")
            sw = top_corner(r, c, "sw")
            bnw = bottom_corner(r, c, "nw")
            bne = bottom_corner(r, c, "ne")
            bse = bottom_corner(r, c, "se")
            bsw = bottom_corner(r, c, "sw")
            cx = x_origin + (float(c) + 0.5) * pixel
            cy = y_origin + (float(rows - r) - 0.5) * pixel
            center = new_vertex(cx, cy, h)

            add_tri(sw, se, center)
            add_tri(se, ne, center)
            add_tri(ne, nw, center)
            add_tri(nw, sw, center)

            add_tri(bnw, bne, bse)
            add_tri(bnw, bse, bsw)

            if (r, c - 1) not in component:  # west
                add_quad_idx(bnw, bsw, sw, nw)
            if (r, c + 1) not in component:  # east
                add_quad_idx(bse, bne, ne, se)
            if (r + 1, c) not in component:  # south
                add_quad_idx(bsw, bse, se, sw)
            if (r - 1, c) not in component:  # north
                add_quad_idx(bne, bnw, nw, ne)

    if active <= 0:
        raise ValueError("Le masque ne contient aucun pixel avec du relief. Essaie Invert ou une image plus sombre.")

    mesh = WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)
    try:
        setattr(mesh, "_lps_skip_boolean_merge", True)
    except Exception:
        pass
    stats = MaskReliefStats(
        source_width=int(source_size[0]),
        source_height=int(source_size[1]),
        width=cols,
        height=rows,
        active_pixels=active,
        vertices=len(vertices),
        triangles=len(triangles),
        max_height_mm=float(max_height_mm),
        pixel_size_mm=pixel,
        downsampled=bool(downsampled),
        binary=False,
        binary_threshold=0.5,
    )
    return MaskReliefResult(mesh=mesh, stats=stats)
