# -*- coding: utf-8 -*-
from __future__ import annotations

from .joint_builder_rays import *  # type: ignore  # noqa: F401,F403

def _local_mesh_thickness_by_rays(
    mesh: WorkMesh,
    *,
    face_origin: np.ndarray,
    inward_dir: np.ndarray,
    face_x_axis: np.ndarray,
    face_z_axis: np.ndarray,
    sample_x_mm: float,
    sample_z_mm: float,
    debug: Callable[[str, dict], None] | None = None,
    label: str = "mesh",
) -> float | None:
    """Measure local thickness at the future joint location.

    Principle: cast several rays from the joint face in the direction that
    enters the part. For a board, the distance to the last local intersection
    corresponds to the crossed thickness. The median makes the measurement robust when rays hit
    an edge, a degenerate triangle, or a small cutout.
    """
    y = _normalize(np.array(inward_dir, dtype=float))
    x = _normalize(np.array(face_x_axis, dtype=float) - y * float(np.dot(face_x_axis, y)))
    z = _normalize(np.array(face_z_axis, dtype=float) - y * float(np.dot(face_z_axis, y)))
    if float(np.linalg.norm(y)) <= 1e-12:
        return None
    if float(np.linalg.norm(x)) <= 1e-12:
        # Fallback axis not parallel to y.
        ref = np.array([0.0, 0.0, 1.0], dtype=float) if abs(float(y[2])) < 0.9 else np.array([1.0, 0.0, 0.0], dtype=float)
        x = _normalize(np.cross(ref, y))
    if float(np.linalg.norm(z)) <= 1e-12:
        z = _normalize(np.cross(x, y))
    if float(np.linalg.norm(z)) <= 1e-12:
        return None

    # Small probes around the center. Intentionally stay away from pin edges.
    ox = max(0.0, float(sample_x_mm))
    oz = max(0.0, float(sample_z_mm))
    offsets = [(0.0, 0.0)]
    for fx, fz in ((0.22, 0.0), (-0.22, 0.0), (0.0, 0.22), (0.0, -0.22), (0.16, 0.16), (-0.16, 0.16), (0.16, -0.16), (-0.16, -0.16)):
        offsets.append((fx * ox, fz * oz))

    values: list[float] = []
    hit_debug: list[dict] = []
    o0 = np.array(face_origin, dtype=float)
    if debug:
        debug(
            "local_thickness_probe_frame",
            {
                "label": label,
                "origin": o0.tolist(),
                "inward_dir_y": y.tolist(),
                "face_x_axis_projected": x.tolist(),
                "face_z_axis_projected": z.tolist(),
                "dot_x_y": float(np.dot(x, y)),
                "dot_z_y": float(np.dot(z, y)),
                "dot_x_z": float(np.dot(x, z)),
                "sample_x_mm": float(sample_x_mm),
                "sample_z_mm": float(sample_z_mm),
                "offsets": [[float(dx), float(dz)] for dx, dz in offsets],
                "note": "Each probe currently takes max(hits > 0.03). If max is huge, the ray probably crossed the part length instead of the thickness.",
            },
        )
    for sample_index, (dx, dz) in enumerate(offsets):
        o = o0 + x * float(dx) + z * float(dz)
        hits = _positive_ray_hits_mm(mesh, o, y)
        details = _positive_ray_hit_details_mm(mesh, o, y, max_hits=40) if debug else None
        # Hits close to zero often correspond to the starting face. The useful measure
        # is the last positive cut: the opposite board face in this direction.
        useful = [t for t in hits if t > 0.03]
        used = float(max(useful)) if useful else None
        if useful:
            val = float(max(useful))
            # V16 diagnostic: keep the raw value from the probe direction, even if it is huge,
            # then the bidirectional selector chooses the smallest positive value.
            if 0.05 <= val <= 10000.0:
                values.append(val)
        sample_payload = {
            "label": label,
            "sample_index": int(sample_index),
            "offset_xz": [float(dx), float(dz)],
            "origin": [float(v) for v in o.tolist()],
            "dir": [float(v) for v in y.tolist()],
            "hits": [float(t) for t in hits],
            "useful_hits": [float(t) for t in useful],
            "used_by_current_algorithm": used,
        }
        if details is not None:
            sample_payload["hit_details"] = details
            merged = details.get("merged_hits", [])
            sample_payload["nearest_hit"] = merged[0] if merged else None
            sample_payload["farthest_hit"] = merged[-1] if merged else None
        hit_debug.append(sample_payload)
        if debug:
            debug("local_thickness_probe_sample", sample_payload)

    if not values:
        if debug:
            debug("local_thickness_ray_fail", {"label": label, "origin": o0.tolist(), "dir": y.tolist(), "samples": hit_debug})
        return None

    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    # Ecarte les outliers puis reprend la mediane.
    kept = arr[np.abs(arr - med) <= max(0.35, med * 0.25)]
    if len(kept) >= 1:
        med = float(np.median(kept))

    if debug:
        debug(
            "local_thickness_raycast",
            {
                "label": label,
                "origin": o0.tolist(),
                "inward_dir": y.tolist(),
                "sample_x_mm": float(sample_x_mm),
                "sample_z_mm": float(sample_z_mm),
                "values": [float(v) for v in values],
                "median": float(med),
                "samples": hit_debug,
            },
        )
    return med

