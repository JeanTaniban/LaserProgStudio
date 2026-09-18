# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from typing import Any

from laserprog_studio.geometry_ops.manifold_contract import (
    construct_manifold as _construct_manifold_arrays,
    manifold_is_valid as _manifold_is_valid,
    manifold_status_text as _manifold_status_text,
)



class BooleanEmptyResult(ValueError):
    """A valid boolean difference consumed the complete target volume."""


def _boolean_diagnostics_enabled() -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics

        return bool(should_record_diagnostics())
    except Exception:
        return False


def _record_boolean_event(stage: str, **payload: Any) -> None:
    if not _boolean_diagnostics_enabled():
        return
    try:
        from laserprog_studio.diagnostics.boolean_debug import record_boolean_event

        record_boolean_event(stage, **payload)
    except Exception:
        pass



def bounds_touch_or_overlap(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
    *,
    tolerance: float = 0.05,
) -> bool:
    """Return True when two world-aligned bounds touch or overlap.

    Bounds use the LaserProg convention:
        xmin, xmax, ymin, ymax, zmin, zmax
    """
    tol = abs(float(tolerance))
    return (
        float(a[0]) <= float(b[1]) + tol and float(a[1]) + tol >= float(b[0])
        and float(a[2]) <= float(b[3]) + tol and float(a[3]) + tol >= float(b[2])
        and float(a[4]) <= float(b[5]) + tol and float(a[5]) + tol >= float(b[4])
    )



def is_closed_triangle_mesh(vertices: Any, triangles: Any) -> tuple[bool, int, int]:
    """Return (closed, boundary_edges, nonmanifold_edges) for indexed triangles."""
    from collections import Counter

    try:
        vertex_count = len(vertices)
    except Exception:
        vertex_count = 0
    edges: Counter[tuple[int, int]] = Counter()
    try:
        iterable = list(triangles)
    except Exception:
        return False, 0, 0
    for tri in iterable:
        try:
            a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
        except Exception:
            return False, 0, 0
        if not (0 <= a < vertex_count and 0 <= b < vertex_count and 0 <= c < vertex_count):
            return False, 0, 0
        for x, y in ((a, b), (b, c), (c, a)):
            if x == y:
                continue
            edge = (x, y) if x < y else (y, x)
            edges[edge] += 1
    boundary = sum(1 for count in edges.values() if count == 1)
    nonmanifold = sum(1 for count in edges.values() if count > 2)
    return boundary == 0 and nonmanifold == 0 and bool(edges), boundary, nonmanifold


def _workmesh_class():
    try:
        from laserprog_studio.domain.work_model import WorkMesh
        return WorkMesh
    except Exception:
        return None


def _mesh_needs_heavy_boolean_repair(mesh: Any) -> tuple[bool, str]:
    """Return whether a boolean input needs optional repair backends.

    Most Studio primitives and generated tools are already closed indexed triangle
    meshes.  Sending every clean mesh through trimesh + PyVista made the first
    boolean pay a large one-time import/VTK initialization cost.  Keep the fast
    path conservative: skip the optional repair stack only when the topology is
    already closed and non-manifold-free.  Winding and tiny degenerate cleanup are
    still handled by _prepared_boolean_arrays below.
    """

    vertices = getattr(mesh, "vertices", [])
    triangles = getattr(mesh, "triangles", [])
    if vertices is None:
        vertices = []
    if triangles is None:
        triangles = []
    closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(vertices, triangles)
    if closed:
        return False, "closed"
    if boundary_edges or nonmanifold_edges:
        return True, f"open/nonmanifold boundary={boundary_edges} nonmanifold={nonmanifold_edges}"
    return True, "invalid"


def _repair_for_boolean(mesh: Any, *, label: str):
    needs_repair, _reason = _mesh_needs_heavy_boolean_repair(mesh)
    if not needs_repair:
        return mesh
    try:
        from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh

        repaired, report = repair_work_mesh(
            mesh,
            tolerance_mm=0.005,
            fill_holes=True,
            remove_tiny_faces=True,
            optional_backends=True,
        )
        return repaired
    except Exception:
        return mesh


