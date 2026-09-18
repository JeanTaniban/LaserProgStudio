"""Pure Cloth document model.

Cloth is represented as a piecewise-planar surface graph.  Curves define panel
boundaries; patches are faces only (never closed solids); folds join two patches
along a shared straight boundary curve.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from laserprog_studio.tool_api.tracing import TraceDraft, TraceMode

Point3 = tuple[float, float, float]


class ClothCurveKind(str, Enum):
    LINE = "line"
    ARC = "arc"
    POLYLINE = "polyline"


class ClothCurveRole(str, Enum):
    BOUNDARY = "boundary"
    FOLD = "fold"
    SEAM = "seam"
    CONSTRUCTION = "construction"


class ClothFoldKind(str, Enum):
    MOUNTAIN = "mountain"
    VALLEY = "valley"
    NEUTRAL = "neutral"


class ClothPatchFunction(str, Enum):
    TEXTILE = "textile"
    PATTERN = "pattern"
    JUNCTION = "junction"


@dataclass(slots=True)
class ClothLayer:
    id: str
    name: str = "Base textile"
    material_name: str = "Textile"
    thickness_mm: float = 0.2
    visible: bool = True
    locked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class ClothWorkflowPhase(str, Enum):
    OPENING = "opening"
    EDITING = "editing"
    VALIDATION_BLOCKED = "validation_blocked"
    FLAT_PREVIEW = "flat_preview"
    APPLY_READY = "apply_ready"
    APPLIED = "applied"
    CANCELLED = "cancelled"


class ClothEditMode(str, Enum):
    MODIFY = TraceMode.MODIFY.value
    POINT = TraceMode.POINT.value
    LINE = TraceMode.LINE.value
    POLYLINE = TraceMode.POLYLINE.value
    ARC = TraceMode.ARC.value
    FACE = "face"
    MESH_TRACE = "mesh_trace"
    FOLD = "fold"
    SEAM = "seam"
    GRAIN = "grain"


@dataclass(slots=True)
class ClothPoint:
    id: str
    position: Point3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClothCurve:
    id: str
    kind: ClothCurveKind
    point_ids: tuple[str, ...]
    role: ClothCurveRole = ClothCurveRole.BOUNDARY
    closed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def endpoint_ids(self) -> tuple[str, str]:
        if len(self.point_ids) < 2:
            return ("", "")
        return (self.point_ids[0], self.point_ids[-1] if self.kind is not ClothCurveKind.ARC else self.point_ids[1])


@dataclass(slots=True)
class ClothPatch:
    id: str
    outer_curve_ids: tuple[str, ...]
    hole_curve_loops: tuple[tuple[str, ...], ...] = ()
    name: str = "Panel"
    grain_direction: Point3 | None = None
    function: ClothPatchFunction = ClothPatchFunction.TEXTILE
    layer_id: str = "layer1"
    material_name: str = "Textile"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClothFold:
    id: str
    curve_id: str
    patch_a_id: str
    patch_b_id: str
    kind: ClothFoldKind = ClothFoldKind.NEUTRAL
    angle_degrees: float = 0.0
    radius_mm: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClothSeam:
    id: str
    first_curve_ids: tuple[str, ...]
    second_curve_ids: tuple[str, ...]
    allowance_mm: float = 0.0
    ease_ratio: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ClothDocument:
    layers: dict[str, ClothLayer] = field(default_factory=dict)
    points: dict[str, ClothPoint] = field(default_factory=dict)
    curves: dict[str, ClothCurve] = field(default_factory=dict)
    patches: dict[str, ClothPatch] = field(default_factory=dict)
    folds: dict[str, ClothFold] = field(default_factory=dict)
    seams: dict[str, ClothSeam] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    revision: int = 0
    _next_id: int = 1

    def clone(self) -> "ClothDocument":
        return deepcopy(self)

    def new_id(self, prefix: str) -> str:
        value = f"{prefix}{self._next_id}"
        self._next_id += 1
        return value

    def _touch(self) -> None:
        self.revision += 1

    @staticmethod
    def _point3(position: Iterable[float]) -> Point3:
        values = tuple(float(value) for value in position)
        if len(values) != 3:
            raise ValueError("Cloth points require exactly three coordinates.")
        return (values[0], values[1], values[2])

    def ensure_layer(
        self,
        layer_id: str = "layer1",
        *,
        name: str = "Base textile",
        material_name: str = "Textile",
        thickness_mm: float = 0.2,
    ) -> ClothLayer:
        key = str(layer_id or "layer1")
        existing = self.layers.get(key)
        if existing is not None:
            return existing
        layer = ClothLayer(
            key,
            name=str(name or key),
            material_name=str(material_name or "Textile"),
            thickness_mm=max(0.001, float(thickness_mm)),
        )
        self.layers[key] = layer
        self._touch()
        return layer

    def add_layer(
        self,
        *,
        name: str = "Textile layer",
        material_name: str = "Textile",
        thickness_mm: float = 0.2,
        layer_id: str | None = None,
    ) -> ClothLayer:
        key = str(layer_id or self.new_id("layer"))
        if key in self.layers:
            raise KeyError(f"Duplicate cloth layer id: {key}")
        layer = ClothLayer(
            key,
            name=str(name or key),
            material_name=str(material_name or "Textile"),
            thickness_mm=max(0.001, float(thickness_mm)),
        )
        self.layers[key] = layer
        self._touch()
        return layer

    def set_patch_properties(
        self,
        patch_ids: Iterable[str],
        *,
        name: str | None = None,
        function: ClothPatchFunction | str | None = None,
        layer_id: str | None = None,
        material_name: str | None = None,
    ) -> tuple[str, ...]:
        changed: list[str] = []
        resolved_function = None if function is None else ClothPatchFunction(str(function.value if isinstance(function, ClothPatchFunction) else function))
        resolved_layer = None if layer_id is None else self.ensure_layer(str(layer_id))
        for patch_id in dict.fromkeys(str(value) for value in patch_ids):
            patch = self.patches.get(patch_id)
            if patch is None:
                continue
            dirty = False
            if name is not None and patch.name != str(name):
                patch.name = str(name)
                dirty = True
            if resolved_function is not None and patch.function is not resolved_function:
                patch.function = resolved_function
                dirty = True
            if resolved_layer is not None and patch.layer_id != resolved_layer.id:
                patch.layer_id = resolved_layer.id
                dirty = True
            if material_name is not None and patch.material_name != str(material_name):
                patch.material_name = str(material_name)
                dirty = True
            if dirty:
                changed.append(patch_id)
        if changed:
            self._touch()
        return tuple(changed)

    def add_point(self, position: Iterable[float], *, point_id: str | None = None, metadata: dict[str, Any] | None = None) -> ClothPoint:
        item = ClothPoint(point_id or self.new_id("p"), self._point3(position), dict(metadata or {}))
        if item.id in self.points:
            raise KeyError(f"Duplicate cloth point id: {item.id}")
        self.points[item.id] = item
        self._touch()
        return item

    def move_point(self, point_id: str, position: Iterable[float]) -> bool:
        point = self.points.get(str(point_id))
        if point is None:
            return False
        updated = self._point3(position)
        if updated == point.position:
            return True
        point.position = updated
        self._touch()
        return True

    def _require_points(self, point_ids: Iterable[str]) -> tuple[str, ...]:
        ids = tuple(str(value) for value in point_ids)
        missing = [point_id for point_id in ids if point_id not in self.points]
        if missing:
            raise KeyError(f"Unknown cloth point ids: {', '.join(missing)}")
        return ids

    def add_line(
        self,
        start_point_id: str,
        end_point_id: str,
        *,
        curve_id: str | None = None,
        role: ClothCurveRole = ClothCurveRole.BOUNDARY,
        metadata: dict[str, Any] | None = None,
    ) -> ClothCurve:
        ids = self._require_points((start_point_id, end_point_id))
        return self._add_curve(ClothCurveKind.LINE, ids, curve_id=curve_id, role=role, metadata=metadata)

    def add_arc(
        self,
        start_point_id: str,
        end_point_id: str,
        control_point_id: str,
        *,
        curve_id: str | None = None,
        role: ClothCurveRole = ClothCurveRole.BOUNDARY,
        metadata: dict[str, Any] | None = None,
    ) -> ClothCurve:
        ids = self._require_points((start_point_id, end_point_id, control_point_id))
        return self._add_curve(ClothCurveKind.ARC, ids, curve_id=curve_id, role=role, metadata=metadata)

    def add_polyline(
        self,
        point_ids: Iterable[str],
        *,
        closed: bool = False,
        curve_id: str | None = None,
        role: ClothCurveRole = ClothCurveRole.BOUNDARY,
        metadata: dict[str, Any] | None = None,
    ) -> ClothCurve:
        ids = self._require_points(point_ids)
        if len(ids) < 2:
            raise ValueError("A cloth polyline needs at least two points.")
        return self._add_curve(ClothCurveKind.POLYLINE, ids, curve_id=curve_id, role=role, closed=closed, metadata=metadata)

    def _add_curve(
        self,
        kind: ClothCurveKind,
        point_ids: tuple[str, ...],
        *,
        curve_id: str | None,
        role: ClothCurveRole,
        closed: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ClothCurve:
        item = ClothCurve(curve_id or self.new_id("c"), kind, point_ids, role=role, closed=bool(closed), metadata=dict(metadata or {}))
        if item.id in self.curves:
            raise KeyError(f"Duplicate cloth curve id: {item.id}")
        self.curves[item.id] = item
        self._touch()
        return item

    def add_patch(
        self,
        outer_curve_ids: Iterable[str],
        *,
        patch_id: str | None = None,
        hole_curve_loops: Iterable[Iterable[str]] = (),
        name: str = "Panel",
        function: ClothPatchFunction | str = ClothPatchFunction.TEXTILE,
        layer_id: str = "layer1",
        material_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ClothPatch:
        outer = tuple(str(value) for value in outer_curve_ids)
        holes = tuple(tuple(str(value) for value in loop) for loop in hole_curve_loops)
        missing = [curve_id for curve_id in (*outer, *(item for loop in holes for item in loop)) if curve_id not in self.curves]
        if missing:
            raise KeyError(f"Unknown cloth curve ids: {', '.join(missing)}")
        if not outer:
            raise ValueError("A cloth patch needs a non-empty outer curve loop.")
        layer = self.ensure_layer(str(layer_id or "layer1"))
        resolved_function = function if isinstance(function, ClothPatchFunction) else ClothPatchFunction(str(function))
        item = ClothPatch(
            patch_id or self.new_id("panel"),
            outer,
            holes,
            name=str(name or "Panel"),
            function=resolved_function,
            layer_id=layer.id,
            material_name=str(material_name or layer.material_name),
            metadata=dict(metadata or {}),
        )
        if item.id in self.patches:
            raise KeyError(f"Duplicate cloth patch id: {item.id}")
        self.patches[item.id] = item
        self._touch()
        return item

    def add_fold(
        self,
        curve_id: str,
        patch_a_id: str,
        patch_b_id: str,
        *,
        fold_id: str | None = None,
        kind: ClothFoldKind = ClothFoldKind.NEUTRAL,
        angle_degrees: float = 0.0,
        radius_mm: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> ClothFold:
        if curve_id not in self.curves:
            raise KeyError(f"Unknown fold curve: {curve_id}")
        for patch_id in (patch_a_id, patch_b_id):
            if patch_id not in self.patches:
                raise KeyError(f"Unknown fold patch: {patch_id}")
        if patch_a_id == patch_b_id:
            raise ValueError("A fold must join two distinct patches.")
        if any(existing.curve_id == str(curve_id) for existing in self.folds.values()):
            raise ValueError(f"Curve {curve_id} already has a Cloth fold relation.")
        item = ClothFold(
            fold_id or self.new_id("fold"),
            str(curve_id),
            str(patch_a_id),
            str(patch_b_id),
            kind=kind,
            angle_degrees=float(angle_degrees),
            radius_mm=max(0.0, float(radius_mm)),
            metadata=dict(metadata or {}),
        )
        if item.id in self.folds:
            raise KeyError(f"Duplicate cloth fold id: {item.id}")
        self.folds[item.id] = item
        self.curves[curve_id].role = ClothCurveRole.FOLD
        self._touch()
        return item

    def add_seam(
        self,
        first_curve_ids: Iterable[str],
        second_curve_ids: Iterable[str],
        *,
        seam_id: str | None = None,
        allowance_mm: float = 0.0,
        ease_ratio: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> ClothSeam:
        first = tuple(str(value) for value in first_curve_ids)
        second = tuple(str(value) for value in second_curve_ids)
        missing = [curve_id for curve_id in (*first, *second) if curve_id not in self.curves]
        if missing:
            raise KeyError(f"Unknown seam curves: {', '.join(missing)}")
        if not first or not second:
            raise ValueError("A seam needs two non-empty boundary chains.")
        item = ClothSeam(
            seam_id or self.new_id("seam"),
            first,
            second,
            allowance_mm=max(0.0, float(allowance_mm)),
            ease_ratio=max(1.0e-6, float(ease_ratio)),
            metadata=dict(metadata or {}),
        )
        if item.id in self.seams:
            raise KeyError(f"Duplicate cloth seam id: {item.id}")
        self.seams[item.id] = item
        for curve_id in (*first, *second):
            if self.curves[curve_id].role is ClothCurveRole.BOUNDARY:
                self.curves[curve_id].role = ClothCurveRole.SEAM
        self._touch()
        return item


@dataclass(slots=True)
class ClothSession:
    document: ClothDocument = field(default_factory=ClothDocument)
    original_document: ClothDocument | None = None
    phase: ClothWorkflowPhase = ClothWorkflowPhase.OPENING
    edit_mode: ClothEditMode = ClothEditMode.POLYLINE
    trace_draft: TraceDraft = field(default_factory=TraceDraft)
    editing_existing: bool = False
    source_mesh_id: str | None = None
    selected_point_ids: tuple[str, ...] = ()
    selected_curve_ids: tuple[str, ...] = ()
    selected_patch_ids: tuple[str, ...] = ()
    status: str = "Polyline ready. Click directly in 3D or hover an existing Cloth."
    dirty: bool = False

    def clone_document_as_origin(self) -> None:
        self.original_document = self.document.clone()


__all__ = [
    "ClothCurve",
    "ClothCurveKind",
    "ClothCurveRole",
    "ClothDocument",
    "ClothEditMode",
    "ClothFold",
    "ClothFoldKind",
    "ClothLayer",
    "ClothPatch",
    "ClothPatchFunction",
    "ClothPoint",
    "ClothSeam",
    "ClothSession",
    "ClothWorkflowPhase",
    "Point3",
]
