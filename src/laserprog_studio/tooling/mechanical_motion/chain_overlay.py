# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .models import GearChainSpec, MechanicalMode
from .session import MechanicalSession

CHAIN_WINDOW_ID = "mechanical.motion.chain"
CHAIN_FIELD_PREFIX = "mechanical.motion.chain.field."
CHAIN_ACTION_PREFIX = "mechanical.motion.chain.action."

_FIELD_TO_PARAMETER = {
    "intermediate_shafts": ("chain_intermediate_shafts", int),
    "reduction": ("chain_reduction", float),
    "distribution": ("chain_distribution", float),
    "target_module": ("chain_target_module", float),
    "min_teeth": ("chain_min_teeth", int),
    "max_teeth": ("chain_max_teeth", int),
}


class MechanicalChainOverlay:
    """Floating numeric editor for the currently selected gear chain."""

    def __init__(self, owner_tool: str, session: MechanicalSession) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session

    def sync(self, ctx: Any) -> None:
        selected = self.session.assembly.selected_element()
        visible = isinstance(selected, GearChainSpec) and self.session.state.mode in {
            MechanicalMode.SELECT,
            MechanicalMode.EDIT_CURVE,
        }
        if not visible:
            try:
                ctx.overlay.hide_window(CHAIN_WINDOW_ID)
            except Exception:
                pass
            return
        chain = selected
        fields = [
            visual.OverlayFieldSpec(
                f"{CHAIN_FIELD_PREFIX}intermediate_shafts",
                "Intermediate shafts",
                str(int(chain.intermediate_shaft_count)),
                kind="number",
                tooltip="Number of shafts inserted between input and output.",
            ),
            visual.OverlayFieldSpec(
                f"{CHAIN_FIELD_PREFIX}reduction",
                "Requested reduction",
                f"{float(chain.total_reduction):.8g}",
                kind="number",
                tooltip="Requested total ratio, expressed as output reduction : 1.",
            ),
            visual.OverlayFieldSpec(
                f"{CHAIN_FIELD_PREFIX}distribution",
                "Ratio distribution",
                f"{float(chain.ratio_distribution):.8g}",
                kind="number",
                tooltip="-1 concentrates reduction near the input; +1 near the output.",
            ),
            visual.OverlayFieldSpec(
                f"{CHAIN_FIELD_PREFIX}target_module",
                "Target module (mm)",
                f"{float(chain.target_module_mm):.8g}",
                kind="number",
            ),
            visual.OverlayFieldSpec(
                f"{CHAIN_FIELD_PREFIX}min_teeth",
                "Minimum teeth",
                str(int(chain.min_teeth)),
                kind="number",
            ),
            visual.OverlayFieldSpec(
                f"{CHAIN_FIELD_PREFIX}max_teeth",
                "Maximum teeth",
                str(int(chain.max_teeth)),
                kind="number",
            ),
            visual.OverlayFieldSpec(
                "mechanical.motion.chain.actual",
                "Obtained ratio",
                f"{float(chain.actual_reduction):.8g}:1",
                kind="info",
            ),
            visual.OverlayFieldSpec(
                "mechanical.motion.chain.warning",
                "Solver",
                str(chain.warning or "No warning."),
                kind="info",
            ),
        ]
        buttons = [
            visual.ToolButtonSpec(
                f"{CHAIN_ACTION_PREFIX}edit_curve",
                "Edit curve",
                icon="sketch.arc",
                style="primary" if self.session.state.mode is MechanicalMode.EDIT_CURVE else "secondary",
            ),
            visual.ToolButtonSpec(
                f"{CHAIN_ACTION_PREFIX}rebuild",
                "Rebuild",
                icon="tool.preview",
                style="ghost",
            ),
        ]
        ctx.overlay.show_window(
            visual.OverlayWindowSpec(
                id=CHAIN_WINDOW_ID,
                title="Gear chain parameters",
                owner_tool=self.owner_tool,
                fields=fields,
                buttons=buttons,
                anchor="viewport_top_right",
                overlay_kind="inspector",
                width_px=320,
                movable=True,
                persistent=True,
                close_on_click_outside=False,
            )
        )

    @staticmethod
    def field_changed(field_id: str, value: str) -> tuple[str, Any] | None:
        raw = str(field_id or "")
        if not raw.startswith(CHAIN_FIELD_PREFIX):
            return None
        key = raw[len(CHAIN_FIELD_PREFIX):]
        target = _FIELD_TO_PARAMETER.get(key)
        if target is None:
            return None
        parameter_id, converter = target
        try:
            number = float(str(value).strip().replace(",", "."))
            parsed = int(round(number)) if converter is int else float(number)
        except Exception:
            return None
        return parameter_id, parsed

    @staticmethod
    def action_from_button(button_id: str) -> str | None:
        raw = str(button_id or "")
        return raw[len(CHAIN_ACTION_PREFIX):] if raw.startswith(CHAIN_ACTION_PREFIX) else None


__all__ = [
    "CHAIN_ACTION_PREFIX",
    "CHAIN_FIELD_PREFIX",
    "CHAIN_WINDOW_ID",
    "MechanicalChainOverlay",
]