def _offset_cutter_for_difference(mesh: Any, *, margin_mm: float = 0.03):
    try:
        from laserprog_studio.geometry_ops.mesh_repair import offset_mesh_uniform_by_face_planes

        return offset_mesh_uniform_by_face_planes(mesh, margin_mm=margin_mm)
    except Exception:
        return mesh


def _orient_triangles_for_manifold(vertices: Any, triangles: Any):
    """Return consistently wound triangles suitable for manifold3d.

    The primitive cylinder/cone code in older LaserProg builds produced closed
    meshes whose side faces had the opposite winding from their caps. Those
    meshes pass a simple watertight edge-count test, but manifold3d interprets
    them as an invalid/inverted solid, which makes a cube-cylinder subtraction
    fail or produce an empty result. This repair is deliberately local and
    topology-preserving: it only flips triangle index order, never moves points.
    """
    from collections import defaultdict, deque
    import numpy as np

    verts = np.asarray(vertices, dtype=np.float64)
    tris = np.asarray(triangles, dtype=np.int32)
    if tris.size == 0:
        return tris
    if tris.ndim == 1:
        tris = tris.reshape((-1, 3))
    if len(tris) == 0:
        return tris

    # Drop degenerate faces. They confuse adjacency and manifold conversion but
    # do not contribute to a valid closed volume.
    a = tris[:, 0]
    b = tris[:, 1]
    c = tris[:, 2]
    valid = (a != b) & (b != c) & (a != c)
    if verts.ndim == 2 and verts.shape[1] >= 3 and len(verts) > 0:
        va = verts[a, :3]
        vb = verts[b, :3]
        vc = verts[c, :3]
        valid &= np.linalg.norm(np.cross(vb - va, vc - va), axis=1) > 1e-12
    tris = tris[valid]
    if len(tris) == 0:
        return tris

    edge_map: dict[tuple[int, int], list[tuple[int, tuple[int, int]]]] = defaultdict(list)
    for ti, (x, y, z) in enumerate(tris):
        for u, v in ((int(x), int(y)), (int(y), int(z)), (int(z), int(x))):
            key = (u, v) if u < v else (v, u)
            edge_map[key].append((ti, (u, v)))

    def effective_edges(tri: Any, flipped: bool) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        x, y, z = int(tri[0]), int(tri[1]), int(tri[2])
        if flipped:
            return ((x, z), (z, y), (y, x))
        return ((x, y), (y, z), (z, x))

    flips = [False] * len(tris)
    visited = [False] * len(tris)
    components: list[list[int]] = []

    for start in range(len(tris)):
        if visited[start]:
            continue
        visited[start] = True
        queue: deque[int] = deque([start])
        component: list[int] = []
        while queue:
            cur = queue.popleft()
            component.append(cur)
            for u, v in effective_edges(tris[cur], flips[cur]):
                key = (u, v) if u < v else (v, u)
                for other, other_base_dir in edge_map.get(key, []):
                    if other == cur:
                        continue
                    # Adjacent triangles must traverse a shared edge in opposite directions.
                    # The neighbour is currently unflipped: if its base edge has the same
                    # direction as the current effective edge, flip it.
                    desired_flip = other_base_dir == (u, v)
                    if not visited[other]:
                        flips[other] = desired_flip
                        visited[other] = True
                        queue.append(other)
        components.append(component)

    fixed = tris.copy()
    for ti, do_flip in enumerate(flips):
        if do_flip:
            fixed[ti] = (fixed[ti, 0], fixed[ti, 2], fixed[ti, 1])

    # Choose outward orientation per connected component. For a closed mesh the
    # signed volume must be positive when faces are wound outward.
    if verts.ndim == 2 and verts.shape[1] >= 3:
        verts3 = verts[:, :3]
        for component in components:
            volume = 0.0
            for ti in component:
                x, y, z = fixed[ti]
                volume += float(np.dot(verts3[x], np.cross(verts3[y], verts3[z])) / 6.0)
            if volume < -1e-9:
                for ti in component:
                    fixed[ti] = (fixed[ti, 0], fixed[ti, 2], fixed[ti, 1])
    return fixed


