"""Mesh generation for folded and flattened Cloth documents."""
from __future__ import annotations

from dataclasses import dataclass, field

from laserprog_studio.domain.work_model import WorkMesh

from .boolean_modifiers import load_cloth_boolean_modifiers
from .boolean_pattern import modified_patch_geometry
from .flattening import ClothFlatteningResult
from .mesh_welding import build_shared_boundary_samples, shared_boundary_weld_key
from .models import ClothDocument
from .solidification import (
    cloth_stitch_tolerance_mm,
    cloth_thickness_mm,
    solidify_cloth_surface_mesh,
)
from .topology import patch_frame
from .triangulation import (
    ClothTriangulationError,
    triangulate_region_geometry,
    triangulate_simple_polygon,
)

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


@dataclass(slots=True)
class ClothMeshBuildResult:
    mesh: WorkMesh | None = None
    issues: list[str] = field(default_factory=list)
    patch_triangle_ranges: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.mesh is not None and not self.issues


def build_cloth_surface_mesh(
    document: ClothDocument,
    *,
    name: str = "Cloth 3D",
    flattened: ClothFlatteningResult | None = None,
    color: str = "#BFD8E8",
    arc_segments: int = 24,
    solid: bool = False,
) -> ClothMeshBuildResult:
    """Build the modified Cloth mid-surface and optionally a closed thin solid.

    Boolean modifiers are parsed once, projected to every panel, then
    triangulated.  Vertex sharing is authorised by document topology rather than
    coordinate coincidence, so unrelated cut boundaries cannot become a
    four-face non-manifold edge.
    """

    result = ClothMeshBuildResult()
    loaded_modifiers = load_cloth_boolean_modifiers(document)
    if loaded_modifiers.issues:
        result.issues.extend(loaded_modifiers.issues)
        return result

    stitch_tolerance = cloth_stitch_tolerance_mm(document)
    shared_samples_by_patch = build_shared_boundary_samples(
        document,
        flattened=flattened is not None,
        arc_segments=arc_segments,
        excluded_curve_ids=(
            flattened.virtual_cut_curve_ids
            if flattened is not None
            else ()
        ),
    )
    vertices: list[Point3] = []
    triangles: list[tuple[int, int, int]] = []
    vertex_patch_ids: list[str] = []
    vertex_index_by_key: dict[tuple[object, ...], int] = {}

    def add_vertex(
        patch_id: str,
        source_world: Point3,
        output_world: Point3,
        *,
        flat_component_index: int | None = None,
    ) -> int:
        shared_key = shared_boundary_weld_key(
            source_world,
            shared_samples=shared_samples_by_patch.get(patch_id, ()),
            tolerance_mm=stitch_tolerance,
        )
        if shared_key is None:
            coordinates = tuple(
                int(round(float(value) * 1.0e7))
                for value in output_world
            )
            key: tuple[object, ...] = ("patch", patch_id, *coordinates)
        else:
            # A virtual pattern cut may place two originally coincident source
            # points in different packed flat components. Prefixing the
            # topological key prevents those components from being welded back
            # together through a shared endpoint id.
            key = (
                ("flat-component", int(flat_component_index), *shared_key)
                if flat_component_index is not None
                else shared_key
            )
        existing = vertex_index_by_key.get(key)
        if existing is not None:
            return existing
        index = len(vertices)
        vertices.append(tuple(float(value) for value in output_world))
        vertex_patch_ids.append(str(patch_id))
        vertex_index_by_key[key] = index
        return index

    for patch in document.patches.values():
        frame = patch_frame(document, patch)
        if frame is None:
            result.issues.append(
                f"Panel {patch.name}: invalid boundary or local plane."
            )
            continue
        region = modified_patch_geometry(
            document,
            patch,
            frame,
            arc_segments=arc_segments,
            tolerance_mm=max(1.0e-5, stitch_tolerance * 0.2),
            modifiers=loaded_modifiers.modifiers,
        )
        result.issues.extend(region.issues)
        try:
            local_triangles = triangulate_region_geometry(region.geometry)
        except ClothTriangulationError as exc:
            result.issues.append(f"Panel {patch.name}: {exc}")
            continue
        if not local_triangles:
            result.issues.append(
                f"Panel {patch.name}: modified boundary triangulation failed "
                "or removed the whole panel."
            )
            continue

        placement = flattened.placements.get(patch.id) if flattened is not None else None
        if flattened is not None and placement is None:
            result.issues.append(f"Panel {patch.name}: no flat placement.")
            continue

        def output_point(local: Point2) -> tuple[Point3, Point3]:
            source_world = frame.lift(local)
            if placement is None:
                return source_world, source_world
            mapped = placement.map_world(source_world)
            return source_world, (mapped[0], mapped[1], 0.0)

        start = len(triangles)
        for local_triangle in local_triangles:
            source_output_pairs = tuple(
                output_point(point)
                for point in local_triangle
            )
            indices = tuple(
                add_vertex(
                    patch.id,
                    source,
                    output,
                    flat_component_index=(
                        placement.component_index
                        if placement is not None
                        else None
                    ),
                )
                for source, output in source_output_pairs
            )
            if len(set(indices)) == 3:
                triangles.append(indices)
        result.patch_triangle_ranges[patch.id] = start, len(triangles)

    if result.issues or not triangles:
        return result

    metadata = {
        "laserprog_generator": "cloth",
        "cloth_surface_only": True,
        "cloth_flattened": flattened is not None,
        "cloth_patch_triangle_ranges": {
            key: list(value)
            for key, value in result.patch_triangle_ranges.items()
        },
        "cloth_vertex_patch_ids": vertex_patch_ids,
        "cloth_topology_welded": True,
        "cloth_thickness_mm": cloth_thickness_mm(document),
        "cloth_stitch_tolerance_mm": stitch_tolerance,
        "cloth_boolean_modifier_count": len(loaded_modifiers.modifiers),
        "cloth_virtual_cut_fold_ids": list(flattened.virtual_cut_fold_ids) if flattened is not None else [],
        "cloth_virtual_cut_curve_ids": list(flattened.virtual_cut_curve_ids) if flattened is not None else [],
        "cloth_virtual_cut_count": len(flattened.virtual_cut_fold_ids) if flattened is not None else 0,
    }
    surface = WorkMesh(
        name=name,
        vertices=vertices,
        triangles=triangles,
        color=color,
        metadata=metadata,
    )
    if solid:
        try:
            surface, _report = solidify_cloth_surface_mesh(
                surface,
                thickness_mm=cloth_thickness_mm(document),
                stitch_tolerance_mm=stitch_tolerance,
                name=name,
            )
        except ValueError as exc:
            result.issues.append(str(exc))
            return result
    result.mesh = surface
    return result


__all__ = [
    "ClothMeshBuildResult",
    "build_cloth_surface_mesh",
    "triangulate_simple_polygon",
]
