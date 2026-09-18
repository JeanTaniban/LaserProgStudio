"""Contextual smart-assistance overlay for Cloth mesh tracing."""
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .geometry_trace import ClothGeometryTraceController

CLOTH_GEOMETRY_WINDOW_ID = "cloth.geometry_trace"
CLOTH_GEOMETRY_ACTION_PREFIX = "cloth.geometry.action."
_GEOMETRY_PICK_GROUP = "cloth.geometry.pick_kind"


class ClothGeometryTraceOverlay:
    def __init__(self, owner_tool: str, controller: ClothGeometryTraceController) -> None:
        self.owner_tool = str(owner_tool)
        self.controller = controller

    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        value = str(button_id or "")
        if value.startswith(CLOTH_GEOMETRY_ACTION_PREFIX):
            return value[len(CLOTH_GEOMETRY_ACTION_PREFIX) :]
        return None

    @staticmethod
    def _mode(action: str, label: str, icon: str, tooltip: str) -> visual.OverlayModeSpec:
        return visual.OverlayModeSpec(
            id=f"{CLOTH_GEOMETRY_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=True,
            display_label=label,
            slot_width_px=max(62, len(label) * 8 + 22),
        )

    @staticmethod
    def _action(
        action: str,
        label: str,
        icon: str,
        tooltip: str,
        *,
        enabled: bool,
        style: str = "ghost",
    ) -> visual.OverlayActionSpec:
        return visual.OverlayActionSpec(
            id=f"{CLOTH_GEOMETRY_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
            display_label=label,
            slot_width_px=max(68, min(116, len(label) * 8 + 26)),
        )

    def sync(self, ctx: Any) -> None:
        predictions = self.controller.predictions()
        active = f"{CLOTH_GEOMETRY_ACTION_PREFIX}pick_{self.controller.pick_kind}"
        sections = (
            visual.OverlayToolbarSectionSpec(
                "pick",
                "Pick",
                modes=(
                    self._mode("pick_face", "Faces", "sketch.face", "Select complete logical source surfaces. Shift+click adds surfaces, including from another mesh."),
                    self._mode("pick_edge", "Edges", "sketch.line", "Select mesh edges to trace as Cloth boundaries."),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "smart",
                "Smart help",
                actions=(
                    self._action(
                        "grow_coplanar",
                        "Logical face",
                        "tool.add",
                        "The shared smart-selection API already expands the clicked triangles into one logical face.",
                        enabled=bool(self.controller.selected_faces),
                    ),
                    self._action(
                        "use_boundary",
                        "Boundary",
                        "sketch.polyline",
                        "Select the outer boundary edges of the selected faces.",
                        enabled=bool(predictions.boundary_edges),
                    ),
                    self._action(
                        "extend_direction",
                        "Continue",
                        "sketch.line",
                        "Predict conjoint edges that continue in the direction of the current selection.",
                        enabled=bool(predictions.directional_edges),
                    ),
                    self._action(
                        "close_source_face",
                        "Close face",
                        "sketch.polyline",
                        "Add the small or hidden source-mesh edges needed to close the predicted face.",
                        enabled=bool(predictions.closure_edges),
                        style="primary" if predictions.closure_edges else "ghost",
                    ),
                    self._action(
                        "select_connected",
                        "Connected",
                        "sketch.modify",
                        "Add one ring of connected semantic edges. Coplanar triangulation diagonals are ignored.",
                        enabled=bool(predictions.connected_edges),
                    ),
                    self._action(
                        "create_bridge",
                        "Cover",
                        "tool.add",
                        "Create a regular Cloth surface between two selected open edge rails.",
                        enabled=predictions.ruled_strip is not None,
                        style="primary",
                    ),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "build",
                "Build",
                actions=(
                    self._action(
                        "trace_selection",
                        "Trace",
                        "tool.apply",
                        "Create Cloth faces and lines from the selected mesh elements.",
                        enabled=self.controller.can_create,
                        style="primary",
                    ),
                    self._action(
                        "clear_selection",
                        "Clear",
                        "tool.reset",
                        "Clear the current mesh-element selection.",
                        enabled=bool(self.controller.selection_count),
                    ),
                ),
            ),
        )
        face_count = len(self.controller.selected_faces)
        edge_count = len(self.controller.selected_edges)
        mesh_count = (
            self.controller.smart_session.selected_mesh_count
            if self.controller.pick_kind == "face"
            else len({item.object_id for item in self.controller.selected_edges})
        )
        if predictions.ruled_strip is not None:
            strip = predictions.ruled_strip
            status = (
                f"Two compatible rails · {strip.segment_count} strip segment(s) · "
                f"mean width {strip.mean_width_mm:.3g} mm"
            )
        elif predictions.closure_edges:
            status = (
                f"Face nearly closed · {len(predictions.closure_edges)} small/hidden source edge(s) can be added · "
                f"{face_count} face triangle(s), {edge_count} edge(s) selected"
            )
        elif any(plan.complete for plan in predictions.closable_faces):
            status = f"Source face boundary detected · Trace can create the face · {edge_count} edge(s) selected"
        elif face_count or edge_count:
            status = f"{face_count} face triangle(s), {edge_count} semantic edge(s), {mesh_count} mesh(es) selected"
        else:
            status = "Select a logical face or edge. Shift+click adds; a quick double-click in empty space clears."
        window = visual.build_command_deck_window(
            window_id=CLOTH_GEOMETRY_WINDOW_ID,
            owner_tool=self.owner_tool,
            group_id=_GEOMETRY_PICK_GROUP,
            sections=sections,
            active_mode_id=active,
            badge_id="cloth.geometry.mode",
            badge_label="Source",
            badge_value="Faces" if self.controller.pick_kind == "face" else "Edges",
            badge_tooltip="Mesh element type currently selected by clicks.",
            status_id="cloth.geometry.status",
            status_label="Smart trace",
            status_value=status,
            title="Cloth · Smart Source Surfaces",
            anchor="viewport_top_right",
            width_px=0,
            persistent=True,
            cursor_offset_px=(0, 0),
        )
        ctx.overlay.show_window(window)
        try:
            ctx.overlay.set_group_active(_GEOMETRY_PICK_GROUP, active)
        except Exception:
            pass

    def hide(self, ctx: Any) -> None:
        try:
            ctx.overlay.hide_window(CLOTH_GEOMETRY_WINDOW_ID)
        except Exception:
            pass


__all__ = [
    "CLOTH_GEOMETRY_ACTION_PREFIX",
    "CLOTH_GEOMETRY_WINDOW_ID",
    "ClothGeometryTraceOverlay",
]
