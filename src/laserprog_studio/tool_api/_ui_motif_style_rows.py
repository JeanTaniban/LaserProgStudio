"""Shared private helpers for Creator UI motif construction."""
from __future__ import annotations

from dataclasses import replace
from math import cos, hypot, pi, sin

from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, GizmoHandle
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, ToolActor

from . import actors
from ._ui_motif_contract import (
    API_UI_VISIBLE_METADATA_KEY,
    FAMILY_ACTOR_INTERACTIONS,
    FAMILY_ACTOR_KINDS,
    FAMILY_LINE_STYLES,
    FAMILY_MANIPULATORS,
    FAMILY_OVERLAYS,
    FAMILY_POINT_STYLES,
    FAMILY_PREVIEWS,
    FAMILY_VISUAL_STATES,
    Point3,
)
from .styles import (
    InteractionVisualState,
    LineStyleId,
    PointStyleId,
    list_line_styles,
    resolve_actor_visual,
)
from .visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

def _build_visual_state_motifs(self) -> None:
    family = FAMILY_VISUAL_STATES
    y = 56.0
    z = 0.42
    states = (
        ("fixed", InteractionVisualState.FIXED, False, False, False, False),
        ("grabbable", InteractionVisualState.GRABBABLE, False, False, False, True),
        ("hover", InteractionVisualState.HOVER, False, True, False, True),
        ("selected", InteractionVisualState.SELECTED, True, False, False, True),
        ("grabbed", InteractionVisualState.GRABBED, False, False, True, True),
        ("disabled", InteractionVisualState.DISABLED, False, False, False, False),
    )
    for index, (label, state, selected, hover, grabbed, selectable) in enumerate(states):
        x = float(index) * 10.0
        self._show_handle(
            family,
            label,
            (x, y, z),
            interaction="grabbable" if selectable else "fixed",
            point_style="target" if label in {"hover", "selected", "grabbed"} else "solid",
            line_style="preview",
            visual_state=state,
            selected=selected,
            hover=hover,
            grabbed=grabbed,
            selectable=selectable,
            radius_px=13,
            kind_suffix=label,
            interactive=False,
        )
        self._label(family, label, label, (x, y - 4.2, z), size_px=11)


def _build_point_style_motifs(self) -> None:
    family = FAMILY_POINT_STYLES
    z = 0.35
    base_radius = 12
    for idx, (style_id, style) in enumerate(DEFAULT_POINT_STYLES.items()):
        y = 72.0 + float(idx) * 12.0
        ids = {
            "fixed": f"{style_id}:fixed",
            "grab": f"{style_id}:grab",
            "line_fixed_a": f"{style_id}:line_fixed:a",
            "line_fixed_b": f"{style_id}:line_fixed:b",
            "line_grab_a": f"{style_id}:line_grab:a",
            "line_grab_b": f"{style_id}:line_grab:b",
            "circle_center": f"{style_id}:circle:center",
            "circle_radius": f"{style_id}:circle:radius",
        }
        points = {
            "fixed": (0.0, y, z),
            "grab": (17.0, y, z),
            "line_fixed_a": (54.0, y, z),
            "line_fixed_b": (70.0, y, z),
            "line_grab_a": (86.0, y, z),
            "line_grab_b": (104.0, y, z),
            "circle_center": (124.0, y, z),
            "circle_radius": (124.0 + 8.0 + float(idx) * 1.4, y, z),
        }

        def add(handle_key: str, *, grabbable: bool, kind_suffix: str) -> None:
            state = InteractionVisualState.GRABBABLE if grabbable else InteractionVisualState.FIXED
            self._show_handle(
                family,
                ids[handle_key],
                points[handle_key],
                interaction="grabbable" if grabbable else "fixed",
                point_style=style_id,
                line_style="grabbable" if grabbable else "fixed",
                visual_state=state,
                selectable=grabbable,
                radius_px=base_radius,
                kind_suffix=f"{style_id}:{'grab' if grabbable else 'fixed'}:{kind_suffix}",
            )

        add("fixed", grabbable=False, kind_suffix="single")
        add("grab", grabbable=True, kind_suffix="single")
        add("line_fixed_a", grabbable=False, kind_suffix="line_end")
        add("line_fixed_b", grabbable=False, kind_suffix="line_end")
        add("line_grab_a", grabbable=True, kind_suffix="line_end")
        add("line_grab_b", grabbable=True, kind_suffix="line_end")
        add("circle_center", grabbable=False, kind_suffix="circle_center")
        add("circle_radius", grabbable=True, kind_suffix="circle_radius")
        self.ctx.preview.show_line(self._id(family, style_id, "standalone_line"), self.owner_tool, (30.0, y, z), (43.0, y + 0.35 * idx, z))
        self._label(family, f"{style_id}:label", f"S / {style.label}", (-10.0, y, z), size_px=11)
        self.ctx.preview.show_line(self._id(family, style_id, "line_fixed"), self.owner_tool, points["line_fixed_a"], points["line_fixed_b"])
        self.ctx.preview.show_line(self._id(family, style_id, "line_grab"), self.owner_tool, points["line_grab_a"], points["line_grab_b"])
        center, radius_pt = points["circle_center"], points["circle_radius"]
        radius_world = max(1.0, hypot(radius_pt[0] - center[0], radius_pt[1] - center[1]))
        circle = tuple((center[0] + cos((2.0 * pi * step) / 48.0) * radius_world, center[1] + sin((2.0 * pi * step) / 48.0) * radius_world, z) for step in range(49))
        self.ctx.preview.show_circle(self._id(family, style_id, "circle"), self.owner_tool, circle)
        self.ctx.preview.show_line(self._id(family, style_id, "circle_radius"), self.owner_tool, center, radius_pt)


def _build_line_style_motifs(self) -> None:
    family = FAMILY_LINE_STYLES
    z = 0.25
    for index, line_style in enumerate(list_line_styles()):
        row = index % 7
        col = index // 7
        x = 0.0 + float(col) * 46.0
        y = -24.0 - float(row) * 6.0
        self.ctx.preview.show_line(
            self._id(family, line_style.id),
            self.owner_tool,
            (x, y, z),
            (x + 28.0, y, z),
            payload=line_style.payload(),
        )
        self._label(family, f"{line_style.id}:label", line_style.id, (x + 34.0, y - 0.6, z), size_px=11)

__all__ = ['_build_visual_state_motifs', '_build_point_style_motifs', '_build_line_style_motifs']
