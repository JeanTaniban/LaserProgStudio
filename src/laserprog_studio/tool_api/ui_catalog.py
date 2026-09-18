"""Official Creator UI vocabulary exposed to tool authors.

This module is the single public catalog for optimized viewport/UI motifs.
New tools should choose actor kinds, interactions, visual states, point styles,
line styles, manipulators, preview primitives and overlays from here instead of
copying ad-hoc GUI code from diagnostic tools or old controllers.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from laserprog_studio.tool_core.preview import PreviewKind
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind

from .styles import InteractionVisualState, list_line_styles, list_point_styles


class CreatorUiFamilyId(str, Enum):
    """Stable ids for the public Creator UI families."""

    ACTOR_KINDS = "actor_kinds"
    ACTOR_INTERACTIONS = "actor_interactions"
    VISUAL_STATES = "visual_states"
    POINT_STYLES = "point_styles"
    LINE_STYLES = "line_styles"
    MANIPULATORS = "manipulators"
    PREVIEWS = "previews"
    OVERLAYS = "overlays"


@dataclass(frozen=True, slots=True)
class CreatorUiItem:
    """One public UI/gizmo capability exposed by the Creator API."""

    id: str
    label: str
    description: str
    api: str
    recommended_for: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatorUiFamily:
    """A coherent family of optimized Creator UI primitives."""

    id: str
    label: str
    description: str
    api_entrypoint: str
    items: tuple[CreatorUiItem, ...]


@dataclass(frozen=True, slots=True)
class ToolUiRecommendation:
    """Recommended public motifs for a common tool category."""

    tool_id: str
    purpose: str
    actor_kinds: tuple[str, ...]
    interactions: tuple[str, ...]
    point_styles: tuple[str, ...]
    line_styles: tuple[str, ...]
    manipulators: tuple[str, ...] = ()
    overlays: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatorUiDirectionLayer:
    """One layer in the official Creator UI ownership model.

    The purpose of this small public object is documentation and tests: it keeps
    the intended boundary between Tool Core Analysis, the public API and the
    built-in Gizmo catalog explicit instead of relying on tribal knowledge.
    """

    id: str
    title: str
    responsibility: str
    not_responsible_for: str
    public_entrypoint: str


_CREATOR_UI_DIRECTION_LAYERS: tuple[CreatorUiDirectionLayer, ...] = (
    CreatorUiDirectionLayer(
        id="tool_core_analysis",
        title="Tool Core Analysis",
        responsibility=(
            "Laboratory and visual reference for optimized viewport UI: actor rendering, handle shapes, "
            "preview primitives, overlay behavior and stress/regression scenes."
        ),
        not_responsible_for=(
            "Being imported by creator tools or by built-in tools as an internal shortcut."
        ),
        public_entrypoint="reference only; extract approved motifs into laserprog_studio.tool_api",
    ),
    CreatorUiDirectionLayer(
        id="ui_catalog",
        title="tool_api.ui_catalog",
        responsibility=(
            "Metadata/vocabulary layer: stable family ids, labels, descriptions, recommendations and docs."
        ),
        not_responsible_for="Drawing a scene or constructing handles/previews.",
        public_entrypoint="iter_creator_ui_families(), recommendations_for_tool(), creator_ui_catalog_markdown()",
    ),
    CreatorUiDirectionLayer(
        id="ui_motifs",
        title="tool_api.ui_motifs",
        responsibility=(
            "Executable motif layer extracted from Tool Core Analysis. It builds the official actors, handles, "
            "previews and overlays that the catalog and tool authors can reuse."
        ),
        not_responsible_for="Experimenting with one-off visuals or tool-local GUI inventions.",
        public_entrypoint="build_creator_ui_motifs() for catalog/diagnostics; CreatorTool + actors.* for normal tools; native runtime owns refresh paths",
    ),
    CreatorUiDirectionLayer(
        id="gizmo_catalog_tool",
        title="Gizmo catalog tool",
        responsibility=(
            "Viewer/reference tool. It calls the public UI motif API and exposes Tool-panel visibility toggles."
        ),
        not_responsible_for="Creating its own sample scene, alternate handle styles or custom PyVista/Qt UI.",
        public_entrypoint="tool id: gizmo_catalog",
    ),
    CreatorUiDirectionLayer(
        id="creator_viewport_renderer",
        title="Creator viewport renderer",
        responsibility=(
            "Rendering the public motifs with the shared Tool Core Analysis painter so Creator tools and the "
            "diagnostic reference look the same. It also applies axis-locked camera orientation and field-of-view "
            "scaling after camera moves."
        ),
        not_responsible_for="Changing the public vocabulary, hiding missing API primitives or making tools compute camera-facing GUI axes.",
        public_entrypoint="automatic through CreatorStudioToolAdapter; application.creator_viewport_ui for host renderer bridges",
    ),
)


_POINT_STYLE_DESCRIPTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "solid": ("Default filled point handle for simple draggable anchors.", ("simple anchors", "single handles")),
    "ring": ("Circular handle optimized for rotation and angular interactions.", ("rotation", "angle handles")),
    "target": ("Target marker for snapping, face anchors and active picks.", ("snap points", "active picks")),
    "diamond": ("Diamond handle for corners, bounds and precise grips.", ("box bounds", "corner edits")),
    "square": ("Square handle for scale or rectangular edits.", ("scale", "rectangular edits")),
    "arrow": ("Directional arrow-like handle for constrained movement.", ("directional move",)),
    "axis": ("Axis-aligned handle for normals and single-axis edits.", ("normal edit", "axis constraint")),
    "chevron": ("Directional chevron for flow or waypoint editing.", ("waypoints", "flow")),
    "triad": ("Compact local XYZ triad handle style.", ("local axes", "orientation")),
    "minimal": ("Tiny dense-point style: 2 px idle, 3 px active, for optimized vertex clouds.", ("dense sketches", "vertex clouds")),
    "translate_arrow": ("Production translation-axis handle style used by optimized transform actors.", ("translation", "axis movement")),
}

_LINE_STYLE_DESCRIPTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "solid": ("Default linework style.", ("generic geometry",)),
    "selectable": ("Linework that can be selected but not moved directly.", ("selectable edges",)),
    "grabbable": ("Linework representing movable/drag-enabled geometry.", ("draggable geometry",)),
    "hover": ("Transient hover feedback; normally selected automatically by the renderer.", ("runtime feedback",)),
    "selected": ("Selection highlight; normally selected automatically by the renderer.", ("runtime feedback",)),
    "grabbed": ("Active drag feedback; normally selected automatically by the renderer.", ("runtime feedback",)),
    "fixed": ("Reference or locked geometry.", ("reference", "locked geometry")),
    "guide": ("Snap guide or helper construction guide.", ("snap guides",)),
    "construction": ("Dotted/dim construction line for non-output geometry.", ("construction geometry",)),
    "axis": ("Axis line for transform, normal or orientation previews.", ("axes", "normals")),
    "preview": ("Temporary preview line before applying a command.", ("command preview",)),
    "warning": ("Warning state linework.", ("validation warnings",)),
    "error": ("Error state linework.", ("validation errors",)),
}

_MANIPULATOR_ITEMS: tuple[CreatorUiItem, ...] = (
    CreatorUiItem("translate", "Translate", "XYZ movement manipulator with optimized axis handles.", "ctx.gizmos.translate(...)", ("move tools", "extrude height")),
    CreatorUiItem("rotate", "Rotate", "Ring-style rotation manipulator.", "ctx.gizmos.rotate(...)", ("rotation tools", "angle edit")),
    CreatorUiItem("scale", "Scale", "Axis and uniform scale grips using shared square handles.", "ctx.gizmos.scale(...)", ("scale tools", "bounds edit")),
    CreatorUiItem("plane", "Plane", "Origin + normal handles for cut/projection planes.", "ctx.gizmos.plane(...)", ("split plane", "projection")),
    CreatorUiItem("triad", "Triad", "Compact XYZ manipulator based on the translate handle policy.", "ctx.gizmos.triad(...)", ("orientation", "local axes")),
    CreatorUiItem("box_bounds", "Box bounds", "Corner handles for axis-aligned bounds.", "ctx.gizmos.box_bounds(...)", ("bounding boxes", "scale bounds")),
)

_OVERLAY_ITEMS: tuple[CreatorUiItem, ...] = (
    CreatorUiItem("palette", "Palette", "Persistent compact tool palette.", "ctx.overlay.show_window(..., overlay_kind='palette')", ("mode palettes",)),
    CreatorUiItem("popover", "Popover", "Small contextual window near the cursor.", "ctx.overlay.show_popover_at_cursor(...)", ("contextual commands",)),
    CreatorUiItem("tooltip", "Tooltip", "Non-editable contextual help.", "ctx.overlay.show_tooltip(...)", ("hover help",)),
    CreatorUiItem("inspector", "Inspector", "Floating mini inspector for numeric/input-heavy tools.", "OverlayWindowSpec(overlay_kind='inspector')", ("mini inspectors",)),
    CreatorUiItem("context_menu", "Context menu", "Click-away contextual command menu.", "ctx.overlay.show_context_popover_at_cursor(...)", ("right-click menus",)),
    CreatorUiItem("modal", "Modal", "Blocking confirmation/details window for rare destructive actions.", "OverlayWindowSpec(modal=True)", ("confirmations",)),
)

_TOOL_UI_RECOMMENDATIONS: tuple[ToolUiRecommendation, ...] = (
    ToolUiRecommendation(
        tool_id="plan_tracer",
        purpose="2D sketching, point editing and closed profile construction.",
        actor_kinds=("point", "line", "polyline"),
        interactions=("grabbable", "selectable", "fixed"),
        point_styles=("minimal", "target", "ring", "solid"),
        line_styles=("preview", "guide", "construction", "selected"),
        overlays=("palette", "inspector", "tooltip"),
        notes=("Use minimal for dense vertices.", "Use target for active snap points instead of custom snap glyphs."),
    ),
    ToolUiRecommendation(
        tool_id="transform_translate",
        purpose="Move selected objects or sketch points along world/local axes.",
        actor_kinds=("point", "line"),
        interactions=("grabbable", "selectable"),
        point_styles=("translate_arrow", "axis", "triad", "solid"),
        line_styles=("axis", "preview", "selected", "grabbed"),
        manipulators=("translate", "triad"),
        overlays=("inspector", "palette"),
    ),
    ToolUiRecommendation(
        tool_id="transform_rotate",
        purpose="Rotate selection around local/world axes.",
        actor_kinds=("point", "arc", "circle"),
        interactions=("grabbable", "selectable"),
        point_styles=("ring", "target", "triad"),
        line_styles=("axis", "preview", "guide", "selected"),
        manipulators=("rotate", "triad"),
        overlays=("inspector",),
    ),
    ToolUiRecommendation(
        tool_id="transform_scale",
        purpose="Scale handles and local bounding-box grips.",
        actor_kinds=("point", "line", "polyline"),
        interactions=("grabbable", "selectable"),
        point_styles=("square", "diamond", "axis"),
        line_styles=("preview", "guide", "selected"),
        manipulators=("scale", "box_bounds"),
        overlays=("inspector",),
    ),
    ToolUiRecommendation(
        tool_id="extrude",
        purpose="Extrude a selected 2D face or mesh profile.",
        actor_kinds=("point", "line", "polyline"),
        interactions=("grabbable", "selectable", "fixed"),
        point_styles=("translate_arrow", "target", "minimal"),
        line_styles=("preview", "axis", "guide", "warning"),
        manipulators=("translate", "plane"),
        overlays=("inspector", "popover"),
    ),
    ToolUiRecommendation(
        tool_id="split_plane",
        purpose="Move and orient a cutting plane.",
        actor_kinds=("point", "line", "polyline"),
        interactions=("grabbable", "selectable"),
        point_styles=("axis", "translate_arrow", "ring", "target"),
        line_styles=("axis", "preview", "guide"),
        manipulators=("plane", "translate", "rotate"),
        overlays=("inspector",),
    ),
    ToolUiRecommendation(
        tool_id="texture_projector",
        purpose="Move, scale and rotate projected textures and masks.",
        actor_kinds=("point", "line", "circle"),
        interactions=("grabbable", "selectable"),
        point_styles=("square", "ring", "target"),
        line_styles=("preview", "axis", "guide", "selected"),
        manipulators=("translate", "rotate", "scale"),
        overlays=("inspector", "palette"),
    ),
    ToolUiRecommendation(
        tool_id="selection",
        purpose="Hover, selection, delete and object inspection.",
        actor_kinds=("point", "line", "circle", "arc", "polyline"),
        interactions=("selectable", "grabbable"),
        point_styles=("solid", "minimal", "target"),
        line_styles=("hover", "selected", "grabbed", "fixed"),
        overlays=("context_menu", "tooltip"),
        notes=("Let resolve_actor_visual choose hover/selected/grabbed feedback instead of hard-coding colors.",),
    ),
)


def _title(value: str) -> str:
    return str(value).replace("_", " ").title()


def _actor_kind_items() -> tuple[CreatorUiItem, ...]:
    descriptions = {
        "point": "Single anchor, grab point or snap point.",
        "line": "Segment actor with shared hit-testing and selection.",
        "circle": "Circle actor represented by center and radius point.",
        "arc": "Curved actor represented by a sampled point chain.",
        "polyline": "Multi-segment actor for paths, outlines and sketch chains.",
    }
    return tuple(
        CreatorUiItem(
            kind.value,
            _title(kind.value),
            descriptions.get(kind.value, "Custom owner-specific actor kind for advanced adapters."),
            f"actors.{kind.value}(...)" if kind.value != "custom" else "actors.make_actor(kind=\"custom\", ...)",
        )
        for kind in ActorKind
    )


def _actor_interaction_items() -> tuple[CreatorUiItem, ...]:
    descriptions = {
        "fixed": "Visible reference only; not selectable or draggable.",
        "selectable": "Can be selected and box-selected but not moved by drag.",
        "grabbable": "Can be selected and moved with shared grab logic.",
    }
    return tuple(
        CreatorUiItem(interaction.value, _title(interaction.value), descriptions[interaction.value], f"interaction={interaction.value!r}")
        for interaction in ActorInteraction
    )


def _visual_state_items() -> tuple[CreatorUiItem, ...]:
    descriptions = {
        "auto": "Let the renderer resolve the state from interaction/hover/selection flags.",
        "fixed": "Reference/locked state.",
        "grabbable": "Idle grabbable state.",
        "hover": "Pointer-over feedback.",
        "selected": "Selection feedback.",
        "grabbed": "Active drag feedback.",
        "disabled": "Visible but inactive/disabled feedback.",
    }
    return tuple(
        CreatorUiItem(state.value, _title(state.value), descriptions[state.value], f"visual_state={state.value!r}")
        for state in InteractionVisualState
    )


def _point_style_items() -> tuple[CreatorUiItem, ...]:
    items: list[CreatorUiItem] = []
    for style in list_point_styles():
        description, recommended_for = _POINT_STYLE_DESCRIPTIONS.get(style.id, ("Point handle style.", ()))
        items.append(
            CreatorUiItem(
                style.id,
                style.label,
                description,
                f"actors.point(..., point_style={style.id!r}) / GizmoHandle(style_id={style.id!r})",
                recommended_for,
            )
        )
    return tuple(items)


def _line_style_items() -> tuple[CreatorUiItem, ...]:
    items: list[CreatorUiItem] = []
    for style in list_line_styles():
        description, recommended_for = _LINE_STYLE_DESCRIPTIONS.get(style.id, ("Line visual style.", ()))
        items.append(
            CreatorUiItem(
                style.id,
                style.label,
                description,
                f"actors.line(..., line_style={style.id!r}) / styles.line_style({style.id!r})",
                recommended_for,
            )
        )
    return tuple(items)


def _preview_items() -> tuple[CreatorUiItem, ...]:
    api_names = {
        PreviewKind.LINE: "show_line",
        PreviewKind.POLYLINE: "show_polyline",
        PreviewKind.ARC: "show_arc",
        PreviewKind.CIRCLE: "show_circle",
        PreviewKind.FACE: "show_face",
        PreviewKind.MESH: "show_mesh",
        PreviewKind.TEXT: "show_text",
    }
    descriptions = {
        "line": "Simple segment preview.",
        "polyline": "Multi-segment sketch or contour preview.",
        "arc": "Curved angular preview.",
        "circle": "Closed circular preview.",
        "face": "Temporary face/profile preview.",
        "mesh": "Temporary mesh preview.",
        "text": "Viewport text annotation.",
    }
    return tuple(
        CreatorUiItem(kind.value, _title(kind.value), descriptions[kind.value], f"ctx.preview.{api_names[kind]}(...)")
        for kind in PreviewKind
    )


def _overlay_kind_values() -> tuple[str, ...]:
    # OverlayKind is a Literal alias at runtime, so keep the official values in
    # one function and assert the catalog against them in tests.
    return ("palette", "popover", "tooltip", "inspector", "modal", "context_menu")


def overlay_kind_choices() -> tuple[tuple[str, str], ...]:
    """Return public overlay kinds as inspector-friendly choices."""

    return tuple((value, _title(value)) for value in _overlay_kind_values())


def creator_ui_direction_layers() -> tuple[CreatorUiDirectionLayer, ...]:
    """Return the official Creator UI responsibility boundaries.

    This is intentionally part of the public API because external tool authors
    need to know where visual motifs are allowed to come from.
    """

    return _CREATOR_UI_DIRECTION_LAYERS


def creator_ui_direction_markdown() -> str:
    """Return Markdown that documents the official Creator UI direction.

    The text is generated from structured public data so tests and docs can keep
    the architecture rule stable: Tool Core Analysis validates visuals, the
    Creator API exposes approved motifs, and the Gizmo catalog only displays
    those motifs.
    """

    lines = [
        "# Creator UI direction",
        "",
        "Source of truth flow:",
        "",
        "```text",
        "Tool Core Analysis -> tool_api.ui_catalog / tool_api.ui_motifs -> Gizmo catalog -> Creator tools",
        "```",
        "",
        "Tool authors must use the public API motifs and styles. They should not copy diagnostic internals, "
        "Qt widgets, PyVista actors or tool-local handle drawings into a tool.",
        "",
    ]
    for layer in _CREATOR_UI_DIRECTION_LAYERS:
        lines.extend(
            [
                f"## {layer.title}",
                f"Responsibility: {layer.responsibility}",
                f"Not responsible for: {layer.not_responsible_for}",
                f"Entry point: `{layer.public_entrypoint}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Non-negotiable rules",
            "- New optimized visuals are first validated in Tool Core Analysis, then extracted into `tool_api`.",
            "- `tool_api.ui_catalog` documents the vocabulary; it does not render visuals.",
            "- `tool_api.ui_motifs` builds and refreshes the official visual motifs; catalog tools do not hand-build samples.",
            "- `CreatorStudioToolAdapter` owns hover/select/grab and empty-click selection clearing for normal Creator tools; low-level interaction helpers are for diagnostics/tests/adapters.",
            "- `CreatorStudioToolAdapter` runs the native API runtime before tool code; it chooses the interaction or drag refresh path internally, so tool authors do not call refresh helpers on mouse moves.",
            "- End-of-camera-move axis orientation and field-of-view scaling are owned by the API/renderer; they are not refreshed continuously during empty camera pan/orbit and are not implemented inside tools.",
            "- `gizmo_catalog` is a viewer with visibility toggles, not a second UI implementation.",
            "- Direct `ctx.gizmos.create_handle(...)` calls are low-level escape hatches for advanced adapters; prefer official actors, "
            "styles, manipulators and motifs.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def list_creator_ui_families() -> tuple[CreatorUiFamily, ...]:
    """Return all official UI families in stable display order."""

    return (
        CreatorUiFamily(
            CreatorUiFamilyId.ACTOR_KINDS.value,
            "Actor kinds",
            "Selectable scene/UI actors available through laserprog_studio.tool_api.actors.",
            "from laserprog_studio.tool_api import actors",
            _actor_kind_items(),
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.ACTOR_INTERACTIONS.value,
            "Actor interactions",
            "Semantic interaction policies used by actors and resolved visuals.",
            "actors.point(..., interaction='grabbable')",
            _actor_interaction_items(),
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.VISUAL_STATES.value,
            "Visual states",
            "Runtime visual states resolved by styles.resolve_actor_visual.",
            "styles.resolve_actor_visual(...)",
            _visual_state_items(),
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.POINT_STYLES.value,
            "Point styles",
            "Optimized point/grab handle styles shared by actors and ctx.gizmos.",
            "styles.list_point_styles()",
            _point_style_items(),
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.LINE_STYLES.value,
            "Line styles",
            "Renderer-neutral line styles for actors, guides and previews.",
            "styles.list_line_styles()",
            _line_style_items(),
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.MANIPULATORS.value,
            "Manipulators",
            "Prebuilt optimized multi-handle gizmos for common viewport transforms.",
            "ctx.gizmos.translate/rotate/scale/plane/triad/box_bounds",
            _MANIPULATOR_ITEMS,
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.PREVIEWS.value,
            "Preview primitives",
            "Non-selectable viewport previews for lines, arcs, faces, text and temporary meshes.",
            "ctx.preview.show_line/show_polyline/show_arc/show_circle/show_face/show_text/show_mesh",
            _preview_items(),
        ),
        CreatorUiFamily(
            CreatorUiFamilyId.OVERLAYS.value,
            "Overlay windows",
            "Lightweight floating UI for palettes, popovers, tooltips and context menus.",
            "ctx.overlay.show_window/show_popover_at_cursor/show_tooltip",
            _OVERLAY_ITEMS,
        ),
    )


def iter_creator_ui_families() -> tuple[CreatorUiFamily, ...]:
    """Stable alias for :func:`list_creator_ui_families`."""

    return list_creator_ui_families()


def get_creator_ui_family(family_id: str | CreatorUiFamilyId) -> CreatorUiFamily | None:
    raw = family_id.value if isinstance(family_id, CreatorUiFamilyId) else str(family_id)
    normalized = raw.strip().lower()
    return next((family for family in list_creator_ui_families() if family.id == normalized), None)


def iter_tool_ui_recommendations() -> tuple[ToolUiRecommendation, ...]:
    return _TOOL_UI_RECOMMENDATIONS


def recommendations_for_tool(tool_id: str) -> ToolUiRecommendation | None:
    normalized = str(tool_id).strip().lower()
    return next((item for item in _TOOL_UI_RECOMMENDATIONS if item.tool_id == normalized), None)


def all_recommended_point_styles() -> tuple[str, ...]:
    return _unique(style for item in _TOOL_UI_RECOMMENDATIONS for style in item.point_styles)


def all_recommended_line_styles() -> tuple[str, ...]:
    return _unique(style for item in _TOOL_UI_RECOMMENDATIONS for style in item.line_styles)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        value = str(value)
        if value not in result:
            result.append(value)
    return tuple(result)


def creator_ui_catalog_markdown() -> str:
    """Return concise Markdown documentation for the official UI catalog."""

    lines = ["# Creator API UI/Gizmo catalog", "", "Use these Tool Core Analysis motifs instead of custom Qt/PyVista UI code inside tools.", ""]
    for family in list_creator_ui_families():
        lines.extend([f"## {family.label}", family.description, "", f"API: `{family.api_entrypoint}`", ""])
        for item in family.items:
            suffix = f" Recommended for: {', '.join(item.recommended_for)}." if item.recommended_for else ""
            lines.append(f"- `{item.id}` — {item.description}{suffix} (`{item.api}`)")
        lines.append("")
    lines.extend(["## Recommended recipes", ""])
    for recommendation in _TOOL_UI_RECOMMENDATIONS:
        lines.append(f"- `{recommendation.tool_id}` — {recommendation.purpose}")
        lines.append(f"  - actors: {', '.join(recommendation.actor_kinds)}")
        lines.append(f"  - interactions: {', '.join(recommendation.interactions)}")
        lines.append(f"  - point styles: {', '.join(recommendation.point_styles)}")
        lines.append(f"  - line styles: {', '.join(recommendation.line_styles)}")
        if recommendation.manipulators:
            lines.append(f"  - manipulators: {', '.join(recommendation.manipulators)}")
        if recommendation.overlays:
            lines.append(f"  - overlays: {', '.join(recommendation.overlays)}")
    return "\n".join(lines).rstrip() + "\n"


# Stable names kept for the pass169 tool/tests and older docs.
GizmoCatalogItem = CreatorUiItem
GizmoUiFamily = CreatorUiFamily
ToolGizmoRecommendation = ToolUiRecommendation
GIZMO_UI_FAMILIES = list_creator_ui_families()
TOOL_GIZMO_RECOMMENDATIONS = _TOOL_UI_RECOMMENDATIONS
iter_gizmo_ui_families = iter_creator_ui_families
get_gizmo_ui_family = get_creator_ui_family
gizmo_ui_catalog_markdown = creator_ui_catalog_markdown

__all__ = [
    "CreatorUiDirectionLayer",
    "CreatorUiFamily",
    "CreatorUiFamilyId",
    "CreatorUiItem",
    "GIZMO_UI_FAMILIES",
    "GizmoCatalogItem",
    "GizmoUiFamily",
    "TOOL_GIZMO_RECOMMENDATIONS",
    "ToolGizmoRecommendation",
    "ToolUiRecommendation",
    "all_recommended_line_styles",
    "all_recommended_point_styles",
    "creator_ui_catalog_markdown",
    "creator_ui_direction_layers",
    "creator_ui_direction_markdown",
    "get_creator_ui_family",
    "get_gizmo_ui_family",
    "gizmo_ui_catalog_markdown",
    "iter_creator_ui_families",
    "iter_gizmo_ui_families",
    "iter_tool_ui_recommendations",
    "list_creator_ui_families",
    "overlay_kind_choices",
    "recommendations_for_tool",
]
