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

def _build_manipulator_motifs(self) -> None:
    family = FAMILY_MANIPULATORS
    y = -78.0
    owner = self.owner_tool
    self.ctx.gizmos.translate(id=self._id(family, "translate"), owner_tool=owner, origin=(0.0, y, 0.4), radius_px=13)
    self.ctx.gizmos.rotate(id=self._id(family, "rotate"), owner_tool=owner, origin=(22.0, y, 0.4), radius_px=13)
    self.ctx.gizmos.scale(id=self._id(family, "scale"), owner_tool=owner, origin=(44.0, y, 0.4), radius_px=13)
    self.ctx.gizmos.plane(id=self._id(family, "plane"), owner_tool=owner, origin=(66.0, y, 0.4), normal=(0.0, 0.0, 1.0), radius_px=13)
    self.ctx.gizmos.triad(id=self._id(family, "triad"), owner_tool=owner, origin=(88.0, y, 0.4), radius_px=12)
    self.ctx.gizmos.box_bounds(id=self._id(family, "box_bounds"), owner_tool=owner, bounds=(104.0, 118.0, y - 7.0, y + 7.0, -1.0, 1.0), radius_px=10)
    self._register_existing_family_handles_as_actors(family)
    for label, x in (("translate", 0.0), ("rotate", 22.0), ("scale", 44.0), ("plane", 66.0), ("triad", 88.0), ("box_bounds", 111.0)):
        self._label(family, label, label, (x, y - 9.0, 0.4), size_px=11)


def _build_preview_motifs(self) -> None:
    family = FAMILY_PREVIEWS
    z = 0.1
    self.ctx.preview.show_line(self._id(family, "line"), self.owner_tool, (0.0, -2.0, z), (28.0, -2.0, z), payload={"style_id": "preview"})
    self.ctx.preview.show_polyline(
        self._id(family, "polyline"),
        self.owner_tool,
        ((0.0, 7.0, z), (7.0, 13.0, z), (17.0, 8.0, z), (29.0, 15.0, z)),
        payload={"style_id": "preview"},
    )
    center = (43.0, 5.0, z)
    radius = 6.0
    circle = tuple((center[0] + cos((2.0 * pi * i) / 48.0) * radius, center[1] + sin((2.0 * pi * i) / 48.0) * radius, center[2]) for i in range(49))
    self.ctx.preview.show_circle(self._id(family, "circle"), self.owner_tool, circle, payload={"style_id": "preview"})
    arc = tuple((62.0 + cos(pi * i / 24.0) * 7.0, 6.0 + sin(pi * i / 24.0) * 7.0, z) for i in range(25))
    self.ctx.preview.show_arc(self._id(family, "arc"), self.owner_tool, arc, payload={"style_id": "guide"})
    face = ((39.0, 17.0, 0.05), (55.0, 17.0, 0.05), (58.0, 27.0, 0.05), (36.0, 27.0, 0.05))
    self.ctx.preview.show_face(self._id(family, "face"), self.owner_tool, face)
    self.ctx.preview.show_text(self._id(family, "text", "face"), self.owner_tool, "closed face preview", (46.0, 22.0, 0.2), size_px=13)
    labels = (
        ("2D overlay text", (0.0, 36.0, 0.25), 16),
        ("constraint: coincident", (23.0, 36.0, 0.25), 13),
        ("dimension: 28.0 mm", (48.0, 36.0, 0.25), 13),
        ("warning / invalid loop", (72.0, 36.0, 0.25), 13),
    )
    for idx, (text, pos, size) in enumerate(labels):
        self.ctx.preview.show_text(self._id(family, "text", idx), self.owner_tool, text, pos, size_px=size)
    # Tool Core Analysis snap motifs: visible anchors are separate from geometry.
    guide_points = ((0.0, 48.0, 0.2), (10.0, 48.0, 0.2), (20.0, 48.0, 0.2), (30.0, 48.0, 0.2))
    for idx, point in enumerate(guide_points):
        self._show_handle(family, f"snap:{idx}", point, interaction="grabbable", point_style="target", line_style="guide", radius_px=13, kind_suffix=f"snap:{idx}")
    self.ctx.preview.show_polyline(self._id(family, "snap", "guide"), self.owner_tool, guide_points, payload={"style_id": "guide"})
    self.ctx.preview.show_text(self._id(family, "text", "snap"), self.owner_tool, "smart snap anchors", (14.0, 44.0, 0.3), size_px=13)


def _build_overlay_motifs(self, *, visible: bool) -> None:
    owner = self.owner_tool
    family = FAMILY_OVERLAYS
    group = f"{owner}.ui_modes"
    self.ctx.overlay.show_window(
        OverlayWindowSpec(
            id=f"{owner}:overlay:palette",
            title="UI / Gizmo Showcase",
            owner_tool=owner,
            fields=[
                OverlayFieldSpec(f"{owner}:overlay:palette:mode", "Mode", "Circle", kind="info"),
                OverlayFieldSpec(f"{owner}:overlay:palette:delete", "Delete", "enabled", kind="info"),
            ],
            buttons=[
                ToolButtonSpec(f"{owner}:overlay:mode:modify", "Modify", icon="cursor", checkable=True, checked=False, group=group, shortcut="Esc"),
                ToolButtonSpec(f"{owner}:overlay:mode:line", "Line", icon="line", checkable=True, checked=False, group=group, shortcut="L"),
                ToolButtonSpec(f"{owner}:overlay:mode:arc", "Arc", icon="arc", checkable=True, checked=False, group=group, shortcut="A"),
                ToolButtonSpec(f"{owner}:overlay:mode:circle", "Circle", icon="circle", checkable=True, checked=True, group=group, shortcut="C"),
                ToolButtonSpec(f"{owner}:overlay:delete", "Delete", icon="trash", enabled=True),
            ],
            anchor="viewport_top_right",
            overlay_kind="palette",
            width_px=290,
            visible=visible,
            persistent=True,
        )
    )
    self.ctx.overlay.show_window(
        OverlayWindowSpec(
            id=f"{owner}:overlay:popover",
            title="Context popover",
            owner_tool=owner,
            fields=[
                OverlayFieldSpec(f"{owner}:overlay:popover:axis", "Axis", "Local / Global", kind="info"),
                OverlayFieldSpec(f"{owner}:overlay:popover:amount", "Amount", "42", kind="number"),
            ],
            buttons=[ToolButtonSpec(f"{owner}:overlay:popover:apply", "Apply")],
            anchor="cursor",
            overlay_kind="popover",
            width_px=250,
            visible=visible,
            persistent=True,
            position_px=(180, 180),
        )
    )
    self.ctx.overlay.show_window(
        OverlayWindowSpec(
            id=f"{owner}:overlay:tooltip",
            title="Tooltip",
            owner_tool=owner,
            fields=[OverlayFieldSpec(f"{owner}:overlay:tooltip:text", "", "Official tooltip/popover/palette overlay motif.", kind="info")],
            anchor="viewport_top_left",
            overlay_kind="tooltip",
            width_px=260,
            visible=visible,
            persistent=True,
            close_on_click_outside=False,
        )
    )

__all__ = ['_build_manipulator_motifs', '_build_preview_motifs', '_build_overlay_motifs']
