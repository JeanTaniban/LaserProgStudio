# -*- coding: utf-8 -*-
"""Tool: cubes + booleans (prototype).

Immediate goals:
- create cubes (actually rectangular boxes) in the ModelStore
- display/edit their transform parameters (position/rotation/scale) via A/B selection
- allow "add" (union) and "subtract" (A - B) between 2 selected solids

Important note:
The Toolbox viewer displays meshes (triangles) only.
Booleans use `manifold3d` (robust 3D booleans on closed/manifold meshes).
Without `manifold3d`, we refuse the operation (the old 2D fallback ignored an axis and
produced wrong results as soon as depth offsets were involved).
"""

from __future__ import annotations

import json
import math
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

import numpy as np

from laserprog_studio.domain.work_model import WorkMesh

TOOL_ID = "cube_boolean"
TOOL_NAME = "Cubes / booleans (prototype)"


DEFAULT_SETTINGS = {
    "next_id": 1,
    "default_color": "#7FB3FF",
    "default_pos": [0.0, 0.0, 0.0],
    "default_rot_deg": [0.0, 0.0, 0.0],
    "default_scale_mm": [10.0, 10.0, 10.0],
    # cube_id -> params
    "cubes": {},
}


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


def _fmt_float(v: float) -> str:
    if abs(v) < 1e-9:
        v = 0.0
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _parse_cube_id(name: str) -> str | None:
    # Convention : "xxx [cube:<id>]" (id = chiffre(s) ou uuid, mais on reste simple).
    s = name or ""
    i = s.find("[cube:")
    if i < 0:
        return None
    j = s.find("]", i)
    if j < 0:
        return None
    cid = s[i + len("[cube:") : j].strip()
    return cid or None


def _cube_name(label: str, cube_id: str) -> str:
    label = (label or "Cube").strip() or "Cube"
    return f"{label} [cube:{cube_id}]"


def _rot_matrix_xyz(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    # Convention: R = Rz @ Ry @ Rx (angles in degrees).
    rx = math.radians(float(rx_deg))
    ry = math.radians(float(ry_deg))
    rz = math.radians(float(rz_deg))

    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    rxm = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=float)
    rym = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=float)
    rzm = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=float)
    return (rzm @ rym) @ rxm


def _box_mesh_vertices_triangles() -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    # Unit cube centered at 0 (+/- 0.5), triangulation matches procedural_assembly.cube_mesh.
    v = [
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ]
    t = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return v, t


def make_cube_mesh(
    *,
    name: str,
    pos: tuple[float, float, float],
    rot_deg: tuple[float, float, float],
    scale_mm: tuple[float, float, float],
    color: str,
) -> WorkMesh:
    sx, sy, sz = (float(scale_mm[0]), float(scale_mm[1]), float(scale_mm[2]))
    if sx <= 0 or sy <= 0 or sz <= 0:
        raise ValueError("Invalid scale: all components must be > 0.")

    base_v, base_t = _box_mesh_vertices_triangles()
    r = _rot_matrix_xyz(rot_deg[0], rot_deg[1], rot_deg[2])
    p = np.array([float(pos[0]), float(pos[1]), float(pos[2])], dtype=float)

    vertices: list[tuple[float, float, float]] = []
    for x, y, z in base_v:
        local = np.array([x * sx, y * sy, z * sz], dtype=float)
        world = (r @ local) + p
        vertices.append((float(world[0]), float(world[1]), float(world[2])))

    return WorkMesh(name=name, vertices=vertices, triangles=list(base_t), color=str(color or "#B8B8B8"))


@dataclass(frozen=True)
class CubeParams:
    cube_id: str
    label: str
    pos: tuple[float, float, float]
    rot_deg: tuple[float, float, float]
    scale_mm: tuple[float, float, float]
    color: str

    @property
    def mesh_name(self) -> str:
        return _cube_name(self.label, self.cube_id)


def _as_float(s: str) -> float:
    return float((s or "").strip().replace(",", "."))


def _as_int(s: str) -> int:
    return int(float((s or "").strip().replace(",", ".")))


def _safe_color(s: str) -> str:
    v = (s or "").strip()
    if len(v) == 7 and v.startswith("#"):
        return v.upper()
    return "#B8B8B8"