def _prepared_boolean_arrays(mesh: Any, *, label: str):
    import numpy as np

    triangles = np.asarray(getattr(mesh, "triangles", []), dtype=np.int32)
    # Keep world-space coordinates in float64.  Converting a valid CAD mesh to
    # float32 before Manifold ingestion can collapse nearby vertices when the
    # object is far from the origin, creating a false NotManifold result.
    vertices = np.asarray(getattr(mesh, "vertices", []), dtype=np.float64)

    if triangles.size == 0 or vertices.size == 0:
        raise ValueError(f"Boolean operation failed: {label} mesh is empty.")
    if vertices.ndim != 2 or vertices.shape[1] < 3:
        raise ValueError(f"Boolean operation failed: {label} mesh vertices are invalid.")
    if triangles.ndim != 2 or triangles.shape[1] != 3:
        raise ValueError(f"Boolean operation failed: {label} mesh triangles are invalid.")

    vertices = vertices[:, :3].copy()
    triangles = _orient_triangles_for_manifold(vertices, triangles).astype(np.int32, copy=False)
    if len(triangles) == 0:
        raise ValueError(f"Boolean operation failed: {label} mesh has no valid triangles.")

    # Keep manifold3d.Mesh.merge() enabled for normal closed solids.  A closed
    # indexed mesh can still contain duplicate XYZ vertices on seams or after a
    # previous boolean; manifold3d is much more reliable when those ordinary
    # duplicates are welded before constructing the Manifold.  The only known
    # case where welding is unsafe is the image-mask relief diagonal-contact
    # geometry, which marks itself explicitly with _lps_skip_boolean_merge.
    #
    # This matters for chained workflows such as:
    #   (mesh - PlanTracer volume) union (another PlanTracer volume)
    # The intermediate result is closed, but skipping merge can let manifold3d
    # interpret the next union as an empty/invalid result on exact seams.
    skip_merge = bool(getattr(mesh, "_lps_skip_boolean_merge", False))
    return vertices, triangles, skip_merge



def _boolean_mesh_extent(mesh: Any) -> float:
    """Return a conservative world-space size used for repair tolerances."""

    try:
        import numpy as np

        vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float64)
        if vertices.ndim != 2 or vertices.shape[0] == 0 or vertices.shape[1] < 3:
            return 1.0
        span = np.ptp(vertices[:, :3], axis=0)
        value = float(np.max(span))
        if not np.isfinite(value) or value <= 0.0:
            return 1.0
        return value
    except Exception:
        return 1.0



def _boolean_input_summary(mesh: Any, *, label: str, manifold_status: str | None = None) -> str:
    vertices = getattr(mesh, "vertices", []) or []
    triangles = getattr(mesh, "triangles", []) or []
    closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(vertices, triangles)
    parts = [
        f"{label}",
        f"vertices={len(vertices)}",
        f"triangles={len(triangles)}",
        f"indexed_closed={bool(closed)}",
        f"boundary_edges={int(boundary_edges)}",
        f"nonmanifold_edges={int(nonmanifold_edges)}",
    ]
    if manifold_status:
        parts.append(f"manifold_status={manifold_status}")
    return ", ".join(parts)


def _boolean_input_provenance(mesh: Any) -> dict[str, Any]:
    metadata = dict(getattr(mesh, "metadata", {}) or {})
    keys = (
        "source_tool",
        "editable_tool_id",
        "editable_kind",
        "plan_trace_operation",
        "boolean_ready",
        "boolean_ready_backend",
        "boolean_geometry_contract",
        "boolean_topology_contract",
        "joint_builder_topology_contract",
        "joint_builder_geometry_contract",
        "boolean_geometric_manifold",
    )
    return {
        "name": str(getattr(mesh, "name", "") or ""),
        "mesh_id": str(getattr(mesh, "mesh_id", "") or ""),
        "metadata": {key: metadata.get(key) for key in keys if key in metadata},
    }


def _geometric_boolean_topology(mesh: Any) -> dict[str, Any] | None:
    try:
        from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology

        return analyze_work_mesh_boolean_topology(mesh).as_dict()
    except Exception:
        return None


