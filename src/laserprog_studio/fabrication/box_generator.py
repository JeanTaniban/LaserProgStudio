# -*- coding: utf-8 -*-
"""Tool: 3MF box generator.

Generates a closed box made of 6 separate boards.
Entered dimensions are the final outer dimensions.

v4: selectable wrapping/inset faces + inner volume estimate.
"""

from __future__ import annotations

import json
import re
import tkinter as tk
import zipfile
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from xml.sax.saxutils import escape

from laserprog_studio.domain.work_model import WorkMesh

TOOL_ID = "box_generator"
TOOL_NAME = "Box generator"


@dataclass
class Board:
    name: str
    min_x: float
    min_y: float
    min_z: float
    size_x: float
    size_y: float
    size_z: float
    color: str


@dataclass(frozen=True)
class BoxMetrics:
    outer_width_mm: float
    outer_depth_mm: float
    outer_height_mm: float
    thickness_mm: float
    inner_width_mm: float
    inner_depth_mm: float
    inner_height_mm: float
    outer_volume_mm3: float
    inner_volume_mm3: float
    board_solid_volume_mm3: float
    board_cut_area_mm2: float

    @property
    def outer_volume_l(self) -> float:
        return self.outer_volume_mm3 / 1_000_000.0

    @property
    def inner_volume_l(self) -> float:
        return self.inner_volume_mm3 / 1_000_000.0

    @property
    def board_solid_volume_l(self) -> float:
        return self.board_solid_volume_mm3 / 1_000_000.0

    @property
    def board_cut_area_m2(self) -> float:
        return self.board_cut_area_mm2 / 1_000_000.0

    @property
    def board_double_face_area_m2(self) -> float:
        return (2.0 * self.board_cut_area_mm2) / 1_000_000.0


DEFAULT_SETTINGS = {
    "outer_width_mm": 120.0,
    "outer_depth_mm": 80.0,
    "outer_height_mm": 60.0,
    "wood_thickness_mm": 3.0,
    "corner_joint": "front_back_wrap",
    "top_front_joint": "top_bottom_wrap",
    "top_side_joint": "top_bottom_wrap",
    "output_name": "box_120x80x60_t3",
    "output_dir": "",
}

CORNER_JOINT_OPTIONS = {
    "front_back_wrap": "Front/Back wrap Left/Right",
    "left_right_wrap": "Left/Right wrap Front/Back",
}

TOP_FRONT_JOINT_OPTIONS = {
    "top_bottom_wrap": "Top/Bottom wrap Front/Back",
    "front_back_wrap": "Front/Back wrap Top/Bottom",
}

TOP_SIDE_JOINT_OPTIONS = {
    "top_bottom_wrap": "Top/Bottom wrap Left/Right",
    "left_right_wrap": "Left/Right wrap Top/Bottom",
}

BOARD_COLORS = {
    "bottom": "#D9A066",
    "top": "#E6B47A",
    "front": "#C8844A",
    "back": "#C8844A",
    "left": "#B8753D",
    "right": "#B8753D",
}


def safe_filename(name: str) -> str:
    name = name.strip() or "box"
    name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)
    return name.strip("._") or "box"


def fmt(v: float) -> str:
    if abs(v) < 1e-9:
        v = 0.0
    return f"{v:.6f}".rstrip("0").rstrip(".")


def option_label(value: str, options: dict[str, str]) -> str:
    return options.get(value, value)


def option_value(label_or_value: str, options: dict[str, str]) -> str:
    if label_or_value in options:
        return label_or_value
    for value, label in options.items():
        if label == label_or_value:
            return value
    return next(iter(options))


