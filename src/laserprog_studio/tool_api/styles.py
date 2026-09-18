"""Public interaction and visual style catalog for creator tools.

Creator tools should choose semantic interaction policies and style ids from
this module instead of hard-coding colors, handle sizes or line payloads.  The
renderer remains free to implement these styles with cached glyphs, batched
linework or overlays without changing tool code.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from laserprog_studio.tool_core.gizmos.styles import DEFAULT_POINT_STYLES, GizmoPointStyle, GizmoVisualState, get_point_style, visual_state_for_flags
from laserprog_studio.tool_core.selection import ActorInteraction

Color = tuple[float, float, float, float]


class PointStyleId(str, Enum):
    """All native point/handle styles available to creator tools."""

    SOLID = "solid"
    RING = "ring"
    TARGET = "target"
    DIAMOND = "diamond"
    SQUARE = "square"
    ARROW = "arrow"
    AXIS = "axis"
    CHEVRON = "chevron"
    TRIAD = "triad"
    MINIMAL = "minimal"
    TRANSLATE_ARROW = "translate_arrow"


class LineStyleId(str, Enum):
    """Native linework styles for preview edges, guides and selected geometry."""

    SOLID = "solid"
    SELECTABLE = "selectable"
    GRABBABLE = "grabbable"
    HOVER = "hover"
    SELECTED = "selected"
    GRABBED = "grabbed"
    FIXED = "fixed"
    GUIDE = "guide"
    CONSTRUCTION = "construction"
    AXIS = "axis"
    PREVIEW = "preview"
    WARNING = "warning"
    ERROR = "error"


class InteractionVisualState(str, Enum):
    """Visual states an actor can request or inherit during interaction."""

    AUTO = "auto"
    FIXED = "fixed"
    GRABBABLE = "grabbable"
    HOVER = "hover"
    SELECTED = "selected"
    GRABBED = "grabbed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class LineVisualStyle:
    """Renderer-neutral line visual style.

    ``pattern`` is declarative only.  Current painters can ignore it when they
    only support solid batched linework; keeping it in the public contract lets
    future renderers add dashed/dotted guides without tool-code changes.
    """

    id: str
    label: str
    color: str
    width_px: float = 3.0
    pattern: str = "solid"
    opacity: float = 1.0

    def payload(self, *, selected: bool = False, hover: bool = False, grabbed: bool = False) -> dict[str, object]:
        width = float(self.width_px)
        if grabbed:
            width = max(width, 6.0)
        elif selected or hover:
            width = max(width, 5.0)
        return {
            "style_id": self.id,
            "color": self.color,
            "line_width": width,
            "pattern": self.pattern,
            "opacity": float(self.opacity),
        }


SELECTED_HIGHLIGHT_COLOR = "#f0a805"
MINIMAL_DOT_IDLE_RADIUS_PX = 2
MINIMAL_DOT_ACTIVE_RADIUS_PX = 3


DEFAULT_LINE_STYLES: dict[str, LineVisualStyle] = {
    "solid": LineVisualStyle("solid", "Solid line", "#2b5f8f", 3.0),
    "selectable": LineVisualStyle("selectable", "Selectable line", "#263445", 4.0),
    "grabbable": LineVisualStyle("grabbable", "Grabbable line", "#0b67aa", 4.0),
    "hover": LineVisualStyle("hover", "Hover line", "#7357ff", 5.0),
    "selected": LineVisualStyle("selected", "Selected line", SELECTED_HIGHLIGHT_COLOR, 6.0),
    "grabbed": LineVisualStyle("grabbed", "Grabbed line", "#e85f18", 7.0),
    "fixed": LineVisualStyle("fixed", "Fixed/reference line", "#8b98a8", 3.0),
    "guide": LineVisualStyle("guide", "Snap guide", "#34a0a4", 2.0, pattern="dashed", opacity=0.9),
    "construction": LineVisualStyle("construction", "Construction line", "#65758b", 2.0, pattern="dotted", opacity=0.8),
    "axis": LineVisualStyle("axis", "Axis line", "#0e7490", 3.0),
    "preview": LineVisualStyle("preview", "Preview line", "#2563eb", 3.0, opacity=0.85),
    "warning": LineVisualStyle("warning", "Warning line", "#d97706", 5.0),
    "error": LineVisualStyle("error", "Error line", "#dc2626", 5.0),
}


@dataclass(frozen=True, slots=True)
class ActorVisualSpec:
    """Resolved visual recipe for a creator ToolActor."""

    point_style_id: str
    line_style_id: str
    visual_state: InteractionVisualState
    point_style: GizmoPointStyle
    line_style: LineVisualStyle
    point_color: Color
    radius_px: int
    line_payload: dict[str, object]


def normalize_point_style(style_id: str | PointStyleId | None) -> str:
    raw = style_id.value if isinstance(style_id, PointStyleId) else str(style_id or PointStyleId.SOLID.value)
    return raw if raw in DEFAULT_POINT_STYLES else PointStyleId.SOLID.value


def normalize_line_style(style_id: str | LineStyleId | None) -> str:
    raw = style_id.value if isinstance(style_id, LineStyleId) else str(style_id or LineStyleId.SOLID.value)
    return raw if raw in DEFAULT_LINE_STYLES else LineStyleId.SOLID.value


def normalize_visual_state(state: str | InteractionVisualState | GizmoVisualState | None) -> InteractionVisualState:
    if isinstance(state, InteractionVisualState):
        return state
    if isinstance(state, GizmoVisualState):
        return InteractionVisualState(state.value)
    raw = str(state or InteractionVisualState.AUTO.value)
    return InteractionVisualState(raw) if raw in InteractionVisualState._value2member_map_ else InteractionVisualState.AUTO


def list_point_styles() -> tuple[GizmoPointStyle, ...]:
    """Return all native point styles in stable display order."""

    return tuple(DEFAULT_POINT_STYLES[key] for key in PointStyleId._value2member_map_ if key in DEFAULT_POINT_STYLES)


def list_line_styles() -> tuple[LineVisualStyle, ...]:
    """Return all native line styles in stable display order."""

    return tuple(DEFAULT_LINE_STYLES[key] for key in LineStyleId._value2member_map_ if key in DEFAULT_LINE_STYLES)


def point_style_choices() -> tuple[tuple[str, str], ...]:
    return tuple((style.id, style.label) for style in list_point_styles())


def line_style_choices() -> tuple[tuple[str, str], ...]:
    return tuple((style.id, style.label) for style in list_line_styles())


def interaction_choices() -> tuple[tuple[str, str], ...]:
    return tuple((interaction.value, interaction.value.title()) for interaction in ActorInteraction)


def visual_state_choices(*, include_auto: bool = True) -> tuple[tuple[str, str], ...]:
    values: Iterable[InteractionVisualState] = InteractionVisualState if include_auto else tuple(state for state in InteractionVisualState if state is not InteractionVisualState.AUTO)
    return tuple((state.value, state.value.replace("_", " ").title()) for state in values)


def point_style(style_id: str | PointStyleId | None) -> GizmoPointStyle:
    return get_point_style(normalize_point_style(style_id))


def line_style(style_id: str | LineStyleId | None) -> LineVisualStyle:
    return DEFAULT_LINE_STYLES[normalize_line_style(style_id)]


def visual_state_for_interaction(
    interaction: str | ActorInteraction,
    *,
    hover: bool = False,
    selected: bool = False,
    grabbed: bool = False,
    visible: bool = True,
    forced: str | InteractionVisualState | None = None,
) -> InteractionVisualState:
    """Resolve the visual state for an actor from interaction flags."""

    forced_state = normalize_visual_state(forced)
    if forced_state is not InteractionVisualState.AUTO:
        return forced_state
    if not visible:
        return InteractionVisualState.DISABLED
    if grabbed:
        return InteractionVisualState.GRABBED
    if hover:
        return InteractionVisualState.HOVER
    if selected:
        return InteractionVisualState.SELECTED
    raw = interaction.value if isinstance(interaction, ActorInteraction) else str(interaction)
    return InteractionVisualState.GRABBABLE if raw == ActorInteraction.GRABBABLE.value else InteractionVisualState.FIXED


def as_gizmo_visual_state(state: str | InteractionVisualState | GizmoVisualState) -> GizmoVisualState:
    resolved = normalize_visual_state(state)
    if resolved is InteractionVisualState.AUTO:
        resolved = InteractionVisualState.GRABBABLE
    return GizmoVisualState(resolved.value)


def resolve_actor_visual(
    *,
    interaction: str | ActorInteraction,
    point_style_id: str | PointStyleId | None = None,
    line_style_id: str | LineStyleId | None = None,
    visual_state: str | InteractionVisualState | None = None,
    base_radius_px: int = 11,
    hover: bool = False,
    selected: bool = False,
    grabbed: bool = False,
    visible: bool = True,
) -> ActorVisualSpec:
    """Resolve all visual data an actor renderer needs without hard-coded colors."""

    resolved_state = visual_state_for_interaction(interaction, hover=hover, selected=selected, grabbed=grabbed, visible=visible, forced=visual_state)
    forced_state = normalize_visual_state(visual_state)
    # Runtime interaction feedback is a locked Creator API contract.  A tool may
    # request a baseline visual state, but it must not be able to hide native
    # selected/grabbed feedback by forcing "grabbable" or "fixed".  Disabled
    # remains authoritative; otherwise hover/selected/grabbed are overlaid by
    # the API runtime before the renderer receives colors.
    if visible and forced_state is not InteractionVisualState.DISABLED:
        if grabbed:
            resolved_state = InteractionVisualState.GRABBED
        elif hover:
            resolved_state = InteractionVisualState.HOVER
        elif selected:
            resolved_state = InteractionVisualState.SELECTED
    point_id = normalize_point_style(point_style_id)
    line_id = normalize_line_style(line_style_id)
    p_style = point_style(point_id)
    l_style = line_style(line_id)
    # Runtime interaction flags are semantic and should be immediately visible.
    # Keep ``line_style_id`` as the creator-requested base style for API
    # stable saved-value semantics, but render actual selected/hover/grabbed linework with the
    # shared interaction palette.  This gives all selected elements the same
    # yellow/orange feedback as the minimal dot without forcing creators to
    # choose the selected style manually.
    payload_style = l_style
    if grabbed:
        payload_style = line_style(LineStyleId.GRABBED.value)
    elif selected:
        payload_style = line_style(LineStyleId.SELECTED.value)
    elif hover:
        payload_style = line_style(LineStyleId.HOVER.value)
    gizmo_state = as_gizmo_visual_state(resolved_state)
    if point_id == PointStyleId.MINIMAL.value:
        # Minimal dot is intentionally tiny and pixel-exact: 2 px idle,
        # 3 px for hover/selected/grabbed.  Do not apply the generic
        # handle base radius here; that path is for larger guide handles.
        active_state = resolved_state in {
            InteractionVisualState.HOVER,
            InteractionVisualState.SELECTED,
            InteractionVisualState.GRABBED,
        } or hover or selected or grabbed
        radius_px = MINIMAL_DOT_ACTIVE_RADIUS_PX if active_state else MINIMAL_DOT_IDLE_RADIUS_PX
    else:
        radius_px = p_style.radius_for(int(base_radius_px), gizmo_state)
    return ActorVisualSpec(
        point_style_id=point_id,
        line_style_id=line_id,
        visual_state=resolved_state,
        point_style=p_style,
        line_style=payload_style,
        point_color=p_style.color_for(gizmo_state),
        radius_px=radius_px,
        line_payload=payload_style.payload(selected=selected or resolved_state is InteractionVisualState.SELECTED, hover=hover or resolved_state is InteractionVisualState.HOVER, grabbed=grabbed or resolved_state is InteractionVisualState.GRABBED),
    )


__all__ = [
    "ActorVisualSpec",
    "Color",
    "DEFAULT_LINE_STYLES",
    "InteractionVisualState",
    "LineStyleId",
    "LineVisualStyle",
    "MINIMAL_DOT_ACTIVE_RADIUS_PX",
    "MINIMAL_DOT_IDLE_RADIUS_PX",
    "SELECTED_HIGHLIGHT_COLOR",
    "PointStyleId",
    "as_gizmo_visual_state",
    "interaction_choices",
    "line_style",
    "line_style_choices",
    "list_line_styles",
    "list_point_styles",
    "normalize_line_style",
    "normalize_point_style",
    "normalize_visual_state",
    "point_style",
    "point_style_choices",
    "resolve_actor_visual",
    "visual_state_choices",
    "visual_state_for_interaction",
]