def _boolean_input_origin_text(mesh: Any) -> str:
    provenance = _boolean_input_provenance(mesh)
    metadata = dict(provenance.get("metadata") or {})
    parts = []
    for key in (
        "source_tool",
        "editable_kind",
        "plan_trace_operation",
        "joint_builder_geometry_contract",
        "joint_builder_topology_contract",
        "boolean_geometry_contract",
        "boolean_topology_contract",
    ):
        value = metadata.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    return ";".join(parts) if parts else "unknown"


def _construct_manifold_once(mesh: Any, *, label: str, np: Any, m3d: Any):
    vertices, triangles, skip_merge = _prepared_boolean_arrays(mesh, label=label)
    try:
        construction = _construct_manifold_arrays(
            m3d,
            vertices=vertices,
            triangles=triangles,
            merge=not skip_merge,
            prefer_64bit=True,
        )
    except Exception as exc:
        raise ValueError(
            "Boolean operation failed while constructing the manifold input: "
            + _boolean_input_summary(mesh, label=label)
        ) from exc
    return (
        construction.manifold,
        str(construction.status),
        bool(construction.merge_changed),
    )


def _construct_valid_manifold(mesh: Any, *, label: str, np: Any, m3d: Any):
    """Build a valid manifold, retrying conservative geometric cleanup.

    Plan Tracer and imported meshes can be closed *by triangle indices* while
    still containing coincident seam vertices or duplicate coplanar triangles.
    ``Mesh.merge()`` then exposes a geometric non-manifold condition.  The old
    boolean path never inspected ``Manifold.status()`` and continued with an
    invalid/empty object, eventually showing the misleading generic message
    that the volumes were not closed.

    Keep the fast path unchanged for normal primitives.  Only invalid manifold
    inputs pay for a conservative vertex weld / duplicate-face cleanup, followed
    by an optional backend repair as a last resort.
    """

    attempts: list[str] = []
    current = mesh
    manifold, status, merge_changed = _construct_manifold_once(current, label=label, np=np, m3d=m3d)
    attempts.append(
        _boolean_input_summary(current, label=label, manifold_status=status)
        + f", merge_changed={merge_changed}, attempt=original"
    )
    _record_boolean_event(
        "boolean.input.manifold",
        label=label,
        attempt="original",
        status=status,
        merge_changed=merge_changed,
        summary=attempts[-1],
    )
    if _manifold_is_valid(manifold, m3d):
        return manifold, current, attempts

    # A mesh may be perfectly closed by triangle indices yet become invalid as
    # soon as manifold3d merges coincident XYZ vertices.  This is the signature
    # of zero-length seam cells / bow-tie contacts seen after legacy Joint
    # Builder output.  Generic tiny-face repair is destructive in that case: it
    # removes the collapsed cells and merely turns the defect into open boundary
    # edges.  Diagnose and reject that source topology instead of pretending the
    # automatic repair can safely invent the missing surface.
    geometric = _geometric_boolean_topology(mesh)
    if geometric is not None:
        _record_boolean_event(
            "boolean.input.geometric_topology",
            label=label,
            topology=geometric,
            provenance=_boolean_input_provenance(mesh),
        )
        if bool(geometric.get("indexed_closed")) and not bool(geometric.get("geometrically_manifold")):
            detail = (
                _boolean_input_summary(mesh, label=label, manifold_status=status)
                + ", geometry_after_weld_invalid=True"
                + f", welded_vertices={geometric.get('welded_vertices')}/{geometric.get('vertices')}"
                + f", collapsed_triangles={geometric.get('collapsed_triangles_after_weld')}"
                + f", duplicate_triangles={geometric.get('duplicate_triangles_after_weld')}"
                + f", welded_boundary_edges={geometric.get('welded_boundary_edges')}"
                + f", welded_nonmanifold_vertices={geometric.get('welded_nonmanifold_vertices')}"
                + f", origin={_boolean_input_origin_text(mesh)}"
            )
            attempts.append(detail)
            _record_boolean_event(
                "boolean.input.rejected_geometric_seam",
                label=label,
                topology=geometric,
                provenance=_boolean_input_provenance(mesh),
                attempts=attempts,
            )
            raise ValueError(
                "Boolean operation rejected a geometrically invalid closed input. "
                "The mesh is watertight by triangle indices, but coincident vertices collapse "
                "zero-length/duplicate cells when the boolean kernel welds the geometry. "
                "This defect must be fixed at the generating/editing tool rather than by deleting triangles.\n  - "
                + "\n  - ".join(attempts)
            )

    extent = _boolean_mesh_extent(mesh)
    tolerance = max(1.0e-7, min(1.0e-4, extent * 1.0e-8))
    try:
        from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh

        repaired, report = repair_work_mesh(
            mesh,
            tolerance_mm=tolerance,
            fill_holes=False,
            remove_tiny_faces=True,
            optional_backends=False,
        )
        manifold, status, merge_changed = _construct_manifold_once(repaired, label=label, np=np, m3d=m3d)
        attempts.append(
            _boolean_input_summary(repaired, label=label, manifold_status=status)
            + (
                f", merge_changed={merge_changed}, attempt=conservative_repair"
                f", tolerance_mm={tolerance:g}"
                f", removed_degenerate={int(getattr(report, 'removed_degenerate', 0))}"
                f", removed_duplicates={int(getattr(report, 'removed_duplicate_triangles', 0))}"
            )
        )
        _record_boolean_event(
            "boolean.input.repair",
            label=label,
            attempt="conservative_repair",
            status=status,
            merge_changed=merge_changed,
            summary=attempts[-1],
        )
        if _manifold_is_valid(manifold, m3d):
            return manifold, repaired, attempts
    except Exception as exc:
        attempts.append(f"{label}, attempt=conservative_repair, error={type(exc).__name__}: {exc}")
        _record_boolean_event(
            "boolean.input.repair_error",
            label=label,
            attempt="conservative_repair",
            error_type=type(exc).__name__,
            error=str(exc),
        )

    # Expensive optional repair is reserved for an input that manifold3d has
    # already rejected.  This keeps the ordinary primitive/Plan Tracer path fast.
    try:
        from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh

        fallback_tolerance = max(tolerance * 10.0, 1.0e-5)
        fallback_tolerance = min(fallback_tolerance, 1.0e-3)
        repaired, report = repair_work_mesh(
            mesh,
            tolerance_mm=fallback_tolerance,
            fill_holes=True,
            remove_tiny_faces=True,
            optional_backends=True,
        )
        manifold, status, merge_changed = _construct_manifold_once(repaired, label=label, np=np, m3d=m3d)
        attempts.append(
            _boolean_input_summary(repaired, label=label, manifold_status=status)
            + (
                f", merge_changed={merge_changed}, attempt=backend_repair"
                f", tolerance_mm={fallback_tolerance:g}"
                f", removed_degenerate={int(getattr(report, 'removed_degenerate', 0))}"
                f", removed_duplicates={int(getattr(report, 'removed_duplicate_triangles', 0))}"
            )
        )
        _record_boolean_event(
            "boolean.input.repair",
            label=label,
            attempt="backend_repair",
            status=status,
            merge_changed=merge_changed,
            summary=attempts[-1],
        )
        if _manifold_is_valid(manifold, m3d):
            return manifold, repaired, attempts
    except Exception as exc:
        attempts.append(f"{label}, attempt=backend_repair, error={type(exc).__name__}: {exc}")
        _record_boolean_event(
            "boolean.input.repair_error",
            label=label,
            attempt="backend_repair",
            error_type=type(exc).__name__,
            error=str(exc),
        )

    detail = "\n  - ".join(attempts)
    _record_boolean_event("boolean.input.rejected", label=label, attempts=attempts)
    raise ValueError(
        "Boolean operation rejected an invalid manifold input after automatic repair.\n"
        f"  - {detail}"
    )


