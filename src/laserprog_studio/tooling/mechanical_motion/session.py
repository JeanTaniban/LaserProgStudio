# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass
from math import inf
from typing import Any, Iterable

from laserprog_studio.domain.work_model import WorkMesh

from .compound_geometry import build_compound_shaft_mesh
from .curve import default_controls
from .gear_solver import replace_chain_solution
from .geometry import build_draft_placeholder, gear_bounds
from .rack_geometry import build_rack_mesh, rack_bounds, snap_rack_to_pinion
from .kinematics import apply_attachment_motion, rotated_mesh, solve_kinematics, translated_mesh
from .plane import MechanicalWorkPlane
from .models import (
    AttachmentSpec,
    GearChainSpec,
    GearSpec,
    MechanicalAssembly,
    MechanicalMode,
    MechanicalSessionState,
    Point3,
    RackSpec,
    RotaryDriverSpec,
    point3,
)
from .shafts import normalize_coaxial_shafts
from .smart_snap import (
    GearSnapCandidate,
    connect_smart_mesh,
    detach_smart_mesh_stages,
    find_gear_snap_candidate,
    is_unique_standalone_gear,
    smart_mesh_stages_for_gear,
)
from .serialization import (
    assembly_from_mesh,
    attach_source,
    detach_source,
    is_generated_mechanical_mesh,
    mesh_belongs_to_assembly,
)


@dataclass(frozen=True, slots=True)
class SessionPreview:
    meshes: tuple[Any, ...]
    generated_count: int
    moved_attachment_count: int


