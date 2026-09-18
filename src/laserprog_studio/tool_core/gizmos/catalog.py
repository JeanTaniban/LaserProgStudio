"""Historical Tool Core gizmo recommendations.

The public, tool-author-facing catalog now lives in
``laserprog_studio.tool_api.ui_catalog``.  This module remains as a small
supported alias for diagnostic tests that query Tool Core directly.
"""
from __future__ import annotations

from dataclasses import dataclass

from .styles import DEFAULT_POINT_STYLES


@dataclass(frozen=True, slots=True)
class ToolGizmoRecommendation:
    tool_id: str
    purpose: str
    point_styles: tuple[str, ...]
    line_styles: tuple[str, ...]
    overlay_patterns: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GizmoCatalogItem:
    """One public UI/gizmo capability exposed by the Creator API."""

    id: str
    label: str
    description: str
    api: str


@dataclass(frozen=True, slots=True)
class GizmoUiFamily:
    """A coherent family of Creator UI primitives.

    Families are used by documentation and by the built-in Gizmo catalog tool.
    The ids are intentionally stable because inspector toggles and tests refer to
    them directly.
    """

    id: str
    label: str
    description: str
    api_entrypoint: str
    items: tuple[GizmoCatalogItem, ...]


TOOL_GIZMO_RECOMMENDATIONS: tuple[ToolGizmoRecommendation, ...] = (
    ToolGizmoRecommendation(
        tool_id="plan_tracer",
        purpose="2D sketching, point editing, closed profile construction",
        point_styles=("minimal", "target", "ring", "solid"),
        line_styles=("preview", "guide", "construction", "selected"),
        overlay_patterns=("mode_palette", "snap_settings", "small_inspector"),
        notes=("Use minimal for dense vertices.", "Use target for active snap points without the old outer ring."),
    ),
    ToolGizmoRecommendation(
        tool_id="transform_translate",
        purpose="Move selected objects or sketch points along world/local axes",
        point_styles=("translate_arrow", "axis", "triad"),
        line_styles=("axis", "preview", "selected", "grabbed"),
        overlay_patterns=("transform_light_ui", "numeric_input_window"),
        notes=("Translate arrows should feel like the existing transform axis handles."),
    ),
    ToolGizmoRecommendation(
        tool_id="transform_rotate",
        purpose="Rotate selection around local/world axes",
        point_styles=("ring", "target", "triad"),
        line_styles=("axis", "preview", "guide", "selected"),
        overlay_patterns=("angle_inspector", "snap_settings"),
    ),
    ToolGizmoRecommendation(
        tool_id="transform_scale",
        purpose="Scale handles and local bounding-box grips",
        point_styles=("square", "diamond", "axis"),
        line_styles=("preview", "guide", "selected"),
        overlay_patterns=("scale_inspector", "lock_toggle"),
    ),
    ToolGizmoRecommendation(
        tool_id="extrude",
        purpose="Extrude a selected 2D face or mesh profile",
        point_styles=("translate_arrow", "target"),
        line_styles=("preview", "axis", "guide", "warning"),
        overlay_patterns=("height_input_window", "confirm_cancel"),
    ),
    ToolGizmoRecommendation(
        tool_id="split_plane",
        purpose="Move and orient a cutting plane",
        point_styles=("axis", "translate_arrow", "ring"),
        line_styles=("axis", "preview", "guide"),
        overlay_patterns=("plane_inspector", "apply_cancel"),
    ),
    ToolGizmoRecommendation(
        tool_id="texture_projector",
        purpose="Move/scale/rotate projected textures and masks",
        point_styles=("square", "ring", "target"),
        line_styles=("preview", "axis", "guide", "selected"),
        overlay_patterns=("texture_inspector", "opacity_toggle"),
    ),
    ToolGizmoRecommendation(
        tool_id="selection",
        purpose="Hover, selection, delete and object inspection",
        point_styles=("solid", "minimal", "target"),
        line_styles=("hover", "selected", "grabbed", "fixed"),
        overlay_patterns=("context_popover", "delete_confirmation"),
    ),
)


def _point_style_items() -> tuple[GizmoCatalogItem, ...]:
    descriptions = {
        "solid": "Default filled point handle for simple draggable anchors.",
        "ring": "Circular handle for rotation and angular interactions.",
        "target": "Target marker for snapping, face anchors and active picks.",
        "diamond": "Diamond handle for corners, bounds and precise grips.",
        "square": "Square handle for scale or rectangular edits.",
        "arrow": "Directional arrow-like handle for constrained movement.",
        "axis": "Axis-aligned handle for normals and single-axis edits.",
        "chevron": "Directional chevron for flow or waypoint editing.",
        "triad": "Local XYZ triad handle style.",
        "minimal": "Very small dense-point style for sketches and vertex clouds.",
        "translate_arrow": "Production translation-axis handle style.",
    }
    return tuple(
        GizmoCatalogItem(
            id=style_id,
            label=style_id.replace("_", " ").title(),
            description=descriptions.get(style_id, "Point handle style."),
            api=f"GizmoHandle(style_id={style_id!r})",
        )
        for style_id in DEFAULT_POINT_STYLES.keys()
    )