def _finalize_canonical_boolean_mesh(mesh: Any):
    """Validate and tag a canonical manifold3d result without retessellating it.

    A manifold3d result has already passed its own solid validity check. Generic
    mesh repair after that point is unsafe because welding/removing tiny faces may
    create holes in a tessellation that was valid before cleanup.
    """
    vertices = getattr(mesh, "vertices", []) or []
    triangles = getattr(mesh, "triangles", []) or []
    closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(vertices, triangles)
    if not closed:
        raise ValueError(
            "Boolean operation produced an invalid canonical result "
            f"(boundary_edges={boundary_edges}, nonmanifold_edges={nonmanifold_edges})."
        )
    metadata = deepcopy(getattr(mesh, "metadata", {}) or {})
    metadata["boolean_ready"] = True
    metadata["boolean_topology_contract"] = "manifold3d_canonical_v1"
    mesh.metadata = metadata
    return mesh


def boolean_mesh_3d(mesh_a: Any, mesh_b: Any, *, operation: str, cutter_margin_mm: float | None = None):
    """Run a robust 3D boolean through manifold3d.

    operation:
        "union"      -> mesh_a U mesh_b
        "difference" -> mesh_a - mesh_b

    This module intentionally refuses approximate 2D fallbacks. Boolean tools are
    expected to modify real 3D solids, and a fallback would silently create bad
    geometry as soon as pieces are rotated or offset in depth.
    """
    try:
        import numpy as np
        import manifold3d as m3d
    except Exception as exc:  # pragma: no cover - optional runtime dependency
        raise RuntimeError(
            "Boolean operations require the 'manifold3d' package. "
            "Run INSTALL_DEPENDENCIES.bat again if it is missing."
        ) from exc

    op = (operation or "").strip().lower()
    if op not in {"union", "difference"}:
        raise ValueError(f"Unknown boolean operation: {operation!r}")

    source_mesh_a = mesh_a
    try:
        from laserprog_studio.tooling.cloth.boolean_bridge import prepare_cloth_mesh_for_boolean

        mesh_a = prepare_cloth_mesh_for_boolean(mesh_a)
    except Exception as exc:
        # A recognised Cloth source must not silently fall back to the old open
        # surface path: that would reproduce a misleading generic manifold error.
        try:
            from laserprog_studio.tooling.cloth.boolean_bridge import is_editable_cloth_mesh

            if is_editable_cloth_mesh(source_mesh_a):
                raise ValueError(f"Cloth boolean preparation failed: {exc}") from exc
        except ValueError:
            raise
        except Exception:
            pass

    if _boolean_diagnostics_enabled():
        _record_boolean_event(
            "boolean.request",
            operation=op,
            first=_boolean_input_summary(mesh_a, label="first"),
            second=_boolean_input_summary(mesh_b, label="second"),
            first_provenance=_boolean_input_provenance(mesh_a),
            second_provenance=_boolean_input_provenance(mesh_b),
            first_geometric_topology=_geometric_boolean_topology(mesh_a),
            second_geometric_topology=_geometric_boolean_topology(mesh_b),
            cutter_margin_mm=cutter_margin_mm,
        )

    # Fast path: clean Studio-generated meshes go directly to manifold3d.
    # Dirty/imported meshes still use the heavier trimesh/PyVista repair stack.
    mesh_a = _repair_for_boolean(mesh_a, label="first")
    mesh_b = _repair_for_boolean(mesh_b, label="second")
    # Difference cutters may receive a user clearance.  This must be a true
    # uniform surface offset, not a proportional bounds scale: a long rectangle
    # and a square must both grow/shrink by the same millimetres on every side.
    # When callers do not specify a value, keep the historical tiny robustness
    # margin used against coplanar/tangent boolean slivers.
    applied_margin = 0.0
    if op == "difference":
        margin = 0.03 if cutter_margin_mm is None else float(cutter_margin_mm)
        applied_margin = margin
        if abs(margin) > 1e-12:
            mesh_b = _offset_cutter_for_difference(mesh_b, margin_mm=margin)

    # Construct and validate each manifold explicitly.  manifold3d does not
    # necessarily raise from its constructor: invalid geometry is often reported
    # only through ``status()`` and represented by an empty manifold.  Repair
    # geometric seam/duplicate defects only after this real validation fails.
    ma, mesh_a, attempts_a = _construct_valid_manifold(mesh_a, label="first", np=np, m3d=m3d)
    mb, mesh_b, attempts_b = _construct_valid_manifold(mesh_b, label="second", np=np, m3d=m3d)

    try:
        if op == "union":
            result = ma.add(mb) if hasattr(ma, "add") else (ma + mb)
            name = f"union({getattr(mesh_a, 'name', 'A')},{getattr(mesh_b, 'name', 'B')})"
        else:
            result = ma.subtract(mb) if hasattr(ma, "subtract") else (ma - mb)
            name = str(getattr(mesh_a, "name", "difference"))
    except Exception as exc:
        raise ValueError("Boolean operation failed inside manifold3d.") from exc

    try:
        out_mesh = result.to_mesh()
        vertices = np.asarray(out_mesh.vert_properties, dtype=float)
        triangles = np.asarray(out_mesh.tri_verts, dtype=np.int32)
    except Exception as exc:
        raise ValueError("Boolean operation failed: cannot convert result mesh.") from exc

    if vertices.ndim == 1:
        if vertices.size % 3 != 0:
            raise ValueError("Boolean operation failed: invalid result vertices.")
        vertices = vertices.reshape((-1, 3))
    if triangles.ndim == 1:
        if triangles.size % 3 != 0:
            raise ValueError("Boolean operation failed: invalid result triangles.")
        triangles = triangles.reshape((-1, 3))

    if vertices.ndim != 2 or vertices.shape[1] < 3 or triangles.ndim != 2 or triangles.shape[1] != 3:
        raise ValueError("Boolean operation failed: malformed result.")
    if len(vertices) == 0 or len(triangles) == 0:
        _record_boolean_event(
            "boolean.result.empty",
            operation=op,
            first_attempts=attempts_a,
            second_attempts=attempts_b,
        )
        if op == "difference":
            raise BooleanEmptyResult(
                "Boolean difference consumed the complete target volume; the target must be removed."
            )
        raise ValueError("Boolean operation produced an empty result.")
    closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(vertices[:, :3], triangles)
    if not closed:
        raise ValueError(
            "Boolean operation produced a non-closed result "
            f"(boundary_edges={boundary_edges}, nonmanifold_edges={nonmanifold_edges})."
        )

    WorkMesh = _workmesh_class()
    if WorkMesh is None:
        raise RuntimeError("Boolean operation failed: WorkMesh class is unavailable.")

    out = WorkMesh(
        name=name,
        vertices=[(float(x), float(y), float(z)) for x, y, z in vertices[:, :3]],
        triangles=[(int(a), int(b), int(c)) for a, b, c in triangles],
        color=str(getattr(mesh_a, "color", "#B8B8B8") or "#B8B8B8"),
        material=deepcopy(getattr(mesh_a, "material", None)),
        engraving=deepcopy(getattr(mesh_a, "engraving", None)),
        metadata=deepcopy(getattr(mesh_a, "metadata", {}) or {}),
    )
    _copy_runtime_mesh_attrs(mesh_a, out)

    # IMPORTANT: ``result.to_mesh()`` above is already the canonical output of a
    # valid manifold3d solid and has just passed the closed-edge contract.  Do
    # not run generic vertex welding / tiny-face removal on that canonical mesh.
    # A previous cleanup pass could delete zero-area/sliver triangles that are
    # topologically required by manifold3d's tessellation.  That turned a valid
    # Joint Builder result into an open mesh (typically a handful of missing
    # triangles and ~10-20 boundary edges), so the *next* boolean failed even
    # though the joint itself had succeeded.
    #
    # Cleanup remains available for *inputs* before manifold construction.  Once
    # manifold3d has produced and validated the result, its topology is the source
    # of truth and must be preserved byte-for-byte at the triangle level.
    out = _finalize_canonical_boolean_mesh(out)
    try:
        from laserprog_studio.tooling.cloth.boolean_bridge import attach_boolean_operation_to_cloth_result

        out = attach_boolean_operation_to_cloth_result(
            source_mesh_a,
            mesh_b,
            out,
            operation=op,
            margin_mm=applied_margin,
        )
    except Exception as exc:
        try:
            from laserprog_studio.tooling.cloth.boolean_bridge import is_editable_cloth_mesh

            if is_editable_cloth_mesh(source_mesh_a):
                raise ValueError(f"Cloth boolean metadata update failed: {exc}") from exc
        except ValueError:
            raise
        except Exception:
            pass
    _record_boolean_event(
        "boolean.result.success",
        operation=op,
        vertices=len(getattr(out, "vertices", []) or []),
        triangles=len(getattr(out, "triangles", []) or []),
        first_attempts=attempts_a,
        second_attempts=attempts_b,
    )
    return out



