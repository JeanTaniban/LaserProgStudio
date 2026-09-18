# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .kinematics import solve_kinematics
from .models import GearChainSpec, GearSpec, MechanicalMode, RackSpec, RotaryDriverSpec, ToothProfile
from .shafts import normalize_coaxial_shafts
from .session import MechanicalSession


class MechanicalParameterService:
    """Own inspector/domain value mapping without viewport or lifecycle logic."""

    def __init__(self, session: MechanicalSession) -> None:
        self.session = session

    @property
    def assembly(self):
        return self.session.assembly

    def gear_defaults(self, ctx: Any) -> dict[str, Any]:
        return {
            "teeth": int(ctx.inspector.value("gear_teeth", 24)),
            "module_mm": float(ctx.inspector.value("gear_module", 2.0)),
            "thickness_mm": float(ctx.inspector.value("gear_thickness", 6.0)),
            "bore_diameter_mm": float(ctx.inspector.value("gear_bore", 5.0)),
            "profile": ToothProfile(str(ctx.inspector.value("gear_profile", ToothProfile.INVOLUTE_APPROX.value))),
            "pressure_angle_deg": float(ctx.inspector.value("gear_pressure_angle", 20.0)),
            "backlash_mm": float(ctx.inspector.value("gear_backlash", 0.1)),
        }

    def chain_defaults(self, ctx: Any) -> dict[str, Any]:
        gear = self.gear_defaults(ctx)
        return {
            "intermediate_shaft_count": int(ctx.inspector.value("chain_intermediate_shafts", 2)),
            "total_reduction": float(ctx.inspector.value("chain_reduction", 4.0)),
            "ratio_distribution": float(ctx.inspector.value("chain_distribution", 0.0)),
            "target_module_mm": float(ctx.inspector.value("chain_target_module", gear["module_mm"])),
            "min_teeth": int(ctx.inspector.value("chain_min_teeth", 12)),
            "max_teeth": int(ctx.inspector.value("chain_max_teeth", 120)),
            "axial_clearance_mm": 0.0,
            "thickness_mm": gear["thickness_mm"],
            "bore_diameter_mm": gear["bore_diameter_mm"],
            "profile": gear["profile"],
            "pressure_angle_deg": gear["pressure_angle_deg"],
            "backlash_mm": gear["backlash_mm"],
        }

    def rack_defaults(self, ctx: Any) -> dict[str, Any]:
        gear = self.gear_defaults(ctx)
        return {
            "body_height_mm": float(ctx.inspector.value("rack_body_height", max(10.0, 5.0 * gear["module_mm"]))),
            "thickness_mm": float(ctx.inspector.value("rack_thickness", gear["thickness_mm"])),
            "backlash_mm": float(ctx.inspector.value("rack_backlash", gear["backlash_mm"])),
        }

    def driver_defaults(self, ctx: Any) -> dict[str, Any]:
        return {
            "speed_rpm": abs(float(ctx.inspector.value("driver_speed_rpm", 10.0))),
            "direction": -1 if bool(ctx.inspector.value("driver_reverse", False)) else 1,
        }

    def input_gear_id_for_selection(self) -> str | None:
        selected = self.assembly.selected_element_id
        candidate = str(self.session.state.driver_candidate_gear_id or "")
        if candidate in self.assembly.gears:
            if selected == candidate:
                return candidate
            chain = self.assembly.chains.get(str(selected))
            if chain is not None and candidate in chain.gear_ids:
                return candidate
        if selected in self.assembly.gears:
            return selected
        chain = self.assembly.chains.get(str(selected))
        return chain.gear_ids[0] if chain is not None and chain.gear_ids else None

    def output_source_element_id(self) -> str | None:
        selected = self.assembly.selected_element_id
        if selected in self.assembly.gears or selected in self.assembly.racks or selected in self.assembly.drivers or selected in self.assembly.chains:
            return selected
        return None

    def effective_driver_speeds(self) -> dict[str, float]:
        return {
            driver.id: float(driver.speed_rpm) * int(driver.direction)
            for driver in self.assembly.drivers.values()
        }

    def apply_selected_value(self, field_id: str, value: Any) -> tuple[bool, RotaryDriverSpec | None]:
        """Apply one inspector value. Return (changed, changed_driver)."""

        selected = self.assembly.selected_element()
        rebuild_chain = False
        changed_driver: RotaryDriverSpec | None = None
        changed = False
        if isinstance(selected, GearSpec):
            mapping = {
                "gear_teeth": ("teeth", int),
                "gear_module": ("module_mm", float),
                "gear_thickness": ("thickness_mm", float),
                "gear_bore": ("bore_diameter_mm", float),
                "gear_pressure_angle": ("pressure_angle_deg", float),
                "gear_backlash": ("backlash_mm", float),
                "gear_profile": ("profile", ToothProfile),
            }
            target = mapping.get(field_id)
            if target:
                plane = self.session.work_plane
                support = plane.clamp(selected.center) if plane is not None else selected.center
                setattr(selected, target[0], target[1](value))
                selected.normalized()
                if target[0] == "thickness_mm" and plane is not None:
                    selected.center = plane.gear_center(support, selected.thickness_mm, layer=0)
                changed = True
        elif isinstance(selected, GearChainSpec):
            mapping = {
                "chain_intermediate_shafts": ("intermediate_shaft_count", int),
                "chain_reduction": ("total_reduction", float),
                "chain_distribution": ("ratio_distribution", float),
                "chain_target_module": ("target_module_mm", float),
                "chain_min_teeth": ("min_teeth", int),
                "chain_max_teeth": ("max_teeth", int),
                "gear_thickness": ("thickness_mm", float),
                "gear_bore": ("bore_diameter_mm", float),
                "gear_pressure_angle": ("pressure_angle_deg", float),
                "gear_backlash": ("backlash_mm", float),
                "gear_profile": ("profile", ToothProfile),
            }
            target = mapping.get(field_id)
            if target:
                setattr(selected, target[0], target[1](value))
                selected.normalized()
                rebuild_chain = changed = True
        elif isinstance(selected, RackSpec):
            mapping = {
                "rack_body_height": ("body_height_mm", float),
                "rack_thickness": ("thickness_mm", float),
                "rack_backlash": ("backlash_mm", float),
            }
            target = mapping.get(field_id)
            if target:
                setattr(selected, target[0], target[1](value))
                selected.normalized()
                self.session.rebuild_rack(selected.id)
                changed = True
        elif isinstance(selected, RotaryDriverSpec):
            if field_id == "driver_speed_rpm":
                selected.speed_rpm = float(value)
                changed = True
            elif field_id == "driver_reverse":
                selected.direction = -1 if bool(value) else 1
                changed = True
            if changed:
                selected.normalized()
                changed_driver = selected
        if rebuild_chain:
            self.session.rebuild_chain(selected.id)
        elif changed:
            if isinstance(selected, GearSpec):
                normalize_coaxial_shafts(self.assembly, plane=self.session.work_plane)
                self.session.refresh_smart_mesh_for_gear(selected.id)
                self.session.resnap_racks_for_gear(selected.id)
                self.sync_attachment_centres_for_gear(selected)
            self.session.state.dirty = True
        return changed, changed_driver

    def sync_attachment_centres_for_gear(self, gear: GearSpec) -> None:
        for attachment in self.assembly.attachments.values():
            if attachment.source_gear_id == gear.id:
                plane = self.session.work_plane
                attachment.center = plane.clamp(gear.center) if plane is not None else gear.center

    def sync_attachment_centres_for_driver(self, driver: RotaryDriverSpec) -> None:
        for attachment in self.assembly.attachments.values():
            if attachment.source_driver_id == driver.id:
                attachment.center = driver.center

    def visible_mode(self) -> MechanicalMode:
        mode = self.session.state.mode
        if mode is MechanicalMode.PLACE_CHAIN_END:
            return MechanicalMode.PLACE_CHAIN_START
        if mode in {MechanicalMode.PICK_RACK_PINION, MechanicalMode.PLACE_RACK_END}:
            return MechanicalMode.PLACE_RACK_START
        if mode is MechanicalMode.PLACE_DRIVER_CENTER:
            return MechanicalMode.PICK_DRIVER_TARGET
        if mode is MechanicalMode.PICK_ATTACHMENTS:
            return MechanicalMode.PICK_ATTACHMENT_SOURCE
        return mode

    def sync_inspector(self, ctx: Any) -> None:
        selected = self.assembly.selected_element()
        updates: dict[str, Any] = {}
        if isinstance(selected, GearSpec):
            updates.update(
                gear_teeth=selected.teeth,
                gear_module=selected.module_mm,
                gear_thickness=selected.thickness_mm,
                gear_bore=selected.bore_diameter_mm,
                gear_profile=selected.profile.value,
                gear_pressure_angle=selected.pressure_angle_deg,
                gear_backlash=selected.backlash_mm,
            )
        elif isinstance(selected, GearChainSpec):
            updates.update(
                chain_intermediate_shafts=selected.intermediate_shaft_count,
                chain_reduction=selected.total_reduction,
                chain_distribution=selected.ratio_distribution,
                chain_target_module=selected.target_module_mm,
                chain_min_teeth=selected.min_teeth,
                chain_max_teeth=selected.max_teeth,
                gear_thickness=selected.thickness_mm,
                gear_bore=selected.bore_diameter_mm,
                gear_profile=selected.profile.value,
                gear_pressure_angle=selected.pressure_angle_deg,
                gear_backlash=selected.backlash_mm,
            )
        elif isinstance(selected, RackSpec):
            updates.update(
                rack_body_height=selected.body_height_mm,
                rack_thickness=selected.thickness_mm,
                rack_backlash=selected.backlash_mm,
            )
        elif isinstance(selected, RotaryDriverSpec):
            updates.update(driver_speed_rpm=selected.speed_rpm, driver_reverse=selected.direction < 0)
        updates.update(
            mechanical_mode=self.visible_mode().value,
            test_angle_deg=self.session.state.test_angle_deg,
            test_playing=self.session.state.test_playing,
        )
        for field_id, field_value in updates.items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        chain = selected if isinstance(selected, GearChainSpec) else None
        try:
            ctx.inspector.set_display_value("chain_actual_ratio", f"{chain.actual_reduction:.6g}:1" if chain else "No chain selected.")
            ctx.inspector.set_display_value("chain_warning", (chain.warning or "No warning.") if chain else "No warning.")
            rack = selected if isinstance(selected, RackSpec) else None
            if rack is not None:
                pinion = self.assembly.gears.get(str(rack.pinion_gear_id or ""))
                ctx.inspector.set_display_value("rack_pinion", getattr(pinion, "name", None) or "Disconnected")
                driver_angles = self.session.state.driver_angles_deg
                state = solve_kinematics(self.assembly, driver_angles if self.assembly.drivers else self.session.state.test_angle_deg)
                travel = float(state.rack_displacements_mm.get(rack.id, 0.0))
                per_rev = 2.0 * 3.141592653589793 * float(pinion.pitch_radius_mm) if pinion is not None else 0.0
                ctx.inspector.set_display_value("rack_travel", f"{travel:.6g} mm now · {per_rev:.6g} mm/rev")
            else:
                ctx.inspector.set_display_value("rack_pinion", "No rack selected.")
                ctx.inspector.set_display_value("rack_travel", "No rack selected.")
            plane = self.session.work_plane
            ctx.inspector.set_display_value(
                "mechanical_work_plane",
                (f"Construction · normal ({plane.normal[0]:.3g}, {plane.normal[1]:.3g}, {plane.normal[2]:.3g})" if plane is not None else "Not selected."),
            )
        except Exception:
            pass


__all__ = ["MechanicalParameterService"]
