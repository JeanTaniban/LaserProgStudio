# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import dist, exp, log
from typing import Iterable

from .curve import equally_spaced_curve_points
from .models import GearChainSpec, GearSpec, GearStage, MechanicalAssembly, ToothProfile, make_id
from .plane import MechanicalWorkPlane


# A path of compound gears needs a distance-two layer colouring.  With only
# two alternating layers, stage N-1 and stage N+1 land on the same level and
# can form a second unintended mesh between adjacent compound shafts.  Three
# layers are the minimum bounded schedule that guarantees one physical contact
# per stage.
_CHAIN_AXIAL_LAYER_COUNT = 3


def chain_stage_axial_layer(stage_index: int) -> int:
    return max(0, int(stage_index)) % _CHAIN_AXIAL_LAYER_COUNT


@dataclass(frozen=True, slots=True)
class ToothPairSolution:
    driver_teeth: int
    driven_teeth: int
    module_mm: float
    actual_reduction: float
    score: float


@dataclass(frozen=True, slots=True)
class ChainSolveResult:
    chain: GearChainSpec
    gears: tuple[GearSpec, ...]
    stages: tuple[GearStage, ...]


def distributed_stage_reductions(total_reduction: float, stage_count: int, bias: float) -> tuple[float, ...]:
    """Split a total reduction across stages in logarithmic space.

    ``bias`` is in [-1, 1]. Negative values put more ratio in the first stages,
    positive values put more ratio in the last stages, and zero distributes it
    evenly. Multiplying all returned stage reductions exactly recreates the
    requested total before integer tooth rounding.
    """

    count = max(1, int(stage_count))
    total = max(0.01, float(total_reduction))
    clamped_bias = max(-1.0, min(1.0, float(bias)))
    if count == 1:
        return (total,)
    strength = 2.75 * clamped_bias
    raw = [exp(strength * ((i / (count - 1)) - 0.5)) for i in range(count)]
    normalizer = sum(raw) or 1.0
    log_total = log(total)
    return tuple(exp(log_total * weight / normalizer) for weight in raw)


def solve_tooth_pair(
    center_distance_mm: float,
    target_reduction: float,
    target_module_mm: float,
    *,
    min_teeth: int = 12,
    max_teeth: int = 120,
) -> ToothPairSolution:
    distance_mm = max(0.1, float(center_distance_mm))
    ratio = max(0.01, float(target_reduction))
    module_target = max(0.05, float(target_module_mm))
    minimum = max(6, int(min_teeth))
    maximum = max(minimum, int(max_teeth))
    ideal_total = max(2 * minimum, min(2 * maximum, int(round((2.0 * distance_mm) / module_target))))
    best: ToothPairSolution | None = None

    total_low = max(2 * minimum, ideal_total - 32)
    total_high = min(2 * maximum, ideal_total + 32)
    for total_teeth in range(total_low, total_high + 1):
        expected_driver = total_teeth / (1.0 + ratio)
        driver_low = max(minimum, int(round(expected_driver)) - 8)
        driver_high = min(maximum, total_teeth - minimum, int(round(expected_driver)) + 8)
        for driver_teeth in range(driver_low, driver_high + 1):
            driven_teeth = total_teeth - driver_teeth
            if not (minimum <= driven_teeth <= maximum):
                continue
            actual = driven_teeth / driver_teeth
            module = (2.0 * distance_mm) / total_teeth
            ratio_error = abs(log(max(actual, 1e-9) / ratio))
            module_error = abs(module - module_target) / module_target
            score = 5.0 * ratio_error + 0.45 * module_error + 0.001 * total_teeth
            candidate = ToothPairSolution(driver_teeth, driven_teeth, module, actual, score)
            if best is None or candidate.score < best.score:
                best = candidate
    if best is None:
        driver = minimum
        driven = max(minimum, min(maximum, int(round(driver * ratio))))
        module = (2.0 * distance_mm) / (driver + driven)
        best = ToothPairSolution(driver, driven, module, driven / driver, float("inf"))
    return best


def _phase_for_mesh(driver: GearSpec, driven: GearSpec, mesh_angle_deg: float) -> tuple[float, float]:
    """Align one driver tooth with one driven gap on the real centre line.

    Tooth centres are generated at ``phase + k * pitch``.  Therefore the driver
    gets a tooth exactly toward the driven centre, while the driven gear gets a
    gap toward the driver centre.  Using the actual U/V-plane angle is essential
    for curved routes; alternating a fixed 0/180 degree phase cannot work once
    two consecutive stages point in different directions.
    """

    driven_pitch = 360.0 / max(1, driven.teeth)
    driver_phase = float(mesh_angle_deg) % 360.0
    driven_phase = (float(mesh_angle_deg) + 180.0 + 0.5 * driven_pitch) % 360.0
    return driver_phase, driven_phase


