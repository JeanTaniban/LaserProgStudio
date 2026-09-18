"""Selection hit-testing and topology-safe deletion for Cloth editing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .groups import create_textile_group, explicit_textile_group_id, textile_group_patch_ids
from .models import ClothCurveRole, ClothDocument
from .topology import sample_patch_boundary

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class ClothDeleteResult:
    changed: bool
    points: int = 0
    curves: int = 0
    patches: int = 0
    folds: int = 0
    seams: int = 0

    @property
    def message(self) -> str:
        if not self.changed:
            return "Nothing is selected."
        parts: list[str] = []
        if self.patches:
            parts.append(f"{self.patches} face(s)")
        if self.curves:
            parts.append(f"{self.curves} edge(s)")
        if self.points:
            parts.append(f"{self.points} point(s)")
        if self.folds:
            parts.append(f"{self.folds} fold relation(s)")
        if self.seams:
            parts.append(f"{self.seams} seam relation(s)")
        return f"Deleted {', '.join(parts)}."


def nearest_document_patch(
    document: ClothDocument,
    screen_pos: Point2,
    world_to_screen: Callable,
) -> str | None:
    """Return the smallest visible Cloth face containing ``screen_pos``.

    Smaller projected faces win when panels overlap, which matches the visual
    expectation that the most specific face under the pointer is selected.
    """

    best: tuple[float, str] | None = None
    for patch in document.patches.values():
        boundary3 = sample_patch_boundary(document, patch, arc_segments=32)
        if len(boundary3) < 3:
            continue
        try:
            boundary = tuple((float(value[0]), float(value[1])) for value in (world_to_screen(point) for point in boundary3))
        except Exception:
            continue
        if not _point_in_polygon(screen_pos, boundary):
            continue
        area = abs(_polygon_area(boundary))
        if best is None or area < best[0]:
            best = (area, patch.id)
    return best[1] if best is not None else None



def logical_patch_group(document: ClothDocument, patch_id: str) -> tuple[str, ...]:
    """Return the persistent logical textile group containing ``patch_id``.

    Technical triangulation may create several Cloth patches for one user-facing
    panel.  Explicit group metadata wins; older documents fall back to stable
    source/proposal metadata, then to the single patch.
    """

    patch = document.patches.get(str(patch_id))
    if patch is None:
        return ()
    metadata = dict(patch.metadata or {})
    group_id = explicit_textile_group_id(document, patch.id)
    if group_id:
        values = textile_group_patch_ids(document, group_id)
        return values or (patch.id,)
    source_object = str(metadata.get("cloth_source_object_id") or "")
    source_component = str(metadata.get("cloth_source_component") or "")
    source_faces = tuple(metadata.get("cloth_source_faces") or ())
    join_id = str(metadata.get("cloth_join_proposal_id") or "")
    creation_id = str(metadata.get("cloth_creation_group_id") or "")
    region_id = str(metadata.get("cloth_region_id") or "")
    strip_id = str(metadata.get("cloth_ruled_strip_id") or "")

    values: list[str] = []
    for candidate_id, candidate in document.patches.items():
        candidate_meta = dict(candidate.metadata or {})
        same = False
        if creation_id:
            same = str(candidate_meta.get("cloth_creation_group_id") or "") == creation_id
        elif source_object and source_component:
            same = (
                str(candidate_meta.get("cloth_source_object_id") or "") == source_object
                and str(candidate_meta.get("cloth_source_component") or "") == source_component
            )
        elif region_id:
            same = str(candidate_meta.get("cloth_region_id") or "") == region_id
        elif strip_id:
            same = str(candidate_meta.get("cloth_ruled_strip_id") or "") == strip_id
        elif source_object and source_faces:
            same = (
                str(candidate_meta.get("cloth_source_object_id") or "") == source_object
                and tuple(candidate_meta.get("cloth_source_faces") or ()) == source_faces
            )
        elif join_id:
            same = str(candidate_meta.get("cloth_join_proposal_id") or "") == join_id
        else:
            same = candidate_id == patch.id
        if same:
            values.append(candidate_id)
    return tuple(values or (patch.id,))


def logical_patch_group_key(document: ClothDocument, patch_id: str) -> str:
    """Return a stable identity for the user-facing textile group."""

    explicit_id = explicit_textile_group_id(document, patch_id)
    if explicit_id:
        return explicit_id
    group = logical_patch_group(document, patch_id)
    return min(group) if group else str(patch_id)


def logical_patch_group_count(document: ClothDocument, patch_ids: Iterable[str]) -> int:
    """Count user-facing groups represented by a technical patch selection."""

    return len({logical_patch_group_key(document, patch_id) for patch_id in patch_ids if str(patch_id) in document.patches})


def logical_patch_group_representatives(document: ClothDocument, patch_ids: Iterable[str]) -> tuple[str, ...]:
    """Return one deterministic technical patch per selected logical group."""

    by_key: dict[str, str] = {}
    for patch_id in patch_ids:
        value = str(patch_id)
        if value not in document.patches:
            continue
        key = logical_patch_group_key(document, value)
        by_key.setdefault(key, value)
    return tuple(by_key[key] for key in sorted(by_key))




def smart_logical_patch_group(
    document: ClothDocument,
    patch_id: str,
    *,
    tolerance: float = 0.35,
    automatic: bool = False,
    cache=None,
) -> tuple[str, ...]:
    """Group connected textile faces through the public selection API.

    Cloth panels are first rendered to their canonical mid-surface mesh.  The
    API then grows a semantic region from one triangle belonging to
    ``patch_id``.  Selected triangles are mapped back to persistent patch ids.
    If the preview cannot be built, the metadata-based logical group remains a
    safe fallback for legacy or temporarily invalid documents.
    """

    seed_patch = document.patches.get(str(patch_id))
    if seed_patch is None:
        return ()
    # A persistent textile group is a user-authored identity.  The surface API
    # may create that identity from scene geometry, but it must never grow an
    # existing textile group into neighbouring groups simply because they touch.
    explicit_group = explicit_textile_group_id(document, patch_id)
    if explicit_group:
        return textile_group_patch_ids(document, explicit_group) or (str(patch_id),)
    try:
        from laserprog_studio.tool_api import surface_selection
        from .mesh_builder import build_cloth_surface_mesh

        build = build_cloth_surface_mesh(document, name="Cloth selection surface")
        if build.mesh is None or build.issues:
            return logical_patch_group(document, patch_id)
        seed_range = build.patch_triangle_ranges.get(str(patch_id))
        if seed_range is None or seed_range[0] >= seed_range[1]:
            return logical_patch_group(document, patch_id)
        snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(
            build.mesh,
            object_id=f"cloth-document:{id(document)}",
            revision_token=str(document.revision),
        )
        seed_face = int(seed_range[0])
        profile = surface_selection.SurfaceSelectionProfile.cloth_support()
        if automatic:
            region = surface_selection.auto_surface_region(
                snapshot, seed_face, profile=profile, cache=cache
            )
        else:
            region = surface_selection.select_surface_region(
                snapshot,
                seed_face,
                max(0.0, min(1.0, float(tolerance))),
                profile=profile,
                cache=cache,
            )
        selected_faces = set(region.face_indices)
        selected_patches = {
            candidate_id
            for candidate_id, (start, end) in build.patch_triangle_ranges.items()
            if any(index in selected_faces for index in range(int(start), int(end)))
        }
        # Persistent creation groups remain an explicit user-level contract.
        # The API can expand beyond them when geometry is continuously related,
        # but it must never split one already-declared logical textile panel.
        selected_patches.update(logical_patch_group(document, patch_id))
        return tuple(
            candidate_id
            for candidate_id in document.patches
            if candidate_id in selected_patches
        ) or logical_patch_group(document, patch_id)
    except Exception:
        return logical_patch_group(document, patch_id)


def assign_logical_patch_group(
    document: ClothDocument,
    patch_ids: Iterable[str],
    group_id: str,
    *,
    origin: str = "legacy_assignment",
    parent_group_ids: Iterable[str] = (),
) -> tuple[str, ...]:
    """Assign one exclusive persistent identity to technical textile patches.

    Parent ids are retained only as provenance.  They never participate in
    selection or merge the new group with the groups that helped create it.
    """

    return create_textile_group(
        document,
        patch_ids,
        group_id=str(group_id),
        origin=origin,
        parent_group_ids=parent_group_ids,
    )

def delete_cloth_selection(
    document: ClothDocument,
    *,
    point_ids: Iterable[str] = (),
    curve_ids: Iterable[str] = (),
    patch_ids: Iterable[str] = (),
) -> ClothDeleteResult:
    """Delete selected entities while keeping the remaining graph valid.

    Deleting a point removes its incident curves. Deleting a curve removes any
    face that depends on it. Deleting a face keeps its reusable boundary curves.
    Orphan points are cleaned automatically after curve removal.
    """

    points = {str(value) for value in point_ids if str(value) in document.points}
    curves = {str(value) for value in curve_ids if str(value) in document.curves}
    patches = {str(value) for value in patch_ids if str(value) in document.patches}

    removed_curve_point_ids: set[str] = set()
    for curve in document.curves.values():
        if points.intersection(curve.point_ids):
            curves.add(curve.id)
    for curve_id in curves:
        curve = document.curves.get(curve_id)
        if curve is not None:
            removed_curve_point_ids.update(curve.point_ids)

    for patch in document.patches.values():
        used = set(patch.outer_curve_ids)
        used.update(value for loop in patch.hole_curve_loops for value in loop)
        if used.intersection(curves):
            patches.add(patch.id)

    folds = {
        fold_id
        for fold_id, fold in document.folds.items()
        if fold.curve_id in curves or fold.patch_a_id in patches or fold.patch_b_id in patches
    }
    seams = {
        seam_id
        for seam_id, seam in document.seams.items()
        if curves.intersection((*seam.first_curve_ids, *seam.second_curve_ids))
    }

    if not (points or curves or patches or folds or seams):
        return ClothDeleteResult(False)

    for fold_id in folds:
        document.folds.pop(fold_id, None)
    for seam_id in seams:
        document.seams.pop(seam_id, None)
    for patch_id in patches:
        document.patches.pop(patch_id, None)
    for curve_id in curves:
        document.curves.pop(curve_id, None)

    referenced_points = {point_id for curve in document.curves.values() for point_id in curve.point_ids}
    # Only clean points made orphan by the curves removed in this operation.
    # Standalone construction points are legitimate Cloth entities and must not
    # disappear merely because the user deleted an unrelated face.
    orphan_points = {point_id for point_id in removed_curve_point_ids if point_id not in referenced_points}
    points.update(orphan_points)
    for point_id in points:
        document.points.pop(point_id, None)

    fold_curves = {fold.curve_id for fold in document.folds.values()}
    seam_curves = {
        curve_id
        for seam in document.seams.values()
        for curve_id in (*seam.first_curve_ids, *seam.second_curve_ids)
    }
    for curve in document.curves.values():
        if curve.id in fold_curves:
            curve.role = ClothCurveRole.FOLD
        elif curve.id in seam_curves:
            curve.role = ClothCurveRole.SEAM
        elif curve.role in {ClothCurveRole.FOLD, ClothCurveRole.SEAM}:
            curve.role = ClothCurveRole.BOUNDARY

    document._touch()
    return ClothDeleteResult(
        True,
        points=len(points),
        curves=len(curves),
        patches=len(patches),
        folds=len(folds),
        seams=len(seams),
    )


def _polygon_area(points: tuple[Point2, ...]) -> float:
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


def _point_in_polygon(point: Point2, polygon: tuple[Point2, ...]) -> bool:
    x, y = float(point[0]), float(point[1])
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if _point_segment_distance((x, y), previous, current) <= 1.0e-6:
            return True
        if (y1 > y) != (y2 > y):
            cross_x = (x2 - x1) * (y - y1) / ((y2 - y1) or 1.0e-30) + x1
            if x < cross_x:
                inside = not inside
        previous = current
    return inside


def _point_segment_distance(point: Point2, start: Point2, end: Point2) -> float:
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-30:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    qx, qy = ax + t * dx, ay + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5


__all__ = [
    "ClothDeleteResult",
    "assign_logical_patch_group",
    "delete_cloth_selection",
    "logical_patch_group",
    "logical_patch_group_count",
    "logical_patch_group_key",
    "logical_patch_group_representatives",
    "nearest_document_patch",
    "smart_logical_patch_group",
]