def make_box_boards(
    width: float,
    depth: float,
    height: float,
    thickness: float,
    corner_joint: str = "front_back_wrap",
    top_front_joint: str = "top_bottom_wrap",
    top_side_joint: str = "top_bottom_wrap",
) -> list[Board]:
    if width <= 0 or depth <= 0 or height <= 0 or thickness <= 0:
        raise ValueError("All dimensions must be strictly positive.")
    if width <= 2 * thickness:
        raise ValueError("Outer width must be greater than 2 x thickness.")
    if depth <= 2 * thickness:
        raise ValueError("Outer depth must be greater than 2 x thickness.")
    if height <= 2 * thickness:
        raise ValueError("Outer height must be greater than 2 x thickness.")

    corner_joint = option_value(corner_joint, CORNER_JOINT_OPTIONS)
    top_front_joint = option_value(top_front_joint, TOP_FRONT_JOINT_OPTIONS)
    top_side_joint = option_value(top_side_joint, TOP_SIDE_JOINT_OPTIONS)

    top_bottom_inset_x = thickness if top_side_joint == "left_right_wrap" else 0.0
    top_bottom_inset_y = thickness if top_front_joint == "front_back_wrap" else 0.0

    front_back_inset_x = thickness if corner_joint == "left_right_wrap" else 0.0
    front_back_inset_z = thickness if top_front_joint == "top_bottom_wrap" else 0.0

    left_right_inset_y = thickness if corner_joint == "front_back_wrap" else 0.0
    left_right_inset_z = thickness if top_side_joint == "top_bottom_wrap" else 0.0

    top_bottom_x = width - 2 * top_bottom_inset_x
    top_bottom_y = depth - 2 * top_bottom_inset_y
    front_back_x = width - 2 * front_back_inset_x
    front_back_z = height - 2 * front_back_inset_z
    left_right_y = depth - 2 * left_right_inset_y
    left_right_z = height - 2 * left_right_inset_z

    dims = {
        "top/bottom width X": top_bottom_x,
        "top/bottom depth Y": top_bottom_y,
        "front/back width X": front_back_x,
        "front/back height Z": front_back_z,
        "left/right depth Y": left_right_y,
        "left/right height Z": left_right_z,
    }
    for name, value in dims.items():
        if value <= 0:
            raise ValueError(f"Invalid dimension for {name}: {value:.3f} mm")

    return [
        Board("bottom", top_bottom_inset_x, top_bottom_inset_y, 0, top_bottom_x, top_bottom_y, thickness, BOARD_COLORS["bottom"]),
        Board("top", top_bottom_inset_x, top_bottom_inset_y, height - thickness, top_bottom_x, top_bottom_y, thickness, BOARD_COLORS["top"]),
        Board("front", front_back_inset_x, 0, front_back_inset_z, front_back_x, thickness, front_back_z, BOARD_COLORS["front"]),
        Board("back", front_back_inset_x, depth - thickness, front_back_inset_z, front_back_x, thickness, front_back_z, BOARD_COLORS["back"]),
        Board("left", 0, left_right_inset_y, left_right_inset_z, thickness, left_right_y, left_right_z, BOARD_COLORS["left"]),
        Board("right", width - thickness, left_right_inset_y, left_right_inset_z, thickness, left_right_y, left_right_z, BOARD_COLORS["right"]),
    ]


def board_cut_area_mm2(board: Board) -> float:
    """Return the one-side sheet area consumed by a board, in mm².

    The generated boards are rectangular planks: one dimension is the material
    thickness, the two other dimensions are the laser-cut panel footprint.
    Using the two largest dimensions makes the function robust to the board
    orientation and to the selected wrapping/inset mode.
    """
    dims = sorted((float(board.size_x), float(board.size_y), float(board.size_z)), reverse=True)
    return dims[0] * dims[1]


