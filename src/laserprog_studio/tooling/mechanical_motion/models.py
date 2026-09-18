# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import uuid
from typing import Any, Iterable

Point3 = tuple[float, float, float]


def make_id(prefix: str) -> str:
    return f"{str(prefix).strip() or 'item'}_{uuid.uuid4().hex[:12]}"


def point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


class MechanicalMode(str, Enum):
    PICK_PLANE = "pick_plane"
    SELECT = "select"
    PLACE_GEAR = "place_gear"
    PLACE_CHAIN_START = "place_chain_start"
    PLACE_CHAIN_END = "place_chain_end"
    PICK_RACK_PINION = "pick_rack_pinion"
    PLACE_RACK_START = "place_rack_start"
    PLACE_RACK_END = "place_rack_end"
    EDIT_CURVE = "edit_curve"
    PICK_DRIVER_TARGET = "pick_driver_target"
    PLACE_DRIVER_CENTER = "place_driver_center"
    PICK_ATTACHMENT_SOURCE = "pick_attachment_source"
    PICK_ATTACHMENTS = "pick_attachments"
    TEST = "test"


class ToothProfile(str, Enum):
    INVOLUTE_APPROX = "involute"
    TRAPEZOID = "trapezoid"
    ROUNDED = "rounded"


class ElementKind(str, Enum):
    GEAR = "gear"
    GEAR_CHAIN = "gear_chain"
    RACK = "rack"
    ROTARY_DRIVER = "rotary_driver"
    ATTACHMENT = "attachment"


@dataclass(slots=True)
class GearSpec:
    id: str = field(default_factory=lambda: make_id("gear"))
    name: str = "Gear"
    center: Point3 = (0.0, 0.0, 0.0)
    teeth: int = 24
    module_mm: float = 2.0
    thickness_mm: float = 6.0
    bore_diameter_mm: float = 5.0
    pressure_angle_deg: float = 20.0
    profile: ToothProfile = ToothProfile.INVOLUTE_APPROX
    backlash_mm: float = 0.10
    phase_deg: float = 0.0
    shaft_id: str | None = None
    stage_index: int | None = None
    role: str = "standalone"
    color: str = "#D9A441"

    @property
    def pitch_radius_mm(self) -> float:
        return max(0.001, 0.5 * float(self.module_mm) * max(3, int(self.teeth)))

    @property
    def outer_radius_mm(self) -> float:
        return self.pitch_radius_mm + max(0.05, float(self.module_mm))

    @property
    def root_radius_mm(self) -> float:
        return max(0.1, self.pitch_radius_mm - 1.25 * max(0.05, float(self.module_mm)))

    def normalized(self) -> "GearSpec":
        self.center = point3(self.center)
        self.teeth = max(6, int(self.teeth))
        self.module_mm = max(0.05, float(self.module_mm))
        self.thickness_mm = max(0.1, float(self.thickness_mm))
        self.bore_diameter_mm = max(0.0, min(float(self.bore_diameter_mm), self.root_radius_mm * 1.8))
        self.pressure_angle_deg = max(10.0, min(35.0, float(self.pressure_angle_deg)))
        self.backlash_mm = max(0.0, float(self.backlash_mm))
        if not isinstance(self.profile, ToothProfile):
            self.profile = ToothProfile(str(self.profile))
        return self


@dataclass(slots=True)
class GearStage:
    id: str = field(default_factory=lambda: make_id("stage"))
    index: int = 0
    driver_gear_id: str = ""
    driven_gear_id: str = ""
    driver_shaft_id: str = ""
    driven_shaft_id: str = ""
    target_reduction: float = 1.0
    actual_reduction: float = 1.0
    center_distance_mm: float = 0.0
    axial_layer: int = 0
    connection_kind: str = "chain"
    owner_id: str | None = None


