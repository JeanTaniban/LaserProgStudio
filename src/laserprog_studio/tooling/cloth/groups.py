"""Persistent user-facing textile group identities.

A Cloth document may contain many technical planar patches for one textile piece.
Those patches must behave as one selectable unit until Draw deliberately splits
that unit.  Geometry proximity is never used to merge two already-declared
textile groups.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import ClothDocument
from .topology import curve_endpoint_ids

_GROUP_REGISTRY_KEY = "cloth_textile_groups_v1"
_GROUP_ID_KEY = "cloth_logical_group_id"
_GROUP_ORIGIN_KEY = "cloth_group_origin"
_GROUP_PARENT_IDS_KEY = "cloth_group_parent_ids"


@dataclass(frozen=True, slots=True)
class TextileGroupNormalization:
    changed: bool = False
    split_group_count: int = 0
    created_group_ids: tuple[str, ...] = ()
    removed_group_ids: tuple[str, ...] = ()


def _registry(document: ClothDocument, *, create: bool) -> dict[str, dict[str, Any]]:
    current = document.metadata.get(_GROUP_REGISTRY_KEY)
    if isinstance(current, dict):
        return current
    if not create:
        return {}
    value: dict[str, dict[str, Any]] = {}
    document.metadata[_GROUP_REGISTRY_KEY] = value
    return value


def explicit_textile_group_id(document: ClothDocument, patch_id: str) -> str:
    patch = document.patches.get(str(patch_id))
    if patch is None:
        return ""
    return str(dict(patch.metadata or {}).get(_GROUP_ID_KEY) or "")


def textile_group_record(document: ClothDocument, group_id: str) -> dict[str, Any] | None:
    value = _registry(document, create=False).get(str(group_id))
    return value if isinstance(value, dict) else None


def textile_group_patch_ids(document: ClothDocument, group_id: str) -> tuple[str, ...]:
    wanted = str(group_id)
    return tuple(
        patch_id
        for patch_id, patch in document.patches.items()
        if str(dict(patch.metadata or {}).get(_GROUP_ID_KEY) or "") == wanted
    )


def create_textile_group(
    document: ClothDocument,
    patch_ids: Iterable[str],
    *,
    group_id: str | None = None,
    origin: str = "unknown",
    parent_group_ids: Iterable[str] = (),
    label: str | None = None,
) -> tuple[str, ...]:
    """Assign exactly one persistent identity to the supplied technical patches.

    Membership is exclusive.  Reassigning a patch removes it from its previous
    group.  Parent ids are provenance only and never influence selection.
    """

    members = tuple(dict.fromkeys(str(value) for value in patch_ids if str(value) in document.patches))
    if not members:
        return ()
    resolved_id = str(group_id or document.new_id("textile_group"))
    registry = _registry(document, create=True)

    # Remove reassigned members from previous records.
    for old_id, raw in tuple(registry.items()):
        if not isinstance(raw, dict):
            registry.pop(old_id, None)
            continue
        previous = [str(value) for value in raw.get("patch_ids") or ()]
        remaining = [value for value in previous if value not in members and value in document.patches]
        if remaining:
            raw["patch_ids"] = remaining
        else:
            registry.pop(old_id, None)

    parents = tuple(dict.fromkeys(str(value) for value in parent_group_ids if str(value)))
    for patch_id in members:
        patch = document.patches[patch_id]
        patch.metadata[_GROUP_ID_KEY] = resolved_id
        patch.metadata[_GROUP_ORIGIN_KEY] = str(origin or "unknown")
        if parents:
            patch.metadata[_GROUP_PARENT_IDS_KEY] = parents
        else:
            patch.metadata.pop(_GROUP_PARENT_IDS_KEY, None)

    registry[resolved_id] = {
        "id": resolved_id,
        "patch_ids": list(members),
        "origin": str(origin or "unknown"),
        "parent_group_ids": list(parents),
        "label": str(label or ""),
        "created_revision": int(document.revision),
    }
    document._touch()
    return members


def remove_stale_textile_group_records(document: ClothDocument) -> tuple[str, ...]:
    registry = _registry(document, create=False)
    if not registry:
        return ()
    removed: list[str] = []
    changed = False
    for group_id, raw in tuple(registry.items()):
        if not isinstance(raw, dict):
            registry.pop(group_id, None)
            removed.append(str(group_id))
            changed = True
            continue
        members = textile_group_patch_ids(document, str(group_id))
        if not members:
            registry.pop(group_id, None)
            removed.append(str(group_id))
            changed = True
        elif list(raw.get("patch_ids") or ()) != list(members):
            raw["patch_ids"] = list(members)
            changed = True
    if changed:
        document._touch()
    return tuple(removed)



def materialize_legacy_textile_groups(document: ClothDocument) -> tuple[str, ...]:
    """Give every legacy textile patch an explicit persistent group identity."""

    buckets: dict[str, list[str]] = {}
    for patch_id, patch in document.patches.items():
        if explicit_textile_group_id(document, patch_id):
            continue
        metadata = dict(patch.metadata or {})
        source_object = str(metadata.get("cloth_source_object_id") or "")
        source_component = str(metadata.get("cloth_source_component") or "")
        creation_id = str(metadata.get("cloth_creation_group_id") or "")
        join_id = str(metadata.get("cloth_join_proposal_id") or "")
        region_id = str(metadata.get("cloth_region_id") or "")
        strip_id = str(metadata.get("cloth_ruled_strip_id") or "")
        source_faces = tuple(metadata.get("cloth_source_faces") or ())
        if creation_id:
            key = f"creation:{creation_id}"
        elif source_object and source_component:
            key = f"source_component:{source_object}:{source_component}"
        elif region_id:
            key = f"draw_region:{region_id}"
        elif strip_id:
            key = f"strip:{strip_id}"
        elif join_id:
            key = f"close:{join_id}"
        elif source_object and source_faces:
            key = f"source_faces:{source_object}:{source_faces!r}"
        else:
            key = f"patch:{patch_id}"
        buckets.setdefault(key, []).append(patch_id)

    created_ids: list[str] = []
    for key, members in buckets.items():
        origin = "legacy"
        if key.startswith("source_"):
            origin = "take_face"
        elif key.startswith("draw_") or key.startswith("strip:"):
            origin = "draw"
        elif key.startswith("close:"):
            origin = "close"
        group_id = document.new_id("textile_group")
        created = create_textile_group(
            document,
            members,
            group_id=group_id,
            origin=origin,
            label="Migrated textile group",
        )
        if created:
            created_ids.append(group_id)
    remove_stale_textile_group_records(document)
    return tuple(created_ids)

def normalize_disconnected_textile_groups(
    document: ClothDocument,
    *,
    group_ids: Iterable[str] | None = None,
    tolerance: float = 1.0e-6,
    origin: str = "draw_split",
) -> TextileGroupNormalization:
    """Split persistent groups whose remaining patches are disconnected.

    This is the group-level foundation for Draw cuts.  Deleting or separating
    technical faces cannot leave two disconnected islands with one selectable
    identity.
    """

    registry = _registry(document, create=False)
    candidates = tuple(
        dict.fromkeys(
            str(value)
            for value in (
                group_ids
                if group_ids is not None
                else (
                    explicit_textile_group_id(document, patch_id)
                    for patch_id in document.patches
                )
            )
            if str(value)
        )
    )
    created: list[str] = []
    removed: list[str] = []
    split_count = 0
    changed = False

    for group_id in candidates:
        members = textile_group_patch_ids(document, group_id)
        if not members:
            if group_id in registry:
                registry.pop(group_id, None)
                removed.append(group_id)
                changed = True
            continue
        components = _patch_components(document, members, tolerance=max(1.0e-12, float(tolerance)))
        if len(components) <= 1:
            raw = registry.get(group_id)
            if isinstance(raw, dict) and list(raw.get("patch_ids") or ()) != list(members):
                raw["patch_ids"] = list(members)
                changed = True
            continue

        split_count += 1
        changed = True
        previous = registry.get(group_id) if isinstance(registry.get(group_id), dict) else {}
        previous_origin = str(previous.get("origin") or "unknown")
        previous_label = str(previous.get("label") or "")
        previous_parents = tuple(str(value) for value in previous.get("parent_group_ids") or ())

        ordered = sorted(components, key=lambda component: (-len(component), min(component)))
        _assign_group_without_touch(
            document,
            registry,
            group_id,
            ordered[0],
            origin=previous_origin,
            parents=previous_parents,
            label=previous_label,
        )
        for index, component in enumerate(ordered[1:], start=1):
            new_id = document.new_id("textile_group")
            _assign_group_without_touch(
                document,
                registry,
                new_id,
                component,
                origin=origin,
                parents=(group_id,),
                label=f"{previous_label or group_id} split {index + 1}",
            )
            created.append(new_id)

    if changed:
        document._touch()
    return TextileGroupNormalization(
        changed=changed,
        split_group_count=split_count,
        created_group_ids=tuple(created),
        removed_group_ids=tuple(removed),
    )


def _assign_group_without_touch(
    document: ClothDocument,
    registry: dict[str, dict[str, Any]],
    group_id: str,
    members: Iterable[str],
    *,
    origin: str,
    parents: Iterable[str],
    label: str,
) -> None:
    values = tuple(dict.fromkeys(str(value) for value in members if str(value) in document.patches))
    parent_values = tuple(dict.fromkeys(str(value) for value in parents if str(value)))
    for patch_id in values:
        patch = document.patches[patch_id]
        patch.metadata[_GROUP_ID_KEY] = str(group_id)
        patch.metadata[_GROUP_ORIGIN_KEY] = str(origin or "unknown")
        if parent_values:
            patch.metadata[_GROUP_PARENT_IDS_KEY] = parent_values
        else:
            patch.metadata.pop(_GROUP_PARENT_IDS_KEY, None)
    registry[str(group_id)] = {
        "id": str(group_id),
        "patch_ids": list(values),
        "origin": str(origin or "unknown"),
        "parent_group_ids": list(parent_values),
        "label": str(label or ""),
        "created_revision": int(document.revision),
    }


def _patch_components(document: ClothDocument, patch_ids: Iterable[str], tolerance: float) -> tuple[tuple[str, ...], ...]:
    members = tuple(dict.fromkeys(str(value) for value in patch_ids if str(value) in document.patches))
    if len(members) <= 1:
        return (members,) if members else ()

    edge_owners: dict[tuple[tuple[int, int, int], tuple[int, int, int]], set[str]] = {}
    curve_owners: dict[str, set[str]] = {}
    for patch_id in members:
        patch = document.patches[patch_id]
        curve_ids = tuple(patch.outer_curve_ids) + tuple(value for loop in patch.hole_curve_loops for value in loop)
        for curve_id in curve_ids:
            curve_owners.setdefault(str(curve_id), set()).add(patch_id)
            curve = document.curves.get(str(curve_id))
            if curve is None:
                continue
            first_id, second_id = curve_endpoint_ids(curve)
            first = document.points.get(first_id)
            second = document.points.get(second_id)
            if first is None or second is None:
                continue
            key = _edge_key(first.position, second.position, tolerance)
            edge_owners.setdefault(key, set()).add(patch_id)

    adjacency: dict[str, set[str]] = {patch_id: set() for patch_id in members}
    for owners in (*curve_owners.values(), *edge_owners.values()):
        values = tuple(owners)
        for index, first in enumerate(values):
            adjacency[first].update(values[:index])
            adjacency[first].update(values[index + 1 :])

    remaining = set(members)
    components: list[tuple[str, ...]] = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, ()) - component)
        remaining.difference_update(component)
        components.append(tuple(sorted(component)))
    return tuple(components)


def _edge_key(first, second, tolerance: float):
    def quantize(point):
        return tuple(int(round(float(value) / tolerance)) for value in point)

    a = quantize(first)
    b = quantize(second)
    return (a, b) if a <= b else (b, a)


__all__ = [
    "TextileGroupNormalization",
    "create_textile_group",
    "explicit_textile_group_id",
    "materialize_legacy_textile_groups",
    "normalize_disconnected_textile_groups",
    "remove_stale_textile_group_records",
    "textile_group_patch_ids",
    "textile_group_record",
]