def _local_mesh_depth_from_inside_offset_by_rays(
    mesh: WorkMesh,
    *,
    face_origin: np.ndarray,
    probe_dir: np.ndarray,
    face_x_axis: np.ndarray,
    face_z_axis: np.ndarray,
    sample_x_mm: float,
    sample_z_mm: float,
    epsilon_mm: float = 0.05,
    debug: Callable[[str, dict], None] | None = None,
    label: str = "mesh",
) -> float | None:
    """Measure depth by casting rays from a point slightly offset inside the volume.

    V17: unlike the old measurement that started exactly on the face, each ray starts from:
        origin_sample + probe_dir * epsilon
    then casts in the same probe_dir direction.

    If this point is inside the material, the first positive hit is the exit face. The depth
    from the arrow origin is therefore hit + epsilon. If the offset point is in empty space, the ray
    should normally hit nothing in that direction, which gives a clear diagnostic.
    """
    y = _normalize(np.array(probe_dir, dtype=float))
    x = _normalize(np.array(face_x_axis, dtype=float) - y * float(np.dot(face_x_axis, y)))
    z = _normalize(np.array(face_z_axis, dtype=float) - y * float(np.dot(face_z_axis, y)))
    eps = max(1e-5, float(epsilon_mm))
    if float(np.linalg.norm(y)) <= 1e-12:
        return None
    if float(np.linalg.norm(x)) <= 1e-12:
        ref = np.array([0.0, 0.0, 1.0], dtype=float) if abs(float(y[2])) < 0.9 else np.array([1.0, 0.0, 0.0], dtype=float)
        x = _normalize(np.cross(ref, y))
    if float(np.linalg.norm(z)) <= 1e-12:
        z = _normalize(np.cross(x, y))
    if float(np.linalg.norm(z)) <= 1e-12:
        return None

    ox = max(0.0, float(sample_x_mm))
    oz = max(0.0, float(sample_z_mm))
    offsets = [(0.0, 0.0)]
    for fx, fz in ((0.22, 0.0), (-0.22, 0.0), (0.0, 0.22), (0.0, -0.22), (0.16, 0.16), (-0.16, 0.16), (0.16, -0.16), (-0.16, -0.16)):
        offsets.append((fx * ox, fz * oz))

    values: list[float] = []
    hit_debug: list[dict] = []
    o0 = np.array(face_origin, dtype=float)
    if debug:
        debug(
            "local_depth_inside_offset_probe_frame",
            {
                "label": label,
                "face_origin": o0.tolist(),
                "probe_dir": y.tolist(),
                "epsilon_mm": float(eps),
                "start_rule": "ray_start = face_origin + face_x_offset + face_z_offset + probe_dir * epsilon_mm ; ray_dir = probe_dir",
                "hit_choice": "nearest positive hit, then depth = hit + epsilon_mm",
                "face_x_axis_projected": x.tolist(),
                "face_z_axis_projected": z.tolist(),
                "dot_x_y": float(np.dot(x, y)),
                "dot_z_y": float(np.dot(z, y)),
                "dot_x_z": float(np.dot(x, z)),
                "sample_x_mm": float(sample_x_mm),
                "sample_z_mm": float(sample_z_mm),
                "offsets": [[float(dx), float(dz)] for dx, dz in offsets],
                "mesh_direction_extent_from_face_origin": _direction_extent_diagnostic(mesh, o0, y),
                "face_origin_inside_diagnostic": _point_inside_diagnostic(mesh, o0),
                "face_origin_plus_epsilon_inside_diagnostic": _point_inside_diagnostic(mesh, o0 + y * eps),
                "face_origin_minus_epsilon_inside_diagnostic": _point_inside_diagnostic(mesh, o0 - y * eps),
            },
        )

    for sample_index, (dx, dz) in enumerate(offsets):
        surface_point = o0 + x * float(dx) + z * float(dz)
        ray_start = surface_point + y * eps
        hits = _positive_ray_hits_mm(mesh, ray_start, y)
        details = _positive_ray_hit_details_mm(mesh, ray_start, y, max_hits=40) if debug else None
        useful = [t for t in hits if t > 0.001]
        used_hit = float(min(useful)) if useful else None
        depth_from_face = None
        if used_hit is not None:
            depth_from_face = float(used_hit + eps)
            if 0.001 <= depth_from_face <= 10000.0:
                values.append(depth_from_face)
        sample_payload = {
            "label": label,
            "sample_index": int(sample_index),
            "offset_xz": [float(dx), float(dz)],
            "surface_point": [float(v) for v in surface_point.tolist()],
            "ray_start": [float(v) for v in ray_start.tolist()],
            "ray_dir": [float(v) for v in y.tolist()],
            "epsilon_mm": float(eps),
            "hits": [float(t) for t in hits],
            "useful_hits": [float(t) for t in useful],
            "used_nearest_hit": used_hit,
            "depth_from_face_used": depth_from_face,
            "surface_point_inside_diagnostic": _point_inside_diagnostic(mesh, surface_point) if debug else None,
            "ray_start_inside_diagnostic": _point_inside_diagnostic(mesh, ray_start) if debug else None,
            "opposite_epsilon_point_inside_diagnostic": _point_inside_diagnostic(mesh, surface_point - y * eps) if debug else None,
            "direction_extent_from_surface_point": _direction_extent_diagnostic(mesh, surface_point, y) if debug else None,
            "direction_extent_from_ray_start": _direction_extent_diagnostic(mesh, ray_start, y) if debug else None,
        }
        if details is not None:
            sample_payload["hit_details"] = details
            merged = details.get("merged_hits", [])
            sample_payload["nearest_hit"] = merged[0] if merged else None
            sample_payload["farthest_hit"] = merged[-1] if merged else None
        hit_debug.append(sample_payload)
        if debug:
            debug("local_depth_inside_offset_probe_sample", sample_payload)

    if not values:
        if debug:
            debug(
                "local_depth_inside_offset_fail",
                {
                    "label": label,
                    "face_origin": o0.tolist(),
                    "probe_dir": y.tolist(),
                    "epsilon_mm": float(eps),
                    "samples": hit_debug,
                    "reason": "no positive exit hit from epsilon-shifted start points",
                },
            )
        return None

    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    kept = arr[np.abs(arr - med) <= max(0.35, med * 0.25)]
    if len(kept) >= 1:
        med = float(np.median(kept))

    if debug:
        debug(
            "local_depth_inside_offset_result",
            {
                "label": label,
                "face_origin": o0.tolist(),
                "probe_dir": y.tolist(),
                "epsilon_mm": float(eps),
                "values_depth_from_face": [float(v) for v in values],
                "median": float(med),
                "samples": hit_debug,
            },
        )
    return med

