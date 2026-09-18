"""Domain-level creator services for advanced Studio tools.

These facades expose materials, engraving metadata, texture assets and planar
sketch helpers without requiring external tools to import historical Qt/PyVista
controllers. They are intentionally conservative: each service discovers the
capabilities available on the bound scene/document and falls back to stable
WorkMesh metadata when no richer backend exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence
import math
import uuid

from .app_services import DocumentObject, ToolServiceError
from .sketch.face_solver import FaceSolver

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class MaterialRecord:
    id: str
    name: str
    base_color: str = "#B8B8B8"
    opacity: float = 1.0
    roughness: float = 0.5
    metallic: float = 0.0
    texture_id: str | None = None
    raw: Any | None = None


@dataclass(frozen=True, slots=True)
class TextureAssetRecord:
    id: str
    path: Path
    usage: Literal["visual", "cut", "engrave"] = "visual"
    width: int | None = None
    height: int | None = None
    raw: Any | None = None

    @property
    def filename(self) -> str:
        return self.path.name


@dataclass(frozen=True, slots=True)
class EngravingRoleSpec:
    id: str
    label: str
    color: str
    layer: Literal["cut", "engrave", "ignore"] = "engrave"
    help_text: str = ""


DEFAULT_ENGRAVING_ROLES: tuple[EngravingRoleSpec, ...] = (
    EngravingRoleSpec("outline", "Outline", "#00C853", "engrave", "Vector outline/cut guide."),
    EngravingRoleSpec("fill", "Fill", "#E53935", "engrave", "Engraved filled region."),
    EngravingRoleSpec("ignore", "Ignore", "#B8B8B8", "ignore", "Ignored by engraving export."),
)


@dataclass(frozen=True, slots=True)
class PlaneSpec:
    origin: Point3 = (0.0, 0.0, 0.0)
    normal: Vector3 = (0.0, 0.0, 1.0)
    x_axis: Vector3 = (1.0, 0.0, 0.0)
    y_axis: Vector3 = (0.0, 1.0, 0.0)
    source: str = "custom"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlanarRegion:
    id: str
    points_2d: tuple[Point2, ...]
    points_3d: tuple[Point3, ...]
    boundary_entity_ids: tuple[str, ...]
    area: float
    hole_points_2d: tuple[tuple[Point2, ...], ...] = ()
    hole_points_3d: tuple[tuple[Point3, ...], ...] = ()
    hole_boundary_entity_ids: tuple[tuple[str, ...], ...] = ()


class MaterialManager:
    """Creator-facing material service.

    Materials are stored on ``WorkMesh.material`` when no scene material library
    exists. The public return type is ``MaterialRecord`` so external tools do
    not depend on internal dataclasses.
    """

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._library: dict[str, MaterialRecord] = {}

    def bind_context(self, ctx: Any) -> "MaterialManager":
        self._ctx = ctx
        return self

    def create(
        self,
        name: str,
        *,
        base_color: str = "#B8B8B8",
        opacity: float = 1.0,
        roughness: float = 0.5,
        metallic: float = 0.0,
        texture_id: str | None = None,
        material_id: str | None = None,
    ) -> MaterialRecord:
        raw = _make_mesh_material(
            name=name,
            base_color=base_color,
            opacity=opacity,
            roughness=roughness,
            metallic=metallic,
            texture_id=texture_id,
        )
        record = _material_record_from_raw(raw, material_id=material_id or _safe_id("mat", name))
        self._library[record.id] = record
        return record

    def list(self) -> tuple[MaterialRecord, ...]:  # noqa: A003 - public DSL name is intentional
        records: dict[str, MaterialRecord] = dict(self._library)
        for obj in self._document_objects():
            raw = getattr(obj.mesh, "material", None)
            if raw is None:
                continue
            record = _material_record_from_raw(raw)
            records.setdefault(record.id, record)
        return tuple(records.values())

    def get(self, object_id: str | int) -> MaterialRecord:
        obj = self._document().get(object_id)
        raw = getattr(obj.mesh, "material", None)
        if raw is None:
            return MaterialRecord("default", "Default", base_color=str(getattr(obj.mesh, "color", "#B8B8B8") or "#B8B8B8"))
        return _material_record_from_raw(raw)

    def assign(self, object_id: str | int, material: MaterialRecord | Any, *, label: str = "Assign material") -> DocumentObject:
        raw = _material_raw(material)
        assigned = self._document().set_material(object_id, raw, label=label)
        color = getattr(raw, "base_color", None) if raw is not None else None
        if isinstance(raw, dict):
            color = raw.get("base_color")
        if color:
            try:
                assigned.mesh.color = str(color)
            except Exception:
                pass
        return assigned

    def assign_selected(self, material: MaterialRecord | Any, *, label: str = "Assign material") -> tuple[DocumentObject, ...]:
        selection = getattr(self._ctx, "scene_selection", None)
        selected = tuple(selection.selected_objects()) if selection is not None else ()
        return tuple(self.assign(obj.id, material, label=label) for obj in selected)

    def _document(self):
        ctx = self._ctx
        if ctx is None:
            raise ToolServiceError("MaterialManager is not bound to a ToolContext.")
        return ctx.document

    def _document_objects(self) -> tuple[DocumentObject, ...]:
        try:
            return tuple(self._document().objects())
        except Exception:
            return ()


class AssetManager:
    """Texture asset registry independent from the historical UI."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._assets: dict[str, TextureAssetRecord] = {}

    def bind_context(self, ctx: Any) -> "AssetManager":
        self._ctx = ctx
        return self

    def import_image(
        self,
        path: str | Path,
        *,
        usage: Literal["visual", "cut", "engrave"] = "visual",
        asset_id: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> TextureAssetRecord:
        asset_path = Path(path)
        raw = _make_texture_asset(asset_id or _safe_id("tex", asset_path.stem), asset_path, usage, width, height)
        record = _asset_record_from_raw(raw)
        self._assets[record.id] = record
        target = self._target()
        mapping = getattr(target, "texture_assets_by_id", None) if target is not None else None
        if isinstance(mapping, dict):
            mapping[record.id] = raw
        return record

    def list_textures(self) -> tuple[TextureAssetRecord, ...]:
        records = dict(self._assets)
        target = self._target()
        mapping = getattr(target, "texture_assets_by_id", None) if target is not None else None
        if isinstance(mapping, dict):
            for key, raw in mapping.items():
                record = _asset_record_from_raw(raw, fallback_id=str(key))
                records.setdefault(record.id, record)
        return tuple(records.values())

    def get_texture(self, texture_id: str) -> TextureAssetRecord:
        for asset in self.list_textures():
            if asset.id == texture_id:
                return asset
        raise KeyError(f"Unknown texture asset: {texture_id!r}")

    def remove_texture(self, texture_id: str) -> bool:
        key = str(texture_id)
        removed = self._assets.pop(key, None) is not None
        target = self._target()
        mapping = getattr(target, "texture_assets_by_id", None) if target is not None else None
        if isinstance(mapping, dict):
            removed = mapping.pop(key, None) is not None or removed
        return removed

    def attach_to_material(self, object_id: str | int, texture_id: str, *, label: str = "Assign texture") -> DocumentObject:
        asset = self.get_texture(texture_id)
        materials = getattr(self._ctx, "materials", None)
        if materials is None:
            raise ToolServiceError("ctx.materials is unavailable.")
        current = materials.get(object_id)
        updated = materials.create(
            current.name,
            base_color=current.base_color,
            opacity=current.opacity,
            roughness=current.roughness,
            metallic=current.metallic,
            texture_id=asset.id,
            material_id=current.id,
        )
        return materials.assign(object_id, updated, label=label)

    def _target(self) -> Any | None:
        ctx = self._ctx
        if ctx is None:
            return None
        raw = getattr(getattr(ctx, "document", None), "raw", None)
        return raw or getattr(ctx, "scene", None) or getattr(ctx, "owner", None)


class EngravingManager:
    """Stable API for engraving roles/layers on scene objects."""

    def __init__(self) -> None:
        self._ctx: Any | None = None

    def bind_context(self, ctx: Any) -> "EngravingManager":
        self._ctx = ctx
        return self

    def roles(self) -> tuple[EngravingRoleSpec, ...]:
        return DEFAULT_ENGRAVING_ROLES

    def role(self, role_id: str) -> EngravingRoleSpec:
        key = str(role_id).strip().lower()
        for role in self.roles():
            if role.id == key:
                return role
        raise KeyError(f"Unknown engraving role: {role_id!r}")

    def assign_role(
        self,
        object_id: str | int,
        role: str,
        *,
        layer: Literal["cut", "engrave", "ignore"] | None = None,
        enabled: bool = True,
        label: str = "Assign engraving role",
    ) -> DocumentObject:
        spec = self.role(role)
        role_layer = layer or spec.layer

        def _assign(mesh: Any) -> Any:
            raw = _make_engraving_settings(role=spec.id, layer=role_layer, enabled=enabled)
            try:
                setattr(mesh, "engraving", raw)
            except Exception:
                pass
            try:
                setattr(mesh, "color", spec.color)
            except Exception:
                pass
            material = getattr(mesh, "material", None)
            if material is not None:
                try:
                    material.base_color = spec.color
                except Exception:
                    if isinstance(material, dict):
                        material["base_color"] = spec.color
            return mesh

        return self._document().update_mesh(object_id, _assign, label=label)

    def assign_selected(self, role: str, **kwargs: Any) -> tuple[DocumentObject, ...]:
        selection = getattr(self._ctx, "scene_selection", None)
        selected = tuple(selection.selected_objects()) if selection is not None else ()
        return tuple(self.assign_role(obj.id, role, **kwargs) for obj in selected)

    def role_for(self, object_id: str | int) -> str:
        obj = self._document().get(object_id)
        engraving = getattr(obj.mesh, "engraving", None)
        if engraving is None:
            return "ignore"
        if isinstance(engraving, dict):
            return str(engraving.get("role") or "ignore")
        return str(getattr(engraving, "role", "ignore") or "ignore")

    def _document(self):
        ctx = self._ctx
        if ctx is None:
            raise ToolServiceError("EngravingManager is not bound to a ToolContext.")
        return ctx.document


class PlanarManager:
    """Planar sketch/workplane helper used by Plan Tracer-like tools."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._plane = PlaneSpec()

    def bind_context(self, ctx: Any) -> "PlanarManager":
        self._ctx = ctx
        return self

    @property
    def plane(self) -> PlaneSpec:
        return self._plane

    def set_plane(
        self,
        *,
        origin: Sequence[float] = (0.0, 0.0, 0.0),
        normal: Sequence[float] = (0.0, 0.0, 1.0),
        x_axis: Sequence[float] | None = None,
        source: str = "custom",
        metadata: dict[str, Any] | None = None,
    ) -> PlaneSpec:
        n = _normalize(_point3(normal))
        x = _normalize(_point3(x_axis) if x_axis is not None else _choose_x_axis(n))
        # Orthogonalize x against n, then compute y.
        dot = _dot(x, n)
        x = _normalize((x[0] - dot * n[0], x[1] - dot * n[1], x[2] - dot * n[2]))
        y = _normalize(_cross(n, x))
        self._plane = PlaneSpec(_point3(origin), n, x, y, source=str(source), metadata=dict(metadata or {}))
        return self._plane

    def lock_to_camera(self) -> PlaneSpec:
        viewport = getattr(self._ctx, "viewport", None)
        normal = getattr(viewport, "camera_direction", None) or getattr(viewport, "view_direction", None) or (0.0, 0.0, 1.0)
        origin = getattr(viewport, "camera_target", None) or (0.0, 0.0, 0.0)
        return self.set_plane(origin=origin, normal=normal, source="camera")

    def lock_to_face(self, pick_or_face: Any) -> PlaneSpec:
        world = getattr(pick_or_face, "world_pos", None) or getattr(pick_or_face, "center", None) or (0.0, 0.0, 0.0)
        normal = getattr(pick_or_face, "normal", None) or (0.0, 0.0, 1.0)
        metadata = {}
        for name in ("object_id", "object_index", "element_index"):
            value = getattr(pick_or_face, name, None)
            if value is not None:
                metadata[name] = value
        return self.set_plane(origin=world, normal=normal, source="face", metadata=metadata)

    def world_to_plane(self, point: Sequence[float]) -> Point2:
        p = _point3(point)
        rel = (p[0] - self._plane.origin[0], p[1] - self._plane.origin[1], p[2] - self._plane.origin[2])
        return (_dot(rel, self._plane.x_axis), _dot(rel, self._plane.y_axis))

    def plane_to_world(self, point: Sequence[float]) -> Point3:
        u, v = float(point[0]), float(point[1])
        o, x, y = self._plane.origin, self._plane.x_axis, self._plane.y_axis
        return (o[0] + u * x[0] + v * y[0], o[1] + u * x[1] + v * y[1], o[2] + u * x[2] + v * y[2])

    def add_point(self, world_pos: Sequence[float] | None = None, plane_pos: Sequence[float] | None = None, *, point_id: str | None = None):
        sketch = self._sketch()
        if plane_pos is None:
            if world_pos is None:
                raise ToolServiceError("Planar point needs either world_pos or plane_pos.")
            plane_pos = self.world_to_plane(world_pos)
        return sketch.add_point((float(plane_pos[0]), float(plane_pos[1])), point_id=point_id)

    def add_line(self, start_point_id: str, end_point_id: str, *, line_id: str | None = None):
        return self._sketch().add_line(start_point_id, end_point_id, line_id=line_id)

    def add_arc(self, start_point_id: str, end_point_id: str, control_point_id: str, *, arc_id: str | None = None):
        return self._sketch().add_arc(start_point_id, end_point_id, control_point_id, arc_id=arc_id)

    def solve_regions(self) -> tuple[PlanarRegion, ...]:
        sketch = self._sketch()
        FaceSolver().solve(sketch)
        regions: list[PlanarRegion] = []
        for face in sketch.faces.values():
            points = tuple((float(x), float(y)) for x, y in face.polygon_points)
            regions.append(
                PlanarRegion(
                    id=face.id,
                    points_2d=points,
                    points_3d=tuple(self.plane_to_world(point) for point in points),
                    boundary_entity_ids=tuple(face.boundary_entity_ids),
                    area=max(0.0, abs(_polygon_area(points)) - sum(abs(_polygon_area(tuple(hole))) for hole in getattr(face, "hole_polygons", ()))),
                    hole_points_2d=tuple(tuple((float(x), float(y)) for x, y in hole) for hole in getattr(face, "hole_polygons", ())),
                    hole_points_3d=tuple(tuple(self.plane_to_world(point) for point in hole) for hole in getattr(face, "hole_polygons", ())),
                    hole_boundary_entity_ids=tuple(tuple(ids) for ids in getattr(face, "hole_boundary_entity_ids", ())),
                )
            )
        return tuple(regions)

    def generate_mesh(self, region: PlanarRegion | str | None = None, *, name: str = "Planar region") -> Any:
        regions = {item.id: item for item in self.solve_regions()}
        if region is None:
            if not regions:
                raise ToolServiceError("No closed planar region is available.")
            selected = next(iter(regions.values()))
        elif isinstance(region, PlanarRegion):
            selected = region
        else:
            selected = regions[str(region)]
        if len(selected.points_3d) < 3:
            raise ToolServiceError("A planar mesh needs at least three points.")
        try:
            from laserprog_studio.domain.work_model import WorkMesh

            vertices = list(selected.points_3d)
            triangles = [(0, i, i + 1) for i in range(1, len(vertices) - 1)]
            return WorkMesh(name=name, vertices=vertices, triangles=triangles)
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ToolServiceError(f"Cannot create planar WorkMesh: {exc}") from exc

    def clear(self) -> None:
        sketch = self._sketch()
        sketch.points.clear()
        sketch.lines.clear()
        sketch.arcs.clear()
        sketch.beziers.clear()
        sketch.circles.clear()
        sketch.faces.clear()

    def _sketch(self):
        ctx = self._ctx
        if ctx is None:
            raise ToolServiceError("PlanarManager is not bound to a ToolContext.")
        return ctx.sketch


def _make_mesh_material(**kwargs: Any) -> Any:
    try:
        from laserprog_studio.domain.material import MeshMaterial

        return MeshMaterial(**kwargs)
    except Exception:
        return dict(kwargs)


def _make_engraving_settings(**kwargs: Any) -> Any:
    try:
        from laserprog_studio.domain.material import EngravingSettings

        return EngravingSettings(**kwargs)
    except Exception:
        return dict(kwargs)


def _make_texture_asset(asset_id: str, path: Path, usage: str, width: int | None, height: int | None) -> Any:
    try:
        from laserprog_studio.domain.texture_asset import TextureAsset

        return TextureAsset(id=str(asset_id), path=Path(path), usage=usage, width=width, height=height)
    except Exception:
        return {"id": str(asset_id), "path": Path(path), "usage": usage, "width": width, "height": height}


def _material_record_from_raw(raw: Any, *, material_id: str | None = None) -> MaterialRecord:
    if isinstance(raw, MaterialRecord):
        return raw
    if isinstance(raw, dict):
        name = str(raw.get("name") or "Material")
        return MaterialRecord(
            material_id or _safe_id("mat", name),
            name,
            base_color=str(raw.get("base_color") or raw.get("color") or "#B8B8B8"),
            opacity=float(raw.get("opacity", 1.0)),
            roughness=float(raw.get("roughness", 0.5)),
            metallic=float(raw.get("metallic", 0.0)),
            texture_id=str(raw.get("texture_id")) if raw.get("texture_id") is not None else None,
            raw=raw,
        )
    name = str(getattr(raw, "name", "Material") or "Material")
    return MaterialRecord(
        material_id or _safe_id("mat", name),
        name,
        base_color=str(getattr(raw, "base_color", "#B8B8B8") or "#B8B8B8"),
        opacity=float(getattr(raw, "opacity", 1.0)),
        roughness=float(getattr(raw, "roughness", 0.5)),
        metallic=float(getattr(raw, "metallic", 0.0)),
        texture_id=str(getattr(raw, "texture_id")) if getattr(raw, "texture_id", None) is not None else None,
        raw=raw,
    )


def _material_raw(value: MaterialRecord | Any) -> Any:
    if isinstance(value, MaterialRecord):
        return value.raw or _make_mesh_material(
            name=value.name,
            base_color=value.base_color,
            opacity=value.opacity,
            roughness=value.roughness,
            metallic=value.metallic,
            texture_id=value.texture_id,
        )
    return value


def _asset_record_from_raw(raw: Any, *, fallback_id: str | None = None) -> TextureAssetRecord:
    if isinstance(raw, TextureAssetRecord):
        return raw
    if isinstance(raw, dict):
        return TextureAssetRecord(
            str(raw.get("id") or fallback_id or _safe_id("tex", Path(str(raw.get("path", "texture"))).stem)),
            Path(raw.get("path", "")),
            raw.get("usage", "visual"),
            raw.get("width"),
            raw.get("height"),
            raw,
        )
    return TextureAssetRecord(
        str(getattr(raw, "id", None) or fallback_id or _safe_id("tex", Path(str(getattr(raw, "path", "texture"))).stem)),
        Path(getattr(raw, "path", "")),
        getattr(raw, "usage", "visual"),
        getattr(raw, "width", None),
        getattr(raw, "height", None),
        raw,
    )


def _safe_id(prefix: str, value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value).strip()).strip("_")
    if not slug:
        slug = uuid.uuid4().hex[:8]
    return f"{prefix}:{slug}"


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


def _dot(a: Point3, b: Point3) -> float:
    return float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(v: Point3) -> Point3:
    length = math.sqrt(max(0.0, _dot(v, v)))
    if length <= 1e-12:
        return (1.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _choose_x_axis(normal: Point3) -> Point3:
    up = (0.0, 0.0, 1.0)
    if abs(_dot(_normalize(normal), up)) > 0.95:
        return (1.0, 0.0, 0.0)
    return _normalize(_cross(up, normal))


def _polygon_area(points: Sequence[Point2]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, [*points[1:], points[0]]):
        total += x1 * y2 - x2 * y1
    return total / 2.0


__all__ = [
    "AssetManager",
    "DEFAULT_ENGRAVING_ROLES",
    "EngravingManager",
    "EngravingRoleSpec",
    "MaterialManager",
    "MaterialRecord",
    "PlanarManager",
    "PlanarRegion",
    "PlaneSpec",
    "TextureAssetRecord",
]