def solve_chain(chain: GearChainSpec, *, plane: MechanicalWorkPlane | None = None) -> ChainSolveResult:
    chain.normalized()
    frame = plane or MechanicalWorkPlane.horizontal_at(chain.start)
    shaft_count = chain.shaft_count
    shafts = equally_spaced_curve_points(
        (chain.start, chain.control_1, chain.control_2, chain.end),
        shaft_count,
    )
    stage_targets = distributed_stage_reductions(chain.total_reduction, shaft_count - 1, chain.ratio_distribution)
    shaft_ids = [make_id(f"{chain.id}_shaft") for _ in range(shaft_count)]
    gears: list[GearSpec] = []
    stages: list[GearStage] = []
    actual_total = 1.0
    warning_parts: list[str] = []

    for index, (a, b, stage_target) in enumerate(zip(shafts, shafts[1:], stage_targets)):
        center_distance = dist(a, b)
        tooth_pair = solve_tooth_pair(
            center_distance,
            stage_target,
            chain.target_module_mm,
            min_teeth=chain.min_teeth,
            max_teeth=chain.max_teeth,
        )
        axial_layer = chain_stage_axial_layer(index)
        # Different mesh stages receive real axial clearance.  The compound
        # shaft builder adds a central hub between coaxial gears, so the two
        # gears on one shaft remain one rigid part without letting neighbouring
        # stages touch at a second, parasitic contact point.
        driver_center = frame.gear_center(
            a,
            chain.thickness_mm,
            layer=axial_layer,
            layer_gap_mm=chain.axial_clearance_mm,
        )
        driven_center = frame.gear_center(
            b,
            chain.thickness_mm,
            layer=axial_layer,
            layer_gap_mm=chain.axial_clearance_mm,
        )
        driver = GearSpec(
            name=f"{chain.name} · stage {index + 1} driver",
            center=driver_center,
            teeth=tooth_pair.driver_teeth,
            module_mm=tooth_pair.module_mm,
            thickness_mm=chain.thickness_mm,
            bore_diameter_mm=chain.bore_diameter_mm,
            pressure_angle_deg=chain.pressure_angle_deg,
            profile=chain.profile if isinstance(chain.profile, ToothProfile) else ToothProfile(str(chain.profile)),
            backlash_mm=chain.backlash_mm,
            shaft_id=shaft_ids[index],
            stage_index=index,
            role="chain_driver",
            color="#D9A441",
        ).normalized()
        driven = GearSpec(
            name=f"{chain.name} · stage {index + 1} driven",
            center=driven_center,
            teeth=tooth_pair.driven_teeth,
            module_mm=tooth_pair.module_mm,
            thickness_mm=chain.thickness_mm,
            bore_diameter_mm=chain.bore_diameter_mm,
            pressure_angle_deg=chain.pressure_angle_deg,
            profile=chain.profile if isinstance(chain.profile, ToothProfile) else ToothProfile(str(chain.profile)),
            backlash_mm=chain.backlash_mm,
            shaft_id=shaft_ids[index + 1],
            stage_index=index,
            role="chain_driven",
            color="#C98C2B",
        ).normalized()
        mesh_angle_deg = frame.angle_deg(a, b)
        driver.phase_deg, driven.phase_deg = _phase_for_mesh(driver, driven, mesh_angle_deg)
        stage = GearStage(
            index=index,
            driver_gear_id=driver.id,
            driven_gear_id=driven.id,
            driver_shaft_id=shaft_ids[index],
            driven_shaft_id=shaft_ids[index + 1],
            target_reduction=stage_target,
            actual_reduction=tooth_pair.actual_reduction,
            center_distance_mm=center_distance,
            axial_layer=axial_layer,
            connection_kind="chain",
            owner_id=chain.id,
        )
        gears.extend((driver, driven))
        stages.append(stage)
        actual_total *= tooth_pair.actual_reduction
        if tooth_pair.module_mm < 0.25 * chain.target_module_mm or tooth_pair.module_mm > 4.0 * chain.target_module_mm:
            warning_parts.append(f"stage {index + 1}: module {tooth_pair.module_mm:.3g} mm")

    chain.shafts = list(shafts)
    chain.shaft_ids = shaft_ids
    chain.gear_ids = [gear.id for gear in gears]
    chain.stage_ids = [stage.id for stage in stages]
    chain.actual_reduction = actual_total
    ratio_error = abs(log(max(actual_total, 1e-9) / max(chain.total_reduction, 1e-9)))
    if ratio_error > 0.03:
        warning_parts.insert(0, f"requested {chain.total_reduction:.4g}:1, obtained {actual_total:.4g}:1 after tooth rounding")
    chain.warning = "; ".join(warning_parts)
    return ChainSolveResult(chain=chain, gears=tuple(gears), stages=tuple(stages))