class MechanicalSession:
    """Domain/session coordinator independent from Qt and viewport rendering."""

    def __init__(self, state: MechanicalSessionState | None = None) -> None:
        self.state = state or MechanicalSessionState()
        self._base_meshes: list[Any] = []
        self._source_path: Any | None = None
        self._editing_mesh_ids: set[str] = set()
        self._shaft_mesh_cache: dict[str, tuple[tuple[Any, ...], WorkMesh]] = {}
        self._shaft_mesh_id_by_shaft_id: dict[str, str] = {}
        self._rack_mesh_cache: dict[str, tuple[tuple[Any, ...], WorkMesh]] = {}
        self._rack_mesh_id_by_rack_id: dict[str, str] = {}

    @property
    def assembly(self) -> MechanicalAssembly:
        return self.state.assembly

    def begin(
        self,
        meshes: Iterable[Any],
        source_path: Any | None = None,
        *,
        selected_meshes: Iterable[Any] = (),
        initial_work_plane: MechanicalWorkPlane | None = None,
    ) -> None:
        self._base_meshes = copy.deepcopy(list(meshes))
        self._source_path = source_path
        loaded = None
        selected_ids: list[str] = []
        for mesh in selected_meshes:
            candidate = assembly_from_mesh(mesh)
            if candidate is not None:
                loaded = candidate
                selected_ids.append(str(getattr(mesh, "mesh_id", "") or ""))
                break
        if loaded is not None:
            self.state.assembly = loaded
            self.state.assembly.enforce_single_driver()
            normalize_coaxial_shafts(self.state.assembly)
            self.state.editing_source_object_ids = tuple(
                str(getattr(mesh, "mesh_id", "") or "")
                for mesh in self._base_meshes
                if mesh_belongs_to_assembly(mesh, loaded.id) and is_generated_mechanical_mesh(mesh)
            )
            self._editing_mesh_ids = set(self.state.editing_source_object_ids)
        else:
            self.state.assembly = MechanicalAssembly(
                work_plane=copy.deepcopy(initial_work_plane) if isinstance(initial_work_plane, MechanicalWorkPlane) else None
            )
            self.state.editing_source_object_ids = ()
            self._editing_mesh_ids.clear()
        self.state.dirty = False
        self.state.applied_since_open = False
        self.state.test_angle_deg = 0.0
        self.state.test_playing = False
        self.state.driver_angles_deg = {driver_id: 0.0 for driver_id in self.state.assembly.drivers}
        self.state.pending_rack_pinion_gear_id = None
        self.state.pending_rack_start = None
        self.state.pending_attachment_source_id = None
        self.state.pending_attachment_mesh_ids = ()
        current_driver = self.state.assembly.primary_driver()
        self.state.driver_candidate_gear_id = current_driver.target_gear_id if current_driver is not None else None
        if self.state.assembly.work_plane is None and self.state.assembly.gears:
            first = next(iter(self.state.assembly.gears.values()))
            support = (first.center[0], first.center[1], first.center[2] - 0.5 * first.thickness_mm)
            self.state.assembly.work_plane = MechanicalWorkPlane.horizontal_at(support)
        if loaded is not None and self.work_plane is not None and self.state.assembly.chains:
            # Re-solve saved chains once on opening.  This transparently migrates
            # the old two-layer layout (which could mesh twice between adjacent
            # compound shafts) to the collision-free three-layer schedule while
            # preserving stable gear, shaft and stage identifiers.
            selected_before_migration = self.state.assembly.selected_element_id
            for saved_chain in tuple(self.state.assembly.chains.values()):
                replace_chain_solution(self.state.assembly, saved_chain)
            if selected_before_migration in self.state.assembly.all_element_ids():
                self.state.assembly.selected_element_id = selected_before_migration
        normalize_coaxial_shafts(self.state.assembly, plane=self.work_plane)
        self.state.mode = MechanicalMode.SELECT if self.state.assembly.work_plane is not None else MechanicalMode.PICK_PLANE
        self._shaft_mesh_cache.clear()
        self._rack_mesh_cache.clear()
        self._index_existing_generated_meshes()

    def _index_existing_generated_meshes(self) -> None:
        self._shaft_mesh_id_by_shaft_id.clear()
        self._rack_mesh_id_by_rack_id.clear()
        for mesh in self._base_meshes:
            metadata = getattr(mesh, "metadata", None)
            if not isinstance(metadata, dict):
                continue
            mesh_id = str(getattr(mesh, "mesh_id", "") or "")
            shaft_id = str(metadata.get("mechanical_shaft_id") or "")
            if shaft_id and mesh_id:
                self._shaft_mesh_id_by_shaft_id[shaft_id] = mesh_id
            rack_id = str(metadata.get("mechanical_rack_id") or "")
            if rack_id and mesh_id:
                self._rack_mesh_id_by_rack_id[rack_id] = mesh_id

    @property
    def work_plane(self) -> MechanicalWorkPlane | None:
        value = self.assembly.work_plane
        return value if isinstance(value, MechanicalWorkPlane) else None

    def set_work_plane(self, plane: MechanicalWorkPlane) -> MechanicalWorkPlane:
        self.assembly.work_plane = plane.normalized()
        self.state.mode = MechanicalMode.SELECT
        self.state.pending_chain_start = None
        self.state.dirty = True
        self._shaft_mesh_cache.clear()
        self._rack_mesh_cache.clear()
        return self.assembly.work_plane

    def require_work_plane(self) -> MechanicalWorkPlane:
        plane = self.work_plane
        if plane is None:
            raise RuntimeError("Select a mechanical construction plane first.")
        return plane

    def add_gear(self, center: Point3, **overrides: Any) -> GearSpec:
        plane = self.require_work_plane()
        values = {key: value for key, value in overrides.items() if key in GearSpec.__dataclass_fields__}
        thickness = max(0.1, float(values.get("thickness_mm", 6.0)))
        gear = GearSpec(center=plane.gear_center(point3(center), thickness), **values).normalized()
        gear.shaft_id = gear.shaft_id or gear.id
        self.assembly.gears[gear.id] = gear
        normalize_coaxial_shafts(self.assembly, plane=plane)
        self.assembly.selected_element_id = gear.id
        self.state.dirty = True
        return gear

    def is_unique_standalone_gear(self, gear_id: str) -> bool:
        return is_unique_standalone_gear(self.assembly, str(gear_id))

    def gear_snap_candidate(self, gear_id: str, raw_support: Point3) -> GearSnapCandidate | None:
        return find_gear_snap_candidate(
            self.assembly,
            str(gear_id),
            self.require_work_plane().clamp(point3(raw_support)),
            self.require_work_plane(),
        )

    def _gear_center_on_current_layer(self, gear: GearSpec, support: Point3) -> Point3:
        plane = self.require_work_plane()
        current_support = plane.clamp(gear.center)
        offset = sum(
            (float(gear.center[index]) - float(current_support[index])) * float(plane.normal[index])
            for index in range(3)
        )
        return plane.offset(plane.clamp(point3(support)), offset)

    def preview_move_unique_gear(
        self,
        gear_id: str,
        raw_support: Point3,
        *,
        unsnapped_phase_deg: float,
    ) -> GearSnapCandidate | None:
        gear = self.assembly.gears[str(gear_id)]
        candidate = self.gear_snap_candidate(gear.id, raw_support)
        if candidate is None:
            gear.center = self._gear_center_on_current_layer(gear, raw_support)
            gear.phase_deg = float(unsnapped_phase_deg) % 360.0
        else:
            gear.center = candidate.center
            gear.phase_deg = candidate.phase_deg
        self.assembly.selected_element_id = gear.id
        self.state.dirty = True
        return candidate

    def commit_unique_gear_drag(
        self,
        gear_id: str,
        candidate: GearSnapCandidate | None,
    ) -> None:
        gear = self.assembly.gears[str(gear_id)]
        detach_smart_mesh_stages(self.assembly, gear.id)
        if candidate is not None and candidate.target_gear_id in self.assembly.gears:
            gear.center = candidate.center
            gear.phase_deg = candidate.phase_deg
            connect_smart_mesh(
                self.assembly,
                target_gear_id=candidate.target_gear_id,
                dragged_gear_id=gear.id,
            )
        normalize_coaxial_shafts(self.assembly, plane=self.require_work_plane())
        for driver in self.assembly.drivers.values():
            if driver.target_gear_id == gear.id:
                driver.center = self.require_work_plane().clamp(gear.center)
                driver.shaft_id = gear.shaft_id or gear.id
        for attachment in self.assembly.attachments.values():
            if attachment.source_gear_id == gear.id or attachment.source_element_id == gear.id:
                attachment.center = self.require_work_plane().clamp(gear.center)
                attachment.shaft_id = gear.shaft_id or gear.id
        self.resnap_racks_for_gear(gear.id)
        self._shaft_mesh_cache.clear()
        self.state.dirty = True

    def refresh_smart_mesh_for_gear(self, gear_id: str) -> bool:
        stages = smart_mesh_stages_for_gear(self.assembly, str(gear_id))
        if not stages:
            return False
        plane = self.require_work_plane()
        changed = False
        for stage in stages:
            dragged_id = str(stage.owner_id or stage.driven_gear_id)
            dragged = self.assembly.gears.get(dragged_id)
            target = self.assembly.gears.get(str(stage.driver_gear_id))
            if dragged is None or target is None:
                detach_smart_mesh_stages(self.assembly, dragged_id)
                changed = True
                continue
            candidate = find_gear_snap_candidate(
                self.assembly,
                dragged.id,
                plane.clamp(dragged.center),
                plane,
                capture_scale=1000.0,
                target_ids=(target.id,),
            )
            if candidate is None:
                detach_smart_mesh_stages(self.assembly, dragged.id)
                changed = True
                continue
            dragged.center = candidate.center
            dragged.phase_deg = candidate.phase_deg
            stage.driver_shaft_id = str(target.shaft_id or target.id)
            stage.driven_shaft_id = str(dragged.shaft_id or dragged.id)
            stage.target_reduction = float(dragged.teeth) / max(1.0, float(target.teeth))
            stage.actual_reduction = stage.target_reduction
            stage.center_distance_mm = candidate.center_distance_mm
            changed = True
        if changed:
            self._shaft_mesh_cache.clear()
            self.state.dirty = True
        return changed

    def add_chain(self, start: Point3, end: Point3, **overrides: Any) -> GearChainSpec:
        plane = self.require_work_plane()
        start_on_plane = plane.clamp(point3(start))
        end_on_plane = plane.clamp(point3(end))
        control_1, control_2 = default_controls(start_on_plane, end_on_plane, bulge=0.12)
        values = {
            "start": start_on_plane,
            "end": end_on_plane,
            "control_1": control_1,
            "control_2": control_2,
            **{key: value for key, value in overrides.items() if key in GearChainSpec.__dataclass_fields__},
        }
        chain = GearChainSpec(**values).normalized()
        replace_chain_solution(self.assembly, chain)
        normalize_coaxial_shafts(self.assembly, plane=plane)
        self.assembly.selected_element_id = chain.id
        self.state.dirty = True
        return chain

    def rebuild_chain(self, chain_id: str) -> GearChainSpec | None:
        chain = self.assembly.chains.get(str(chain_id))
        if chain is None:
            return None
        replace_chain_solution(self.assembly, chain)
        normalize_coaxial_shafts(self.assembly, plane=self.work_plane)
        for rack in self.assembly.racks.values():
            if rack.pinion_gear_id in self.assembly.gears:
                snap_rack_to_pinion(rack, self.assembly.gears[rack.pinion_gear_id], self.require_work_plane())
                self._rack_mesh_cache.pop(rack.id, None)
        self._shaft_mesh_cache.clear()
        self.state.dirty = True
        return chain

    def add_rack(self, start: Point3, end: Point3, *, pinion_gear_id: str, **overrides: Any) -> RackSpec:
        plane = self.require_work_plane()
        pinion = self.assembly.gears[str(pinion_gear_id)]
        values = {key: value for key, value in overrides.items() if key in RackSpec.__dataclass_fields__}
        values.setdefault("module_mm", pinion.module_mm)
        values.setdefault("thickness_mm", pinion.thickness_mm)
        values.setdefault("pressure_angle_deg", pinion.pressure_angle_deg)
        values.setdefault("backlash_mm", pinion.backlash_mm)
        rack = RackSpec(
            start=plane.clamp(point3(start)),
            end=plane.clamp(point3(end)),
            pinion_gear_id=pinion.id,
            **values,
        ).normalized()
        snap_rack_to_pinion(rack, pinion, plane)
        self.assembly.racks[rack.id] = rack
        self.assembly.selected_element_id = rack.id
        self.state.dirty = True
        return rack

    def rebuild_rack(self, rack_id: str) -> RackSpec | None:
        rack = self.assembly.racks.get(str(rack_id))
        if rack is None:
            return None
        pinion = self.assembly.gears.get(str(rack.pinion_gear_id or ""))
        if pinion is not None:
            snap_rack_to_pinion(rack, pinion, self.require_work_plane())
        self._rack_mesh_cache.pop(rack.id, None)
        self.state.dirty = True
        return rack

    def resnap_racks_for_gear(self, gear_id: str) -> None:
        for rack in self.assembly.racks.values():
            if rack.pinion_gear_id == str(gear_id):
                self.rebuild_rack(rack.id)

    def _replace_driver(self, driver: RotaryDriverSpec) -> RotaryDriverSpec:
        previous = tuple(self.assembly.drivers.values())
        previous_ids = {item.id for item in previous}
        previous_by_id = {item.id: item for item in previous}
        self.assembly.drivers.clear()
        self.assembly.drivers[driver.id] = driver
        for attachment in self.assembly.attachments.values():
            old_id = str(attachment.source_driver_id or "")
            if old_id not in previous_ids:
                continue
            old = previous_by_id.get(old_id)
            if old is not None and str(old.shaft_id or "") == str(driver.shaft_id or ""):
                attachment.source_driver_id = driver.id
                attachment.center = driver.center
            else:
                attachment.source_driver_id = None
        self.state.driver_angles_deg = {driver.id: 0.0}
        self.state.driver_candidate_gear_id = driver.target_gear_id
        self.assembly.selected_element_id = driver.id
        self.state.dirty = True
        return driver

    def add_driver_for_gear(self, gear_id: str, *, speed_rpm: float = 10.0, direction: int = 1) -> RotaryDriverSpec:
        gear = self.assembly.gears[str(gear_id)]
        driver = RotaryDriverSpec(
            target_gear_id=gear.id,
            shaft_id=gear.shaft_id or gear.id,
            center=self.require_work_plane().clamp(gear.center),
            speed_rpm=speed_rpm,
            direction=direction,
        ).normalized()
        return self._replace_driver(driver)

    def add_driver_for_mesh(self, mesh_id: str, center: Point3, *, speed_rpm: float = 10.0, direction: int = 1) -> RotaryDriverSpec:
        plane = self.require_work_plane()
        driver = RotaryDriverSpec(
            target_mesh_id=str(mesh_id),
            shaft_id=f"mesh:{mesh_id}",
            center=plane.clamp(point3(center)),
            speed_rpm=speed_rpm,
            direction=direction,
        ).normalized()
        return self._replace_driver(driver)

    def attach_meshes(self, mesh_ids: Iterable[str], *, source_element_id: str) -> AttachmentSpec:
        source_id = str(source_element_id)
        gear = self.assembly.gears.get(source_id)
        rack = self.assembly.racks.get(source_id)
        driver = self.assembly.drivers.get(source_id)
        if gear is None and rack is None and driver is None:
            raise KeyError(f"Unknown gear/rack/driver: {source_id}")
        if gear is not None:
            center = self.require_work_plane().clamp(gear.center)
            shaft = gear.shaft_id or gear.id
        elif rack is not None:
            center = tuple((rack.start[index] + rack.end[index]) * 0.5 for index in range(3))
            shaft = None
        else:
            center = driver.center
            shaft = driver.shaft_id or driver.id
        attachment = AttachmentSpec(
            target_mesh_ids=[str(value) for value in mesh_ids if str(value)],
            source_element_id=source_id,
            source_gear_id=gear.id if gear is not None else None,
            source_driver_id=driver.id if driver is not None else None,
            source_rack_id=rack.id if rack is not None else None,
            shaft_id=shaft,
            center=center,
        ).normalized()
        self.assembly.attachments[attachment.id] = attachment
        self.assembly.selected_element_id = attachment.id
        self.state.dirty = True
        return attachment

    def remove_selected(self) -> bool:
        selected = self.assembly.selected_element_id
        if not selected:
            return False
        was_driver = selected in self.assembly.drivers
        changed = self.assembly.remove_element(selected)
        if was_driver:
            self.state.driver_angles_deg.pop(str(selected), None)
            self.state.driver_candidate_gear_id = None
        self.state.dirty = self.state.dirty or changed
        return changed

    def select_nearest_marker(self, world_pos: Point3, *, tolerance_mm: float = inf) -> str | None:
        point = point3(world_pos)
        chain_owner_by_gear = {
            gear_id: chain.id
            for chain in self.assembly.chains.values()
            for gear_id in chain.gear_ids
        }
        candidates: list[tuple[float, str, str | None]] = []
        for gear in self.assembly.gears.values():
            distance = ((gear.center[0] - point[0]) ** 2 + (gear.center[1] - point[1]) ** 2 + (gear.center[2] - point[2]) ** 2) ** 0.5
            candidates.append((distance, chain_owner_by_gear.get(gear.id, gear.id), gear.id))
        for chain in self.assembly.chains.values():
            for marker in (chain.start, chain.end, chain.control_1, chain.control_2):
                distance = sum((marker[i] - point[i]) ** 2 for i in range(3)) ** 0.5
                candidates.append((distance, chain.id, None))
        for rack in self.assembly.racks.values():
            midpoint = tuple((rack.start[index] + rack.end[index]) * 0.5 for index in range(3))
            for marker in (rack.start, rack.end, midpoint):
                distance = sum((marker[i] - point[i]) ** 2 for i in range(3)) ** 0.5
                candidates.append((distance, rack.id, rack.pinion_gear_id))
        if not candidates:
            return None
        distance, element_id, gear_id = min(candidates, key=lambda value: value[0])
        if distance > float(tolerance_mm):
            return None
        self.assembly.selected_element_id = element_id
        self.state.driver_candidate_gear_id = gear_id
        return element_id

    def chain_owner_for_gear(self, gear_id: str | None) -> str | None:
        value = str(gear_id or "")
        if not value:
            return None
        for chain in self.assembly.chains.values():
            if value in chain.gear_ids:
                return chain.id
        return value if value in self.assembly.gears else None

    def gear_id_from_mesh(self, mesh: Any) -> str | None:
        """Resolve the logical gear represented by a clicked generated mesh.

        Standalone gears carry one exact id. Compound shaft meshes carry several
        coaxial ids; because every id belongs to the same shaft, a deterministic
        representative is sufficient for driver propagation and avoids the old
        scene-index/overlay-index mismatch.
        """

        metadata = getattr(mesh, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        exact = str(metadata.get("mechanical_gear_id") or "")
        if exact in self.assembly.gears:
            return exact
        values = tuple(str(value) for value in (metadata.get("mechanical_gear_ids") or ()) if str(value))
        preferred = str(self.state.driver_candidate_gear_id or "")
        if preferred in values and preferred in self.assembly.gears:
            return preferred
        for value in values:
            if value in self.assembly.gears:
                return value
        shaft_id = str(metadata.get("mechanical_shaft_id") or "")
        if shaft_id:
            for gear in self.assembly.gears.values():
                if str(gear.shaft_id or gear.id) == shaft_id:
                    return gear.id
        return None

    def element_id_from_mesh(self, mesh: Any) -> str | None:
        gear_id = self.gear_id_from_mesh(mesh)
        if gear_id:
            return self.chain_owner_for_gear(gear_id)
        metadata = getattr(mesh, "metadata", None)
        if isinstance(metadata, dict):
            rack_id = str(metadata.get("mechanical_rack_id") or "")
            if rack_id in self.assembly.racks:
                return rack_id
        mesh_id = str(getattr(mesh, "mesh_id", "") or "")
        for driver in self.assembly.drivers.values():
            if mesh_id and str(driver.target_mesh_id or "") == mesh_id:
                return driver.id
        for attachment in self.assembly.attachments.values():
            if mesh_id and mesh_id in attachment.target_mesh_ids:
                return attachment.id
        return None

    def attachment_source_from_mesh(self, mesh: Any) -> str | None:
        element_id = self.element_id_from_mesh(mesh)
        if element_id in self.assembly.gears or element_id in self.assembly.racks or element_id in self.assembly.drivers or element_id in self.assembly.chains:
            return element_id
        return None

    def select_from_mesh(self, mesh: Any) -> str | None:
        element_id = self.element_id_from_mesh(mesh)
        if not element_id:
            return None
        self.assembly.selected_element_id = element_id
        gear_id = self.gear_id_from_mesh(mesh)
        self.state.driver_candidate_gear_id = gear_id if gear_id in self.assembly.gears else None
        return element_id

    def shaft_centers(self) -> dict[str, Point3]:
        centers: dict[str, Point3] = {}
        plane = self.work_plane
        for gear in self.assembly.gears.values():
            shaft_id = str(gear.shaft_id or gear.id)
            center = plane.clamp(gear.center) if plane is not None else gear.center
            centers.setdefault(shaft_id, center)
        for driver in self.assembly.drivers.values():
            shaft_id = str(driver.shaft_id or driver.id)
            centers.setdefault(shaft_id, driver.center)
        return centers

    def rack_id_from_mesh(self, mesh: Any) -> str | None:
        metadata = getattr(mesh, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        rack_id = str(metadata.get("mechanical_rack_id") or "")
        return rack_id if rack_id in self.assembly.racks else None

    def base_without_current_assembly(self) -> list[Any]:
        assembly_id = self.assembly.id
        result: list[Any] = []
        for mesh in self._base_meshes:
            mesh_id = str(getattr(mesh, "mesh_id", "") or "")
            belongs = mesh_belongs_to_assembly(mesh, assembly_id)
            if mesh_id in self._editing_mesh_ids or (belongs and is_generated_mechanical_mesh(mesh)):
                continue
            clone = copy.deepcopy(mesh)
            if belongs:
                detach_source(clone)
            result.append(clone)
        return result

    @staticmethod
    def _gear_signature(gear: GearSpec) -> tuple[Any, ...]:
        return (
            gear.center,
            int(gear.teeth),
            float(gear.module_mm),
            float(gear.thickness_mm),
            float(gear.bore_diameter_mm),
            float(gear.pressure_angle_deg),
            str(gear.profile.value),
            float(gear.backlash_mm),
            float(gear.phase_deg),
            str(gear.color),
        )

    def _shaft_signature(self, gears: tuple[GearSpec, ...]) -> tuple[Any, ...]:
        plane = self.require_work_plane()
        return (
            tuple(self._gear_signature(gear) for gear in gears),
            plane.normal,
            plane.u_axis,
            plane.v_axis,
            float(plane.depth),
        )

    def _baseline_shaft_mesh(self, shaft_id: str, gears: tuple[GearSpec, ...]) -> WorkMesh:
        signature = self._shaft_signature(gears)
        cached = self._shaft_mesh_cache.get(shaft_id)
        if cached is None or cached[0] != signature:
            mesh = build_compound_shaft_mesh(gears, plane=self.require_work_plane(), name=f"Mechanical shaft {shaft_id}")
            existing_id = self._shaft_mesh_id_by_shaft_id.get(shaft_id)
            if existing_id:
                mesh.mesh_id = existing_id
            self._shaft_mesh_cache[shaft_id] = (signature, mesh)
            cached = self._shaft_mesh_cache[shaft_id]
        return cached[1]

    @staticmethod
    def _rack_signature(rack: RackSpec, plane: MechanicalWorkPlane) -> tuple[Any, ...]:
        return (
            rack.start, rack.end, rack.pinion_gear_id, float(rack.module_mm),
            float(rack.thickness_mm), float(rack.body_height_mm),
            float(rack.backlash_mm), float(rack.pressure_angle_deg),
            str(rack.profile.value), int(rack.contact_sign), float(rack.phase_mm),
            str(rack.color), plane.normal, plane.u_axis, plane.v_axis, float(plane.depth),
        )

    def _baseline_rack_mesh(self, rack: RackSpec) -> WorkMesh:
        plane = self.require_work_plane()
        signature = self._rack_signature(rack, plane)
        cached = self._rack_mesh_cache.get(rack.id)
        if cached is None or cached[0] != signature:
            mesh = build_rack_mesh(rack, plane=plane, name=rack.name)
            existing_id = self._rack_mesh_id_by_rack_id.get(rack.id)
            if existing_id:
                mesh.mesh_id = existing_id
            self._rack_mesh_cache[rack.id] = (signature, mesh)
            cached = self._rack_mesh_cache[rack.id]
        return cached[1]

    @staticmethod
    def _merge_bounds(*values: tuple[float, float, float, float, float, float] | None):
        present = [value for value in values if value is not None]
        if not present:
            return None
        return (
            min(value[0] for value in present), min(value[1] for value in present), min(value[2] for value in present),
            max(value[3] for value in present), max(value[4] for value in present), max(value[5] for value in present),
        )

    def build_preview(
        self,
        *,
        test_angle_deg: float | None = None,
        draft: bool = False,
        use_test_state: bool = True,
    ) -> SessionPreview:
        normalize_coaxial_shafts(self.assembly, plane=self.work_plane)
        base = self.base_without_current_assembly()
        angle = self.state.test_angle_deg if test_angle_deg is None else float(test_angle_deg)
        if not use_test_state:
            driver_angles = {driver_id: 0.0 for driver_id in self.assembly.drivers}
        elif test_angle_deg is not None:
            driver_angles = {driver_id: angle for driver_id in self.assembly.drivers}
        else:
            driver_angles = self.state.driver_angles_deg
        input_angles: Any = driver_angles if self.assembly.drivers else (angle if use_test_state else 0.0)
        kinematic = solve_kinematics(self.assembly, input_angles)
        moved_attachment_ids: set[str] = set()
        has_motion = (
            use_test_state
            and (angle != 0.0 or self.state.test_playing or any(abs(value) > 1.0e-12 for value in driver_angles.values()))
        )
        if has_motion:
            moved_attachment_ids.update(
                str(driver.target_mesh_id)
                for driver in self.assembly.drivers.values()
                if driver.target_mesh_id
            )
            for attachment in self.assembly.attachments.values():
                moved_attachment_ids.update(attachment.target_mesh_ids)
            base = apply_attachment_motion(base, self.assembly, kinematic)
        generated: list[WorkMesh] = []
        if draft:
            plane_for_bounds = self.work_plane or MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
            bounds = self._merge_bounds(
                gear_bounds(self.assembly.gears.values()),
                rack_bounds(self.assembly.racks.values(), plane_for_bounds),
            )
            if bounds is None and self.assembly.drivers:
                centres = tuple(driver.center for driver in self.assembly.drivers.values())
                bounds = (
                    min(point[0] for point in centres) - 5.0,
                    min(point[1] for point in centres) - 5.0,
                    min(point[2] for point in centres) - 1.0,
                    max(point[0] for point in centres) + 5.0,
                    max(point[1] for point in centres) + 5.0,
                    max(point[2] for point in centres) + 1.0,
                )
            if bounds is not None:
                placeholder = build_draft_placeholder(bounds)
                if self.state.editing_source_object_ids:
                    placeholder.mesh_id = self.state.editing_source_object_ids[0]
                attach_source(placeholder, self.assembly, draft=True)
                generated.append(placeholder)
        else:
            by_shaft: dict[str, list[GearSpec]] = {}
            for gear in self.assembly.gears.values():
                shaft_id = str(gear.shaft_id or gear.id)
                by_shaft.setdefault(shaft_id, []).append(gear)
            plane = self.work_plane or MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
            for shaft_id, shaft_gears in by_shaft.items():
                gears = tuple(shaft_gears)
                baseline = self._baseline_shaft_mesh(shaft_id, gears)
                reference = gears[0]
                absolute_angle = kinematic.shaft_angles_deg.get(shaft_id, 0.0)
                mesh = rotated_mesh(baseline, plane.clamp(reference.center), absolute_angle, axis=plane.normal) if abs(absolute_angle) > 1.0e-12 else copy.deepcopy(baseline)
                attach_source(mesh, self.assembly, draft=False)
                generated.append(mesh)
            for rack in self.assembly.racks.values():
                baseline = self._baseline_rack_mesh(rack)
                displacement = float(kinematic.rack_displacements_mm.get(rack.id, 0.0))
                if abs(displacement) > 1.0e-12:
                    from .rack_geometry import rack_axis
                    axis = rack_axis(rack)
                    mesh = translated_mesh(baseline, (axis[0] * displacement, axis[1] * displacement, axis[2] * displacement))
                else:
                    mesh = copy.deepcopy(baseline)
                attach_source(mesh, self.assembly, draft=False)
                generated.append(mesh)
            if not generated and self.assembly.drivers:
                carrier_ids = {
                    str(driver.target_mesh_id)
                    for driver in self.assembly.drivers.values()
                    if driver.target_mesh_id
                }
                for mesh in base:
                    if str(getattr(mesh, "mesh_id", "") or "") in carrier_ids:
                        attach_source(mesh, self.assembly, draft=False)
                        break
        return SessionPreview(tuple((*base, *generated)), len(generated), len(moved_attachment_ids))

    def mesh_by_id(self, mesh_id: str) -> Any | None:
        target = str(mesh_id)
        for mesh in self._base_meshes:
            if str(getattr(mesh, "mesh_id", "") or "") == target:
                return mesh
        return None

    @staticmethod
    def mesh_center(mesh: Any) -> Point3 | None:
        vertices = tuple(getattr(mesh, "vertices", ()) or ())
        if not vertices:
            return None
        xs = [float(point[0]) for point in vertices]
        ys = [float(point[1]) for point in vertices]
        zs = [float(point[2]) for point in vertices]
        return (
            0.5 * (min(xs) + max(xs)),
            0.5 * (min(ys) + max(ys)),
            0.5 * (min(zs) + max(zs)),
        )

    def is_current_assembly_committed(self, meshes: Iterable[Any]) -> bool:
        """Return True when the document already contains this exact applied state.

        Studio's generic preview Apply path commits the preview before calling
        ``on_close``.  This equality check distinguishes that path from Cancel,
        preventing ``on_close`` from replacing a successful Apply with a red
        recoverable draft.
        """

        from .serialization import assembly_persistence_signature

        expected = assembly_persistence_signature(self.assembly)
        for mesh in meshes:
            loaded = assembly_from_mesh(mesh)
            if loaded is None or loaded.id != self.assembly.id or loaded.draft:
                continue
            if assembly_persistence_signature(loaded) == expected:
                return True
        return False

    def mark_applied(self) -> None:
        self.state.applied_since_open = True
        self.state.dirty = False
        self.assembly.draft = False
        self._base_meshes = list(self.build_preview(test_angle_deg=0.0, draft=False, use_test_state=False).meshes)
        self._editing_mesh_ids = {
            str(getattr(mesh, "mesh_id", "") or "")
            for mesh in self._base_meshes
            if mesh_belongs_to_assembly(mesh, self.assembly.id) and is_generated_mechanical_mesh(mesh)
        }
        self._index_existing_generated_meshes()

    def draft_meshes(self) -> tuple[Any, ...]:
        self.assembly.draft = True
        return self.build_preview(test_angle_deg=0.0, draft=True, use_test_state=False).meshes

    def applied_meshes(self) -> tuple[Any, ...]:
        self.assembly.draft = False
        return self.build_preview(test_angle_deg=0.0, draft=False, use_test_state=False).meshes


__all__ = ["MechanicalSession", "SessionPreview"]
