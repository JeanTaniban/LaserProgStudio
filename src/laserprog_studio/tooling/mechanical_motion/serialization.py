# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict
import copy
from typing import Any

from .models import (
    AttachmentSpec,
    GearChainSpec,
    GearSpec,
    GearStage,
    MechanicalAssembly,
    RackSpec,
    RotaryDriverSpec,
    ToothProfile,
)
from .plane import MechanicalWorkPlane

MECHANICAL_SOURCE_KEY = "mechanical_motion_source"
MECHANICAL_SOURCE_KIND = "mechanical_motion_assembly"
MECHANICAL_DRAFT_KIND = "mechanical_motion_draft"
MECHANICAL_SOURCE_SCHEMA = 3


def _plain(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_plain(item) for item in value]
    if hasattr(value, "value"):
        return _plain(value.value)
    return str(value)


def serialize_assembly(assembly: MechanicalAssembly, *, draft: bool | None = None) -> dict[str, Any]:
    payload = asdict(assembly)
    payload["gears"] = {key: _plain(value) for key, value in payload.get("gears", {}).items()}
    payload["chains"] = {key: _plain(value) for key, value in payload.get("chains", {}).items()}
    payload["racks"] = {key: _plain(value) for key, value in payload.get("racks", {}).items()}
    payload["stages"] = {key: _plain(value) for key, value in payload.get("stages", {}).items()}
    payload["drivers"] = {key: _plain(value) for key, value in payload.get("drivers", {}).items()}
    payload["attachments"] = {key: _plain(value) for key, value in payload.get("attachments", {}).items()}
    payload["draft"] = bool(assembly.draft if draft is None else draft)
    return {
        "schema_version": MECHANICAL_SOURCE_SCHEMA,
        "kind": MECHANICAL_DRAFT_KIND if payload["draft"] else MECHANICAL_SOURCE_KIND,
        "tool_id": "mechanical_motion",
        "assembly": _plain(payload),
    }


def _gear(data: dict[str, Any]) -> GearSpec:
    values = dict(data)
    try:
        values["profile"] = ToothProfile(str(values.get("profile") or ToothProfile.INVOLUTE_APPROX.value))
    except Exception:
        values["profile"] = ToothProfile.INVOLUTE_APPROX
    return GearSpec(**{key: value for key, value in values.items() if key in GearSpec.__dataclass_fields__}).normalized()


def _chain(data: dict[str, Any]) -> GearChainSpec:
    values = dict(data)
    try:
        values["profile"] = ToothProfile(str(values.get("profile") or ToothProfile.INVOLUTE_APPROX.value))
    except Exception:
        values["profile"] = ToothProfile.INVOLUTE_APPROX
    return GearChainSpec(**{key: value for key, value in values.items() if key in GearChainSpec.__dataclass_fields__}).normalized()


def _rack(data: dict[str, Any]) -> RackSpec:
    values = dict(data)
    try:
        values["profile"] = ToothProfile(str(values.get("profile") or ToothProfile.TRAPEZOID.value))
    except Exception:
        values["profile"] = ToothProfile.TRAPEZOID
    return RackSpec(**{key: value for key, value in values.items() if key in RackSpec.__dataclass_fields__}).normalized()