@dataclass(slots=True)
class GearChainSpec:
    id: str = field(default_factory=lambda: make_id("chain"))
    name: str = "Gear chain"
    start: Point3 = (0.0, 0.0, 0.0)
    end: Point3 = (100.0, 0.0, 0.0)
    control_1: Point3 = (33.333, 0.0, 0.0)
    control_2: Point3 = (66.667, 0.0, 0.0)
    intermediate_shaft_count: int = 2
    total_reduction: float = 4.0
    ratio_distribution: float = 0.0
    target_module_mm: float = 2.0
    min_teeth: int = 12
    max_teeth: int = 120
    thickness_mm: float = 6.0
    bore_diameter_mm: float = 5.0
    axial_clearance_mm: float = 1.0
    pressure_angle_deg: float = 20.0
    profile: ToothProfile = ToothProfile.INVOLUTE_APPROX
    backlash_mm: float = 0.10
    shafts: list[Point3] = field(default_factory=list)
    shaft_ids: list[str] = field(default_factory=list)
    gear_ids: list[str] = field(default_factory=list)
    stage_ids: list[str] = field(default_factory=list)
    actual_reduction: float = 1.0
    warning: str = ""

    @property
    def shaft_count(self) -> int:
        return max(2, int(self.intermediate_shaft_count) + 2)

    @property
    def stage_count(self) -> int:
        return self.shaft_count - 1

    def normalized(self) -> "GearChainSpec":
        self.start = point3(self.start)
        self.end = point3(self.end)
        self.control_1 = point3(self.control_1)
        self.control_2 = point3(self.control_2)
        self.intermediate_shaft_count = max(0, min(24, int(self.intermediate_shaft_count)))
        self.total_reduction = max(0.01, min(10_000.0, float(self.total_reduction)))
        self.ratio_distribution = max(-1.0, min(1.0, float(self.ratio_distribution)))
        self.target_module_mm = max(0.05, float(self.target_module_mm))
        self.min_teeth = max(6, int(self.min_teeth))
        self.max_teeth = max(self.min_teeth, int(self.max_teeth))
        self.thickness_mm = max(0.1, float(self.thickness_mm))
        self.bore_diameter_mm = max(0.0, float(self.bore_diameter_mm))
        self.axial_clearance_mm = max(0.0, float(self.axial_clearance_mm))
        self.pressure_angle_deg = max(10.0, min(35.0, float(self.pressure_angle_deg)))
        self.backlash_mm = max(0.0, float(self.backlash_mm))
        if not isinstance(self.profile, ToothProfile):
            self.profile = ToothProfile(str(self.profile))
        return self


@dataclass(slots=True)
class RackSpec:
    """Straight rack constrained to the MEC construction plane.

    ``start`` and ``end`` describe the neutral pitch line. The geometry is
    automatically snapped tangent to ``pinion_gear_id`` so the rack and pinion
    always have a physically meaningful no-slip relationship in Test mode.
    """

    id: str = field(default_factory=lambda: make_id("rack"))
    name: str = "Rack"
    start: Point3 = (0.0, 0.0, 0.0)
    end: Point3 = (100.0, 0.0, 0.0)
    pinion_gear_id: str | None = None
    module_mm: float = 2.0
    thickness_mm: float = 6.0
    body_height_mm: float = 10.0
    backlash_mm: float = 0.10
    pressure_angle_deg: float = 20.0
    profile: ToothProfile = ToothProfile.TRAPEZOID
    contact_sign: int = 1
    phase_mm: float = 0.0
    color: str = "#7CB7D8"

    @property
    def length_mm(self) -> float:
        dx = float(self.end[0]) - float(self.start[0])
        dy = float(self.end[1]) - float(self.start[1])
        dz = float(self.end[2]) - float(self.start[2])
        return max(0.001, (dx * dx + dy * dy + dz * dz) ** 0.5)

    @property
    def tooth_pitch_mm(self) -> float:
        from math import pi

        return pi * max(0.05, float(self.module_mm))

    @property
    def tooth_count(self) -> int:
        return max(1, int(round(self.length_mm / self.tooth_pitch_mm)))

    def normalized(self) -> "RackSpec":
        self.start = point3(self.start)
        self.end = point3(self.end)
        self.module_mm = max(0.05, float(self.module_mm))
        self.thickness_mm = max(0.1, float(self.thickness_mm))
        self.body_height_mm = max(1.5 * self.module_mm, float(self.body_height_mm))
        self.backlash_mm = max(0.0, float(self.backlash_mm))
        self.pressure_angle_deg = max(10.0, min(35.0, float(self.pressure_angle_deg)))
        self.contact_sign = 1 if int(self.contact_sign) >= 0 else -1
        self.phase_mm = float(self.phase_mm)
        if not isinstance(self.profile, ToothProfile):
            self.profile = ToothProfile(str(self.profile))
        return self


