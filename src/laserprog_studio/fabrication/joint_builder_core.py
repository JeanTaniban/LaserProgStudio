# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Sequence

try:
    from .joint_builder_probing import *  # type: ignore
except Exception:  # pragma: no cover
    from .joint_builder_probing import *  # type: ignore


def _validate_joint_boolean_outputs(
    male_mesh: WorkMesh,
    female_mesh: WorkMesh,
    *,
    debug: Callable[[str, dict], None] | None = None,
) -> dict[str, dict[str, int | bool | float]]:
    """Enforce Joint Builder's closed-solid output contract."""
    try:
        from laserprog_studio.geometry_ops.boolean_topology_contract import (
            require_geometric_boolean_manifold,
        )
    except Exception as exc:
        raise ValueError(f"Joint Builder could not load topology validation: {exc}") from exc

    result_stats: dict[str, dict[str, int | bool | float]] = {}
    for role, result_mesh in (("male", male_mesh), ("female", female_mesh)):
        metadata = dict(getattr(result_mesh, "metadata", {}) or {})
        # ``boolean_mesh_3d`` has already constructed this exact result with
        # Manifold and verified its native status.  Its exported tessellation
        # may contain vertices closer than our diagnostic weld tolerance even
        # though Manifold itself accepts it (and accepts it again when used as
        # the input to a later boolean).  Rejecting that canonical result here
        # turns a successful Joint Builder subtraction into a false failure.
        #
        # Do not apply this exception to imported/user meshes: only the private
        # contract written by ``_finalize_canonical_boolean_mesh`` earns it.
        if metadata.get("boolean_topology_contract") == "manifold3d_canonical_v1":
            try:
                from laserprog_studio.boolean_ops import is_closed_triangle_mesh

                closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(
                    getattr(result_mesh, "vertices", ()) or (),
                    getattr(result_mesh, "triangles", ()) or (),
                )
            except Exception:
                closed, boundary_edges, nonmanifold_edges = (False, 1, 1)
            if not closed:
                raise ValueError(
                    "Joint Builder received a malformed canonical boolean result "
                    f"(boundary_edges={boundary_edges}, nonmanifold_edges={nonmanifold_edges})."
                )
            result_stats[role] = {
                "vertices": int(len(getattr(result_mesh, "vertices", ()) or ())),
                "triangles": int(len(getattr(result_mesh, "triangles", ()) or ())),
                "closed": True,
                "boundary_edges": int(boundary_edges),
                "nonmanifold_edges": int(nonmanifold_edges),
                "native_canonical": True,
            }
            metadata["boolean_ready"] = True
            metadata["joint_builder_topology_contract"] = "closed_solid_v1"
            metadata["joint_builder_geometry_contract"] = "manifold3d_canonical_v1"
            metadata["boolean_geometric_manifold"] = True
            result_mesh.metadata = metadata
            continue
        try:
            topology = require_geometric_boolean_manifold(
                result_mesh,
                label=f"Joint Builder {role} result",
            )
        except ValueError as exc:
            try:
                from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology

                topology = analyze_work_mesh_boolean_topology(result_mesh)
                stats = topology.as_dict()
                stats.update({
                    "closed": bool(topology.geometrically_manifold),
                    "boundary_edges": int(topology.indexed_boundary_edges),
                    "nonmanifold_edges": int(topology.indexed_nonmanifold_edges),
                })
            except Exception:
                stats = {
                    "vertices": int(len(getattr(result_mesh, "vertices", ()) or ())),
                    "triangles": int(len(getattr(result_mesh, "triangles", ()) or ())),
                }
            result_stats[role] = stats
            if debug:
                debug("joint_output_topology_rejected", {"role": role, **stats, "error": str(exc)})
            raise ValueError(
                "Joint Builder refused an invalid solid result that would fail a later Union/Subtract. "
                f"{exc} The original parts were left unchanged."
            ) from exc

        stats = topology.as_dict()
        stats.update({
            "closed": bool(topology.geometrically_manifold),
            "boundary_edges": int(topology.indexed_boundary_edges),
            "nonmanifold_edges": int(topology.indexed_nonmanifold_edges),
        })
        result_stats[role] = stats
        metadata["boolean_ready"] = True
        # Keep the historical key stable for compatibility while recording the
        # stronger geometry-level contract separately.
        metadata["joint_builder_topology_contract"] = "closed_solid_v1"
        metadata["joint_builder_geometry_contract"] = "geometric_manifold_v2"
        metadata["boolean_geometric_manifold"] = True
        metadata["boolean_weld_tolerance"] = float(topology.weld_tolerance)
        result_mesh.metadata = metadata

    if debug:
        debug("joint_output_topology_validated", {"results": result_stats})
    return result_stats