def deserialize_assembly(source: Any) -> MechanicalAssembly | None:
    if not isinstance(source, dict):
        return None
    data = source.get("assembly") if isinstance(source.get("assembly"), dict) else source
    if not isinstance(data, dict):
        return None
    assembly = MechanicalAssembly(
        id=str(data.get("id") or ""),
        name=str(data.get("name") or "Mechanical assembly"),
        work_plane=(MechanicalWorkPlane(**data["work_plane"]).normalized() if isinstance(data.get("work_plane"), dict) else None),
        selected_element_id=data.get("selected_element_id"),
        schema_version=int(data.get("schema_version") or MECHANICAL_SOURCE_SCHEMA),
        draft=bool(data.get("draft", source.get("kind") == MECHANICAL_DRAFT_KIND)),
    )
    if not assembly.id:
        assembly = MechanicalAssembly(name=assembly.name, draft=assembly.draft)
    for key, value in (data.get("gears") or {}).items():
        if isinstance(value, dict):
            gear = _gear(value)
            assembly.gears[str(key or gear.id)] = gear
    for key, value in (data.get("chains") or {}).items():
        if isinstance(value, dict):
            chain = _chain(value)
            assembly.chains[str(key or chain.id)] = chain
    for key, value in (data.get("racks") or {}).items():
        if isinstance(value, dict):
            rack = _rack(value)
            assembly.racks[str(key or rack.id)] = rack
    for key, value in (data.get("stages") or {}).items():
        if isinstance(value, dict):
            stage = GearStage(**{field: item for field, item in value.items() if field in GearStage.__dataclass_fields__})
            assembly.stages[str(key or stage.id)] = stage
    for key, value in (data.get("drivers") or {}).items():
        if isinstance(value, dict):
            driver = RotaryDriverSpec(**{field: item for field, item in value.items() if field in RotaryDriverSpec.__dataclass_fields__}).normalized()
            assembly.drivers[str(key or driver.id)] = driver
    for key, value in (data.get("attachments") or {}).items():
        if isinstance(value, dict):
            attachment = AttachmentSpec(**{field: item for field, item in value.items() if field in AttachmentSpec.__dataclass_fields__}).normalized()
            assembly.attachments[str(key or attachment.id)] = attachment
    assembly.enforce_single_driver()
    return assembly


def attach_source(mesh: Any, assembly: MechanicalAssembly, *, draft: bool = False) -> Any:
    metadata = getattr(mesh, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        try:
            mesh.metadata = metadata
        except Exception:
            return mesh
    metadata[MECHANICAL_SOURCE_KEY] = serialize_assembly(assembly, draft=draft)
    metadata["mechanical_assembly_id"] = assembly.id
    metadata["mechanical_draft"] = bool(draft)
    metadata["source_tool"] = "mechanical_motion"
    metadata["editable_tool_id"] = "mechanical_motion"
    metadata["editable_kind"] = MECHANICAL_DRAFT_KIND if bool(draft) else MECHANICAL_SOURCE_KIND
    return mesh



def detach_source(mesh: Any) -> Any:
    """Remove mechanical ownership metadata from a copied scene carrier."""

    metadata = getattr(mesh, "metadata", None)
    if isinstance(metadata, dict):
        metadata.pop(MECHANICAL_SOURCE_KEY, None)
        metadata.pop("mechanical_assembly_id", None)
        metadata.pop("mechanical_draft", None)
        metadata.pop("source_tool", None)
        metadata.pop("editable_tool_id", None)
        metadata.pop("editable_kind", None)
    return mesh


def is_generated_mechanical_mesh(mesh: Any) -> bool:
    metadata = getattr(mesh, "metadata", None)
    return isinstance(metadata, dict) and bool(
        metadata.get("mechanical_generated") or metadata.get("mechanical_draft_placeholder")
    )


def assembly_persistence_signature(assembly: MechanicalAssembly) -> dict[str, Any]:
    """Serializable geometry/configuration state without transient UI selection."""

    source = serialize_assembly(assembly, draft=False)
    payload = copy.deepcopy(source.get("assembly") or {})
    payload.pop("selected_element_id", None)
    payload.pop("draft", None)
    return payload


def source_from_mesh(mesh: Any) -> dict[str, Any] | None:
    metadata = getattr(mesh, "metadata", None)
    if not isinstance(metadata, dict):
        return None
    source = metadata.get(MECHANICAL_SOURCE_KEY)
    return copy.deepcopy(source) if isinstance(source, dict) else None


def assembly_from_mesh(mesh: Any) -> MechanicalAssembly | None:
    return deserialize_assembly(source_from_mesh(mesh))


def mesh_belongs_to_assembly(mesh: Any, assembly_id: str) -> bool:
    metadata = getattr(mesh, "metadata", None)
    return isinstance(metadata, dict) and str(metadata.get("mechanical_assembly_id") or "") == str(assembly_id)


__all__ = [
    "MECHANICAL_DRAFT_KIND",
    "MECHANICAL_SOURCE_KEY",
    "MECHANICAL_SOURCE_KIND",
    "MECHANICAL_SOURCE_SCHEMA",
    "assembly_from_mesh",
    "assembly_persistence_signature",
    "attach_source",
    "deserialize_assembly",
    "detach_source",
    "is_generated_mechanical_mesh",
    "mesh_belongs_to_assembly",
    "serialize_assembly",
    "source_from_mesh",
]
