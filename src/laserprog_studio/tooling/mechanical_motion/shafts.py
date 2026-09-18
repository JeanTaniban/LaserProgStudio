# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .models import GearSpec, MechanicalAssembly
from .plane import MechanicalWorkPlane


@dataclass(frozen=True, slots=True)
class ShaftNormalizationResult:
    aliases: dict[str, str]
    merged_groups: tuple[tuple[str, ...], ...]

    @property
    def changed(self) -> bool:
        return any(source != target for source, target in self.aliases.items())


class _UnionFind:
    def __init__(self, values: Iterable[str]) -> None:
        self.parent = {str(value): str(value) for value in values}

    def find(self, value: str) -> str:
        key = str(value)
        parent = self.parent.setdefault(key, key)
        if parent != key:
            self.parent[key] = self.find(parent)
        return self.parent[key]

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _planar_distance(a: GearSpec, b: GearSpec, plane: MechanicalWorkPlane) -> float:
    au, av = plane.coordinates(a.center)
    bu, bv = plane.coordinates(b.center)
    return sqrt((au - bu) ** 2 + (av - bv) ** 2)


def _axial_gap(a: GearSpec, b: GearSpec, plane: MechanicalWorkPlane) -> float:
    ac = _dot(a.center, plane.normal)
    bc = _dot(b.center, plane.normal)
    a0, a1 = ac - 0.5 * float(a.thickness_mm), ac + 0.5 * float(a.thickness_mm)
    b0, b1 = bc - 0.5 * float(b.thickness_mm), bc + 0.5 * float(b.thickness_mm)
    return max(0.0, max(a0, b0) - min(a1, b1))


def gears_are_rigidly_coaxial(
    a: GearSpec,
    b: GearSpec,
    plane: MechanicalWorkPlane,
    *,
    radial_tolerance_mm: float = 0.08,
    axial_tolerance_mm: float = 0.10,
) -> bool:
    """Return True when two gear bodies share an axis and touch/overlap axially.

    MEC has no clutch/freewheel element yet, so touching coaxial gear bodies are
    a rigid compound shaft. Treating them as separate shafts creates the exact
    visual defect where apparently fused gears rotate at different speeds.
    """

    if str(a.shaft_id or a.id) == str(b.shaft_id or b.id):
        return True
    return (
        _planar_distance(a, b, plane) <= max(1.0e-6, float(radial_tolerance_mm))
        and _axial_gap(a, b, plane) <= max(1.0e-6, float(axial_tolerance_mm))
    )


def normalize_coaxial_shafts(
    assembly: MechanicalAssembly,
    *,
    plane: MechanicalWorkPlane | None = None,
) -> ShaftNormalizationResult:
    """Canonicalize every rigid coaxial group to one stable shaft identifier.

    This is intentionally run on load, after geometry edits and before solving.
    It repairs older projects and also prevents manually stacked gears from
    becoming independent kinematic nodes.
    """

    frame = plane or (assembly.work_plane if isinstance(assembly.work_plane, MechanicalWorkPlane) else None)
    gears = tuple(assembly.gears.values())
    shaft_order: list[str] = []
    for gear in gears:
        shaft_id = str(gear.shaft_id or gear.id)
        gear.shaft_id = shaft_id
        if shaft_id not in shaft_order:
            shaft_order.append(shaft_id)
    if not gears:
        return ShaftNormalizationResult({}, ())

    uf = _UnionFind(shaft_order)
    if frame is not None:
        for index, gear in enumerate(gears):
            for other in gears[index + 1 :]:
                if gears_are_rigidly_coaxial(gear, other, frame):
                    uf.union(str(gear.shaft_id), str(other.shaft_id))

    members: dict[str, list[str]] = {}
    for shaft_id in shaft_order:
        members.setdefault(uf.find(shaft_id), []).append(shaft_id)

    order_index = {shaft_id: index for index, shaft_id in enumerate(shaft_order)}
    aliases: dict[str, str] = {}
    merged_groups: list[tuple[str, ...]] = []
    for values in members.values():
        canonical = min(values, key=lambda value: order_index.get(value, 10**9))
        group = tuple(values)
        if len(group) > 1:
            merged_groups.append(group)
        for value in values:
            aliases[value] = canonical

    def alias(value: str | None) -> str | None:
        if value is None:
            return None
        raw = str(value)
        return aliases.get(raw, raw)

    for gear in gears:
        gear.shaft_id = alias(gear.shaft_id) or gear.id
    for stage in assembly.stages.values():
        stage.driver_shaft_id = alias(stage.driver_shaft_id) or stage.driver_shaft_id
        stage.driven_shaft_id = alias(stage.driven_shaft_id) or stage.driven_shaft_id
    for chain in assembly.chains.values():
        chain.shaft_ids = [alias(value) or str(value) for value in chain.shaft_ids]
    for driver in assembly.drivers.values():
        if driver.target_gear_id in assembly.gears:
            target = assembly.gears[str(driver.target_gear_id)]
            driver.shaft_id = target.shaft_id or target.id
            driver.center = target.center
        else:
            driver.shaft_id = alias(driver.shaft_id)
    for attachment in assembly.attachments.values():
        if attachment.source_gear_id in assembly.gears:
            source = assembly.gears[str(attachment.source_gear_id)]
            attachment.shaft_id = source.shaft_id or source.id
            if frame is not None:
                attachment.center = frame.clamp(source.center)
        else:
            attachment.shaft_id = alias(attachment.shaft_id)

    return ShaftNormalizationResult(aliases, tuple(merged_groups))


__all__ = ["ShaftNormalizationResult", "gears_are_rigidly_coaxial", "normalize_coaxial_shafts"]