def compute_box_metrics(
    width: float,
    depth: float,
    height: float,
    thickness: float,
    boards: list[Board] | None = None,
    corner_joint: str = "front_back_wrap",
    top_front_joint: str = "top_bottom_wrap",
    top_side_joint: str = "top_bottom_wrap",
) -> BoxMetrics:
    """Compute useful workshop metrics for the generated rectangular box.

    Volumes are returned in mm³ and exposed as litre properties.  The external
    volume is the bounding box volume.  The internal volume is the theoretical
    usable void after subtracting one wall thickness on each side.  The board
    surface is the one-side sheet area to cut, not the painted double-face area.
    """
    if boards is None:
        boards = make_box_boards(width, depth, height, thickness, corner_joint, top_front_joint, top_side_joint)
    inner_width = max(0.0, float(width) - 2.0 * float(thickness))
    inner_depth = max(0.0, float(depth) - 2.0 * float(thickness))
    inner_height = max(0.0, float(height) - 2.0 * float(thickness))
    outer_volume = float(width) * float(depth) * float(height)
    inner_volume = inner_width * inner_depth * inner_height
    board_volume = sum(float(b.size_x) * float(b.size_y) * float(b.size_z) for b in boards)
    cut_area = sum(board_cut_area_mm2(b) for b in boards)
    return BoxMetrics(
        outer_width_mm=float(width),
        outer_depth_mm=float(depth),
        outer_height_mm=float(height),
        thickness_mm=float(thickness),
        inner_width_mm=inner_width,
        inner_depth_mm=inner_depth,
        inner_height_mm=inner_height,
        outer_volume_mm3=outer_volume,
        inner_volume_mm3=inner_volume,
        board_solid_volume_mm3=board_volume,
        board_cut_area_mm2=cut_area,
    )


def format_box_metrics_summary(metrics: BoxMetrics) -> str:
    return (
        f"External volume : {metrics.outer_volume_l:.4f} L\n"
        f"Internal volume : {metrics.inner_volume_l:.4f} L\n"
        f"Board surface : {metrics.board_cut_area_m2:.4f} m²"
    )


def attach_box_metadata(
    mesh,
    *,
    group_id: str,
    board_name: str,
    width: float,
    depth: float,
    height: float,
    thickness: float,
    corner_joint: str = "front_back_wrap",
    top_front_joint: str = "top_bottom_wrap",
    top_side_joint: str = "top_bottom_wrap",
):
    """Attach lightweight Box-generator metadata to a WorkMesh-like object.

    Studio preview/transform code uses this metadata to recognise the six boards
    as one generated box and to refresh the volume/sheet-area report when the
    box is resized from the transform inspector.  The metadata is deliberately
    stored as a plain dynamic attribute so it survives ``copy.deepcopy`` without
    changing the public 3MF export model.
    """
    try:
        setattr(mesh, "box_generator_meta", {
            "tool": TOOL_ID,
            "group_id": str(group_id),
            "board_name": str(board_name),
            "outer_width_mm": float(width),
            "outer_depth_mm": float(depth),
            "outer_height_mm": float(height),
            "thickness_mm": float(thickness),
            "corner_joint": option_value(corner_joint, CORNER_JOINT_OPTIONS),
            "top_front_joint": option_value(top_front_joint, TOP_FRONT_JOINT_OPTIONS),
            "top_side_joint": option_value(top_side_joint, TOP_SIDE_JOINT_OPTIONS),
        })
    except Exception:
        pass
    return mesh


def box_metadata(mesh) -> dict | None:
    """Return Box-generator metadata from a mesh, if present and valid."""
    try:
        meta = getattr(mesh, "box_generator_meta", None)
        if isinstance(meta, dict) and meta.get("tool") == TOOL_ID and meta.get("group_id"):
            return meta
    except Exception:
        pass
    return None