def _cube_params_from_settings(settings: dict, cube_id: str) -> CubeParams | None:
    cubes = settings.get("cubes", {})
    if not isinstance(cubes, dict):
        return None
    raw = cubes.get(str(cube_id))
    if not isinstance(raw, dict):
        return None

    label = str(raw.get("label", f"Cube {cube_id}"))
    pos = raw.get("pos", [0.0, 0.0, 0.0])
    rot = raw.get("rot_deg", [0.0, 0.0, 0.0])
    scl = raw.get("scale_mm", [10.0, 10.0, 10.0])
    color = _safe_color(str(raw.get("color", settings.get("default_color", "#B8B8B8"))))

    def t3(x, default: float) -> tuple[float, float, float]:
        try:
            a, b, c = x
            return (float(a), float(b), float(c))
        except Exception:
            return (default, default, default)

    return CubeParams(
        cube_id=str(cube_id),
        label=label,
        pos=t3(pos, 0.0),
        rot_deg=t3(rot, 0.0),
        scale_mm=t3(scl, 10.0),
        color=color,
    )


def _write_cube_params_to_settings(settings: dict, params: CubeParams) -> None:
    cubes = settings.setdefault("cubes", {})
    if not isinstance(cubes, dict):
        settings["cubes"] = {}
        cubes = settings["cubes"]
    cubes[str(params.cube_id)] = {
        "label": str(params.label),
        "pos": [float(params.pos[0]), float(params.pos[1]), float(params.pos[2])],
        "rot_deg": [float(params.rot_deg[0]), float(params.rot_deg[1]), float(params.rot_deg[2])],
        "scale_mm": [float(params.scale_mm[0]), float(params.scale_mm[1]), float(params.scale_mm[2])],
        "color": str(params.color),
    }


def _cleanup_settings_cubes(settings: dict, meshes: list[WorkMesh]) -> None:
    cubes = settings.get("cubes", {})
    if not isinstance(cubes, dict):
        return
    present_ids: set[str] = set()
    for m in meshes:
        cid = _parse_cube_id(m.name)
        if cid:
            present_ids.add(str(cid))
    stale = [k for k in cubes.keys() if str(k) not in present_ids]
    for k in stale:
        try:
            del cubes[k]
        except Exception:
            pass


def _cube_basis_from_params(params: CubeParams):
    # Reuse PlankBasis from joint_builder to benefit from its helpers.
    from .joint_builder import PlankBasis

    r = _rot_matrix_xyz(params.rot_deg[0], params.rot_deg[1], params.rot_deg[2])
    # columns = local axes in world coordinates
    u = r @ np.array([1.0, 0.0, 0.0], dtype=float)
    v = r @ np.array([0.0, 1.0, 0.0], dtype=float)
    n = r @ np.array([0.0, 0.0, 1.0], dtype=float)
    origin = np.array([params.pos[0], params.pos[1], params.pos[2]], dtype=float)
    w_min = -float(params.scale_mm[2]) / 2.0
    w_max = +float(params.scale_mm[2]) / 2.0
    return PlankBasis(origin=origin, u=u, v=v, n=n, w_min=float(w_min), w_max=float(w_max))


def _bool_prism_2d(
    mesh_a: WorkMesh,
    mesh_b: WorkMesh,
    *,
    op: str,
    basis_a,
    basis_b,
    eps_parallel: float = 1.0,
    thickness_tol: float = 0.2,
) -> WorkMesh:
    """Boolean operation on two aligned prism solids.

    op: "union" or "difference".
    The result is re-extruded along basis_a.
    """
    from . import joint_builder as jb

    op = (op or "").strip().lower()
    if op not in {"union", "difference"}:
        raise ValueError(f"Unknown operation: {op!r}")

    n_a = jb._normalize(np.array(basis_a.n, dtype=float))
    n_b = jb._normalize(np.array(basis_b.n, dtype=float))
    cos_tol = float(math.cos(math.radians(float(abs(eps_parallel)))))
    if abs(float(np.dot(n_a, n_b))) < cos_tol:
        raise ValueError("Boolean: solids are not aligned (normals are not parallel).")

    ta = float(basis_a.thickness)
    tb = float(basis_b.thickness)
    if abs(ta - tb) > float(abs(thickness_tol)):
        raise ValueError(f"Boolean: different thicknesses (A={ta:.3f} mm, B={tb:.3f} mm).")

    # Footprints in A's basis.
    poly_a = jb.footprint_polygon(mesh_a, basis_a)
    poly_b = jb.footprint_polygon(mesh_b, basis_a)

    if op == "union":
        out = poly_a.union(poly_b)
    else:
        out = poly_a.difference(poly_b)

    poly_out = jb._clean_poly(out)
    if poly_out.is_empty or float(getattr(poly_out, "area", 0.0)) <= 1e-9:
        raise ValueError("Boolean: empty result.")

    name = mesh_a.name if op == "difference" else f"union({mesh_a.name},{mesh_b.name})"
    color = mesh_a.color
    return jb.extrude_polygon_to_mesh(name, poly_out, basis_a, color)