def _local_mesh_depth_from_external_through_probe_by_rays(
    mesh: WorkMesh,
    *,
    face_origin: np.ndarray,
    outside_dir: np.ndarray,
    face_x_axis: np.ndarray,
    face_z_axis: np.ndarray,
    sample_x_mm: float,
    sample_z_mm: float,
    offset_mm: float = 10.0,
    debug: Callable[[str, dict], None] | None = None,
    label: str = "mesh",
) -> float | None:
    """V19 : external through-probe.

    Tested approach:
      start = surface_point + outside_dir * offset_mm
      ray_dir = -outside_dir

    Do not simply use the start->first hit distance because that mostly measures the
    10 mm offset. To obtain material depth, search for two intersections
    successive around the expected face position (t ~= offset_mm), then measure
    the gap between entry and exit: thickness = t_exit - t_entry.
    """
    outside = _normalize(np.array(outside_dir, dtype=float))
    ray_dir = -outside
    x = _normalize(np.array(face_x_axis, dtype=float) - ray_dir * float(np.dot(face_x_axis, ray_dir)))
    z = _normalize(np.array(face_z_axis, dtype=float) - ray_dir * float(np.dot(face_z_axis, ray_dir)))
    off = max(0.001, float(offset_mm))
    if float(np.linalg.norm(outside)) <= 1e-12:
        return None
    if float(np.linalg.norm(x)) <= 1e-12:
        ref = np.array([0.0, 0.0, 1.0], dtype=float) if abs(float(ray_dir[2])) < 0.9 else np.array([1.0, 0.0, 0.0], dtype=float)
        x = _normalize(np.cross(ref, ray_dir))
    if float(np.linalg.norm(z)) <= 1e-12:
        z = _normalize(np.cross(x, ray_dir))
    if float(np.linalg.norm(z)) <= 1e-12:
        return None

    ox = max(0.0, float(sample_x_mm))
    oz = max(0.0, float(sample_z_mm))
    offsets = [(0.0, 0.0)]
    for fx, fz in ((0.22, 0.0), (-0.22, 0.0), (0.0, 0.22), (0.0, -0.22), (0.16, 0.16), (-0.16, 0.16), (0.16, -0.16), (-0.16, -0.16)):
        offsets.append((fx * ox, fz * oz))

    values: list[float] = []
    sample_logs: list[dict] = []
    o0 = np.array(face_origin, dtype=float)

    if debug:
        debug(
            "local_depth_external_through_probe_frame",
            {
                "label": label,
                "face_origin": o0.tolist(),
                "outside_dir": outside.tolist(),
                "ray_dir": ray_dir.tolist(),
                "offset_mm": float(off),
                "start_center": (o0 + outside * off).tolist(),
                "expected_surface_t_from_start": float(off),
                "rule": "start = surface_point + outside_dir*offset ; dir = -outside_dir ; depth = t_exit - t_entry, not first_hit",
                "face_x_axis_projected": x.tolist(),
                "face_z_axis_projected": z.tolist(),
                "dot_ray_face_x": float(np.dot(ray_dir, x)),
                "dot_ray_face_z": float(np.dot(ray_dir, z)),
                "mesh_extent_from_face_origin_ray_dir": _direction_extent_diagnostic(mesh, o0, ray_dir),
                "mesh_extent_from_face_origin_outside_dir": _direction_extent_diagnostic(mesh, o0, outside),
                "face_origin_inside_diagnostic": _point_inside_diagnostic(mesh, o0),
                "start_center_inside_diagnostic": _point_inside_diagnostic(mesh, o0 + outside * off),
            },
        )

    for sample_index, (dx, dz) in enumerate(offsets):
        surface_point = o0 + x * float(dx) + z * float(dz)
        ray_start = surface_point + outside * off
        hits = _positive_ray_hits_mm(mesh, ray_start, ray_dir)
        details = _positive_ray_hit_details_mm(mesh, ray_start, ray_dir, max_hits=80) if debug else None
        useful = [float(t) for t in hits if float(t) > 0.001]

        # Search for material segments between two successive hits. For a closed mesh,
        # an external line generally gives [entry, exit]. The correct entry should
        # be close to offset_mm if surface_point is on the targeted wall.
        segments: list[dict] = []
        for i in range(0, max(0, len(useful) - 1)):
            t_entry = float(useful[i])
            t_exit = float(useful[i + 1])
            depth = float(t_exit - t_entry)
            if depth <= 0.001:
                continue
            midpoint_t = 0.5 * (t_entry + t_exit)
            midpoint = ray_start + ray_dir * midpoint_t
            segments.append({
                "entry_index": int(i),
                "exit_index": int(i + 1),
                "t_entry": t_entry,
                "t_exit": t_exit,
                "depth": depth,
                "entry_distance_to_expected_surface_t": float(abs(t_entry - off)),
                "exit_distance_to_expected_surface_t": float(abs(t_exit - off)),
                "midpoint": [float(v) for v in midpoint.tolist()],
            })

        selected_segment = None
        if segments:
            # Prioritize the segment whose entry is closest to t=offset_mm.
            # This is the segment starting on the face around the arrow origin.
            selected_segment = min(
                segments,
                key=lambda seg: (float(seg["entry_distance_to_expected_surface_t"]), float(seg["depth"])),
            )
            depth_value = float(selected_segment["depth"])
            if 0.001 <= depth_value <= 10000.0:
                values.append(depth_value)

        sample_payload = {
            "label": label,
            "sample_index": int(sample_index),
            "offset_xz": [float(dx), float(dz)],
            "surface_point": [float(v) for v in surface_point.tolist()],
            "ray_start": [float(v) for v in ray_start.tolist()],
            "ray_dir": [float(v) for v in ray_dir.tolist()],
            "outside_dir": [float(v) for v in outside.tolist()],
            "offset_mm": float(off),
            "expected_surface_t_from_start": float(off),
            "hits": [float(t) for t in useful],
            "hit_count": int(len(useful)),
            "segments_between_successive_hits": segments,
            "selected_segment": selected_segment,
            "selected_depth": None if selected_segment is None else float(selected_segment["depth"]),
            "first_hit_start_to_hit_distance": None if not useful else float(useful[0]),
            "note": "The start->first hit distance is not the thickness; thickness is t_exit-t_entry.",
            "surface_point_inside_diagnostic": _point_inside_diagnostic(mesh, surface_point) if debug else None,
            "ray_start_inside_diagnostic": _point_inside_diagnostic(mesh, ray_start) if debug else None,
            "direction_extent_from_surface_point_ray_dir": _direction_extent_diagnostic(mesh, surface_point, ray_dir) if debug else None,
            "direction_extent_from_ray_start_ray_dir": _direction_extent_diagnostic(mesh, ray_start, ray_dir) if debug else None,
        }
        if details is not None:
            sample_payload["hit_details"] = details
            merged = details.get("merged_hits", [])
            sample_payload["nearest_hit"] = merged[0] if merged else None
            sample_payload["farthest_hit"] = merged[-1] if merged else None
        sample_logs.append(sample_payload)
        if debug:
            debug("local_depth_external_through_probe_sample", sample_payload)

    if not values:
        if debug:
            debug(
                "local_depth_external_through_probe_fail",
                {
                    "label": label,
                    "face_origin": o0.tolist(),
                    "outside_dir": outside.tolist(),
                    "ray_dir": ray_dir.tolist(),
                    "offset_mm": float(off),
                    "samples": sample_logs,
                    "reason": "no pair of positive hits found; impossible to compute t_exit-t_entry",
                },
            )
        return None

    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    kept = arr[np.abs(arr - med) <= max(0.35, med * 0.25)]
    if len(kept) >= 1:
        med = float(np.median(kept))

    if debug:
        debug(
            "local_depth_external_through_probe_result",
            {
                "label": label,
                "face_origin": o0.tolist(),
                "outside_dir": outside.tolist(),
                "ray_dir": ray_dir.tolist(),
                "offset_mm": float(off),
                "values_depth_t_exit_minus_t_entry": [float(v) for v in values],
                "median": float(med),
                "samples": sample_logs,
            },
        )
    return med