def build_box_meshes(
    width: float,
    depth: float,
    height: float,
    thickness: float,
    corner_joint: str = "front_back_wrap",
    top_front_joint: str = "top_bottom_wrap",
    top_side_joint: str = "top_bottom_wrap",
    *,
    group_id: str | None = None,
) -> tuple[list[Board], list[WorkMesh], BoxMetrics]:
    """Build tagged Studio meshes for a generated box.

    This is the pure runtime backend used by both the historical preview bridge
    and the Creator API implementation.  Keeping it here avoids having new
    tools import from ``application/`` just to generate box boards.
    """
    import datetime as _dt

    corner = option_value(corner_joint, CORNER_JOINT_OPTIONS)
    top_front = option_value(top_front_joint, TOP_FRONT_JOINT_OPTIONS)
    top_side = option_value(top_side_joint, TOP_SIDE_JOINT_OPTIONS)
    boards = make_box_boards(width, depth, height, thickness, corner, top_front, top_side)
    metrics = compute_box_metrics(width, depth, height, thickness, boards, corner, top_front, top_side)
    tris = cuboid_triangles()
    resolved_group_id = str(group_id or f"box-{_dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}")
    meshes: list[WorkMesh] = []
    for board in boards:
        mesh = WorkMesh(name=board.name, vertices=cuboid_vertices(board), triangles=tris, color=board.color)
        meshes.append(
            attach_box_metadata(
                mesh,
                group_id=resolved_group_id,
                board_name=board.name,
                width=width,
                depth=depth,
                height=height,
                thickness=thickness,
                corner_joint=corner,
                top_front_joint=top_front,
                top_side_joint=top_side,
            )
        )
    return boards, meshes, metrics


def format_box_metrics_report(
    boards: list[Board],
    metrics: BoxMetrics,
    corner_joint: str = "front_back_wrap",
    top_front_joint: str = "top_bottom_wrap",
    top_side_joint: str = "top_bottom_wrap",
) -> str:
    lines = [
        f"External volume : {metrics.outer_volume_l:.4f} L",
        f"Internal volume : {metrics.inner_volume_l:.4f} L",
        f"Internal dimensions : {metrics.inner_width_mm:.1f} × {metrics.inner_depth_mm:.1f} × {metrics.inner_height_mm:.1f} mm",
        f"Board surface : {metrics.board_cut_area_m2:.4f} m²",
        f"Two-face area : {metrics.board_double_face_area_m2:.4f} m²",
        "",
        f"Corners : {option_label(corner_joint, CORNER_JOINT_OPTIONS)}",
        f"Top/bottom ↔ front/back: {option_label(top_front_joint, TOP_FRONT_JOINT_OPTIONS)}",
        f"Top/bottom ↔ sides: {option_label(top_side_joint, TOP_SIDE_JOINT_OPTIONS)}",
        "",
        "Boards :",
    ]
    for board in boards:
        lines.append(
            f"- {board.name}: {board.size_x:.1f} × {board.size_y:.1f} × {board.size_z:.1f} mm "
            f"| {board_cut_area_mm2(board) / 1_000_000.0:.4f} m²"
        )
    return "\n".join(lines)


def cuboid_vertices(board: Board) -> list[tuple[float, float, float]]:
    x0, y0, z0 = board.min_x, board.min_y, board.min_z
    x1, y1, z1 = x0 + board.size_x, y0 + board.size_y, z0 + board.size_z
    return [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]


def cuboid_triangles() -> list[tuple[int, int, int]]:
    return [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]


def build_3mf_model_xml(boards: list[Board]) -> str:
    import uuid

    core_ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    material_ns = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
    production_ns = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        f'<model unit="millimeter" xml:lang="fr-FR" '
        f'xmlns="{core_ns}" '
        f'xmlns:m="{material_ns}" '
        f'xmlns:p="{production_ns}">'
    )
    lines.append('  <metadata name="Application">Laser Toolbox - Box Generator</metadata>')
    lines.append('  <resources>')

    material_id = 1
    lines.append(f'    <m:basematerials id="{material_id}">')
    for board in boards:
        lines.append(f'      <m:base name="{escape(board.name)}" displaycolor="{board.color}"/>')
    lines.append('    </m:basematerials>')

    triangles = cuboid_triangles()
    for index, board in enumerate(boards, start=1):
        material_index = index - 1
        lines.append(f'    <object id="{index}" name="{escape(board.name)}" type="model" p:UUID="{uuid.uuid4()}">')
        lines.append('      <mesh>')
        lines.append('        <vertices>')
        for x, y, z in cuboid_vertices(board):
            lines.append(f'          <vertex x="{fmt(x)}" y="{fmt(y)}" z="{fmt(z)}"/>')
        lines.append('        </vertices>')
        lines.append('        <triangles>')
        for v1, v2, v3 in triangles:
            lines.append(
                f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" '
                f'pid="{material_id}" p1="{material_index}" p2="{material_index}" p3="{material_index}"/>'
            )
        lines.append('        </triangles>')
        lines.append('      </mesh>')
        lines.append('    </object>')

    lines.append('  </resources>')
    lines.append(f'  <build p:UUID="{uuid.uuid4()}">')
    for index, board in enumerate(boards, start=1):
        lines.append(f'    <item objectid="{index}" partnumber="{escape(board.name)}" p:UUID="{uuid.uuid4()}"/>')
    lines.append('  </build>')
    lines.append('</model>')
    return "\n".join(lines)


