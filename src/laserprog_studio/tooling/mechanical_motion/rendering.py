# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import projected_drawing as draw2d

from .curve import sample_bezier
from .drag_preview import MechanicalGearDragPreview
from .geometry import gear_drag_outline_points
from .kinematics import solve_kinematics
from .live_motion import MechanicalLiveMotionPreview
from .models import MechanicalMode
from .rack_geometry import rack_axis
from .session import MechanicalSession
from .smart_snap import GearSnapCandidate, is_smart_mesh_stage


class MechanicalRenderer:
    """Viewport-only renderer for mechanical markers and scene previews."""

    def __init__(self, owner_tool: str, session: MechanicalSession) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session
        self._preview_mesh_by_id: dict[str, Any] = {}
        self._live_motion = MechanicalLiveMotionPreview(session)
        self._gear_drag = MechanicalGearDragPreview()

    def sync(self, ctx: Any, *, status: str | None = None, render: bool = True, update_mesh_preview: bool = True) -> None:
        if update_mesh_preview:
            self.sync_mesh_preview(ctx)
        self.sync_projected_markers(ctx, render=False)
        self.sync_status(ctx, status=status)
        self.render(ctx, render=render)

    def sync_mesh_preview(self, ctx: Any) -> None:
        self.end_gear_drag(ctx, render=False)
        self.end_live_motion(ctx, render=False)
        if not ctx.document.ensure():
            return
        preview = self.session.build_preview(test_angle_deg=self.session.state.test_angle_deg, draft=False)
        self._preview_mesh_by_id = {
            str(getattr(mesh, "mesh_id", "") or ""): mesh
            for mesh in preview.meshes
            if str(getattr(mesh, "mesh_id", "") or "")
        }
        try:
            ctx.document.set_preview_meshes(preview.meshes)
        except Exception:
            return
        owner = getattr(ctx, "owner", None)
        rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
        if callable(rebuild):
            try:
                rebuild(keep_camera=True)
            except TypeError:
                rebuild()
        update = getattr(owner, "update_preview_state", None) if owner is not None else None
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def sync_gear_drag(
        self,
        ctx: Any,
        gear_id: str,
        candidate: GearSnapCandidate | None,
        *,
        origin_center: tuple[float, float, float] | None = None,
        origin_phase_deg: float | None = None,
        render: bool = True,
    ) -> bool:
        """High-frequency standalone-gear drag path with no mesh rebuild."""

        gear = self.session.assembly.gears.get(str(gear_id))
        plane = self.session.work_plane
        if gear is None or plane is None:
            return False
        self._gear_drag.update(
            ctx,
            gear,
            axis=plane.normal,
            baseline_center=origin_center,
            baseline_phase_deg=origin_phase_deg,
            render=False,
        )
        snapped = candidate is not None
        color = "#74F3A5" if snapped else "#FFD36B"
        center = plane.clamp(gear.center)
        radius_point = plane.radial_point(center, gear.pitch_radius_mm, 0.0)
        outline = gear_drag_outline_points(gear, plane)
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        primitives: list[Any] = [
            draw2d.polyline(
                f"mechanical:drag:{gear.id}:outline",
                outline,
                color=color,
                width_px=2.4,
                opacity=0.95,
                layer=34,
                metadata={
                    "mechanical_role": "gear_drag_outline",
                    "mechanical_element_id": gear.id,
                    "projected_drawing_only": True,
                },
            ),
            draw2d.point(
                f"mechanical:gear:{gear.id}:center",
                center,
                color=color,
                size_px=13.0,
                interaction="grabbable",
                hit_radius_px=15.0,
                metadata={
                    "mechanical_role": "gear_center",
                    "mechanical_element_id": gear.id,
                    "mechanical_gear_id": gear.id,
                },
            ),
            draw2d.circle(
                f"mechanical:gear:{gear.id}:pitch",
                center,
                radius_point,
                color=color,
                width_px=2.6,
                opacity=0.92,
                interaction="selectable",
                hit_radius_px=8.0,
                metadata={
                    "mechanical_role": "gear_pitch",
                    "mechanical_element_id": gear.id,
                    "mechanical_gear_id": gear.id,
                },
            ),
        ]
        snap_ids = (
            "mechanical:drag:snap:target",
            "mechanical:drag:snap:link",
            "mechanical:drag:snap:contact",
            "mechanical:drag:snap:label",
        )
        if candidate is not None:
            target = self.session.assembly.gears.get(candidate.target_gear_id)
            if target is not None:
                target_center = plane.clamp(target.center)
                target_radius = plane.radial_point(target_center, target.pitch_radius_mm, 0.0)
                label_position = tuple(
                    0.5 * (target_center[index] + center[index])
                    for index in range(3)
                )
                primitives.extend(
                    (
                        draw2d.circle(
                            snap_ids[0],
                            target_center,
                            target_radius,
                            color="#74F3A5",
                            width_px=3.0,
                            opacity=0.95,
                            layer=33,
                            metadata={"mechanical_role": "gear_snap_target", "mechanical_gear_id": target.id},
                        ),
                        draw2d.line(
                            snap_ids[1],
                            target_center,
                            center,
                            color="#74F3A5",
                            width_px=2.0,
                            opacity=0.85,
                            layer=35,
                        ),
                        draw2d.point(
                            snap_ids[2],
                            candidate.contact_point,
                            color="#E8FFF0",
                            size_px=10.0,
                            layer=42,
                        ),
                        draw2d.text(
                            snap_ids[3],
                            f"SMART SNAP · {target.teeth}T ↔ {gear.teeth}T · phase aligned",
                            label_position,
                            color="#E8FFF0",
                            size_px=12,
                            bold=True,
                            anchor="bottom_left",
                            offset_px=(8.0, -8.0),
                            layer=48,
                        ),
                    )
                )
        registry.add_many(tuple(primitives), replace=True, render=False)
        if candidate is None:
            registry.remove_many(snap_ids, render=False)
        if render:
            registry.render(render=True)
        return True

    def end_gear_drag(self, ctx: Any, *, render: bool = False) -> None:
        self._gear_drag.end(ctx, render=render)

    def begin_live_motion(self, ctx: Any) -> bool:
        return self._live_motion.begin(ctx)

    def end_live_motion(self, ctx: Any, *, render: bool = False) -> None:
        self._live_motion.end(ctx, render=render)

    def sync_test_motion(self, ctx: Any, *, render: bool = True) -> bool:
        """Fast Test path: actor matrices plus one lightweight handle update."""

        moved = self._live_motion.update(ctx, self.session.state.driver_angles_deg, render=False)
        if not moved:
            # Headless/non-VTK fallback retained for tests and unusual hosts.
            self.sync_mesh_preview(ctx)
            self.sync_projected_markers(ctx, render=render)
            return False
        self.sync_test_handle(ctx, render=render)
        return True

    def sync_test_handle(self, ctx: Any, *, render: bool = True) -> None:
        driver = self.session.assembly.primary_driver()
        plane = self.session.work_plane
        if driver is None or plane is None:
            return
        target_gear = self.session.assembly.gears.get(str(driver.target_gear_id))
        radius = max(16.0, (target_gear.outer_radius_mm + 7.0) if target_gear is not None else 22.0)
        center = plane.clamp(driver.center)
        angle = float(self.session.state.driver_angles_deg.get(driver.id, 0.0))
        handle = plane.radial_point(center, radius, angle)
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        registry.add_many(
            (
                draw2d.line(
                    f"mechanical:test:{driver.id}:arm",
                    center,
                    handle,
                    color="#FFD0B5",
                    width_px=2.0,
                    opacity=0.9,
                ),
                draw2d.point(
                    f"mechanical:test:{driver.id}:handle",
                    handle,
                    color="#FFF1E7",
                    size_px=13.0,
                    interaction="grabbable",
                    hit_radius_px=16.0,
                    metadata={
                        "mechanical_role": "test_rotation_handle",
                        "mechanical_element_id": driver.id,
                        "mechanical_driver_id": driver.id,
                    },
                ),
            ),
            replace=True,
            render=False,
        )
        if render:
            registry.render(render=True)

    def sync_curve_drag(self, ctx: Any, chain_id: str, *, render: bool = True) -> bool:
        """Fast path used while a Bézier anchor is being dragged.

        Only the sampled route and its two handle links are replaced. Generated
        gears, shaft markers, labels and mesh previews remain untouched until
        release, where the normal full sync performs the one required solve.
        """

        chain = self.session.assembly.chains.get(str(chain_id))
        if chain is None:
            return False
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        curve = sample_bezier((chain.start, chain.control_1, chain.control_2, chain.end), segments=120)
        registry.add_many(
            (
                draw2d.polyline(
                    f"mechanical:chain:{chain.id}:curve",
                    curve,
                    color="#82D8FF",
                    width_px=3.0,
                    interaction="selectable",
                    hit_radius_px=10.0,
                    metadata={"mechanical_role": "chain_curve", "mechanical_element_id": chain.id},
                ),
                draw2d.line(
                    f"mechanical:chain:{chain.id}:handle_line_1",
                    chain.start,
                    chain.control_1,
                    color="#7A91A8",
                    width_px=1.0,
                    opacity=0.7,
                ),
                draw2d.line(
                    f"mechanical:chain:{chain.id}:handle_line_2",
                    chain.end,
                    chain.control_2,
                    color="#7A91A8",
                    width_px=1.0,
                    opacity=0.7,
                ),
            ),
            replace=True,
            render=False,
        )
        registry.update_positions(
            {
                f"mechanical:chain:{chain.id}:control_1": chain.control_1,
                f"mechanical:chain:{chain.id}:control_2": chain.control_2,
            },
            render=False,
        )
        if render:
            registry.render(render=True)
        return True

    def sync_projected_markers(self, ctx: Any, *, render: bool = False) -> None:
        assembly = self.session.assembly
        plane = self.session.work_plane
        selected = assembly.selected_element_id
        driver_candidate = str(self.session.state.driver_candidate_gear_id or "")
        mode = self.session.state.mode
        primitives: list[Any] = []
        if plane is None:
            registry = ctx.projected_drawing.for_tool(self.owner_tool)
            registry.replace_all((), render=False)
            registry.set_visible(True, render=False)
            if render:
                registry.render(render=True)
            return

        def overlay_mesh(mesh_id: str) -> Any | None:
            return self._preview_mesh_by_id.get(str(mesh_id)) or self.session.mesh_by_id(str(mesh_id))

        def mesh_center(mesh: Any) -> tuple[float, float, float] | None:
            return self.session.mesh_center(mesh)

        def add_part_highlight(
            *,
            actor_id: str,
            mesh_id: str,
            color: str,
            label: str,
            element_id: str,
            role: str,
        ) -> tuple[float, float, float] | None:
            mesh = overlay_mesh(mesh_id)
            if mesh is None:
                return None
            vertices = tuple(getattr(mesh, "vertices", ()) or ())
            triangles = tuple(getattr(mesh, "triangles", ()) or ())
            center = mesh_center(mesh)
            if mode is not MechanicalMode.TEST and len(vertices) >= 3 and triangles:
                try:
                    primitives.append(
                        draw2d.triangle_mesh(
                            f"{actor_id}:surface",
                            vertices,
                            triangles,
                            fill_color=color,
                            fill_opacity=0.045,
                            outline_color=color,
                            outline_width_px=3.0,
                            outline_opacity=0.9,
                            layer=12,
                            metadata={
                                "mechanical_role": role,
                                "mechanical_element_id": element_id,
                                "mechanical_target_mesh_id": mesh_id,
                                "projected_drawing_only": True,
                            },
                        )
                    )
                except Exception:
                    pass
            if center is not None:
                primitives.extend(
                    (
                        draw2d.point(
                            f"{actor_id}:center",
                            center,
                            color=color,
                            size_px=12.0,
                            interaction="selectable",
                            hit_radius_px=14.0,
                            metadata={
                                "mechanical_role": role,
                                "mechanical_element_id": element_id,
                                "mechanical_target_mesh_id": mesh_id,
                            },
                        ),
                        draw2d.text(
                            f"{actor_id}:label",
                            label,
                            center,
                            color=color,
                            size_px=12,
                            bold=True,
                            anchor="bottom_left",
                            offset_px=(10.0, -10.0),
                            layer=45,
                            metadata={"mechanical_role": role, "mechanical_element_id": element_id},
                        ),
                    )
                )
            return center

        chain_owner_by_gear = {
            gear_id: chain.id
            for chain in assembly.chains.values()
            for gear_id in chain.gear_ids
        }
        for gear in assembly.gears.values():
            owner_element_id = chain_owner_by_gear.get(gear.id, gear.id)
            is_chain_gear = owner_element_id != gear.id
            is_selected = owner_element_id == selected
            is_driver_candidate = gear.id == driver_candidate
            point_color = "#FF8A4C" if is_driver_candidate else ("#FFF0A8" if is_selected else "#FFD36B")
            interaction = (
                "grabbable"
                if not is_chain_gear and mode in {MechanicalMode.SELECT, MechanicalMode.EDIT_CURVE}
                else "selectable"
            )
            support_center = plane.clamp(gear.center)
            primitives.append(
                draw2d.point(
                    f"mechanical:gear:{gear.id}:center",
                    support_center,
                    color=point_color,
                    size_px=15.0 if is_driver_candidate else (13.0 if is_selected else 10.0),
                    interaction=interaction,
                    hit_radius_px=13.0,
                    metadata={"mechanical_role": "gear_center", "mechanical_element_id": owner_element_id, "mechanical_gear_id": gear.id},
                )
            )
            radius_point = plane.radial_point(support_center, gear.pitch_radius_mm, 0.0)
            primitives.append(
                draw2d.circle(
                    f"mechanical:gear:{gear.id}:pitch",
                    support_center,
                    radius_point,
                    color="#FF8A4C" if is_driver_candidate else ("#FFE08C" if is_selected else "#C89335"),
                    width_px=2.8 if is_driver_candidate else (2.2 if is_selected else 1.2),
                    opacity=0.95 if is_driver_candidate else (0.85 if is_selected else 0.55),
                    interaction="selectable",
                    hit_radius_px=8.0,
                    metadata={"mechanical_role": "gear_pitch", "mechanical_element_id": owner_element_id, "mechanical_gear_id": gear.id},
                )
            )

        for stage in assembly.stages.values():
            if not is_smart_mesh_stage(stage, assembly):
                continue
            driver_gear = assembly.gears.get(str(stage.driver_gear_id))
            driven_gear = assembly.gears.get(str(stage.driven_gear_id))
            if driver_gear is None or driven_gear is None:
                continue
            driver_center = plane.clamp(driver_gear.center)
            driven_center = plane.clamp(driven_gear.center)
            mesh_angle = plane.angle_deg(driver_center, driven_center)
            contact = plane.radial_point(driver_center, driver_gear.pitch_radius_mm, mesh_angle)
            selected_connection = selected in {driver_gear.id, driven_gear.id}
            primitives.extend(
                (
                    draw2d.line(
                        f"mechanical:smart_mesh:{stage.id}:centres",
                        driver_center,
                        driven_center,
                        color="#74F3A5",
                        width_px=2.2 if selected_connection else 1.25,
                        opacity=0.85 if selected_connection else 0.48,
                        layer=18,
                        metadata={
                            "mechanical_role": "smart_mesh_connection",
                            "mechanical_stage_id": stage.id,
                        },
                    ),
                    draw2d.point(
                        f"mechanical:smart_mesh:{stage.id}:contact",
                        contact,
                        color="#DFFFF0",
                        size_px=9.0 if selected_connection else 6.0,
                        layer=36,
                        metadata={
                            "mechanical_role": "smart_mesh_contact",
                            "mechanical_stage_id": stage.id,
                        },
                    ),
                )
            )

        for chain in assembly.chains.values():
            is_selected = chain.id == selected
            curve = sample_bezier((chain.start, chain.control_1, chain.control_2, chain.end), segments=120)
            primitives.append(
                draw2d.polyline(
                    f"mechanical:chain:{chain.id}:curve",
                    curve,
                    color="#82D8FF" if is_selected else "#5FA6C7",
                    width_px=3.0 if is_selected else 1.6,
                    interaction="selectable",
                    hit_radius_px=10.0,
                    metadata={"mechanical_role": "chain_curve", "mechanical_element_id": chain.id},
                )
            )
            gear_by_shaft: dict[str, str] = {}
            for gear_id in chain.gear_ids:
                gear = assembly.gears.get(gear_id)
                if gear is not None:
                    gear_by_shaft.setdefault(str(gear.shaft_id or gear.id), gear.id)
            for index, shaft in enumerate(chain.shafts):
                shaft_id = chain.shaft_ids[index] if index < len(chain.shaft_ids) else ""
                candidate_gear_id = gear_by_shaft.get(str(shaft_id), "")
                primitives.append(
                    draw2d.point(
                        f"mechanical:chain:{chain.id}:shaft:{index}",
                        shaft,
                        color="#FF8A4C" if candidate_gear_id == driver_candidate else ("#C7F1FF" if is_selected else "#72BFD9"),
                        size_px=13.0 if candidate_gear_id == driver_candidate else (10.0 if index in {0, len(chain.shafts) - 1} else 8.0),
                        interaction="selectable",
                        hit_radius_px=11.0,
                        metadata={
                            "mechanical_role": "chain_shaft",
                            "mechanical_element_id": chain.id,
                            "mechanical_gear_id": candidate_gear_id,
                            "mechanical_shaft_id": shaft_id,
                            "shaft_index": index,
                        },
                    )
                )
            if is_selected or mode is MechanicalMode.EDIT_CURVE:
                primitives.extend(
                    (
                        draw2d.line(
                            f"mechanical:chain:{chain.id}:handle_line_1",
                            chain.start,
                            chain.control_1,
                            color="#7A91A8",
                            width_px=1.0,
                            opacity=0.7,
                        ),
                        draw2d.line(
                            f"mechanical:chain:{chain.id}:handle_line_2",
                            chain.end,
                            chain.control_2,
                            color="#7A91A8",
                            width_px=1.0,
                            opacity=0.7,
                        ),
                        draw2d.point(
                            f"mechanical:chain:{chain.id}:control_1",
                            chain.control_1,
                            color="#A8E6FF",
                            size_px=11.0,
                            interaction="grabbable",
                            hit_radius_px=14.0,
                            metadata={"mechanical_role": "chain_control_1", "mechanical_element_id": chain.id},
                        ),
                        draw2d.point(
                            f"mechanical:chain:{chain.id}:control_2",
                            chain.control_2,
                            color="#A8E6FF",
                            size_px=11.0,
                            interaction="grabbable",
                            hit_radius_px=14.0,
                            metadata={"mechanical_role": "chain_control_2", "mechanical_element_id": chain.id},
                        ),
                    )
                )

        rack_state = solve_kinematics(assembly, self.session.state.driver_angles_deg if assembly.drivers else self.session.state.test_angle_deg)
        for rack in assembly.racks.values():
            is_selected = rack.id == selected
            displacement = float(rack_state.rack_displacements_mm.get(rack.id, 0.0)) if mode is MechanicalMode.TEST else 0.0
            direction = rack_axis(rack)
            offset = (direction[0] * displacement, direction[1] * displacement, direction[2] * displacement)
            start = tuple(rack.start[index] + offset[index] for index in range(3))
            end = tuple(rack.end[index] + offset[index] for index in range(3))
            midpoint = tuple((start[index] + end[index]) * 0.5 for index in range(3))
            color = "#A7E1FF" if is_selected else "#6FB6D9"
            interaction = "selectable" if mode is MechanicalMode.TEST else "grabbable"
            primitives.extend(
                (
                    draw2d.line(
                        f"mechanical:rack:{rack.id}:pitch",
                        start,
                        end,
                        color=color,
                        width_px=4.0 if is_selected else 2.4,
                        opacity=0.95,
                        interaction="selectable",
                        hit_radius_px=12.0,
                        metadata={"mechanical_role": "rack_line", "mechanical_element_id": rack.id, "mechanical_rack_id": rack.id},
                    ),
                    draw2d.point(
                        f"mechanical:rack:{rack.id}:start",
                        start,
                        color=color,
                        size_px=11.0 if is_selected else 8.0,
                        interaction=interaction,
                        hit_radius_px=13.0,
                        metadata={"mechanical_role": "rack_start", "mechanical_element_id": rack.id, "mechanical_rack_id": rack.id},
                    ),
                    draw2d.point(
                        f"mechanical:rack:{rack.id}:end",
                        end,
                        color=color,
                        size_px=11.0 if is_selected else 8.0,
                        interaction=interaction,
                        hit_radius_px=13.0,
                        metadata={"mechanical_role": "rack_end", "mechanical_element_id": rack.id, "mechanical_rack_id": rack.id},
                    ),
                    draw2d.text(
                        f"mechanical:rack:{rack.id}:label",
                        f"RACK · {rack.tooth_count} teeth · {displacement:.4g} mm",
                        midpoint,
                        color=color,
                        size_px=12,
                        bold=is_selected,
                        anchor="bottom_left",
                        offset_px=(8.0, -8.0),
                        layer=44,
                        metadata={"mechanical_role": "rack_label", "mechanical_element_id": rack.id},
                    ),
                )
            )
            pinion = assembly.gears.get(str(rack.pinion_gear_id or ""))
            if pinion is not None:
                primitives.append(
                    draw2d.line(
                        f"mechanical:rack:{rack.id}:pinion_link",
                        plane.clamp(pinion.center),
                        midpoint,
                        color="#78C6E8",
                        width_px=1.3,
                        opacity=0.55,
                        metadata={"mechanical_role": "rack_pinion_link", "mechanical_element_id": rack.id},
                    )
                )

        for driver in assembly.drivers.values():
            is_selected = driver.id == selected
            driver_center = plane.clamp(driver.center)
            driver_color = "#FFB08F" if is_selected else "#FF6F4A"
            primitives.extend(
                (
                    draw2d.point(
                        f"mechanical:driver:{driver.id}:center",
                        driver_center,
                        color=driver_color,
                        size_px=14.0 if is_selected else 11.0,
                        interaction=(
                            "selectable"
                            if mode in {MechanicalMode.TEST, MechanicalMode.PICK_DRIVER_TARGET, MechanicalMode.PICK_ATTACHMENT_SOURCE}
                            else "grabbable"
                        ),
                        hit_radius_px=14.0,
                        metadata={"mechanical_role": "driver_center", "mechanical_element_id": driver.id},
                    ),
                    draw2d.text(
                        f"mechanical:driver:{driver.id}:label",
                        f"DRIVER · {driver.speed_rpm * driver.direction:.4g} rpm",
                        driver_center,
                        color=driver_color,
                        size_px=12,
                        bold=True,
                        anchor="bottom_left",
                        offset_px=(10.0, -12.0),
                        layer=45,
                        metadata={"mechanical_role": "driver_label", "mechanical_element_id": driver.id},
                    ),
                )
            )
            if driver.target_mesh_id:
                add_part_highlight(
                    actor_id=f"mechanical:driver:{driver.id}:target:{driver.target_mesh_id}",
                    mesh_id=str(driver.target_mesh_id),
                    color="#FF7A45",
                    label="DRIVER PART",
                    element_id=driver.id,
                    role="driver_target_part",
                )
            if mode is MechanicalMode.TEST:
                target_gear = assembly.gears.get(str(driver.target_gear_id))
                radius = max(16.0, (target_gear.outer_radius_mm + 7.0) if target_gear is not None else 22.0)
                angle = float(self.session.state.driver_angles_deg.get(driver.id, 0.0))
                handle = plane.radial_point(driver_center, radius, angle)
                primitives.extend(
                    (
                        draw2d.circle(
                            f"mechanical:test:{driver.id}:ring",
                            driver_center,
                            plane.radial_point(driver_center, radius, 0.0),
                            color="#FF9C65",
                            width_px=2.2,
                            opacity=0.85,
                            interaction="selectable",
                            hit_radius_px=8.0,
                            metadata={"mechanical_role": "test_rotation_ring", "mechanical_element_id": driver.id, "mechanical_driver_id": driver.id},
                        ),
                        draw2d.line(
                            f"mechanical:test:{driver.id}:arm",
                            driver_center,
                            handle,
                            color="#FFD0B5",
                            width_px=2.0,
                            opacity=0.9,
                        ),
                        draw2d.point(
                            f"mechanical:test:{driver.id}:handle",
                            handle,
                            color="#FFF1E7",
                            size_px=13.0,
                            interaction="grabbable",
                            hit_radius_px=16.0,
                            metadata={"mechanical_role": "test_rotation_handle", "mechanical_element_id": driver.id, "mechanical_driver_id": driver.id},
                        ),
                    )
                )

        for attachment in assembly.attachments.values():
            is_selected = attachment.id == selected
            source_center = plane.clamp(attachment.center)
            color = "#F4A9FF" if is_selected else "#D96BE8"
            primitives.extend(
                (
                    draw2d.point(
                        f"mechanical:attachment:{attachment.id}:source",
                        source_center,
                        color=color,
                        size_px=13.0 if is_selected else 10.0,
                        interaction="selectable",
                        hit_radius_px=14.0,
                        metadata={"mechanical_role": "attachment_source", "mechanical_element_id": attachment.id},
                    ),
                    draw2d.text(
                        f"mechanical:attachment:{attachment.id}:label",
                        f"MOVING · {len(attachment.target_mesh_ids)} part(s)",
                        source_center,
                        color=color,
                        size_px=12,
                        bold=True,
                        anchor="top_left",
                        offset_px=(10.0, 12.0),
                        layer=45,
                        metadata={"mechanical_role": "attachment_label", "mechanical_element_id": attachment.id},
                    ),
                )
            )
            for target_mesh_id in attachment.target_mesh_ids:
                target_center = add_part_highlight(
                    actor_id=f"mechanical:attachment:{attachment.id}:target:{target_mesh_id}",
                    mesh_id=str(target_mesh_id),
                    color=color,
                    label="MOVING PART",
                    element_id=attachment.id,
                    role="attachment_target_part",
                )
                if target_center is not None:
                    primitives.append(
                        draw2d.line(
                            f"mechanical:attachment:{attachment.id}:link:{target_mesh_id}",
                            source_center,
                            target_center,
                            color=color,
                            width_px=1.8,
                            opacity=0.75,
                            layer=20,
                            metadata={"mechanical_role": "attachment_link", "mechanical_element_id": attachment.id},
                        )
                    )

        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        registry.replace_all(tuple(primitives), render=False)
        registry.set_visible(True, render=False)
        if render:
            registry.render(render=True)

    def sync_status(self, ctx: Any, *, status: str | None = None) -> None:
        assembly = self.session.assembly
        plane = self.session.work_plane
        selected = assembly.selected_element()
        text = status or self.session.state.last_status or "Mechanical assembly ready."
        try:
            ctx.inspector.set_display_value("mechanical_status", text)
            ctx.inspector.set_display_value(
                "mechanical_summary",
                f"{len(assembly.gears)} gear(s) · {len(assembly.chains)} chain(s) · {len(assembly.racks)} rack(s) · {len(assembly.drivers)} driver(s) · {len(assembly.attachments)} attachment group(s)",
            )
            ctx.inspector.set_display_value(
                "mechanical_selection",
                getattr(selected, "name", "No mechanical element selected.") if selected is not None else "No mechanical element selected.",
            )
        except Exception:
            pass

    def render(self, ctx: Any, *, render: bool = True) -> None:
        registry = ctx.projected_drawing.for_tool(self.owner_tool)
        registry.render(render=render)

    def clear(self, ctx: Any) -> None:
        self.end_gear_drag(ctx, render=False)
        self.end_live_motion(ctx, render=False)
        self._preview_mesh_by_id.clear()
        try:
            ctx.projected_drawing.for_tool(self.owner_tool).clear(render=False)
        except Exception:
            pass


__all__ = ["MechanicalRenderer"]
