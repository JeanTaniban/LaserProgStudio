"""Contextual fold/cut editor for the Cloth flat pattern."""
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .interaction import ClothInteractionState
from .models import ClothCurveKind, ClothSession
from .pattern_edges import analyze_pattern, pattern_edge_state, would_create_fold_cycle

CLOTH_PATTERN_WINDOW_ID = "cloth.pattern_edges"
CLOTH_PATTERN_ACTION_PREFIX = "cloth.pattern.action."
_PATTERN_OPERATION_GROUP = "cloth.pattern.operation"


class ClothPatternEdgeOverlay:
    def __init__(self, owner_tool: str, session: ClothSession, interaction: ClothInteractionState) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session
        self.interaction = interaction

    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        value = str(button_id or "")
        if value.startswith(CLOTH_PATTERN_ACTION_PREFIX):
            return value[len(CLOTH_PATTERN_ACTION_PREFIX) :]
        return None

    @staticmethod
    def _mode(action: str, label: str, icon: str, tooltip: str, *, enabled: bool = True) -> visual.OverlayModeSpec:
        return visual.OverlayModeSpec(
            id=f"{CLOTH_PATTERN_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            display_label=label,
            slot_width_px=max(66, min(94, len(label) * 8 + 24)),
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
            id=f"{CLOTH_PATTERN_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            tooltip=tooltip,
            enabled=bool(enabled),
            style=style,  # type: ignore[arg-type]
            display_label=label,
            slot_width_px=max(62, min(110, len(label) * 8 + 24)),
        )

    def sync(self, ctx: Any) -> None:
        document = self.session.document
        selected_curve_id = self.interaction.selected_pattern_curve_id
        selected = None
        if selected_curve_id is not None:
            try:
                selected = pattern_edge_state(document, selected_curve_id)
            except Exception:
                selected = None
        operation = self.interaction.pattern_operation if self.interaction.pattern_operation in {"fold", "cut"} else "fold"
        can_fold = bool(selected is not None and selected.can_fold)
        has_selection = selected is not None
        analysis = analyze_pattern(document)
        prospective_cycle = bool(has_selection and operation == "fold" and would_create_fold_cycle(document, selected.curve_id))
        selected_cycle = bool(selected is not None and selected.fold_id in analysis.cycle_fold_ids)
        fold_blocked = prospective_cycle or selected_cycle

        sections = (
            visual.OverlayToolbarSectionSpec(
                "kind",
                "Edge role",
                modes=(
                    self._mode(
                        "operation_fold",
                        "Fold",
                        "tool.rotate",
                        "Keep both panels linked in the flat pattern and define their 3D fold angle.",
                        enabled=selected is None or can_fold,
                    ),
                    self._mode(
                        "operation_cut",
                        "Cut",
                        "tool.clear",
                        "Separate the adjacent panels in the flat pattern while preserving the folded 3D surface.",
                    ),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "angle",
                "Fold angle",
                actions=(
                    self._action("angle_minus_90", "−90°", "tool.rotate", "Set a 90° mountain fold.", enabled=has_selection and operation == "fold" and can_fold and not fold_blocked),
                    self._action("angle_flat", "Flat", "view.top", "Set the selected fold to 0°.", enabled=has_selection and operation == "fold" and can_fold and not fold_blocked),
                    self._action("angle_plus_90", "+90°", "tool.rotate", "Set a 90° valley fold.", enabled=has_selection and operation == "fold" and can_fold and not fold_blocked),
                    self._action("invert_angle", "Invert", "transform.rotate", "Reverse the fold direction.", enabled=has_selection and operation == "fold" and can_fold and not fold_blocked),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "pattern",
                "Pattern help",
                actions=(
                    self._action(
                        "auto_cut_cycles",
                        "Fix cycles",
                        "tool.clear",
                        "Convert only cycle-closing fold relations into cuts so the pattern can unfold.",
                        enabled=bool(analysis.cycle_fold_ids),
                        style="primary" if analysis.cycle_fold_ids else "ghost",
                    ),
                ),
            ),
            visual.OverlayToolbarSectionSpec(
                "commit",
                "Validation",
                actions=(
                    self._action(
                        "apply_edge",
                        "Apply edge",
                        "tool.apply",
                        "Validate the selected fold or cut and keep editing other pattern edges.",
                        enabled=has_selection and not fold_blocked and (operation == "cut" or can_fold),
                        style="primary",
                    ),
                    self._action("clear_edge", "Clear", "tool.reset", "Clear the current unvalidated edge selection.", enabled=has_selection),
                    self._action("done", "Done", "tool.close", "Finish pattern-edge editing and return to Modify.", enabled=True),
                ),
            ),
        )

        if selected is None:
            status = (
                f"Select a shared panel edge · {analysis.fold_count} fold(s), {analysis.cut_count} cut(s), "
                f"{analysis.component_count} pattern component(s)"
            )
        elif prospective_cycle:
            status = "This fold would close a cycle. Cut another edge in the loop before applying it."
        elif selected_cycle and operation == "fold":
            status = "This existing fold belongs to a cycle. Use Fix cycles or convert this edge to Cut."
        elif operation == "cut":
            status = "Cut preview · adjacent panels will become separate flat-pattern components."
        else:
            curve = document.curves[selected.curve_id]
            label = "straight" if curve.kind is ClothCurveKind.LINE else "curved"
            status = (
                f"Fold preview · {label} shared edge · angle {self.interaction.pattern_angle_degrees:.1f}° · "
                f"radius {self.interaction.pattern_radius_mm:.3g} mm"
            )

        active = f"{CLOTH_PATTERN_ACTION_PREFIX}operation_{operation}"
        window = visual.build_command_deck_window(
            window_id=CLOTH_PATTERN_WINDOW_ID,
            owner_tool=self.owner_tool,
            group_id=_PATTERN_OPERATION_GROUP,
            sections=sections,
            active_mode_id=active,
            badge_id="cloth.pattern.role",
            badge_label="Role",
            badge_value="Fold" if operation == "fold" else "Cut",
            badge_tooltip="How the selected shared edge behaves in the flat pattern.",
            status_id="cloth.pattern.status",
            status_label="Pattern",
            status_value=status,
            title="Cloth · Fold & Cut Pattern",
            anchor="viewport_top_right",
            width_px=0,
            persistent=True,
            cursor_offset_px=(0, 0),
        )
        ctx.overlay.show_window(window)
        try:
            ctx.overlay.set_group_active(_PATTERN_OPERATION_GROUP, active)
        except Exception:
            pass

    def hide(self, ctx: Any) -> None:
        try:
            ctx.overlay.hide_window(CLOTH_PATTERN_WINDOW_ID)
        except Exception:
            pass


__all__ = [
    "CLOTH_PATTERN_ACTION_PREFIX",
    "CLOTH_PATTERN_WINDOW_ID",
    "ClothPatternEdgeOverlay",
]