def apply_tab_slot_simple(
    mesh_a: WorkMesh,
    mesh_b: WorkMesh,
    *,
    touch_tolerance: float,
    clearance: float,
    joint_size: float = 10.0,
    joint_count: int = 1,
    joint_edge_margin: float | None = None,
    single_depth_probe: bool = True,
    return_female_tool: bool = False,
    debug: Callable[[str, dict], None] | None = None,
) -> tuple[WorkMesh, WorkMesh] | tuple[WorkMesh, WorkMesh, WorkMesh]:
    basis_a = compute_basis(mesh_a)
    basis_b = compute_basis(mesh_b)

    if debug:
        debug(
            "mesh_basis_summary",
            {
                "piece_a": _mesh_basis_diagnostic(mesh_a, basis_a, label="A_male_selected_first"),
                "piece_b": _mesh_basis_diagnostic(mesh_b, basis_b, label="B_female_selected_second"),
            },
        )

    # Real dimensions of the boolean boxes.
    # Convention: A receives the male pin, B receives the female opening.
    thickness_a = float(basis_a.thickness)
    thickness_b = float(basis_b.thickness)
    t_min = min(thickness_a, thickness_b)
    if not (t_min > 0):
        t_min = 3.0
    if not (thickness_a > 0):
        thickness_a = t_min
    if not (thickness_b > 0):
        thickness_b = t_min

    joint_size = float(joint_size)
    if not (joint_size > 0.0):
        raise ValueError("Invalid joint size.")
    clearance = float(clearance)
    min_boolean_size_mm = 0.2
    if joint_size + 2.0 * clearance < min_boolean_size_mm:
        raise ValueError("Clearance is too negative: the female slot length would become smaller than 0.2 mm.")

    joint_count = max(1, int(joint_count))
    if joint_edge_margin is None:
        edge_margin = None
    else:
        edge_margin = float(max(0.0, joint_edge_margin))

    poly_a = footprint_polygon(mesh_a, basis_a)
    poly_b = footprint_polygon(mesh_b, basis_b)

    # Contact estimation in 3D (works for coplanar + angled boards).
    pa3, pb3, _dist = _estimate_contact_points(
        mesh_a,
        basis_a,
        poly_a,
        mesh_b,
        basis_b,
        poly_b,
        touch_tolerance=touch_tolerance,
    )
    if debug:
        debug(
            "contact_points",
            {
                "pa3": np.array(pa3, dtype=float).tolist(),
                "pb3": np.array(pb3, dtype=float).tolist(),
                "dist": float(_dist),
                "touch_tolerance": float(touch_tolerance),
            },
        )

    # 1) Draw a joint face (contact patch) on the separator plane
    # 2) Use its center as the reference point
    contact_n = pb3 - pa3
    if float(np.linalg.norm(contact_n)) <= 1e-9:
        # Degenerate closest points (overlap / vertex exactly on boundary): fall back to centroid direction.
        verts_a = np.array(mesh_a.vertices, dtype=float)
        verts_b = np.array(mesh_b.vertices, dtype=float)
        ca3 = verts_a.mean(axis=0)
        cb3 = verts_b.mean(axis=0)
        contact_n = cb3 - ca3

    if float(np.linalg.norm(contact_n)) <= 1e-9:
        # Last resort: use A normal (coplanar case).
        contact_n = basis_a.n.copy()

    center3, max_a, min_b, patch_s, patch_t, patch_geom = _contact_patch_center(
        mesh_a,
        mesh_b,
        contact_normal=contact_n,
        touch_tolerance=touch_tolerance,
    )
    patch_n3 = _normalize(np.cross(patch_s, patch_t))
    if debug:
        patch_n = _normalize(np.cross(patch_s, patch_t))
        patch_area = float(getattr(patch_geom, "area", 0.0)) if patch_geom is not None else 0.0
        debug(
            "contact_patch",
            {
                "contact_n": np.array(contact_n, dtype=float).tolist(),
                "patch_n": np.array(patch_n, dtype=float).tolist(),
                "center3": np.array(center3, dtype=float).tolist(),
                "max_a": float(max_a),
                "min_b": float(min_b),
                "plane_gap": float(abs(float(max_a) - float(min_b))),
                "patch_area": float(patch_area),
                "patch_geom_type": str(getattr(patch_geom, "geom_type", "")) if patch_geom is not None else None,
                "patch_bounds_2d": [float(v) for v in getattr(patch_geom, "bounds", (0.0, 0.0, 0.0, 0.0))] if patch_geom is not None else None,
                "patch_s": np.array(patch_s, dtype=float).tolist(),
                "patch_t": np.array(patch_t, dtype=float).tolist(),
                "joint_count": int(joint_count),
            },
        )

    # Distribute N centers along the contact patch long axis (separating plane).
    # We keep this consistent with the blue-arrow visualization so pins land exactly on the arrows.
    centers_3d: list[np.ndarray] = []
    used_seam = False
    try:
            axis2 = _major_axis_dir_2d(patch_geom)
            cx = float(np.dot(center3, patch_s))
            cy = float(np.dot(center3, patch_t))
            seg = _line_segment_along_axis_in_geom(patch_geom, center_xy=(cx, cy), axis_xy=axis2)
            if seg is None:
                # Fallback to projection range if intersection is degenerate.
                pmin, pmax = _projected_range_2d(patch_geom, axis2)
                # Convert to relative-to-center coords
                cproj = cx * axis2[0] + cy * axis2[1]
                dmin = float(pmin - cproj)
                dmax = float(pmax - cproj)
            else:
                dmin, dmax, _ = seg
            if dmax < dmin:
                dmin, dmax = dmax, dmin
            span = float(dmax - dmin)

            # Margin rule for multiple joints.
            # Earlier behavior used a hard-coded center margin of 2.5 * joint_size.
            # When the UI provides an edge margin, the user value means distance from
            # the contact border to the real edge of the joint. The center therefore
            # needs half a joint width added to stay fully inside the contact patch.
            if edge_margin is None:
                margin = float(max(0.0, 2.5 * joint_size))
                edge_margin_used = float(max(0.0, margin - 0.5 * joint_size))
                margin_mode = "historical_center_margin"
            else:
                edge_margin_used = float(edge_margin)
                margin = float(edge_margin_used + 0.5 * joint_size)
                margin_mode = "edge_margin"
            usable = span - 2.0 * margin

            if joint_count == 1:
                centers_3d = [center3]
            elif usable <= 1e-6:
                raise ValueError(
                    f"Contact surface too small for {joint_count} pins (usable length {usable:.2f} mm). "
                    f"Increase tolerance, reduce pin size, reduce N, or reduce edge margin."
                )
            else:
                # ``usable`` measures the span between the two *centres*.
                # It is not enough for it merely to be positive: neighbouring
                # tab boxes must be at least one tab width apart.  Otherwise
                # the batched tool contains overlapping solids and a later
                # union can return an indexed-closed but geometric
                # non-manifold result.
                minimum_center_span = float((joint_count - 1) * joint_size)
                if usable + 1e-6 < minimum_center_span:
                    if edge_margin is not None:
                        max_pin_size = float(max(0.0, (span - 2.0 * edge_margin_used) / joint_count))
                        size_hint = f" For these margins, use a pin size no greater than {max_pin_size:.2f} mm."
                    else:
                        size_hint = " Reduce pin size, reduce N, or provide a smaller edge margin."
                    raise ValueError(
                        f"Contact surface is too short for {joint_count} separate pins: "
                        f"available centre span is {usable:.2f} mm but {minimum_center_span:.2f} mm is required "
                        f"to prevent pin overlap.{size_hint}"
                    )
                step = usable / (joint_count - 1)
                # Use the patch plane basis returned by `_contact_patch_center`.
                # `contact_n` is only a hint and can be unstable (dist==0 cases).
                n_patch = _normalize(np.cross(patch_s, patch_t))
                d_plane = (max_a + min_b) / 2.0
                for i in range(joint_count):
                    d = dmin + margin + step * i
                    px = cx + axis2[0] * d
                    py = cy + axis2[1] * d
                    p3 = patch_s * px + patch_t * py + n_patch * d_plane
                    centers_3d.append(np.array(p3, dtype=float))
                if debug:
                    debug(
                        "multi_centers",
                        {
                            "span": float(span),
                            "center_margin": float(margin),
                            "edge_margin": float(edge_margin_used),
                            "margin_mode": str(margin_mode),
                            "usable": float(usable),
                            "axis2": [float(axis2[0]), float(axis2[1])],
                            "centers": [c.tolist() for c in centers_3d],
                        },
                    )
    except Exception as exc:
        if joint_count > 1:
            raise
        centers_3d = [center3]
        if debug:
            debug("multi_centers_fallback", {"error": str(exc)})

    if debug:
        try:
            debug(
                "centers_depth_probe_scope",
                {
                    "center3_used_for_dimension_probe": np.array(center3, dtype=float).tolist(),
                    "all_boolean_centers": [np.array(c, dtype=float).tolist() for c in centers_3d],
                    "warning": "V18: the dimension is currently measured once at the center of the contact face, not individually for each multi-pin center.",
                },
            )
        except Exception as exc:
            debug("centers_depth_probe_scope_error", {"error": str(exc)})

    # Z width = real short width of the joint face.
    # X = joint size selected in the UI.
    # Y = depth in the arrow direction, enough to cross the female part.
    face_width_z = _contact_patch_short_side_mm(patch_geom)
    if not (face_width_z > 0.0):
        raise ValueError("Cannot compute joint face width.")

    # Long and short axes of the joint face. They orient the boolean box
    # and position the local thickness measurement probes.
    try:
        axis2_major = _major_axis_dir_2d(patch_geom)
        face_long_axis = _normalize(patch_s * float(axis2_major[0]) + patch_t * float(axis2_major[1]))
    except Exception:
        face_long_axis = _normalize(np.array(patch_s, dtype=float))
    if float(np.linalg.norm(face_long_axis)) <= 1e-12:
        raise ValueError("Cannot compute joint face long axis.")

    arrow_forward = _normalize(np.array(patch_n3, dtype=float))
    if float(np.linalg.norm(arrow_forward)) <= 1e-12:
        raise ValueError("Invalid arrow normal to place boolean boxes.")
    face_short_axis = _normalize(np.cross(face_long_axis, arrow_forward))
    if float(np.linalg.norm(face_short_axis)) <= 1e-12:
        face_short_axis = _normalize(np.array(patch_t, dtype=float))

    if debug:
        try:
            axis2_major_dbg = _major_axis_dir_2d(patch_geom)
        except Exception:
            axis2_major_dbg = (None, None)
        debug(
            "joint_local_frame",
            {
                "center3": np.array(center3, dtype=float).tolist(),
                "arrow_forward_y": np.array(arrow_forward, dtype=float).tolist(),
                "face_long_axis_x": np.array(face_long_axis, dtype=float).tolist(),
                "face_short_axis_z": np.array(face_short_axis, dtype=float).tolist(),
                "axis2_major_patch": [None if v is None else float(v) for v in axis2_major_dbg],
                "dot_x_y": float(np.dot(face_long_axis, arrow_forward)),
                "dot_z_y": float(np.dot(face_short_axis, arrow_forward)),
                "dot_x_z": float(np.dot(face_long_axis, face_short_axis)),
                "face_width_z_short_side": float(face_width_z),
                "joint_size_x_ui": float(joint_size),
            },
        )

    # Local measurement of useful joint depth.
    # V21 adds a fast mode: one depth measurement can be reused
    # for all pin locations. In precise mode, the measurement is repeated for
    # each arrow origin.
    raw_thickness_a = float(thickness_a)
    raw_thickness_b = float(thickness_b)
    guarded_thickness_a = _effective_joint_thickness(raw_thickness_a, face_width_z)
    guarded_thickness_b = _effective_joint_thickness(raw_thickness_b, face_width_z)
    single_depth_probe = bool(single_depth_probe)

    def _compute_depth_and_sizes_for_center(probe_center3: np.ndarray, label_suffix: str) -> dict:
        probe_center3 = np.array(probe_center3, dtype=float)
        local_thickness_a = _local_mesh_thickness_by_rays_bidirectional(
            mesh_a,
            face_origin=probe_center3,
            arrow_dir=arrow_forward,
            face_x_axis=face_long_axis,
            face_z_axis=face_short_axis,
            sample_x_mm=max(0.5, min(float(joint_size), 20.0)),
            sample_z_mm=max(0.5, min(float(face_width_z), 20.0)),
            debug=debug,
            label=f"male_piece_A_{label_suffix}",
        )
        local_thickness_b = _local_mesh_thickness_by_rays_bidirectional(
            mesh_b,
            face_origin=probe_center3,
            arrow_dir=arrow_forward,
            face_x_axis=face_long_axis,
            face_z_axis=face_short_axis,
            sample_x_mm=max(0.5, min(float(joint_size), 20.0)),
            sample_z_mm=max(0.5, min(float(face_width_z), 20.0)),
            debug=debug,
            label=f"female_piece_B_{label_suffix}",
        )

        if debug:
            try:
                debug(
                    "measurement_axis_comparison",
                    {
                        "label_suffix": str(label_suffix),
                        "probe_center3": probe_center3.tolist(),
                        "arrow_forward": np.array(arrow_forward, dtype=float).tolist(),
                        "basis_a_n": np.array(basis_a.n, dtype=float).tolist(),
                        "basis_b_n": np.array(basis_b.n, dtype=float).tolist(),
                        "abs_dot_arrow_basis_a_n": float(abs(np.dot(arrow_forward, basis_a.n))),
                        "abs_dot_arrow_basis_b_n": float(abs(np.dot(arrow_forward, basis_b.n))),
                        "basis_a_thickness": float(basis_a.thickness),
                        "basis_b_thickness": float(basis_b.thickness),
                        "guarded_thickness_a": float(guarded_thickness_a),
                        "guarded_thickness_b": float(guarded_thickness_b),
                        "local_thickness_a_by_arrow": None if local_thickness_a is None else float(local_thickness_a),
                        "local_thickness_b_by_arrow": None if local_thickness_b is None else float(local_thickness_b),
                        "four_measurement_strategy_v20": "A+/A- then B+/B-, then choose the smallest valid value between both parts.",
                        "depth_probe_mode_v21": "single_shared" if single_depth_probe else "per_arrow_center",
                    },
                )
            except Exception as exc:
                debug("measurement_axis_comparison_error", {"label_suffix": str(label_suffix), "error": str(exc)})

        thickness_candidates: list[tuple[str, float]] = []
        if local_thickness_a is not None and float(local_thickness_a) > 0.05:
            thickness_candidates.append(("mesh_a_min_of_plus_minus", float(local_thickness_a)))
        if local_thickness_b is not None and float(local_thickness_b) > 0.05:
            thickness_candidates.append(("mesh_b_min_of_plus_minus", float(local_thickness_b)))

        if thickness_candidates:
            joint_thickness_source, joint_thickness = min(thickness_candidates, key=lambda item: item[1])
        else:
            fallback_candidates = [
                ("guarded_thickness_a", float(guarded_thickness_a)),
                ("guarded_thickness_b", float(guarded_thickness_b)),
            ]
            joint_thickness_source, joint_thickness = min(fallback_candidates, key=lambda item: item[1])

        thickness_a_individual = float(local_thickness_a) if local_thickness_a and local_thickness_a > 0.05 else float(guarded_thickness_a)
        thickness_b_individual = float(local_thickness_b) if local_thickness_b and local_thickness_b > 0.05 else float(guarded_thickness_b)
        thickness_used_for_boolean_depth = float(joint_thickness)

        male_size_x = float(joint_size)

        # A tab is an extension of A *towards* B, not a volume centred through
        # the end of A.  The former depth rule used twice the smallest probe
        # thickness and centred that volume on the contact plane.  On a thin
        # upright this consumed several millimetres of the male end and made
        # the original face look cut away.  Keep only a shallow overlap for a
        # reliable union, then project the tab across B's actual thickness.
        male_tab_anchor_depth = float(max(0.05, min(0.25, thickness_a_individual * 0.05)))
        male_tab_projection_depth = float(max(min_boolean_size_mm, thickness_b_individual))
        male_size_y = float(max(min_boolean_size_mm, male_tab_anchor_depth + male_tab_projection_depth))
        # Local +Y follows ``arrow_forward``.  This places the rear face
        # ``male_tab_anchor_depth`` inside A and the front face flush with the
        # far side of B.
        male_center_offset_along_arrow = float(male_size_y / 2.0 - male_tab_anchor_depth)

        # The male tab must overlap the entire thickness of piece A.  Making
        # its width *exactly* equal to the contact face width leaves its two
        # side faces coplanar with the source board.  At an exterior board this
        # produces a valid-looking indexed output with duplicated zero-length
        # seam cells: manifold3d subsequently reports it as ``NotManifold``.
        #
        # Extend both sides by a very small manufacturing-safe overscan.  The
        # female slot already includes the user clearance on both sides, so up
        # to 0.01 mm of extra tab width remains well inside the default 0.30 mm
        # slot allowance.  More importantly, it gives the union a real volume
        # overlap and prevents the coplanar seam from being emitted at all.
        male_width_overscan = float(max(0.0005, min(0.005, face_width_z * 0.001)))
        male_size_z = float(face_width_z + 2.0 * male_width_overscan)

        female_size_x_raw = float(joint_size + 2.0 * clearance)
        female_size_z_raw = float(face_width_z + 2.0 * clearance)
        if female_size_x_raw < min_boolean_size_mm:
            raise ValueError("Clearance is too negative: the female slot length would become smaller than 0.2 mm.")
        if female_size_z_raw < min_boolean_size_mm:
            raise ValueError("Clearance is too negative: the female slot width would become smaller than 0.2 mm.")

        female_size_x = float(female_size_x_raw)
        female_size_y = float(max(min_boolean_size_mm, thickness_used_for_boolean_depth * 2.0))
        female_size_z = float(female_size_z_raw)

        result = {
            "label_suffix": str(label_suffix),
            "probe_center3": probe_center3.tolist(),
            "local_thickness_a": None if local_thickness_a is None else float(local_thickness_a),
            "local_thickness_b": None if local_thickness_b is None else float(local_thickness_b),
            "thickness_a_used_individual": float(thickness_a_individual),
            "thickness_b_used_individual": float(thickness_b_individual),
            "thickness_candidates": [(str(src), float(val)) for src, val in thickness_candidates],
            "joint_thickness_source": str(joint_thickness_source),
            "joint_thickness_used_for_boolean_depth": float(thickness_used_for_boolean_depth),
            "male_size_x": float(male_size_x),
            "male_size_y": float(male_size_y),
            "male_size_z": float(male_size_z),
            "male_tab_anchor_depth": float(male_tab_anchor_depth),
            "male_tab_projection_depth": float(male_tab_projection_depth),
            "male_center_offset_along_arrow": float(male_center_offset_along_arrow),
            "male_width_overscan": float(male_width_overscan),
            "female_size_x": float(female_size_x),
            "female_size_y": float(female_size_y),
            "female_size_z": float(female_size_z),
        }

        if debug:
            debug(
                "pin_dimensions",
                {
                    "label_suffix": str(label_suffix),
                    "probe_center3": probe_center3.tolist(),
                    "depth_probe_mode_v21": "single_shared" if single_depth_probe else "per_arrow_center",
                    "joint_size_x": float(joint_size),
                    "face_width_z": float(face_width_z),
                    "male_width_overscan": float(male_width_overscan),
                    "clearance": float(clearance),
                    "raw_thickness_a": float(raw_thickness_a),
                    "raw_thickness_b": float(raw_thickness_b),
                    "guarded_thickness_a": float(guarded_thickness_a),
                    "guarded_thickness_b": float(guarded_thickness_b),
                    "local_thickness_a": result["local_thickness_a"],
                    "local_thickness_b": result["local_thickness_b"],
                    "thickness_a_used_individual": float(thickness_a_individual),
                    "thickness_b_used_individual": float(thickness_b_individual),
                    "four_measurement_candidates_after_pair_reduce": [
                        {"source": str(src), "value": float(val)} for src, val in thickness_candidates
                    ],
                    "joint_thickness_source": str(joint_thickness_source),
                    "joint_thickness_used_for_boolean_depth": float(thickness_used_for_boolean_depth),
                    "boolean_depth_y_before_x2": float(thickness_used_for_boolean_depth),
                    "male_tab_anchor_depth": float(male_tab_anchor_depth),
                    "male_tab_projection_depth": float(male_tab_projection_depth),
                    "male_center_offset_along_arrow": float(male_center_offset_along_arrow),
                    "male_size_xyz": [float(male_size_x), float(male_size_y), float(male_size_z)],
                    "female_size_xyz": [float(female_size_x), float(female_size_y), float(female_size_z)],
                    "decision_note": "V21: if fast mode is checked, this measurement is reused for all pins; otherwise it is recomputed for each arrow origin.",
                },
            )
        return result

    shared_depth_result = None
    if single_depth_probe:
        shared_depth_result = _compute_depth_and_sizes_for_center(np.array(center3, dtype=float), "shared_center")
        if debug:
            debug(
                "single_depth_probe_cache",
                {
                    "enabled": True,
                    "probe_center3": np.array(center3, dtype=float).tolist(),
                    "reused_for_centers_count": int(len(centers_3d[: max(1, int(joint_count))])),
                    "joint_thickness_source": shared_depth_result["joint_thickness_source"],
                    "joint_thickness_used_for_boolean_depth": float(shared_depth_result["joint_thickness_used_for_boolean_depth"]),
                },
            )
    elif debug:
        debug(
            "single_depth_probe_cache",
            {
                "enabled": False,
                "note": "Depth will be recomputed for each arrow/pin origin.",
                "centers_count": int(len(centers_3d[: max(1, int(joint_count))])),
            },
        )

    # Determine direction for the joint inside each plank plane.
    # We want the male tab to extend *towards the other plank*.
    vec_contact = pb3 - pa3
    used_contact_n_for_axis = False
    # If closest points are coincident (dist ~ 0), vec_contact is degenerate and the axis sign becomes ambiguous.
    # In that case, reuse the non-degenerate contact normal (already stabilized via centroids fallback).
    if float(np.linalg.norm(vec_contact)) <= 1e-9:
        vec_contact = np.array(contact_n, dtype=float)
        used_contact_n_for_axis = True
    # Prefer using the contact face normal for the in-plane direction.
    # Pins must be placed on the contact face, so this is the most stable axis.
    axis_a3 = patch_n3 - basis_a.n * float(np.dot(patch_n3, basis_a.n))
    axis_b3 = (-patch_n3) - basis_b.n * float(np.dot(-patch_n3, basis_b.n))
    axis_a3 = _normalize(axis_a3)
    axis_b3 = _normalize(axis_b3)

    if float(np.linalg.norm(axis_a3)) <= 1e-9 or float(np.linalg.norm(axis_b3)) <= 1e-9:
        # Fallback: previous seam/contact-based logic.
        seam_dir = np.cross(basis_a.n, basis_b.n)
        if float(np.linalg.norm(seam_dir)) > 1e-9:
            seam_dir = _normalize(seam_dir)
            axis_a3 = _normalize(np.cross(seam_dir, basis_a.n))  # in A plane, perpendicular to seam
            axis_b3 = _normalize(np.cross(seam_dir, basis_b.n))  # in B plane, perpendicular to seam
            proj_a = vec_contact - basis_a.n * float(np.dot(vec_contact, basis_a.n))
            proj_b = (-vec_contact) - basis_b.n * float(np.dot(-vec_contact, basis_b.n))
            if float(np.dot(axis_a3, proj_a)) < 0:
                axis_a3 = -axis_a3
            if float(np.dot(axis_b3, proj_b)) < 0:
                axis_b3 = -axis_b3
        else:
            axis_a3 = vec_contact - basis_a.n * float(np.dot(vec_contact, basis_a.n))
            axis_b3 = (-vec_contact) - basis_b.n * float(np.dot(-vec_contact, basis_b.n))
            axis_a3 = _normalize(axis_a3)
            axis_b3 = _normalize(axis_b3)
            if float(np.linalg.norm(axis_a3)) <= 1e-12:
                verts_a = np.array(mesh_a.vertices, dtype=float)
                verts_b = np.array(mesh_b.vertices, dtype=float)
                ca3 = verts_a.mean(axis=0)
                cb3 = verts_b.mean(axis=0)
                v = cb3 - ca3
                axis_a3 = _normalize(v - basis_a.n * float(np.dot(v, basis_a.n)))
                axis_b3 = _normalize((-v) - basis_b.n * float(np.dot(-v, basis_b.n)))

    # Ensure sign matches the contact face normal direction (as shown by the blue arrows).
    proj_patch_a = patch_n3 - basis_a.n * float(np.dot(patch_n3, basis_a.n))
    proj_patch_b = (-patch_n3) - basis_b.n * float(np.dot(-patch_n3, basis_b.n))
    if float(np.linalg.norm(proj_patch_a)) > 1e-9 and float(np.dot(axis_a3, proj_patch_a)) < 0:
        axis_a3 = -axis_a3
    if float(np.linalg.norm(proj_patch_b)) > 1e-9 and float(np.dot(axis_b3, proj_patch_b)) < 0:
        axis_b3 = -axis_b3

    ax2, ay2 = _project_vec_to_basis_2d(basis_a, axis_a3)
    bx2, by2 = _project_vec_to_basis_2d(basis_b, axis_b3)
    if math.hypot(ax2, ay2) <= 1e-9 or math.hypot(bx2, by2) <= 1e-9:
        raise ValueError("Cannot estimate a stable joint direction (axes too short).")
    if debug:
        debug(
            "axes",
            {
                "used_contact_n_for_axis": bool(used_contact_n_for_axis),
                "vec_contact": np.array(vec_contact, dtype=float).tolist(),
                "axis_a3": np.array(axis_a3, dtype=float).tolist(),
                "axis_b3": np.array(axis_b3, dtype=float).tolist(),
                "ax2": float(ax2),
                "ay2": float(ay2),
                "bx2": float(bx2),
                "by2": float(by2),
            },
        )

    # Build N oriented boolean boxes exactly on the arrow origins, then apply true 3D booleans.
    #
    # Current rule:
    # - X = joint size, long axis of the joint face ;
    # - Y = female part thickness * 2, aligned with the normal/arrow ;
    # - Z = short width of the joint face ;
    # - female = X/Z offset by clearance. Positive clearance loosens; negative clearance tightens.
    male_mesh = mesh_a
    female_mesh = mesh_b

    if debug:
        debug(
            "boolean_box_rule",
            {
                "local_axes": "X=joint size, Y=normal/arrow, Z=short face width",
                "depth_strategy": "V21: Y depth = 2 * min(probe A, probe B); shared single measurement if fast toggle is checked.",
                "single_depth_probe": bool(single_depth_probe),
                "shared_depth_result": None if shared_depth_result is None else {
                    "joint_thickness_source": shared_depth_result["joint_thickness_source"],
                    "joint_thickness_used_for_boolean_depth": float(shared_depth_result["joint_thickness_used_for_boolean_depth"]),
                    "male_size_xyz": [float(shared_depth_result["male_size_x"]), float(shared_depth_result["male_size_y"]), float(shared_depth_result["male_size_z"])],
                    "female_size_xyz": [float(shared_depth_result["female_size_x"]), float(shared_depth_result["female_size_y"]), float(shared_depth_result["female_size_z"])],
                },
                "arrow_forward_y": np.array(arrow_forward, dtype=float).tolist(),
                "face_long_axis_x": np.array(face_long_axis, dtype=float).tolist(),
                "centers": [np.array(c, dtype=float).tolist() for c in centers_3d[: max(1, int(joint_count))]],
                "operation_a": "union",
                "operation_b": "difference",
            },
        )

    boolean_t0 = time.perf_counter()
    male_boxes: list[WorkMesh] = []
    female_boxes: list[WorkMesh] = []
    build_boxes_t0 = time.perf_counter()

    for idx, c3 in enumerate(centers_3d[: max(1, int(joint_count))], start=1):
        c3 = np.array(c3, dtype=float)
        depth_result = shared_depth_result if shared_depth_result is not None else _compute_depth_and_sizes_for_center(c3, f"pin_{idx}")
        male_size_x = float(depth_result["male_size_x"])
        male_size_y = float(depth_result["male_size_y"])
        male_size_z = float(depth_result["male_size_z"])
        female_size_x = float(depth_result["female_size_x"])
        female_size_y = float(depth_result["female_size_y"])
        female_size_z = float(depth_result["female_size_z"])
        male_center = c3 + arrow_forward * float(depth_result["male_center_offset_along_arrow"])
        cube_male = _make_oriented_boolean_box(
            name=f"joint_male_box_{idx}",
            center=male_center,
            forward=arrow_forward,
            x_axis_hint=face_long_axis,
            size_x_mm=male_size_x,
            size_y_mm=male_size_y,
            size_z_mm=male_size_z,
            color="#FF7F7F",
        )
        cube_female = _make_oriented_boolean_box(
            name=f"joint_female_box_{idx}",
            center=c3,
            forward=arrow_forward,
            x_axis_hint=face_long_axis,
            size_x_mm=female_size_x,
            size_y_mm=female_size_y,
            size_z_mm=female_size_z,
            color="#FF7F7F",
        )
        male_boxes.append(cube_male)
        female_boxes.append(cube_female)

        if debug:
            ax0, ay0, aw0 = _coords_in_basis(basis_a, c3)
            bx0, by0, bw0 = _coords_in_basis(basis_b, c3)
            debug(
                "placement_boolean_cube",
                {
                    "index": int(idx),
                    "origin3": c3.tolist(),
                    "male_tab_center3": male_center.tolist(),
                    "male_tab_anchor_depth": float(depth_result["male_tab_anchor_depth"]),
                    "male_tab_projection_depth": float(depth_result["male_tab_projection_depth"]),
                    "a_center_local": [float(ax0), float(ay0), float(aw0)],
                    "b_center_local": [float(bx0), float(by0), float(bw0)],
                    "forward_y": np.array(arrow_forward, dtype=float).tolist(),
                    "face_long_axis_x": np.array(face_long_axis, dtype=float).tolist(),
                    "male_size_xyz": [float(male_size_x), float(male_size_y), float(male_size_z)],
                    "female_size_xyz": [float(female_size_x), float(female_size_y), float(female_size_z)],
                    "a_origin_inside_diagnostic": _point_inside_diagnostic(mesh_a, c3),
                    "b_origin_inside_diagnostic": _point_inside_diagnostic(mesh_b, c3),
                    "a_origin_plus_arrow_eps_inside": _point_inside_diagnostic(mesh_a, c3 + arrow_forward * 0.05),
                    "a_origin_minus_arrow_eps_inside": _point_inside_diagnostic(mesh_a, c3 - arrow_forward * 0.05),
                    "b_origin_plus_arrow_eps_inside": _point_inside_diagnostic(mesh_b, c3 + arrow_forward * 0.05),
                    "b_origin_minus_arrow_eps_inside": _point_inside_diagnostic(mesh_b, c3 - arrow_forward * 0.05),
                    "a_extent_plus_arrow_from_origin": _direction_extent_diagnostic(mesh_a, c3, arrow_forward),
                    "a_extent_minus_arrow_from_origin": _direction_extent_diagnostic(mesh_a, c3, -arrow_forward),
                    "b_extent_plus_arrow_from_origin": _direction_extent_diagnostic(mesh_b, c3, arrow_forward),
                    "b_extent_minus_arrow_from_origin": _direction_extent_diagnostic(mesh_b, c3, -arrow_forward),
                },
            )

    build_boxes_ms = (time.perf_counter() - build_boxes_t0) * 1000.0

    # V22 optimization: instead of applying one boolean on the part for each pin,
    # merge all tool boxes into two multi-component meshes, then perform
    # one heavy union and one heavy subtraction.
    build_tools_t0 = time.perf_counter()
    male_tool = _merge_work_meshes(male_boxes, name="joint_male_tool_batch", color="#FF7F7F")
    female_tool = _merge_work_meshes(female_boxes, name="joint_female_tool_batch", color="#FF7F7F")
    build_tools_ms = (time.perf_counter() - build_tools_t0) * 1000.0

    if debug:
        debug(
            "boolean_batch_tools_v22",
            {
                "enabled": True,
                "strategy": "concatenate the N boxes into one multi-component tool, then 1 union + 1 difference on the parts",
                "male_tool_count": int(len(male_boxes)),
                "female_tool_count": int(len(female_boxes)),
                "male_tool_vertices": int(len(male_tool.vertices)),
                "male_tool_triangles": int(len(male_tool.triangles)),
                "female_tool_vertices": int(len(female_tool.vertices)),
                "female_tool_triangles": int(len(female_tool.triangles)),
                "timer_build_boxes_ms": float(build_boxes_ms),
                "timer_build_tools_ms": float(build_tools_ms),
                "previous_heavy_boolean_count_estimate": int(2 * len(male_boxes)),
                "new_heavy_boolean_count": 2,
            },
        )

    union_t0 = time.perf_counter()
    male_mesh = _boolean_3d(mesh_a, male_tool, op="union")
    union_ms = (time.perf_counter() - union_t0) * 1000.0
    # _bool_mesh_3d_manifold names a union "union(A,B)"; keep the original part name.
    male_mesh.name = mesh_a.name
    male_mesh.color = mesh_a.color

    diff_t0 = time.perf_counter()
    female_mesh = _boolean_3d(mesh_b, female_tool, op="difference")
    diff_ms = (time.perf_counter() - diff_t0) * 1000.0
    female_mesh.name = mesh_b.name
    female_mesh.color = mesh_b.color

    # Joint Builder is a solid-to-solid modifier. Never let an open preview be
    # committed: downstream Union/Subtract operations rely on this contract.
    result_stats = _validate_joint_boolean_outputs(male_mesh, female_mesh, debug=debug)

    if debug:
        debug(
            "boolean_batch_timers_v22",
            {
                "timer_union_piece_ms": float(union_ms),
                "timer_difference_piece_ms": float(diff_ms),
                "timer_boolean_total_ms": float((time.perf_counter() - boolean_t0) * 1000.0),
                "result_male_vertices": int(len(male_mesh.vertices)),
                "result_male_triangles": int(len(male_mesh.triangles)),
                "result_female_vertices": int(len(female_mesh.vertices)),
                "result_female_triangles": int(len(female_mesh.triangles)),
                "topology_contract": result_stats,
            },
        )

    if return_female_tool:
        return male_mesh, female_mesh, female_tool
    return male_mesh, female_mesh