def _copy_runtime_mesh_attrs(src: Any, dst: Any) -> None:
    """Copy LaserProg runtime metadata that is not part of WorkMesh itself.

    Boolean results are freshly generated meshes.  Do not propagate
    _lps_skip_boolean_merge from an input: that flag protects one very specific
    mask-relief topology before boolean conversion, but a manifold3d result is
    already re-indexed and should be allowed to merge normally in later chained
    booleans.
    """
    try:
        for name in dir(src):
            if not name.startswith("_lps_"):
                continue
            if name == "_lps_skip_boolean_merge":
                continue
            try:
                setattr(dst, name, getattr(src, name))
            except Exception:
                pass
    except Exception:
        pass


def split_disconnected_mesh(mesh: Any) -> list[Any]:
    """Split one mesh into its disconnected triangle islands.

    Connectivity is based on shared vertex indices. This is exactly what is
    needed after a boolean difference that leaves several independent solids in
    a single mesh container.
    """
    WorkMesh = _workmesh_class()
    if WorkMesh is None:
        raise RuntimeError("Separate operation failed: WorkMesh class is unavailable.")

    vertices_in = list(getattr(mesh, "vertices", []) or [])
    triangles_in = list(getattr(mesh, "triangles", []) or [])
    if not vertices_in or not triangles_in:
        return [mesh]

    vertices: list[tuple[float, float, float]] = []
    for v in vertices_in:
        try:
            vertices.append((float(v[0]), float(v[1]), float(v[2])))
        except Exception:
            raise ValueError("Separate operation failed: invalid vertex data.")

    triangles: list[tuple[int, int, int]] = []
    for t in triangles_in:
        try:
            a, b, c = int(t[0]), int(t[1]), int(t[2])
        except Exception:
            raise ValueError("Separate operation failed: invalid triangle data.")
        if not (0 <= a < len(vertices) and 0 <= b < len(vertices) and 0 <= c < len(vertices)):
            raise ValueError("Separate operation failed: triangle index is out of range.")
        triangles.append((a, b, c))

    parent = list(range(len(vertices)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b, c in triangles:
        union(a, b)
        union(a, c)

    tri_groups: dict[int, list[tuple[int, int, int]]] = {}
    for tri in triangles:
        root = find(tri[0])
        tri_groups.setdefault(root, []).append(tri)

    if len(tri_groups) <= 1:
        return [mesh]

    base_name = str(getattr(mesh, "name", "part") or "part")
    color = str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8")
    components: list[Any] = []
    for comp_index, group in enumerate(tri_groups.values(), start=1):
        used: list[int] = sorted({idx for tri in group for idx in tri})
        remap = {old: new for new, old in enumerate(used)}
        comp_vertices = [vertices[old] for old in used]
        comp_triangles = [(remap[a], remap[b], remap[c]) for a, b, c in group]
        comp = WorkMesh(
            name=f"{base_name}_part_{comp_index:02d}",
            vertices=comp_vertices,
            triangles=comp_triangles,
            color=color,
        )
        _copy_runtime_mesh_attrs(mesh, comp)
        components.append(comp)

    # Keep deterministic order from left/front/bottom to right/back/top. This
    # makes selection and exported object order stable across runs.
    def comp_sort_key(comp: Any) -> tuple[float, float, float, str]:
        pts = list(getattr(comp, "vertices", []) or [])
        if not pts:
            return (0.0, 0.0, 0.0, str(getattr(comp, "name", "")))
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        zs = [float(p[2]) for p in pts]
        return (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs), str(getattr(comp, "name", "")))

    components.sort(key=comp_sort_key)
    for i, comp in enumerate(components, start=1):
        try:
            comp.name = f"{base_name}_part_{i:02d}"
        except Exception:
            pass
    return components


def boolean_difference(mesh_a: Any, mesh_b: Any, *, cutter_margin_mm: float | None = None):
    return boolean_mesh_3d(mesh_a, mesh_b, operation="difference", cutter_margin_mm=cutter_margin_mm)


def boolean_union(mesh_a: Any, mesh_b: Any):
    return boolean_mesh_3d(mesh_a, mesh_b, operation="union")