GIZMO_UI_FAMILIES: tuple[GizmoUiFamily, ...] = (
    GizmoUiFamily(
        id="point_styles",
        label="Point styles",
        description="Atomic selectable point handles rendered by ctx.gizmos.",
        api_entrypoint="ctx.gizmos.create_handle(GizmoHandle(...))",
        items=_point_style_items(),
    ),
    GizmoUiFamily(
        id="manipulators",
        label="Manipulators",
        description="Prebuilt multi-handle gizmos for common viewport transforms.",
        api_entrypoint="ctx.gizmos.translate/rotate/scale/plane/triad/box_bounds",
        items=(
            GizmoCatalogItem("translate", "Translate", "XYZ movement manipulator with axis handles.", "ctx.gizmos.translate(...)"),
            GizmoCatalogItem("rotate", "Rotate", "Ring-style rotation manipulator.", "ctx.gizmos.rotate(...)"),
            GizmoCatalogItem("scale", "Scale", "Axis and uniform scale grips.", "ctx.gizmos.scale(...)"),
            GizmoCatalogItem("plane", "Plane", "Origin + normal handles for cut/projection planes.", "ctx.gizmos.plane(...)"),
            GizmoCatalogItem("triad", "Triad", "Compact XYZ manipulator.", "ctx.gizmos.triad(...)"),
            GizmoCatalogItem("box_bounds", "Box bounds", "Corner handles for axis-aligned bounds.", "ctx.gizmos.box_bounds(...)"),
        ),
    ),
    GizmoUiFamily(
        id="previews",
        label="Preview primitives",
        description="Non-selectable viewport previews for lines, arcs, faces, text and temporary meshes.",
        api_entrypoint="ctx.preview.show_line/show_polyline/show_arc/show_circle/show_face/show_text/show_mesh",
        items=(
            GizmoCatalogItem("line", "Line", "Simple segment preview.", "ctx.preview.show_line(...)"),
            GizmoCatalogItem("polyline", "Polyline", "Multi-segment sketch or contour preview.", "ctx.preview.show_polyline(...)"),
            GizmoCatalogItem("arc", "Arc", "Curved angular preview.", "ctx.preview.show_arc(...)"),
            GizmoCatalogItem("circle", "Circle", "Closed circular preview.", "ctx.preview.show_circle(...)"),
            GizmoCatalogItem("face", "Face", "Temporary face/profile preview.", "ctx.preview.show_face(...)"),
            GizmoCatalogItem("text", "Text", "Viewport text annotation.", "ctx.preview.show_text(...)"),
            GizmoCatalogItem("mesh", "Mesh", "Temporary mesh preview.", "ctx.preview.show_mesh(...)"),
        ),
    ),
    GizmoUiFamily(
        id="overlays",
        label="Overlay windows",
        description="Lightweight floating UI for palettes, popovers, tooltips and context menus.",
        api_entrypoint="ctx.overlay.show_window/show_popover_at_cursor/show_tooltip",
        items=(
            GizmoCatalogItem("palette", "Palette", "Persistent compact tool palette.", "ctx.overlay.show_window(..., overlay_kind='palette')"),
            GizmoCatalogItem("popover", "Popover", "Small contextual window near the cursor.", "ctx.overlay.show_popover_at_cursor(...)"),
            GizmoCatalogItem("tooltip", "Tooltip", "Non-editable contextual help.", "ctx.overlay.show_tooltip(...)"),
            GizmoCatalogItem("inspector", "Inspector", "Floating mini inspector.", "OverlayWindowSpec(overlay_kind='inspector')"),
            GizmoCatalogItem("context_menu", "Context menu", "Click-away contextual command menu.", "ctx.overlay.show_context_popover_at_cursor(...)"),
            GizmoCatalogItem("modal", "Modal", "Blocking confirmation/details window.", "OverlayWindowSpec(modal=True)"),
        ),
    ),
)


def recommendations_for_tool(tool_id: str) -> ToolGizmoRecommendation | None:
    normalized = str(tool_id).strip().lower()
    return next((item for item in TOOL_GIZMO_RECOMMENDATIONS if item.tool_id == normalized), None)


def all_recommended_point_styles() -> tuple[str, ...]:
    styles: list[str] = []
    for item in TOOL_GIZMO_RECOMMENDATIONS:
        for style in item.point_styles:
            if style not in styles:
                styles.append(style)
    return tuple(styles)


def iter_gizmo_ui_families() -> tuple[GizmoUiFamily, ...]:
    """Return the stable Creator UI families documented by the API."""

    return GIZMO_UI_FAMILIES


def get_gizmo_ui_family(family_id: str) -> GizmoUiFamily | None:
    normalized = str(family_id).strip().lower()
    return next((family for family in GIZMO_UI_FAMILIES if family.id == normalized), None)


def gizmo_ui_catalog_markdown() -> str:
    """Return concise Markdown documentation for the public UI catalog."""

    lines = ["# Creator API Gizmo/UI catalog", ""]
    for family in GIZMO_UI_FAMILIES:
        lines.extend([f"## {family.label}", family.description, "", f"API: `{family.api_entrypoint}`", ""])
        for item in family.items:
            lines.append(f"- `{item.id}` — {item.description} (`{item.api}`)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