def _bool_mesh_3d_manifold(mesh_a: WorkMesh, mesh_b: WorkMesh, *, op: str) -> WorkMesh:
    """Robust 3D boolean via manifold3d (if installed)."""
    # Studio builds route through the shared boolean engine. It adds consistent
    # triangle winding repair, tiny-face cleanup and a small cutter margin for
    # tangent/copanar differences. The fallback below is kept for standalone
    # toolbox usage when laserprog_studio is not importable.
    try:
        from laserprog_studio.boolean_ops import boolean_mesh_3d
    except ImportError:
        boolean_mesh_3d = None

    # In Studio, the shared boolean engine is the topology authority.  Never
    # swallow an operation/validation failure and silently retry through the
    # legacy float32 path: that path does not enforce the same manifold status
    # contract and can turn a rejected Joint Builder result into geometry that
    # only fails at the *next* Union/Subtract.  The legacy implementation below
    # remains solely for standalone toolbox environments where the Studio module
    # itself cannot be imported.
    if boolean_mesh_3d is not None:
        return boolean_mesh_3d(
            mesh_a,
            mesh_b,
            operation=("union" if str(op).lower() == "union" else "difference"),
        )
    try:
        import manifold3d as m3d
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "The 'manifold3d' module is not installed.\n"
            "Install it (e.g. re-run install_dependencies.bat) to enable 3D booleans."
        ) from exc

    op = (op or "").strip().lower()
    if op not in {"union", "difference"}:
        raise ValueError(f"Unknown operation: {op!r}")

    # Convertit WorkMesh -> Manifold
    try:
        tri_a = np.asarray(mesh_a.triangles, dtype=np.int32)
        vp_a = np.asarray(mesh_a.vertices, dtype=np.float32)
        tri_b = np.asarray(mesh_b.triangles, dtype=np.int32)
        vp_b = np.asarray(mesh_b.vertices, dtype=np.float32)
    except Exception as exc:
        raise ValueError("3D boolean: invalid mesh (vertices/triangles).") from exc

    if tri_a.size == 0 or vp_a.size == 0:
        raise ValueError("3D boolean: mesh A is empty.")
    if tri_b.size == 0 or vp_b.size == 0:
        raise ValueError("3D boolean: mesh B is empty.")

    # Contrainte: vertex properties = positions (3 floats).
    if vp_a.ndim != 2 or vp_a.shape[1] < 3:
        raise ValueError("3D boolean: invalid vertices A (expected Nx3).")
    if vp_b.ndim != 2 or vp_b.shape[1] < 3:
        raise ValueError("3D boolean: invalid vertices B (expected Nx3).")

    vp_a = vp_a[:, :3].copy()
    vp_b = vp_b[:, :3].copy()

    # Repair inconsistent triangle winding before sending meshes to manifold3d.
    # This keeps old cylinders/cones usable: they can be watertight but still
    # interpreted as inverted/invalid by the boolean engine.
    try:
        from laserprog_studio.boolean_ops import _orient_triangles_for_manifold

        tri_a = _orient_triangles_for_manifold(vp_a, tri_a).astype(np.int32, copy=False)
        tri_b = _orient_triangles_for_manifold(vp_b, tri_b).astype(np.int32, copy=False)
    except Exception:
        pass

    try:
        meshgl_a = m3d.Mesh(tri_verts=tri_a, vert_properties=vp_a)
        meshgl_b = m3d.Mesh(tri_verts=tri_b, vert_properties=vp_b)
    except Exception as exc:
        raise ValueError("3D boolean: cannot convert to manifold3d.Mesh.") from exc

    # Best effort: fix some small manifoldness defects (if the API is available).
    for mg in (meshgl_a, meshgl_b):
        try:
            mg.merge()
        except Exception:
            pass

    try:
        ma = m3d.Manifold(meshgl_a)
        mb = m3d.Manifold(meshgl_b)
    except Exception as exc:
        raise ValueError(
            "3D boolean: non-manifold (or invalid) input for manifold3d.\n"
            "Tip: try with closed (watertight) solids."
        ) from exc

    try:
        if op == "union":
            mout = ma.add(mb) if hasattr(ma, "add") else (ma + mb)
            name = f"union({mesh_a.name},{mesh_b.name})"
        else:
            mout = ma.subtract(mb) if hasattr(ma, "subtract") else (ma - mb)
            name = mesh_a.name
    except Exception as exc:
        raise ValueError("3D boolean: operation failed (union/difference).") from exc

    try:
        out_mesh = mout.to_mesh()
        verts = np.asarray(out_mesh.vert_properties, dtype=float)
        tris = np.asarray(out_mesh.tri_verts, dtype=np.int32)
    except Exception as exc:
        raise ValueError("3D boolean: cannot convert result.") from exc

    if verts.ndim == 1:
        if verts.size % 3 != 0:
            raise ValueError("3D boolean: invalid vert_properties.")
        verts = verts.reshape((-1, 3))
    if tris.ndim == 1:
        if tris.size % 3 != 0:
            raise ValueError("3D boolean: invalid tri_verts.")
        tris = tris.reshape((-1, 3))

    if verts.ndim != 2 or verts.shape[1] < 3 or tris.ndim != 2 or tris.shape[1] != 3 or len(tris) == 0:
        raise ValueError("3D boolean: empty result.")

    vertices_out: list[tuple[float, float, float]] = [(float(x), float(y), float(z)) for x, y, z in verts[:, :3]]
    triangles_out: list[tuple[int, int, int]] = [(int(a), int(b), int(c)) for a, b, c in tris]
    return WorkMesh(name=name, vertices=vertices_out, triangles=triangles_out, color=mesh_a.color)


