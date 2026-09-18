"""Shared handle visual styles for viewport tools.

Tools should choose a style id and semantic state, not hand-code hover/grab
colors in their own controllers. Keeping this logic here makes it much harder
for a new tool to rebuild every actor just to change a point visual state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Color = tuple[float, float, float, float]


class GizmoVisualState(str, Enum):
    FIXED = "fixed"
    GRABBABLE = "grabbable"
    HOVER = "hover"
    GRABBED = "grabbed"
    SELECTED = "selected"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class GizmoPointStyle:
    id: str
    label: str
    guide_shape: str
    fixed_color: Color
    grabbable_color: Color
    hover_color: Color
    grabbed_color: Color
    selected_color: Color
    disabled_color: Color = (0.45, 0.48, 0.52, 0.45)
    ring_color: Color = (0.08, 0.20, 0.46, 0.98)
    cross_color: Color = (0.44, 0.12, 0.04, 0.98)
    hover_radius_add_px: int = 5
    grabbed_radius_add_px: int = 8
    selected_radius_add_px: int = 4
    draw_core: bool = True
    min_radius_px: int | None = None
    geometry_dot: bool = False

    def color_for(self, state: GizmoVisualState | str) -> Color:
        if not isinstance(state, GizmoVisualState):
            state = GizmoVisualState(str(state)) if str(state) in GizmoVisualState._value2member_map_ else GizmoVisualState.GRABBABLE
        return {
            GizmoVisualState.FIXED: self.fixed_color,
            GizmoVisualState.GRABBABLE: self.grabbable_color,
            GizmoVisualState.HOVER: self.hover_color,
            GizmoVisualState.GRABBED: self.grabbed_color,
            GizmoVisualState.SELECTED: self.selected_color,
            GizmoVisualState.DISABLED: self.disabled_color,
        }[state]

    def radius_for(self, base_radius_px: int, state: GizmoVisualState | str) -> int:
        if not isinstance(state, GizmoVisualState):
            state = GizmoVisualState(str(state)) if str(state) in GizmoVisualState._value2member_map_ else GizmoVisualState.GRABBABLE
        extra = 0
        if state == GizmoVisualState.HOVER:
            extra = self.hover_radius_add_px
        elif state == GizmoVisualState.GRABBED:
            extra = self.grabbed_radius_add_px
        elif state == GizmoVisualState.SELECTED:
            extra = self.selected_radius_add_px
        radius = max(3, int(base_radius_px) + int(extra))
        if self.min_radius_px is not None:
            radius = max(radius, int(self.min_radius_px))
        return radius


DEFAULT_POINT_STYLES: dict[str, GizmoPointStyle] = {
    "solid": GizmoPointStyle(
        id="solid",
        label="Solid dot",
        guide_shape="none",
        fixed_color=(0.16, 0.23, 0.34, 0.98),
        grabbable_color=(0.00, 0.45, 0.82, 1.0),
        hover_color=(0.42, 0.10, 0.92, 1.0),
        grabbed_color=(0.93, 0.32, 0.04, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
    ),
    "ring": GizmoPointStyle(
        id="ring",
        label="Ring handle",
        guide_shape="ring",
        fixed_color=(0.18, 0.26, 0.38, 0.98),
        grabbable_color=(0.00, 0.51, 0.90, 1.0),
        hover_color=(0.48, 0.16, 0.94, 1.0),
        grabbed_color=(0.95, 0.36, 0.07, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.04, 0.22, 0.62, 0.98),
    ),
    "target": GizmoPointStyle(
        id="target",
        label="Target handle",
        guide_shape="target",
        fixed_color=(0.17, 0.25, 0.39, 0.98),
        grabbable_color=(0.00, 0.42, 0.92, 1.0),
        hover_color=(0.52, 0.14, 0.95, 1.0),
        grabbed_color=(0.96, 0.30, 0.03, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.04, 0.20, 0.56, 0.98),
        cross_color=(0.46, 0.09, 0.74, 0.98),
    ),
    "diamond": GizmoPointStyle(
        id="diamond",
        label="Diamond handle",
        guide_shape="diamond",
        fixed_color=(0.24, 0.23, 0.43, 0.98),
        grabbable_color=(0.43, 0.23, 0.92, 1.0),
        hover_color=(0.70, 0.16, 0.95, 1.0),
        grabbed_color=(0.95, 0.28, 0.09, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.23, 0.12, 0.58, 0.98),
    ),
    "square": GizmoPointStyle(
        id="square",
        label="Square handle",
        guide_shape="square",
        fixed_color=(0.16, 0.32, 0.28, 0.98),
        grabbable_color=(0.00, 0.56, 0.38, 1.0),
        hover_color=(0.00, 0.74, 0.58, 1.0),
        grabbed_color=(0.94, 0.34, 0.04, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.03, 0.38, 0.27, 0.98),
    ),
    "arrow": GizmoPointStyle(
        id="arrow",
        label="Arrow handle",
        guide_shape="arrow",
        fixed_color=(0.22, 0.26, 0.34, 0.98),
        grabbable_color=(0.02, 0.40, 0.76, 1.0),
        hover_color=(0.20, 0.16, 0.92, 1.0),
        grabbed_color=(0.96, 0.34, 0.03, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.04, 0.23, 0.54, 0.98),
        cross_color=(0.02, 0.33, 0.72, 0.98),
    ),
    "axis": GizmoPointStyle(
        id="axis",
        label="Axis handle",
        guide_shape="axis",
        fixed_color=(0.22, 0.29, 0.32, 0.98),
        grabbable_color=(0.00, 0.50, 0.64, 1.0),
        hover_color=(0.00, 0.66, 0.94, 1.0),
        grabbed_color=(0.93, 0.30, 0.04, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.02, 0.36, 0.46, 0.98),
        cross_color=(0.52, 0.10, 0.06, 0.98),
    ),
    "chevron": GizmoPointStyle(
        id="chevron",
        label="Chevron handle",
        guide_shape="chevron",
        fixed_color=(0.30, 0.25, 0.33, 0.98),
        grabbable_color=(0.62, 0.25, 0.74, 1.0),
        hover_color=(0.82, 0.18, 0.84, 1.0),
        grabbed_color=(0.97, 0.32, 0.05, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.42, 0.14, 0.52, 0.98),
        cross_color=(0.62, 0.15, 0.70, 0.98),
    ),
    "triad": GizmoPointStyle(
        id="triad",
        label="Triad handle",
        guide_shape="triad",
        fixed_color=(0.24, 0.28, 0.37, 0.98),
        grabbable_color=(0.10, 0.44, 0.68, 1.0),
        hover_color=(0.16, 0.58, 0.94, 1.0),
        grabbed_color=(0.96, 0.36, 0.05, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.04, 0.26, 0.50, 0.98),
        cross_color=(0.10, 0.44, 0.68, 0.98),
    ),
    "minimal": GizmoPointStyle(
        id="minimal",
        label="Minimal dot",
        # No guide geometry: minimal means one persistent point only.
        # The state feedback is carried by the point color and point size.
        guide_shape="none",
        fixed_color=(0.10, 0.15, 0.21, 0.98),
        grabbable_color=(0.00, 0.33, 0.72, 1.0),
        hover_color=(0.02, 0.78, 0.96, 1.0),
        grabbed_color=(1.00, 0.34, 0.02, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.08, 0.20, 0.35, 0.92),
        cross_color=(0.08, 0.22, 0.44, 0.92),
        hover_radius_add_px=1,
        grabbed_radius_add_px=2,
        selected_radius_add_px=1,
        draw_core=True,
        min_radius_px=None,
        geometry_dot=True,
    ),
    "translate_arrow": GizmoPointStyle(
        id="translate_arrow",
        label="Translate arrow",
        guide_shape="translate_axis",
        fixed_color=(0.24, 0.26, 0.30, 0.98),
        grabbable_color=(0.02, 0.45, 0.92, 1.0),
        hover_color=(0.02, 0.62, 1.00, 1.0),
        grabbed_color=(0.95, 0.30, 0.04, 1.0),
        selected_color=(0.94, 0.66, 0.02, 1.0),
        ring_color=(0.02, 0.24, 0.58, 0.98),
        cross_color=(0.00, 0.30, 0.78, 0.98),
    ),

}


def get_point_style(style_id: str | None) -> GizmoPointStyle:
    return DEFAULT_POINT_STYLES.get(str(style_id or "solid"), DEFAULT_POINT_STYLES["solid"])


def visual_state_for_flags(*, selectable: bool, hover: bool = False, grabbed: bool = False, selected: bool = False, visible: bool = True) -> GizmoVisualState:
    if not visible:
        return GizmoVisualState.DISABLED
    if grabbed:
        return GizmoVisualState.GRABBED
    if hover:
        return GizmoVisualState.HOVER
    if selected:
        return GizmoVisualState.SELECTED
    return GizmoVisualState.GRABBABLE if selectable else GizmoVisualState.FIXED