def replace_chain_solution(assembly: MechanicalAssembly, chain: GearChainSpec) -> ChainSolveResult:
    """Replace one parametric chain while preserving external references.

    Re-solving creates fresh domain objects. Stable gear/stage/shaft identifiers
    are retained whenever topology is unchanged. If the number of stages changes,
    old references are migrated to the nearest corresponding gear so drivers and
    attachments do not silently disconnect.
    """

    old = assembly.chains.get(chain.id)
    old_gear_ids = list(old.gear_ids) if old is not None else []
    old_stage_ids = list(old.stage_ids) if old is not None else []
    old_shaft_ids = list(old.shaft_ids) if old is not None else []
    work_plane = assembly.work_plane if isinstance(assembly.work_plane, MechanicalWorkPlane) else None
    result = solve_chain(chain, plane=work_plane)
    new_gears = list(result.gears)
    new_stages = list(result.stages)

    if old_gear_ids and len(old_gear_ids) == len(new_gears):
        for gear, stable_id in zip(new_gears, old_gear_ids):
            gear.id = stable_id
    if old_shaft_ids and len(old_shaft_ids) == len(result.chain.shaft_ids):
        shaft_map = dict(zip(result.chain.shaft_ids, old_shaft_ids))
        result.chain.shaft_ids = list(old_shaft_ids)
        for gear in new_gears:
            gear.shaft_id = shaft_map.get(str(gear.shaft_id), gear.shaft_id)
        for stage in new_stages:
            stage.driver_shaft_id = shaft_map.get(stage.driver_shaft_id, stage.driver_shaft_id)
            stage.driven_shaft_id = shaft_map.get(stage.driven_shaft_id, stage.driven_shaft_id)
    if old_stage_ids and len(old_stage_ids) == len(new_stages):
        for stage, stable_id in zip(new_stages, old_stage_ids):
            stage.id = stable_id

    for index, stage in enumerate(new_stages):
        stage.driver_gear_id = new_gears[2 * index].id
        stage.driven_gear_id = new_gears[2 * index + 1].id
    result.chain.gear_ids = [gear.id for gear in new_gears]
    result.chain.stage_ids = [stage.id for stage in new_stages]

    reference_map: dict[str, str] = {}
    if old_gear_ids and new_gears:
        old_last = max(1, len(old_gear_ids) - 1)
        new_last = max(0, len(new_gears) - 1)
        for index, old_id in enumerate(old_gear_ids):
            mapped_index = int(round((index / old_last) * new_last)) if len(old_gear_ids) > 1 else 0
            reference_map[old_id] = new_gears[mapped_index].id

    for gear_id in old_gear_ids:
        assembly.gears.pop(gear_id, None)
    for stage_id in old_stage_ids:
        assembly.stages.pop(stage_id, None)
    assembly.chains[chain.id] = result.chain
    for gear in new_gears:
        assembly.gears[gear.id] = gear
    for stage in new_stages:
        assembly.stages[stage.id] = stage

    for driver in assembly.drivers.values():
        replacement = reference_map.get(str(driver.target_gear_id))
        if replacement:
            driver.target_gear_id = replacement
            driver.shaft_id = assembly.gears[replacement].shaft_id or replacement
            driver.center = assembly.gears[replacement].center
    for attachment in assembly.attachments.values():
        replacement = reference_map.get(str(attachment.source_gear_id))
        if replacement:
            attachment.source_gear_id = replacement
            if attachment.source_element_id in reference_map:
                attachment.source_element_id = replacement
            attachment.shaft_id = assembly.gears[replacement].shaft_id or replacement
            attachment.center = assembly.gears[replacement].center
    for rack in assembly.racks.values():
        replacement = reference_map.get(str(rack.pinion_gear_id))
        if replacement:
            rack.pinion_gear_id = replacement
    return ChainSolveResult(chain=result.chain, gears=tuple(new_gears), stages=tuple(new_stages))


__all__ = [
    "ChainSolveResult",
    "ToothPairSolution",
    "chain_stage_axial_layer",
    "distributed_stage_reductions",
    "replace_chain_solution",
    "solve_chain",
    "solve_tooth_pair",
]
