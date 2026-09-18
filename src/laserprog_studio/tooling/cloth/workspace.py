"""Headless state machine for the compact single-overlay Cloth workflow.

The state machine owns only user intent and button enablement. Geometry,
selection picking and document mutations stay in their dedicated modules.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClothOverlayMode(str, Enum):
    MAIN = "main"
    CLOSE = "close"
    DRAW = "draw"
    PROPERTIES = "properties"


class ClothDrawMode(str, Enum):
    MODIFY = "modify"
    LINE = "line"
    POLYLINE = "polyline"


class ClothDrawPickMode(str, Enum):
    FACE = "face"
    EDGE = "edge"


class ClothPropertySelectionMode(str, Enum):
    FACE = "face"
    GROUP = "group"


class ClothWorkspacePhase(str, Enum):
    READY = "ready"
    SELECTING = "selecting"
    REVIEWING_CLOSE = "reviewing_close"
    DRAWING = "drawing"
    EDITING_PROPERTIES = "editing_properties"
    COMPUTING = "computing"
    FLAT_PREVIEW = "flat_preview"
    BLOCKED = "blocked"


@dataclass(slots=True)
class ClothWorkspaceState:
    overlay_mode: ClothOverlayMode = ClothOverlayMode.MAIN
    phase: ClothWorkspacePhase = ClothWorkspacePhase.READY
    draw_mode: ClothDrawMode = ClothDrawMode.MODIFY
    draw_pick_mode: ClothDrawPickMode = ClothDrawPickMode.FACE
    property_selection_mode: ClothPropertySelectionMode = ClothPropertySelectionMode.GROUP
    selected_source_regions: int = 0
    selected_source_meshes: int = 0
    selected_textile_faces: int = 0
    selected_textile_edges: int = 0
    close_proposal_count: int = 0
    close_proposal_index: int = 0
    pending_draw_points: int = 0
    smart_snap_enabled: bool = True
    axis_guides_enabled: bool = True
    message: str = (
        "Select logical mesh surfaces, textile groups or textile edges. "
        "Shift adds to the current selection."
    )

    @property
    def textile_anchor_count(self) -> int:
        return self.selected_textile_faces + self.selected_textile_edges

    @property
    def can_take_face(self) -> bool:
        return self.overlay_mode is ClothOverlayMode.MAIN and self.selected_source_regions > 0

    @property
    def can_close(self) -> bool:
        return self.overlay_mode is ClothOverlayMode.MAIN and self.textile_anchor_count >= 1

    @property
    def can_apply_close(self) -> bool:
        return self.overlay_mode is ClothOverlayMode.CLOSE and self.close_proposal_count > 0

    @property
    def can_set_properties(self) -> bool:
        return self.overlay_mode is ClothOverlayMode.PROPERTIES and self.selected_textile_faces > 0


class ClothWorkspaceMachine:
    """Deterministic UX state machine for Cloth's single overlay."""

    def __init__(self, state: ClothWorkspaceState | None = None) -> None:
        self.state = state or ClothWorkspaceState()

    def reset(self) -> ClothWorkspaceState:
        # Preserve object identity because the persistent single overlay keeps a
        # direct reference to this state object.  Replacing it can leave button
        # enablement (notably Close Apply) bound to a stale snapshot.
        fresh = ClothWorkspaceState()
        for field_name in fresh.__dataclass_fields__:
            setattr(self.state, field_name, getattr(fresh, field_name))
        return self.state

    def enter_main(self) -> ClothWorkspaceState:
        state = self.state
        state.overlay_mode = ClothOverlayMode.MAIN
        state.phase = ClothWorkspacePhase.SELECTING
        state.close_proposal_count = 0
        state.close_proposal_index = 0
        state.pending_draw_points = 0
        state.message = self._main_message()
        return state

    def enter_close(self, *, proposals: int = 0, proposal_index: int = 0) -> ClothWorkspaceState:
        state = self.state
        state.overlay_mode = ClothOverlayMode.CLOSE
        state.close_proposal_count = max(0, int(proposals))
        state.close_proposal_index = max(0, int(proposal_index))
        state.phase = ClothWorkspacePhase.REVIEWING_CLOSE if proposals else ClothWorkspacePhase.COMPUTING
        state.message = (
            f"Closure proposal {state.close_proposal_index + 1}/{proposals}. Review it, then Apply."
            if proposals
            else "Analyzing the selected textile faces and edges."
        )
        return state

    def enter_draw(self, mode: ClothDrawMode | str | None = None) -> ClothWorkspaceState:
        state = self.state
        state.overlay_mode = ClothOverlayMode.DRAW
        state.phase = ClothWorkspacePhase.DRAWING
        if mode is not None:
            state.draw_mode = mode if isinstance(mode, ClothDrawMode) else ClothDrawMode(str(mode))
        state.close_proposal_count = 0
        state.close_proposal_index = 0
        state.message = self._draw_message()
        return state

    def enter_properties(self) -> ClothWorkspaceState:
        state = self.state
        state.overlay_mode = ClothOverlayMode.PROPERTIES
        state.phase = ClothWorkspacePhase.EDITING_PROPERTIES
        state.close_proposal_count = 0
        state.close_proposal_index = 0
        state.pending_draw_points = 0
        state.message = self._properties_message()
        return state

    def set_draw_mode(self, mode: ClothDrawMode | str) -> ClothWorkspaceState:
        self.state.draw_mode = mode if isinstance(mode, ClothDrawMode) else ClothDrawMode(str(mode))
        self.state.message = self._draw_message()
        return self.state

    def set_draw_pick_mode(self, mode: ClothDrawPickMode | str) -> ClothWorkspaceState:
        self.state.draw_pick_mode = mode if isinstance(mode, ClothDrawPickMode) else ClothDrawPickMode(str(mode))
        self.state.message = self._draw_message()
        return self.state

    def set_property_selection_mode(self, mode: ClothPropertySelectionMode | str) -> ClothWorkspaceState:
        self.state.property_selection_mode = (
            mode if isinstance(mode, ClothPropertySelectionMode) else ClothPropertySelectionMode(str(mode))
        )
        self.state.message = self._properties_message()
        return self.state

    def update_selection(
        self,
        *,
        source_regions: int | None = None,
        source_meshes: int | None = None,
        textile_faces: int | None = None,
        textile_edges: int | None = None,
    ) -> ClothWorkspaceState:
        state = self.state
        if source_regions is not None:
            state.selected_source_regions = max(0, int(source_regions))
        if source_meshes is not None:
            state.selected_source_meshes = max(0, int(source_meshes))
        if textile_faces is not None:
            state.selected_textile_faces = max(0, int(textile_faces))
        if textile_edges is not None:
            state.selected_textile_edges = max(0, int(textile_edges))
        if state.overlay_mode is ClothOverlayMode.MAIN:
            state.message = self._main_message()
        elif state.overlay_mode is ClothOverlayMode.PROPERTIES:
            state.message = self._properties_message()
        return state

    def update_close(self, *, proposals: int, proposal_index: int = 0) -> ClothWorkspaceState:
        return self.enter_close(proposals=proposals, proposal_index=proposal_index)

    def update_draw(
        self,
        pending_points: int,
        *,
        smart_snap_enabled: bool | None = None,
        axis_guides_enabled: bool | None = None,
    ) -> ClothWorkspaceState:
        self.state.pending_draw_points = max(0, int(pending_points))
        if smart_snap_enabled is not None:
            self.state.smart_snap_enabled = bool(smart_snap_enabled)
        if axis_guides_enabled is not None:
            self.state.axis_guides_enabled = bool(axis_guides_enabled)
        if self.state.overlay_mode is ClothOverlayMode.DRAW:
            self.state.message = self._draw_message()
        return self.state

    def block(self, message: str) -> ClothWorkspaceState:
        self.state.phase = ClothWorkspacePhase.BLOCKED
        self.state.message = str(message)
        return self.state

    def _main_message(self) -> str:
        state = self.state
        parts: list[str] = []
        if state.selected_source_regions:
            parts.append(
                f"{state.selected_source_regions} mesh surface group(s) on {state.selected_source_meshes} mesh(es)"
            )
        if state.selected_textile_faces:
            parts.append(f"{state.selected_textile_faces} textile group(s)")
        if state.selected_textile_edges:
            parts.append(f"{state.selected_textile_edges} textile edge(s)")
        if parts:
            return "Selected: " + ", ".join(parts) + ". Shift adds another element."
        return "Select logical mesh surfaces, textile groups or textile edges. Shift adds to the selection."

    def _draw_message(self) -> str:
        state = self.state
        if state.draw_mode is ClothDrawMode.MODIFY:
            target = "faces" if state.draw_pick_mode is ClothDrawPickMode.FACE else "edges"
            return f"Modify textile {target} individually. Shift adds; Apply separates selected faces; Delete removes them."
        if state.draw_mode is ClothDrawMode.LINE:
            return "Line: place two points. Smart Snap remains available."
        count = state.pending_draw_points
        return (
            f"Polyline: {count} point(s). Click the first point to close and create a textile face automatically."
            if count
            else "Polyline: place points. A closed contour creates a textile face automatically."
        )

    def _properties_message(self) -> str:
        state = self.state
        mode = "individual face" if state.property_selection_mode is ClothPropertySelectionMode.FACE else "logical group"
        if state.selected_textile_faces:
            return f"{state.selected_textile_faces} textile face(s) selected by {mode}. Choose a Set role."
        return f"Select textile faces by {mode}. Mesh surfaces cannot be selected in Properties."


# Compatibility aliases retained for older imports and saved UI tests.
ClothWorkspace = ClothOverlayMode
ClothDrawTool = ClothDrawMode


__all__ = [
    "ClothDrawMode",
    "ClothDrawPickMode",
    "ClothDrawTool",
    "ClothOverlayMode",
    "ClothPropertySelectionMode",
    "ClothWorkspace",
    "ClothWorkspaceMachine",
    "ClothWorkspacePhase",
    "ClothWorkspaceState",
]
