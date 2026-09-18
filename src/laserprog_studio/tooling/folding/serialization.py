# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec

from .geometry import mesh_from_serialized, serialize_mesh
from .models import FoldingCurve, FoldingDeformationMode, FoldingFixedSide, FoldingMode, clamp_folding_angle_deg


FOLDING_SOURCE_KEY = "folding_source"
FOLDING_SOURCE_VERSION = 5


def attach_folding_source(
    mesh: Any,
    *,
    source_mesh: Any,
    plane: LockedPlaneSpec,
    curve: FoldingCurve,
    group_id: str | None = None,
    group_member_ids: tuple[str, ...] = (),
    group_member_index: int = 0,
) -> Any:
    metadata = copy.deepcopy(dict(getattr(mesh, "metadata", {}) or {}))
    metadata[FOLDING_SOURCE_KEY] = {
        "version": FOLDING_SOURCE_VERSION,
        "source_tool": "folding",
        "source_mesh": serialize_mesh(source_mesh),
        "plane": {
            "view": str(getattr(plane.view, "value", plane.view)),
            "normal": tuple(float(v) for v in plane.normal),
            "u_axis": tuple(float(v) for v in plane.u_axis),
            "v_axis": tuple(float(v) for v in plane.v_axis),
            "depth": float(plane.depth),
        },
        "curve": {
            "start": tuple(float(v) for v in curve.start) if curve.start is not None else None,
            "end": tuple(float(v) for v in curve.end) if curve.end is not None else None,
            "mode": str(curve.mode),
            "fold_angle_deg": float(curve.fold_angle_deg),
            "fixed_side": curve.normalized_fixed_side(),
            "shape_angles_deg": tuple(float(value) for value in curve.normalized_shape_angles()),
            "deformation_mode": curve.normalized_deformation_mode(),
            # Kept for old free-curve results and round-trip compatibility.
            "control_1_offset_mm": float(curve.control_1_offset_mm),
            "control_2_offset_mm": float(curve.control_2_offset_mm),
        },
        "group": {
            "id": str(group_id or ""),
            "member_ids": tuple(str(value) for value in tuple(group_member_ids or ())),
            "member_index": int(group_member_index),
        },
    }
    metadata["source_tool"] = "folding"
    metadata["editable_tool_id"] = "folding"
    mesh.metadata = metadata
    return mesh


def has_folding_source(mesh: Any) -> bool:
    metadata = getattr(mesh, "metadata", None)
    return isinstance(metadata, dict) and isinstance(metadata.get(FOLDING_SOURCE_KEY), dict)


def folding_source(mesh: Any) -> dict[str, Any] | None:
    metadata = getattr(mesh, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    source = metadata.get(FOLDING_SOURCE_KEY)
    return copy.deepcopy(source) if isinstance(source, dict) else None


def folding_group_info(mesh: Any) -> tuple[str, tuple[str, ...], int] | None:
    """Return persisted group identity for a Folding result.

    Version 1-3 projects have no group block and naturally reopen as a
    one-object Folding session.
    """

    source = folding_source(mesh)
    if source is None:
        return None
    try:
        group = dict(source.get("group") or {})
        group_id = str(group.get("id") or "").strip()
        if not group_id:
            return None
        member_ids = tuple(str(value) for value in tuple(group.get("member_ids") or ()) if str(value))
        return group_id, member_ids, int(group.get("member_index", 0) or 0)
    except Exception:
        return None


def restore_folding_source(mesh: Any) -> tuple[Any, LockedPlaneSpec, FoldingCurve] | None:
    source = folding_source(mesh)
    if source is None:
        return None
    try:
        version = int(source.get("version", 1) or 1)
        source_mesh = mesh_from_serialized(source.get("source_mesh"))
        plane_data = dict(source.get("plane") or {})
        view_text = str(plane_data.get("view") or FixedPlanarView.TOP.value)
        try:
            view = FixedPlanarView(view_text)
        except Exception:
            view = FixedPlanarView.TOP
        plane = LockedPlaneSpec(
            view,
            tuple(float(v) for v in plane_data["normal"]),
            tuple(float(v) for v in plane_data["u_axis"]),
            tuple(float(v) for v in plane_data["v_axis"]),
            float(plane_data["depth"]),
        )
        curve_data = dict(source.get("curve") or {})
        mode = str(curve_data.get("mode") or (FoldingMode.FREE_CURVE.value if version <= 1 else FoldingMode.LIVING_HINGE.value))
        if mode not in {FoldingMode.FREE_CURVE.value, FoldingMode.LIVING_HINGE.value}:
            mode = FoldingMode.FREE_CURVE.value if version <= 1 else FoldingMode.LIVING_HINGE.value
        fixed_side = str(curve_data.get("fixed_side") or FoldingFixedSide.START.value)
        if fixed_side not in {FoldingFixedSide.START.value, FoldingFixedSide.END.value}:
            fixed_side = FoldingFixedSide.START.value
        deformation_mode = str(curve_data.get("deformation_mode") or FoldingDeformationMode.PRESERVE_STRUCTURE.value)
        if deformation_mode not in {FoldingDeformationMode.PRESERVE_STRUCTURE.value, FoldingDeformationMode.UNIFORM.value}:
            deformation_mode = FoldingDeformationMode.PRESERVE_STRUCTURE.value
        curve = FoldingCurve(
            start=tuple(float(v) for v in curve_data["start"]),
            end=tuple(float(v) for v in curve_data["end"]),
            control_1_offset_mm=float(curve_data.get("control_1_offset_mm", 0.0)),
            control_2_offset_mm=float(curve_data.get("control_2_offset_mm", 0.0)),
            mode=mode,
            fold_angle_deg=clamp_folding_angle_deg(float(curve_data.get("fold_angle_deg", 0.0))),
            fixed_side=fixed_side,
            shape_angles_deg=tuple(float(value) for value in tuple(curve_data.get("shape_angles_deg") or (0.0, 0.0, 0.0))),
            deformation_mode=deformation_mode,
        )
        return source_mesh, plane, curve
    except Exception:
        return None


__all__ = [
    "FOLDING_SOURCE_KEY",
    "FOLDING_SOURCE_VERSION",
    "attach_folding_source",
    "folding_source",
    "folding_group_info",
    "has_folding_source",
    "restore_folding_source",
]