def _local_mesh_thickness_by_rays_bidirectional(
    mesh: WorkMesh,
    *,
    face_origin: np.ndarray,
    arrow_dir: np.ndarray,
    face_x_axis: np.ndarray,
    face_z_axis: np.ndarray,
    sample_x_mm: float,
    sample_z_mm: float,
    debug: Callable[[str, dict], None] | None = None,
    label: str = "mesh",
) -> float | None:
    """V19 : bidirectional measurement using external through-rays.

    Requested approach:
      1) start = origin + arrow*10, dir = -arrow
      2) start = origin - arrow*10, dir = +arrow

    Important calculation correction: thickness is not start->first hit.
    Material thickness along the ray is t_exit - t_entry, between two successive hits.
    Then keep the smallest positive depth between both sides.
    """
    arrow = _normalize(np.array(arrow_dir, dtype=float))
    if float(np.linalg.norm(arrow)) <= 1e-12:
        if debug:
            debug(
                "local_thickness_bidirectional_fail",
                {
                    "label": label,
                    "reason": "arrow_dir_zero",
                    "face_origin": np.array(face_origin, dtype=float).tolist(),
                    "arrow_dir": np.array(arrow_dir, dtype=float).tolist(),
                },
            )
        return None

    off = 10.0
    plus_label = f"{label}:external_plus_start_arrow_plus10_dir_minus_arrow"
    minus_label = f"{label}:external_minus_start_arrow_minus10_dir_plus_arrow"

    if debug:
        try:
            debug(
                "local_thickness_bidirectional_frame",
                {
                    "label": label,
                    "face_origin": np.array(face_origin, dtype=float).tolist(),
                    "arrow_dir": arrow.tolist(),
                    "offset_mm": float(off),
                    "plus_probe": {
                        "start": (np.array(face_origin, dtype=float) + arrow * off).tolist(),
                        "dir": (-arrow).tolist(),
                    },
                    "minus_probe": {
                        "start": (np.array(face_origin, dtype=float) - arrow * off).tolist(),
                        "dir": arrow.tolist(),
                    },
                    "face_x_axis_input": np.array(face_x_axis, dtype=float).tolist(),
                    "face_z_axis_input": np.array(face_z_axis, dtype=float).tolist(),
                    "dot_arrow_face_x": float(np.dot(arrow, _normalize(np.array(face_x_axis, dtype=float)))),
                    "dot_arrow_face_z": float(np.dot(arrow, _normalize(np.array(face_z_axis, dtype=float)))),
                    "mesh_extent_plus_arrow": _direction_extent_diagnostic(mesh, np.array(face_origin, dtype=float), arrow),
                    "mesh_extent_minus_arrow": _direction_extent_diagnostic(mesh, np.array(face_origin, dtype=float), -arrow),
                    "origin_inside_diagnostic": _point_inside_diagnostic(mesh, np.array(face_origin, dtype=float)),
                    "plus_start_inside_diagnostic": _point_inside_diagnostic(mesh, np.array(face_origin, dtype=float) + arrow * off),
                    "minus_start_inside_diagnostic": _point_inside_diagnostic(mesh, np.array(face_origin, dtype=float) - arrow * off),
                    "note": "V19: teste start=originarrow*10 et direction vers origin. Valeur = t_exit-t_entry, pas start->premier hit.",
                },
            )
        except Exception as exc:
            debug("local_thickness_bidirectional_frame_error", {"label": label, "error": str(exc)})

    plus_value = _local_mesh_depth_from_external_through_probe_by_rays(
        mesh,
        face_origin=np.array(face_origin, dtype=float),
        outside_dir=arrow,
        face_x_axis=np.array(face_x_axis, dtype=float),
        face_z_axis=np.array(face_z_axis, dtype=float),
        sample_x_mm=float(sample_x_mm),
        sample_z_mm=float(sample_z_mm),
        offset_mm=off,
        debug=debug,
        label=plus_label,
    )
    minus_value = _local_mesh_depth_from_external_through_probe_by_rays(
        mesh,
        face_origin=np.array(face_origin, dtype=float),
        outside_dir=-arrow,
        face_x_axis=np.array(face_x_axis, dtype=float),
        face_z_axis=np.array(face_z_axis, dtype=float),
        sample_x_mm=float(sample_x_mm),
        sample_z_mm=float(sample_z_mm),
        offset_mm=off,
        debug=debug,
        label=minus_label,
    )

    candidates: list[tuple[str, float]] = []
    if plus_value is not None and float(plus_value) > 0.001:
        candidates.append(("plus_start_origin_plus_arrow10_dir_minus_arrow", float(plus_value)))
    if minus_value is not None and float(minus_value) > 0.001:
        candidates.append(("minus_start_origin_minus_arrow10_dir_plus_arrow", float(minus_value)))

    if not candidates:
        if debug:
            debug(
                "local_thickness_bidirectional_choice",
                {
                    "label": label,
                    "face_origin": np.array(face_origin, dtype=float).tolist(),
                    "arrow_dir": arrow.tolist(),
                    "offset_mm": float(off),
                    "plus_arrow_value": None if plus_value is None else float(plus_value),
                    "minus_arrow_value": None if minus_value is None else float(minus_value),
                    "chosen_side": None,
                    "chosen_value": None,
                    "reason": "no_positive_candidate_v20_external_through_probe",
                },
            )
        return None

    chosen_side, chosen_value = min(candidates, key=lambda item: item[1])
    if debug:
        debug(
            "local_thickness_bidirectional_choice",
            {
                "label": label,
                "face_origin": np.array(face_origin, dtype=float).tolist(),
                "arrow_dir": arrow.tolist(),
                "offset_mm": float(off),
                "plus_arrow_value": None if plus_value is None else float(plus_value),
                "minus_arrow_value": None if minus_value is None else float(minus_value),
                "candidates": [{"side": side, "value": float(value)} for side, value in candidates],
                "chosen_side": chosen_side,
                "chosen_value": float(chosen_value),
                "reason": "min_positive_bidirectional_external_through_probe_v20_piece_level",
                "important_note": "If chosen_value remains large, the ray really crosses a large mesh dimension along the arrow axis.",
            },
        )
    return float(chosen_value)

__all__ = [name for name in globals() if not name.startswith("__")]