@dataclass(slots=True)
class RotaryDriverSpec:
    id: str = field(default_factory=lambda: make_id("driver"))
    name: str = "Rotary driver"
    target_mesh_id: str | None = None
    target_gear_id: str | None = None
    shaft_id: str | None = None
    center: Point3 = (0.0, 0.0, 0.0)
    speed_rpm: float = 10.0
    direction: int = 1

    def normalized(self) -> "RotaryDriverSpec":
        self.center = point3(self.center)
        speed = float(self.speed_rpm)
        direction = 1 if int(self.direction) >= 0 else -1
        if speed < 0.0:
            speed = abs(speed)
            direction *= -1
        self.speed_rpm = speed
        self.direction = direction
        return self


@dataclass(slots=True)
class AttachmentSpec:
    id: str = field(default_factory=lambda: make_id("attachment"))
    name: str = "Driven parts"
    target_mesh_ids: list[str] = field(default_factory=list)
    # Canonical generic source for new mechanism types. The type-specific
    # fields below remain serialized for backward compatibility with v1/v2 MEC.
    source_element_id: str | None = None
    source_gear_id: str | None = None
    source_driver_id: str | None = None
    source_rack_id: str | None = None
    shaft_id: str | None = None
    center: Point3 = (0.0, 0.0, 0.0)
    angle_offset_deg: float = 0.0

    def normalized(self) -> "AttachmentSpec":
        self.target_mesh_ids = [str(value) for value in self.target_mesh_ids if str(value)]
        if not self.source_element_id:
            self.source_element_id = self.source_rack_id or self.source_gear_id or self.source_driver_id
        self.center = point3(self.center)
        self.angle_offset_deg = float(self.angle_offset_deg)
        return self