def write_3mf(path: Path, boards: list[Board]) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="jpg" ContentType="image/jpeg"/>
  <Default Extension="jpeg" ContentType="image/jpeg"/>
  <Default Extension="texture" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodeltexture"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", build_3mf_model_xml(boards))


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


class ToolFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget, app_context) -> None:
        super().__init__(parent)
        self.context = app_context
        self.settings = AutoSaveSettings(self.context.settings_dir / f"{TOOL_ID}.json", DEFAULT_SETTINGS)
        if not self.settings.data.get("output_dir"):
            self.settings.data["output_dir"] = str(self.context.exports_dir)
            self.settings.save()

        self._save_after_id: str | None = None
        self.vars: dict[str, tk.Variable] = {}
        self._build_ui()
        self._load_vars_from_settings()
        self._connect_autosave()
        self._update_preview()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=(0, 0, 12, 0))
        left.grid(row=0, column=0, sticky="nsw")

        right = ttk.Frame(self, padding=(12, 0, 0, 0))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="Box generator", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))

        self.vars = {
            "outer_width_mm": tk.StringVar(),
            "outer_depth_mm": tk.StringVar(),
            "outer_height_mm": tk.StringVar(),
            "wood_thickness_mm": tk.StringVar(),
            "corner_joint": tk.StringVar(),
            "top_front_joint": tk.StringVar(),
            "top_side_joint": tk.StringVar(),
            "output_name": tk.StringVar(),
            "output_dir": tk.StringVar(),
        }

        row = 1
        row = self._add_float_field(left, row, "Outer width X", "outer_width_mm", "mm")
        row = self._add_float_field(left, row, "Outer depth Y", "outer_depth_mm", "mm")
        row = self._add_float_field(left, row, "Outer height Z", "outer_height_mm", "mm")
        row = self._add_float_field(left, row, "Board thickness", "wood_thickness_mm", "mm")

        ttk.Separator(left).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(left, text="Wrapping faces", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
        row += 1
        row = self._add_combo_field(left, row, "Vertical corners", "corner_joint", CORNER_JOINT_OPTIONS)
        row = self._add_combo_field(left, row, "Top/Bottom <-> Front/Back", "top_front_joint", TOP_FRONT_JOINT_OPTIONS)
        row = self._add_combo_field(left, row, "Top/Bottom <-> Left/Right", "top_side_joint", TOP_SIDE_JOINT_OPTIONS)

        ttk.Label(
            left,
            text="A wrapping face keeps its full size. An inset face is shortened by 2 x thickness.",
            wraplength=330,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        row += 1

        ttk.Separator(left).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1

        ttk.Label(left, text="File name").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(left, textvariable=self.vars["output_name"], width=28).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        row += 1

        ttk.Label(left, text="Output folder").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(left, textvariable=self.vars["output_dir"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(left, text="...", width=4, command=self._choose_output_dir).grid(row=row, column=2, sticky="e", padx=(4, 0), pady=4)
        row += 1

        self.generate_button = ttk.Button(left, text="Generate 3MF", command=self._generate_3mf)
        self.generate_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(16, 6))
        row += 1

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(left, textvariable=self.status_var, wraplength=330, foreground="#444").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        ttk.Label(right, text="Preview of the 6 boards", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.info_text = tk.Text(right, height=18, wrap="word", state="disabled")
        self.info_text.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.info_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.info_text.configure(yscrollcommand=scrollbar.set)

    def _add_float_field(self, parent: tk.Widget, row: int, label: str, key: str, unit: str) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.vars[key], width=12).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(parent, text=unit).grid(row=row, column=2, sticky="w", padx=(4, 0), pady=4)
        return row + 1

    def _add_combo_field(self, parent: tk.Widget, row: int, label: str, key: str, options: dict[str, str]) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(parent, textvariable=self.vars[key], values=list(options.values()), state="readonly", width=42)
        combo.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        combo.bind("<<ComboboxSelected>>", self._on_any_change)
        return row + 1

    def _load_vars_from_settings(self) -> None:
        combo_options = {
            "corner_joint": CORNER_JOINT_OPTIONS,
            "top_front_joint": TOP_FRONT_JOINT_OPTIONS,
            "top_side_joint": TOP_SIDE_JOINT_OPTIONS,
        }
        for key, var in self.vars.items():
            value = self.settings.data.get(key, DEFAULT_SETTINGS.get(key, ""))
            if key in combo_options:
                var.set(option_label(option_value(str(value), combo_options[key]), combo_options[key]))
            else:
                var.set(str(value))

    def _connect_autosave(self) -> None:
        for var in self.vars.values():
            var.trace_add("write", self._on_any_change)

    def _on_any_change(self, *_args) -> None:
        self._schedule_autosave()
        self._update_preview()

    def _schedule_autosave(self) -> None:
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(180, self._save_settings_now)

    def _save_settings_now(self) -> None:
        self._save_after_id = None
        combo_options = {
            "corner_joint": CORNER_JOINT_OPTIONS,
            "top_front_joint": TOP_FRONT_JOINT_OPTIONS,
            "top_side_joint": TOP_SIDE_JOINT_OPTIONS,
        }
        for key, var in self.vars.items():
            raw = var.get()
            if key.endswith("_mm"):
                try:
                    self.settings.data[key] = float(raw.replace(",", "."))
                except ValueError:
                    continue
            elif key in combo_options:
                self.settings.data[key] = option_value(raw, combo_options[key])
            else:
                self.settings.data[key] = raw
        self.settings.save()

    def _read_float(self, key: str) -> float:
        return float(self.vars[key].get().strip().replace(",", "."))

    def _read_option(self, key: str, options: dict[str, str]) -> str:
        return option_value(self.vars[key].get(), options)

    def _current_boards(self) -> list[Board]:
        return make_box_boards(
            self._read_float("outer_width_mm"),
            self._read_float("outer_depth_mm"),
            self._read_float("outer_height_mm"),
            self._read_float("wood_thickness_mm"),
            self._read_option("corner_joint", CORNER_JOINT_OPTIONS),
            self._read_option("top_front_joint", TOP_FRONT_JOINT_OPTIONS),
            self._read_option("top_side_joint", TOP_SIDE_JOINT_OPTIONS),
        )

    def _choose_output_dir(self) -> None:
        initial = self.vars["output_dir"].get() or str(self.context.exports_dir)
        selected = filedialog.askdirectory(initialdir=initial, title="Choose output folder")
        if selected:
            self.vars["output_dir"].set(selected)

    def _set_text(self, content: str) -> None:
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", content)
        self.info_text.configure(state="disabled")

    def _update_preview(self) -> None:
        try:
            boards = self._current_boards()
            width = self._read_float("outer_width_mm")
            depth = self._read_float("outer_depth_mm")
            height = self._read_float("outer_height_mm")
            thickness = self._read_float("wood_thickness_mm")
            corner_joint = self._read_option("corner_joint", CORNER_JOINT_OPTIONS)
            top_front_joint = self._read_option("top_front_joint", TOP_FRONT_JOINT_OPTIONS)
            top_side_joint = self._read_option("top_side_joint", TOP_SIDE_JOINT_OPTIONS)

            lines = []
            metrics = compute_box_metrics(width, depth, height, thickness, boards)

            lines.append("Final outer dimensions:")
            lines.append(f"  X width     : {width:.3f} mm")
            lines.append(f"  Y depth     : {depth:.3f} mm")
            lines.append(f"  Z height    : {height:.3f} mm")
            lines.append(f"  Thickness   : {thickness:.3f} mm")
            lines.append("")
            lines.append("Volumes:")
            lines.append(f"  External envelope : {metrics.outer_volume_l:.4f} L ({metrics.outer_volume_mm3:.3f} mm3)")
            lines.append(f"  Internal usable   : {metrics.inner_volume_l:.4f} L ({metrics.inner_volume_mm3:.3f} mm3)")
            lines.append(f"  Internal dims     : {metrics.inner_width_mm:.3f} x {metrics.inner_depth_mm:.3f} x {metrics.inner_height_mm:.3f} mm")
            lines.append(f"  Board solid volume: {metrics.board_solid_volume_l:.4f} L")
            lines.append("")
            lines.append("Board surface:")
            lines.append(f"  Sheet area to cut : {metrics.board_cut_area_m2:.4f} m²")
            lines.append(f"  Two visible faces : {metrics.board_double_face_area_m2:.4f} m²")
            lines.append("")
            lines.append("Wrapping / inset faces:")
            lines.append(f"  - Vertical corners: {option_label(corner_joint, CORNER_JOINT_OPTIONS)}")
            lines.append(f"  - Top/Bottom with Front/Back: {option_label(top_front_joint, TOP_FRONT_JOINT_OPTIONS)}")
            lines.append(f"  - Top/Bottom with Left/Right: {option_label(top_side_joint, TOP_SIDE_JOINT_OPTIONS)}")
            lines.append("")
            lines.append("Generated boards (all separate in the 3MF):")
            for board in boards:
                lines.append(
                    f"  - {board.name:<8}  position=({board.min_x:.3f}, {board.min_y:.3f}, {board.min_z:.3f}) mm  "
                    f"size=({board.size_x:.3f} x {board.size_y:.3f} x {board.size_z:.3f}) mm  "
                    f"cut area={board_cut_area_mm2(board) / 1_000_000.0:.4f} m²"
                )
            lines.append("")
            lines.append("Quick read:")
            lines.append("  - a wrapping board keeps full length at the joint;")
            lines.append("  - an inset board is shortened by 2 x thickness;")
            lines.append("  - all 6 boards remain separate objects in the 3MF file.")
            self._set_text("\n".join(lines))
            self.status_var.set("Valid parameters. Ready to generate.")
            self.generate_button.configure(state="normal")

            # Auto-apply: update the work model (viewer on the right).
            meshes: list[WorkMesh] = []
            tris = cuboid_triangles()
            for b in boards:
                meshes.append(WorkMesh(name=b.name, vertices=cuboid_vertices(b), triangles=tris, color=b.color))
            self.context.model_store.set_preview_meshes(meshes, source_path=None)
        except Exception as exc:
            self._set_text(f"Invalid parameters:\n\n{exc}")
            self.status_var.set("Fix parameters before generating.")
            self.generate_button.configure(state="disabled")

    def _generate_3mf(self) -> None:
        try:
            self._save_settings_now()
            boards = self._current_boards()
            output_dir = Path(self.vars["output_dir"].get() or self.context.exports_dir)
            name = safe_filename(self.vars["output_name"].get())
            path = output_dir / f"{name}.3mf"
            write_3mf(path, boards)
            self.status_var.set(f"3MF generated: {path}")
            messagebox.showinfo("3MF generated", f"File created:\n{path}")
        except Exception as exc:
            messagebox.showerror("Generation error", str(exc))
            self.status_var.set("Error during generation.")
