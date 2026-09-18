"""Single context-sensitive overlay for the Cloth tool."""
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .models import ClothPatchFunction, ClothSession
from .workspace import (
    ClothDrawMode,
    ClothDrawPickMode,
    ClothOverlayMode,
    ClothPropertySelectionMode,
    ClothWorkspaceState,
)

CLOTH_WORKFLOW_WINDOW_ID = "cloth.workflow"
CLOTH_ACTION_PREFIX = "cloth.workflow.action."
_CLOTH_GROUP = "cloth.single_overlay"


class ClothWorkflowOverlay:
    def __init__(self, owner_tool: str, session: ClothSession, interaction: Any, workspace: ClothWorkspaceState) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session
        self.interaction = interaction
        self.workspace = workspace

    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        value = str(button_id or "")
        return value[len(CLOTH_ACTION_PREFIX) :] if value.startswith(CLOTH_ACTION_PREFIX) else None

    @staticmethod
    def _action(
        action: str,
        label: str,
        icon: str,
        tooltip: str,
        *,
        enabled: bool = True,
        style: str = "ghost",
    ) -> visual.OverlayActionSpec:
        return visual.OverlayActionSpec(
            id=f"{CLOTH_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
            display_label=label,
            slot_width_px=max(62, min(112, len(label) * 7 + 22)),
        )

    def _main_sections(self, *, can_apply: bool, pending_count: int = 0) -> tuple[visual.OverlayToolbarSectionSpec, ...]:
        state = self.workspace
        return (
            visual.OverlayToolbarSectionSpec(
                "main",
                "Cloth",
                actions=(
                    self._action(
                        "take_face",
                        "Take face",
                        "sketch.face",
                        "Copy each connected mesh selection as one persistent textile group.",
                        enabled=state.can_take_face,
                        style="primary" if state.can_take_face else "ghost",
                    ),
                    self._action(
                        "open_closure",
                        "Close",
                        "tool.link",
                        "Generate closure proposals from the selected textile groups or isolated edges. Apply creates one new independent textile group.",
                        enabled=state.can_close,
                        style="secondary",
                    ),
                    self._action("open_draw", "Draw", "sketch.polyline", "Draw or modify textile geometry.", style="secondary"),
                    self._action("open_properties", "Properties", "sketch.modify", "Assign Textile, Anchor or Pattern roles.", style="secondary"),
                    self._action(
                        "apply_output",
                        "Apply",
                        "tool.apply",
                        "Generate the folded output and linked flat-pattern preview, then continue editing.",
                        # Keep the main Apply action clickable whenever a document
                        # exists and no primitive is currently unfinished.  The
                        # actual validation still runs in ClothCreatorTool.on_apply
                        # and reports the precise blocking issue.  A disabled button
                        # previously hid validation errors and could leave users with
                        # apparently valid faces but no actionable feedback.
                        enabled=bool(self.session.document.patches) and int(pending_count) == 0,
                        style="primary" if can_apply else "secondary",
                    ),
                ),
            ),
        )

    def _close_sections(self) -> tuple[visual.OverlayToolbarSectionSpec, ...]:
        state = self.workspace
        # The interaction owns the authoritative proposal tuple.  Workspace
        # counters are presentation state and can lag by one sync when analysis
        # finishes during an overlay rebuild.  Deriving enablement from both
        # sources prevents a visible proposal from having a disabled Apply.
        proposal_count = max(
            int(state.close_proposal_count),
            len(tuple(getattr(self.interaction, "join_proposals", ()) or ())),
        )
        return (
            visual.OverlayToolbarSectionSpec(
                "close",
                "Close · proposals",
                actions=(
                    self._action(
                        "apply_closure",
                        "Apply",
                        "tool.apply",
                        "Create the displayed closure as one new textile group, independent from its input groups.",
                        enabled=proposal_count > 0,
                        style="primary",
                    ),
                    self._action(
                        "previous_closure",
                        "Prev",
                        "tool.back",
                        "Show the previous closure proposal.",
                        enabled=proposal_count > 1,
                        style="secondary",
                    ),
                    self._action(
                        "next_closure",
                        "Next",
                        "tool.forward",
                        "Show the next closure proposal.",
                        enabled=proposal_count > 1,
                        style="secondary",
                    ),
                    self._action("reset_closure", "Reset", "tool.reset", "Discard proposals and return to the main Cloth menu.", style="danger"),
                ),
            ),
        )

    def _draw_sections(self) -> tuple[visual.OverlayToolbarSectionSpec, ...]:
        state = self.workspace
        return (
            visual.OverlayToolbarSectionSpec(
                "draw_actions",
                "Draw · validate",
                actions=(
                    self._action("apply_draw", "Apply", "tool.apply", "Finish drawing. In Modify, selected technical faces become independent textile groups.", style="primary"),
                    self._action(
                        "draw_modify",
                        "Modify",
                        "sketch.modify",
                        "Select technical textile faces or edges. Apply separates selected faces into independent groups; Delete removes them.",
                        style="primary" if state.draw_mode is ClothDrawMode.MODIFY else "ghost",
                    ),
                    self._action(
                        "draw_line",
                        "Line",
                        "sketch.line",
                        "Draw one textile edge from two points.",
                        style="primary" if state.draw_mode is ClothDrawMode.LINE else "ghost",
                    ),
                    self._action(
                        "draw_polyline",
                        "Polyline",
                        "sketch.polyline",
                        "Draw an open or closed textile polyline. Closing creates a face automatically.",
                        style="primary" if state.draw_mode is ClothDrawMode.POLYLINE else "ghost",
                    ),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "draw_pick",
                "Pick",
                actions=(
                    self._action(
                        "draw_pick_faces",
                        "Faces",
                        "sketch.face",
                        "Select technical faces inside a group for deletion or separation.",
                        style="primary" if state.draw_pick_mode is ClothDrawPickMode.FACE else "ghost",
                    ),
                    self._action(
                        "draw_pick_edges",
                        "Edges",
                        "sketch.line",
                        "Modify individual textile edges without logical grouping.",
                        style="primary" if state.draw_pick_mode is ClothDrawPickMode.EDGE else "ghost",
                    ),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "draw_smart",
                "Smart",
                actions=(
                    self._action(
                        "toggle_smart_snap",
                        "Smart snap",
                        "tool.snap",
                        "Toggle Smart Snap for new points.",
                        style="primary" if state.smart_snap_enabled else "ghost",
                    ),
                    self._action(
                        "toggle_axis_guides",
                        "Axis guides",
                        "tool.axis",
                        "Toggle construction-axis guides.",
                        style="primary" if state.axis_guides_enabled else "ghost",
                    ),
                    self._action("clear_draw", "Clear", "tool.reset", "Cancel the current primitive and clear Draw selection.", style="danger"),
                ),
            ),
        )

    def _properties_sections(self) -> tuple[visual.OverlayToolbarSectionSpec, ...]:
        state = self.workspace
        selected = tuple(self.session.selected_patch_ids)
        functions = {
            self.session.document.patches[patch_id].function
            for patch_id in selected
            if patch_id in self.session.document.patches
        }
        enabled = state.can_set_properties
        return (
            visual.OverlayToolbarSectionSpec(
                "properties_apply",
                "Properties",
                actions=(
                    self._action("apply_properties", "Apply", "tool.apply", "Keep the assigned roles and return to Cloth.", style="primary"),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "properties_set",
                "Set",
                actions=(
                    self._action(
                        "set_function_textile",
                        "Textile",
                        "sketch.face",
                        "Set selected textile faces to the normal textile role.",
                        enabled=enabled,
                        style="primary" if functions == {ClothPatchFunction.TEXTILE} else "ghost",
                    ),
                    self._action(
                        "set_function_junction",
                        "Anchor",
                        "tool.link",
                        "Set selected textile faces to the anchoring/junction role.",
                        enabled=enabled,
                        style="primary" if functions == {ClothPatchFunction.JUNCTION} else "ghost",
                    ),
                    self._action(
                        "set_function_pattern",
                        "Pattern",
                        "tool.texture",
                        "Set selected textile faces to the decorative-pattern role.",
                        enabled=enabled,
                        style="primary" if functions == {ClothPatchFunction.PATTERN} else "ghost",
                    ),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "properties_selection",
                "Selection mode",
                actions=(
                    self._action(
                        "properties_select_face",
                        "Face",
                        "sketch.face",
                        "Select one technical textile face at a time.",
                        style="primary" if state.property_selection_mode is ClothPropertySelectionMode.FACE else "ghost",
                    ),
                    self._action(
                        "properties_select_group",
                        "Group",
                        "tool.select",
                        "Select exactly one persistent textile group; touching neighbours are never included.",
                        style="primary" if state.property_selection_mode is ClothPropertySelectionMode.GROUP else "ghost",
                    ),
                    self._action("reset_properties", "Reset", "tool.reset", "Clear the textile selection.", style="danger"),
                ),
            ),
        )

    def _sections(self, *, can_apply: bool, pending_count: int = 0) -> tuple[visual.OverlayToolbarSectionSpec, ...]:
        mode = self.workspace.overlay_mode
        if mode is ClothOverlayMode.CLOSE:
            return self._close_sections()
        if mode is ClothOverlayMode.DRAW:
            return self._draw_sections()
        if mode is ClothOverlayMode.PROPERTIES:
            return self._properties_sections()
        return self._main_sections(can_apply=can_apply, pending_count=pending_count)

    def sync_document(self, ctx: Any, *, can_apply: bool, pending_count: int, validation_report: Any | None) -> None:
        state = self.workspace
        title = {
            ClothOverlayMode.MAIN: "Cloth",
            ClothOverlayMode.CLOSE: "Cloth · Close",
            ClothOverlayMode.DRAW: "Cloth · Draw",
            ClothOverlayMode.PROPERTIES: "Cloth · Properties",
        }[state.overlay_mode]
        badge = {
            ClothOverlayMode.MAIN: "Selection",
            ClothOverlayMode.CLOSE: "Closure",
            ClothOverlayMode.DRAW: "Drawing",
            ClothOverlayMode.PROPERTIES: "Roles",
        }[state.overlay_mode]
        accent = {
            ClothOverlayMode.MAIN: "#38BDF8",
            ClothOverlayMode.CLOSE: "#F59E0B",
            ClothOverlayMode.DRAW: "#22C55E",
            ClothOverlayMode.PROPERTIES: "#A855F7",
        }[state.overlay_mode]
        status = self._status_text(validation_report, can_apply=can_apply)
        ctx.overlay.show_window(
            visual.build_command_deck_window(
                window_id=CLOTH_WORKFLOW_WINDOW_ID,
                owner_tool=self.owner_tool,
                group_id=_CLOTH_GROUP,
                sections=self._sections(can_apply=can_apply, pending_count=pending_count),
                active_mode_id="",
                badge_id="cloth.workflow.mode",
                badge_label="Mode",
                badge_value=badge,
                badge_tooltip="Current Cloth context. The same overlay changes content instead of opening another window.",
                status_id="cloth.workflow.status",
                status_label="Status",
                status_value=status,
                title=title,
                anchor="viewport_top_left",
                width_px=0,
                persistent=True,
                cursor_offset_px=(0, 0),
                accent_color=accent,
            )
        )
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import sync_creator_overlay_windows

                sync_creator_overlay_windows(owner, ctx)
            except Exception:
                pass

    def _status_text(self, report: Any | None, *, can_apply: bool) -> str:
        if report is not None and getattr(report, "errors", None) and not can_apply:
            return self._compact(str(report.errors[0].message))
        return self._compact(self.workspace.message)

    @staticmethod
    def _compact(value: str, *, limit: int = 112) -> str:
        text = " ".join(str(value).split())
        return text if len(text) <= limit else f"{text[: limit - 1].rstrip()}…"

    def hide(self, ctx: Any) -> None:
        try:
            ctx.overlay.hide_window(CLOTH_WORKFLOW_WINDOW_ID)
        except Exception:
            pass


__all__ = ["CLOTH_ACTION_PREFIX", "CLOTH_WORKFLOW_WINDOW_ID", "ClothWorkflowOverlay"]