def _aabb_overlap(mesh_a: WorkMesh, mesh_b: WorkMesh, *, tolerance_mm: float = 1e-7) -> bool:
    """Cheap conservative filter before applying a scene-wide joint cut."""

    try:
        points_a = np.asarray(mesh_a.vertices, dtype=float)
        points_b = np.asarray(mesh_b.vertices, dtype=float)
        if points_a.size == 0 or points_b.size == 0:
            return False
        lower_a, upper_a = np.min(points_a[:, :3], axis=0), np.max(points_a[:, :3], axis=0)
        lower_b, upper_b = np.min(points_b[:, :3], axis=0), np.max(points_b[:, :3], axis=0)
        return bool(np.all(upper_a + tolerance_mm >= lower_b) and np.all(upper_b + tolerance_mm >= lower_a))
    except Exception:
        # Keep the operation semantically global if a third-party mesh does not
        # expose ordinary point data; the boolean layer will report any issue.
        return True


def apply_tab_slot_to_scene(
    meshes: Sequence[WorkMesh],
    *,
    index_a: int,
    index_b: int,
    touch_tolerance: float,
    clearance: float,
    joint_size: float = 10.0,
    joint_count: int = 1,
    joint_edge_margin: float | None = None,
    single_depth_probe: bool = True,
    subtract_all: bool = False,
    debug: Callable[[str, dict], None] | None = None,
) -> tuple[list[WorkMesh], tuple[int, ...]]:
    """Build a joint and optionally apply its female cut to scene neighbours.

    ``subtract_all=False`` is exactly the historic A/B behaviour.  When true,
    the female cutting volume is also subtracted from every *other* intersecting
    scene mesh.  A is deliberately excluded: it owns the male tab and cutting it
    again would erase the joint that has just been added.
    """

    out = list(meshes)
    if not (0 <= int(index_a) < len(out) and 0 <= int(index_b) < len(out) and int(index_a) != int(index_b)):
        raise ValueError("Joint Builder received invalid scene part indices.")
    a, b = int(index_a), int(index_b)
    result = apply_tab_slot_simple(
        out[a],
        out[b],
        touch_tolerance=touch_tolerance,
        clearance=clearance,
        joint_size=joint_size,
        joint_count=joint_count,
        joint_edge_margin=joint_edge_margin,
        single_depth_probe=single_depth_probe,
        return_female_tool=bool(subtract_all),
        debug=debug,
    )
    if not subtract_all:
        male_mesh, female_mesh = result
        out[a], out[b] = male_mesh, female_mesh
        return out, (a, b)

    male_mesh, female_mesh, female_tool = result
    out[a], out[b] = male_mesh, female_mesh
    changed = [a, b]
    for index, source_mesh in enumerate(meshes):
        if index in (a, b) or not _aabb_overlap(source_mesh, female_tool):
            continue
        cut_mesh = _boolean_3d(source_mesh, female_tool, op="difference")
        cut_mesh.name = source_mesh.name
        cut_mesh.color = source_mesh.color
        # The same strict contract that protects A/B also protects every extra
        # target altered by the global cut before the preview can be applied.
        _validate_joint_boolean_outputs(cut_mesh, cut_mesh, debug=None)
        metadata = dict(getattr(cut_mesh, "metadata", {}) or {})
        metadata["joint_builder_global_subtract"] = True
        cut_mesh.metadata = metadata
        out[index] = cut_mesh
        changed.append(index)
    if debug:
        debug("joint_global_subtract", {"enabled": True, "changed_indices": changed, "excluded_male_index": a})
    return out, tuple(changed)

__all__ = [name for name in globals() if not name.startswith("__")]