def _boolean(mesh_a: WorkMesh, mesh_b: WorkMesh, *, op: str, basis_a=None, basis_b=None) -> WorkMesh:
    """Booleans: require 3D (manifold3d) to avoid wrong results."""
    _ = basis_a
    _ = basis_b
    return _bool_mesh_3d_manifold(mesh_a, mesh_b, op=op)


class _TransformVars:
    def __init__(self) -> None:
        self.label = tk.StringVar()
        self.color = tk.StringVar()
        self.px = tk.StringVar()
        self.py = tk.StringVar()
        self.pz = tk.StringVar()
        self.rx = tk.StringVar()
        self.ry = tk.StringVar()
        self.rz = tk.StringVar()
        self.sx = tk.StringVar()
        self.sy = tk.StringVar()
        self.sz = tk.StringVar()

    def set_from_params(self, params: CubeParams) -> None:
        self.label.set(str(params.label))
        self.color.set(str(params.color))
        self.px.set(_fmt_float(params.pos[0]))
        self.py.set(_fmt_float(params.pos[1]))
        self.pz.set(_fmt_float(params.pos[2]))
        self.rx.set(_fmt_float(params.rot_deg[0]))
        self.ry.set(_fmt_float(params.rot_deg[1]))
        self.rz.set(_fmt_float(params.rot_deg[2]))
        self.sx.set(_fmt_float(params.scale_mm[0]))
        self.sy.set(_fmt_float(params.scale_mm[1]))
        self.sz.set(_fmt_float(params.scale_mm[2]))

    def set_empty(self) -> None:
        self.label.set("")
        self.color.set("")
        for v in (self.px, self.py, self.pz, self.rx, self.ry, self.rz, self.sx, self.sy, self.sz):
            v.set("")

    def read_params(self, cube_id: str) -> CubeParams:
        label = self.label.get().strip() or f"Cube {cube_id}"
        color = _safe_color(self.color.get().strip() or "#B8B8B8")
        pos = (_as_float(self.px.get()), _as_float(self.py.get()), _as_float(self.pz.get()))
        rot = (_as_float(self.rx.get()), _as_float(self.ry.get()), _as_float(self.rz.get()))
        scl = (_as_float(self.sx.get()), _as_float(self.sy.get()), _as_float(self.sz.get()))
        return CubeParams(cube_id=str(cube_id), label=label, pos=pos, rot_deg=rot, scale_mm=scl, color=color)


class ToolFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget, app_context) -> None:
        super().__init__(parent)
        self.context = app_context
        self.settings = AutoSaveSettings(self.context.settings_dir / f"{TOOL_ID}.json", DEFAULT_SETTINGS)

        self._sync_guard = False

        self.vars_new = _TransformVars()
        self.vars_a = _TransformVars()
        self.vars_b = _TransformVars()

        self._build_ui()
        self._load_defaults()

        self.context.model_store.subscribe(self._sync_from_selection)
        self._sync_from_selection()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Cubes / booleans (prototype)", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        self.selection_label = ttk.Label(self, text="", foreground="#444", justify="left")
        self.selection_label.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        body = ttk.Frame(self)
        body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=1)

        # New cube
        new_box = ttk.LabelFrame(body, text="New cube")
        new_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        new_box.columnconfigure(0, weight=1)
        self._build_transform_fields(new_box, self.vars_new, row0=0)
        ttk.Button(new_box, text="Add cube (preview)", command=self._add_cube).grid(
            row=13, column=0, sticky="ew", pady=(8, 0)
        )

        # A
        a_box = ttk.LabelFrame(body, text="Selection A")
        a_box.grid(row=0, column=1, sticky="nsew", padx=8)
        a_box.columnconfigure(0, weight=1)
        self._build_transform_fields(a_box, self.vars_a, row0=0)
        self.btn_update_a = ttk.Button(a_box, text="Update A (preview)", command=lambda: self._update_selected("a"))
        self.btn_update_a.grid(row=13, column=0, sticky="ew", pady=(8, 0))

        # B
        b_box = ttk.LabelFrame(body, text="Selection B")
        b_box.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        b_box.columnconfigure(0, weight=1)
        self._build_transform_fields(b_box, self.vars_b, row0=0)
        self.btn_update_b = ttk.Button(b_box, text="Update B (preview)", command=lambda: self._update_selected("b"))
        self.btn_update_b.grid(row=13, column=0, sticky="ew", pady=(8, 0))

        # Boolean ops
        ops = ttk.Frame(self)
        ops.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ops.columnconfigure(0, weight=1)
        ops.columnconfigure(1, weight=1)
        self.btn_union = ttk.Button(ops, text="Union (A U B) (preview)", command=self._op_union)
        self.btn_diff = ttk.Button(ops, text="Difference (A - B) (preview)", command=self._op_diff)
        self.btn_union.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.btn_diff.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _build_transform_fields(self, parent: tk.Widget, v: _TransformVars, *, row0: int) -> None:
        row = row0

        def add_line(lbl: str, a: tk.StringVar, b: tk.StringVar, c: tk.StringVar) -> None:
            nonlocal row
            line = ttk.Frame(parent)
            line.grid(row=row, column=0, sticky="ew", pady=2)
            line.columnconfigure(1, weight=1)
            ttk.Label(line, text=lbl, width=10).grid(row=0, column=0, sticky="w", padx=(0, 8))
            ttk.Entry(line, textvariable=a, width=9).grid(row=0, column=1, sticky="w")
            ttk.Entry(line, textvariable=b, width=9).grid(row=0, column=2, sticky="w", padx=(6, 0))
            ttk.Entry(line, textvariable=c, width=9).grid(row=0, column=3, sticky="w", padx=(6, 0))
            row += 1

        # Label + color
        line = ttk.Frame(parent)
        line.grid(row=row, column=0, sticky="ew", pady=2)
        line.columnconfigure(1, weight=1)
        ttk.Label(line, text="Name", width=10).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(line, textvariable=v.label).grid(row=0, column=1, columnspan=3, sticky="ew")
        row += 1

        line = ttk.Frame(parent)
        line.grid(row=row, column=0, sticky="ew", pady=2)
        line.columnconfigure(1, weight=1)
        ttk.Label(line, text="Color", width=10).grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(line, textvariable=v.color).grid(row=0, column=1, columnspan=3, sticky="ew")
        row += 1

        ttk.Separator(parent).grid(row=row, column=0, sticky="ew", pady=(6, 6))
        row += 1

        add_line("Pos (mm)", v.px, v.py, v.pz)
        add_line("Rot (deg)", v.rx, v.ry, v.rz)
        add_line("Scale (mm)", v.sx, v.sy, v.sz)

        ttk.Label(
            parent,
            text="Rotation: R = Rz @ Ry @ Rx (degrees).",
            foreground="#666",
            wraplength=260,
        ).grid(row=row, column=0, sticky="ew", pady=(6, 0))

    def _load_defaults(self) -> None:
        dpos = self.settings.data.get("default_pos", DEFAULT_SETTINGS["default_pos"])
        drot = self.settings.data.get("default_rot_deg", DEFAULT_SETTINGS["default_rot_deg"])
        dscl = self.settings.data.get("default_scale_mm", DEFAULT_SETTINGS["default_scale_mm"])
        col = str(self.settings.data.get("default_color", DEFAULT_SETTINGS["default_color"]))
        try:
            params = CubeParams(
                cube_id="0",
                label="Cube",
                pos=(float(dpos[0]), float(dpos[1]), float(dpos[2])),
                rot_deg=(float(drot[0]), float(drot[1]), float(drot[2])),
                scale_mm=(float(dscl[0]), float(dscl[1]), float(dscl[2])),
                color=_safe_color(col),
            )
        except Exception:
            params = CubeParams(
                cube_id="0",
                label="Cube",
                pos=(0.0, 0.0, 0.0),
                rot_deg=(0.0, 0.0, 0.0),
                scale_mm=(10.0, 10.0, 10.0),
                color="#B8B8B8",
            )
        self.vars_new.set_from_params(params)

    def _set_enabled(self, vars_obj: _TransformVars, enabled: bool) -> None:
        # ttk.Entry state is widget-level; we control via the update buttons only.
        # (We keep entries editable to allow user to copy/paste quickly.)
        # This method currently only exists for future extension.
        _ = vars_obj
        _ = enabled

    def _sync_from_selection(self) -> None:
        if self._sync_guard:
            return
        self._sync_guard = True
        try:
            meshes = self.context.model_store.meshes
            _cleanup_settings_cubes(self.settings.data, meshes)
            self.settings.save()

            a, b = self.context.model_store.selected_pair

            def name(i: int | None) -> str:
                if i is None:
                    return "(none)"
                if 0 <= i < len(meshes):
                    return f"{i+1}. {meshes[i].name}"
                return f"{i+1}. (invalid)"

            self.selection_label.configure(text=f"Selection:\nA = {name(a)}\nB = {name(b)}")
            self.btn_union.configure(state=("normal" if a is not None and b is not None else "disabled"))
            self.btn_diff.configure(state=("normal" if a is not None and b is not None else "disabled"))

            # Fill A/B fields if they are cubes we control.
            self._sync_transform_panel(which="a", index=a, meshes=meshes)
            self._sync_transform_panel(which="b", index=b, meshes=meshes)
        finally:
            self._sync_guard = False

    def _sync_transform_panel(self, *, which: str, index: int | None, meshes: list[WorkMesh]) -> None:
        vars_obj = self.vars_a if which == "a" else self.vars_b
        btn = self.btn_update_a if which == "a" else self.btn_update_b
        if index is None or not (0 <= index < len(meshes)):
            vars_obj.set_empty()
            btn.configure(state="disabled")
            return

        cid = _parse_cube_id(meshes[index].name)
        if not cid:
            vars_obj.set_empty()
            btn.configure(state="disabled")
            return

        params = _cube_params_from_settings(self.settings.data, cid)
        if params is None:
            vars_obj.set_empty()
            btn.configure(state="disabled")
            return

        vars_obj.set_from_params(params)
        btn.configure(state="normal")

    def _alloc_cube_id(self) -> str:
        nid = int(self.settings.data.get("next_id", 1))
        if nid <= 0:
            nid = 1
        self.settings.data["next_id"] = nid + 1
        return str(nid)

    def _add_cube(self) -> None:
        try:
            meshes = list(self.context.model_store.meshes)
            cube_id = self._alloc_cube_id()
            params = self.vars_new.read_params(cube_id)
            _write_cube_params_to_settings(self.settings.data, params)
            self.settings.save()

            mesh = make_cube_mesh(
                name=params.mesh_name,
                pos=params.pos,
                rot_deg=params.rot_deg,
                scale_mm=params.scale_mm,
                color=params.color,
            )
            meshes.append(mesh)
            self.context.model_store.set_preview_meshes(meshes, source_path=self.context.model_store.source_path)
        except Exception as exc:
            messagebox.showerror("Cubes", str(exc))

    def _update_selected(self, which: str) -> None:
        try:
            meshes = list(self.context.model_store.meshes)
            a, b = self.context.model_store.selected_pair
            idx = a if which == "a" else b
            if idx is None or not (0 <= idx < len(meshes)):
                raise ValueError("No valid selection.")

            cid = _parse_cube_id(meshes[idx].name)
            if not cid:
                raise ValueError("Selection is not an editable cube (missing [cube:...] tag).")

            vars_obj = self.vars_a if which == "a" else self.vars_b
            params = vars_obj.read_params(cid)
            _write_cube_params_to_settings(self.settings.data, params)
            self.settings.save()

            meshes[idx] = make_cube_mesh(
                name=params.mesh_name,
                pos=params.pos,
                rot_deg=params.rot_deg,
                scale_mm=params.scale_mm,
                color=params.color,
            )
            self.context.model_store.set_preview_meshes(meshes, source_path=self.context.model_store.source_path)
        except Exception as exc:
            messagebox.showerror("Cubes", str(exc))

    def _bases_for_pair(self, meshes: list[WorkMesh], a: int, b: int):
        mesh_a = meshes[a]
        mesh_b = meshes[b]

        # Basis A
        cid_a = _parse_cube_id(mesh_a.name)
        cid_b = _parse_cube_id(mesh_b.name)

        if cid_a:
            pa = _cube_params_from_settings(self.settings.data, cid_a)
            basis_a = _cube_basis_from_params(pa) if pa else None
        else:
            basis_a = None

        if cid_b:
            pb = _cube_params_from_settings(self.settings.data, cid_b)
            basis_b = _cube_basis_from_params(pb) if pb else None
        else:
            basis_b = None

        # Fallback: PCA basis for non-cubes.
        from . import joint_builder as jb

        if basis_a is None:
            basis_a = jb.compute_basis(mesh_a)
        if basis_b is None:
            basis_b = jb.compute_basis(mesh_b)

        return mesh_a, mesh_b, basis_a, basis_b

    def _op_union(self) -> None:
        self._op("union")

    def _op_diff(self) -> None:
        self._op("difference")

    def _op(self, op: str) -> None:
        try:
            meshes = list(self.context.model_store.meshes)
            a, b = self.context.model_store.selected_pair
            if a is None or b is None:
                raise ValueError("Select 2 items (A and B) in the 3D view.")
            if not (0 <= a < len(meshes) and 0 <= b < len(meshes)) or a == b:
                raise ValueError("Invalid selection.")

            mesh_a = meshes[a]
            mesh_b = meshes[b]
            result = _boolean(mesh_a, mesh_b, op=op)

            # Replace operands by the result (without keeping originals).
            # - union: delete A and B, insert the result at index min(A,B)
            # - difference: delete A and B, insert the result at index A (if A < B) else A-1 (after deleting B)
            if op == "union":
                insert_at = min(a, b)
                for idx in sorted((a, b), reverse=True):
                    del meshes[idx]
                meshes.insert(insert_at, result)
            else:
                # difference: result = modified A
                insert_at = a
                if b < a:
                    insert_at -= 1
                for idx in sorted((a, b), reverse=True):
                    del meshes[idx]
                meshes.insert(insert_at, result)
            self.context.model_store.set_preview_meshes(meshes, source_path=self.context.model_store.source_path)
        except Exception as exc:
            messagebox.showerror("Booleans", str(exc))