@dataclass(slots=True)
class MechanicalAssembly:
    id: str = field(default_factory=lambda: make_id("mechanism"))
    name: str = "Mechanical assembly"
    gears: dict[str, GearSpec] = field(default_factory=dict)
    chains: dict[str, GearChainSpec] = field(default_factory=dict)
    racks: dict[str, RackSpec] = field(default_factory=dict)
    stages: dict[str, GearStage] = field(default_factory=dict)
    drivers: dict[str, RotaryDriverSpec] = field(default_factory=dict)
    attachments: dict[str, AttachmentSpec] = field(default_factory=dict)
    work_plane: Any | None = None
    selected_element_id: str | None = None
    schema_version: int = 3
    draft: bool = False

    def primary_driver(self) -> RotaryDriverSpec | None:
        return next(iter(self.drivers.values()), None)

    def enforce_single_driver(self) -> RotaryDriverSpec | None:
        """Keep only the newest driver when loading an older multi-driver MEC."""

        if len(self.drivers) <= 1:
            return self.primary_driver()
        driver = tuple(self.drivers.values())[-1]
        removed_ids = set(self.drivers).difference({driver.id})
        self.drivers = {driver.id: driver}
        for attachment in self.attachments.values():
            if attachment.source_driver_id in removed_ids:
                attachment.source_driver_id = None
            if attachment.source_element_id in removed_ids:
                attachment.source_element_id = None
        return driver

    def all_element_ids(self) -> tuple[str, ...]:
        return tuple((*self.gears.keys(), *self.chains.keys(), *self.racks.keys(), *self.drivers.keys(), *self.attachments.keys()))

    def element_kind(self, element_id: str | None) -> ElementKind | None:
        if element_id in self.gears:
            return ElementKind.GEAR
        if element_id in self.chains:
            return ElementKind.GEAR_CHAIN
        if element_id in self.racks:
            return ElementKind.RACK
        if element_id in self.drivers:
            return ElementKind.ROTARY_DRIVER
        if element_id in self.attachments:
            return ElementKind.ATTACHMENT
        return None

    def selected_element(self) -> Any | None:
        value = self.selected_element_id
        if value in self.gears:
            return self.gears[value]
        if value in self.chains:
            return self.chains[value]
        if value in self.racks:
            return self.racks[value]
        if value in self.drivers:
            return self.drivers[value]
        if value in self.attachments:
            return self.attachments[value]
        return None

    def generated_gear_ids_for_chain(self, chain_id: str) -> tuple[str, ...]:
        chain = self.chains.get(str(chain_id))
        return tuple(chain.gear_ids) if chain is not None else ()

    def remove_element(self, element_id: str) -> bool:
        value = str(element_id)
        if value in self.chains:
            chain = self.chains.pop(value)
            for gear_id in tuple(chain.gear_ids):
                self.gears.pop(gear_id, None)
            for stage_id in tuple(chain.stage_ids):
                self.stages.pop(stage_id, None)
            self._remove_references_to_gears(set(chain.gear_ids))
            for attachment in self.attachments.values():
                if attachment.source_element_id == value:
                    attachment.source_element_id = None
            if self.selected_element_id == value:
                self.selected_element_id = None
            return True
        if value in self.gears:
            self.gears.pop(value, None)
            self._remove_references_to_gears({value})
            if self.selected_element_id == value:
                self.selected_element_id = None
            return True
        if value in self.racks:
            self.racks.pop(value, None)
            for attachment in self.attachments.values():
                if attachment.source_rack_id == value:
                    attachment.source_rack_id = None
                if attachment.source_element_id == value:
                    attachment.source_element_id = None
            if self.selected_element_id == value:
                self.selected_element_id = None
            return True
        if value in self.drivers:
            self.drivers.pop(value, None)
            for attachment in self.attachments.values():
                if attachment.source_driver_id == value:
                    attachment.source_driver_id = None
                if attachment.source_element_id == value:
                    attachment.source_element_id = None
            if self.selected_element_id == value:
                self.selected_element_id = None
            return True
        if value in self.attachments:
            self.attachments.pop(value, None)
            if self.selected_element_id == value:
                self.selected_element_id = None
            return True
        return False

    def _remove_references_to_gears(self, gear_ids: set[str]) -> None:
        removed_stage_ids = {
            stage_id
            for stage_id, stage in self.stages.items()
            if stage.driver_gear_id in gear_ids or stage.driven_gear_id in gear_ids
        }
        for stage_id in removed_stage_ids:
            self.stages.pop(stage_id, None)
        if removed_stage_ids:
            for chain in self.chains.values():
                chain.stage_ids = [stage_id for stage_id in chain.stage_ids if stage_id not in removed_stage_ids]
        for driver in self.drivers.values():
            if driver.target_gear_id in gear_ids:
                driver.target_gear_id = None
                driver.shaft_id = None
        for rack in self.racks.values():
            if rack.pinion_gear_id in gear_ids:
                rack.pinion_gear_id = None
        for attachment in self.attachments.values():
            if attachment.source_gear_id in gear_ids:
                attachment.source_gear_id = None
                attachment.shaft_id = None
            if attachment.source_element_id in gear_ids:
                attachment.source_element_id = None


@dataclass(slots=True)
class MechanicalSessionState:
    assembly: MechanicalAssembly = field(default_factory=MechanicalAssembly)
    mode: MechanicalMode = MechanicalMode.PICK_PLANE
    pending_chain_start: Point3 | None = None
    pending_rack_pinion_gear_id: str | None = None
    pending_rack_start: Point3 | None = None
    pending_driver_mesh_id: str | None = None
    pending_attachment_source_id: str | None = None
    pending_attachment_mesh_ids: tuple[str, ...] = ()
    editing_source_object_ids: tuple[str, ...] = ()
    dirty: bool = False
    applied_since_open: bool = False
    test_angle_deg: float = 0.0
    test_playing: bool = False
    driver_angles_deg: dict[str, float] = field(default_factory=dict)
    driver_candidate_gear_id: str | None = None
    surface_pick_press_screen_pos: tuple[float, float] | None = None
    last_status: str = ""


__all__ = [
    "AttachmentSpec",
    "ElementKind",
    "GearChainSpec",
    "GearSpec",
    "GearStage",
    "MechanicalAssembly",
    "MechanicalMode",
    "MechanicalSessionState",
    "Point3",
    "RackSpec",
    "RotaryDriverSpec",
    "ToothProfile",
    "make_id",
    "point3",
]
