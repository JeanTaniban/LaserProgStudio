"""Versioned Cloth metadata serialization for editable generated surfaces."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from laserprog_studio.domain.work_model import WorkMesh

from .models import (
    ClothCurve,
    ClothCurveKind,
    ClothCurveRole,
    ClothDocument,
    ClothFold,
    ClothFoldKind,
    ClothLayer,
    ClothPatch,
    ClothPatchFunction,
    ClothPoint,
    ClothSeam,
)

CLOTH_SCHEMA_VERSION = 2
CLOTH_SOURCE_KEY = "laserprog.cloth.source"


def cloth_document_to_dict(document: ClothDocument) -> dict[str, Any]:
    return {
        "schema_version": CLOTH_SCHEMA_VERSION,
        "revision": int(document.revision),
        "next_id": int(document._next_id),
        "metadata": deepcopy(document.metadata),
        "layers": [
            {
                "id": item.id,
                "name": item.name,
                "material_name": item.material_name,
                "thickness_mm": float(item.thickness_mm),
                "visible": bool(item.visible),
                "locked": bool(item.locked),
                "metadata": deepcopy(item.metadata),
            }
            for item in document.layers.values()
        ],
        "points": [
            {"id": item.id, "position": list(item.position), "metadata": deepcopy(item.metadata)}
            for item in document.points.values()
        ],
        "curves": [
            {
                "id": item.id,
                "kind": item.kind.value,
                "point_ids": list(item.point_ids),
                "role": item.role.value,
                "closed": bool(item.closed),
                "metadata": deepcopy(item.metadata),
            }
            for item in document.curves.values()
        ],
        "patches": [
            {
                "id": item.id,
                "outer_curve_ids": list(item.outer_curve_ids),
                "hole_curve_loops": [list(loop) for loop in item.hole_curve_loops],
                "name": item.name,
                "grain_direction": None if item.grain_direction is None else list(item.grain_direction),
                "function": item.function.value,
                "layer_id": item.layer_id,
                "material_name": item.material_name,
                "metadata": deepcopy(item.metadata),
            }
            for item in document.patches.values()
        ],
        "folds": [
            {
                "id": item.id,
                "curve_id": item.curve_id,
                "patch_a_id": item.patch_a_id,
                "patch_b_id": item.patch_b_id,
                "kind": item.kind.value,
                "angle_degrees": float(item.angle_degrees),
                "radius_mm": float(item.radius_mm),
                "metadata": deepcopy(item.metadata),
            }
            for item in document.folds.values()
        ],
        "seams": [
            {
                "id": item.id,
                "first_curve_ids": list(item.first_curve_ids),
                "second_curve_ids": list(item.second_curve_ids),
                "allowance_mm": float(item.allowance_mm),
                "ease_ratio": float(item.ease_ratio),
                "metadata": deepcopy(item.metadata),
            }
            for item in document.seams.values()
        ],
    }


def cloth_document_from_dict(payload: dict[str, Any]) -> ClothDocument:
    schema_version = int(payload.get("schema_version", 0))
    if schema_version not in {1, CLOTH_SCHEMA_VERSION}:
        raise ValueError(f"Unsupported Cloth schema version: {payload.get('schema_version')!r}")
    document = ClothDocument(metadata=deepcopy(payload.get("metadata") or {}))
    document.layers = {
        str(item["id"]): ClothLayer(
            str(item["id"]),
            name=str(item.get("name") or item["id"]),
            material_name=str(item.get("material_name") or "Textile"),
            thickness_mm=max(0.001, float(item.get("thickness_mm", 0.2))),
            visible=bool(item.get("visible", True)),
            locked=bool(item.get("locked", False)),
            metadata=deepcopy(item.get("metadata") or {}),
        )
        for item in payload.get("layers") or []
    }
    if not document.layers:
        document.layers["layer1"] = ClothLayer("layer1")
    document.points = {
        str(item["id"]): ClothPoint(
            str(item["id"]),
            tuple(float(value) for value in item["position"]),
            deepcopy(item.get("metadata") or {}),
        )
        for item in payload.get("points") or []
    }
    document.curves = {
        str(item["id"]): ClothCurve(
            str(item["id"]),
            ClothCurveKind(str(item["kind"])),
            tuple(str(value) for value in item.get("point_ids") or ()),
            role=ClothCurveRole(str(item.get("role") or ClothCurveRole.BOUNDARY.value)),
            closed=bool(item.get("closed", False)),
            metadata=deepcopy(item.get("metadata") or {}),
        )
        for item in payload.get("curves") or []
    }
    document.patches = {
        str(item["id"]): ClothPatch(
            str(item["id"]),
            tuple(str(value) for value in item.get("outer_curve_ids") or ()),
            tuple(tuple(str(value) for value in loop) for loop in item.get("hole_curve_loops") or ()),
            name=str(item.get("name") or "Panel"),
            grain_direction=None
            if item.get("grain_direction") is None
            else tuple(float(value) for value in item.get("grain_direction")),
            function=ClothPatchFunction(str(item.get("function") or ClothPatchFunction.TEXTILE.value)),
            layer_id=str(item.get("layer_id") or "layer1"),
            material_name=str(item.get("material_name") or document.layers.get(str(item.get("layer_id") or "layer1"), ClothLayer("layer1")).material_name),
            metadata=deepcopy(item.get("metadata") or {}),
        )
        for item in payload.get("patches") or []
    }
    for patch in document.patches.values():
        if patch.layer_id not in document.layers:
            document.layers[patch.layer_id] = ClothLayer(patch.layer_id, name=patch.layer_id, material_name=patch.material_name)

    document.folds = {
        str(item["id"]): ClothFold(
            str(item["id"]),
            str(item["curve_id"]),
            str(item["patch_a_id"]),
            str(item["patch_b_id"]),
            kind=ClothFoldKind(str(item.get("kind") or ClothFoldKind.NEUTRAL.value)),
            angle_degrees=float(item.get("angle_degrees", 0.0)),
            radius_mm=float(item.get("radius_mm", 0.0)),
            metadata=deepcopy(item.get("metadata") or {}),
        )
        for item in payload.get("folds") or []
    }
    document.seams = {
        str(item["id"]): ClothSeam(
            str(item["id"]),
            tuple(str(value) for value in item.get("first_curve_ids") or ()),
            tuple(str(value) for value in item.get("second_curve_ids") or ()),
            allowance_mm=float(item.get("allowance_mm", 0.0)),
            ease_ratio=float(item.get("ease_ratio", 1.0)),
            metadata=deepcopy(item.get("metadata") or {}),
        )
        for item in payload.get("seams") or []
    }
    document.revision = int(payload.get("revision", 0))
    document._next_id = max(int(payload.get("next_id", 1)), 1)
    return document


def attach_cloth_source_in_place(
    mesh: WorkMesh,
    *,
    document: ClothDocument,
    output_kind: str,
) -> WorkMesh:
    """Attach editable Cloth metadata to a freshly owned mesh without copying geometry."""

    mesh.metadata = dict(mesh.metadata or {})
    mesh.metadata[CLOTH_SOURCE_KEY] = {
        "schema_version": CLOTH_SCHEMA_VERSION,
        "output_kind": str(output_kind),
        "document": cloth_document_to_dict(document),
    }
    return mesh


def attach_cloth_source(mesh: WorkMesh, *, document: ClothDocument, output_kind: str) -> WorkMesh:
    """Return a detached mesh carrying an editable Cloth source document.

    This public API preserves the historical copy-on-write behaviour.
    Internal builders that already own a fresh mesh use
    :func:`attach_cloth_source_in_place` to avoid copying large vertex buffers.
    """

    return attach_cloth_source_in_place(
        deepcopy(mesh),
        document=document,
        output_kind=output_kind,
    )


def cloth_output_kind(mesh: WorkMesh | None) -> str | None:
    """Return the lightweight output kind without deserializing the document."""

    metadata = getattr(mesh, "metadata", None)
    source = (metadata or {}).get(CLOTH_SOURCE_KEY) if isinstance(metadata, dict) else None
    document_payload = source.get("document") if isinstance(source, dict) else None
    if not isinstance(document_payload, dict):
        return None
    try:
        if int(document_payload.get("schema_version", 0)) not in {1, CLOTH_SCHEMA_VERSION}:
            return None
    except (TypeError, ValueError):
        return None
    return str(source.get("output_kind") or "folded")


def restore_cloth_source(mesh: WorkMesh | None) -> tuple[ClothDocument, str] | None:
    metadata = getattr(mesh, "metadata", None)
    source = (metadata or {}).get(CLOTH_SOURCE_KEY) if isinstance(metadata, dict) else None
    if not isinstance(source, dict) or not isinstance(source.get("document"), dict):
        return None
    try:
        document = cloth_document_from_dict(source["document"])
    except (KeyError, TypeError, ValueError):
        return None
    return document, str(source.get("output_kind") or "folded")


__all__ = [
    "CLOTH_SCHEMA_VERSION",
    "CLOTH_SOURCE_KEY",
    "attach_cloth_source",
    "attach_cloth_source_in_place",
    "cloth_document_from_dict",
    "cloth_document_to_dict",
    "cloth_output_kind",
    "restore_cloth_source",
]
