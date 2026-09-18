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

def _build_actor_kind_motifs(self) -> None:
    owner = self.owner_tool
    family = FAMILY_ACTOR_KINDS
    samples = (
        actors.point(self._id(family, "point"), (-28.0, 0.0, 0.42), owner_tool=owner, interaction="grabbable", point_style="target", line_style="grabbable"),
        actors.line(self._id(family, "line_selectable"), (18.0, 0.0, 0.42), (36.0, 7.0, 0.42), owner_tool=owner, interaction="selectable", point_style="solid", line_style="selectable"),
        actors.line(self._id(family, "line_grabbable"), (45.0, 0.0, 0.42), (63.0, 7.0, 0.42), owner_tool=owner, interaction="grabbable", point_style="solid", line_style="grabbable"),
        actors.circle(self._id(family, "circle"), (78.0, 0.0, 0.42), (86.0, 0.0, 0.42), owner_tool=owner, interaction="selectable", point_style="target", line_style="selectable"),
        actors.arc(self._id(family, "arc"), ((0.0, 24.0, 0.42), (8.0, 34.0, 0.42), (18.0, 24.0, 0.42)), owner_tool=owner, interaction="selectable", point_style="solid", line_style="preview"),
        actors.polyline(self._id(family, "polyline"), ((38.0, 24.0, 0.42), (46.0, 31.0, 0.42), (56.0, 26.0, 0.42), (63.0, 34.0, 0.42)), owner_tool=owner, interaction="grabbable", point_style="solid", line_style="grabbable"),
    )
    for actor in samples:
        actor = self._register_actor_motif(actor)
        self._render_actor_motif(actor, family)
    self._label(family, "actor_point", "point", (-28.0, -5.0, 0.42), size_px=11)
    self._label(family, "actor_line", "line", (27.0, -5.0, 0.42), size_px=11)
    self._label(family, "actor_circle", "circle", (78.0, -10.0, 0.42), size_px=11)
    self._label(family, "actor_arc", "arc", (9.0, 18.5, 0.42), size_px=11)
    self._label(family, "actor_polyline", "polyline", (51.0, 18.5, 0.42), size_px=11)


def _render_actor_motif(self, actor: ToolActor, family: str) -> None:
    interaction = actor.interaction_mode
    if not bool(actor.metadata.get(API_UI_VISIBLE_METADATA_KEY, True)):
        return
    selected = self.ctx.selection.is_selected(actor.id)
    hover = actor.id == self.ctx.selection.state.hover_id
    grabbed = actor.id in self.ctx.selection.state.grabbed_ids
    visual = resolve_actor_visual(
        interaction=interaction,
        point_style_id=actor.metadata.get("point_style", PointStyleId.TARGET.value if selected or hover or grabbed else PointStyleId.SOLID.value),
        line_style_id=actor.metadata.get("line_style", LineStyleId.GRABBABLE.value if actor.grabbable else LineStyleId.SELECTABLE.value if actor.selectable else LineStyleId.FIXED.value),
        visual_state=actor.metadata.get("visual_state", InteractionVisualState.AUTO.value),
        base_radius_px=11,
        hover=hover,
        selected=selected,
        grabbed=grabbed,
    )
    kind_value = actor.kind.value if isinstance(actor.kind, ActorKind) else str(actor.kind)
    local = actor.id.split(f"{family}:", 1)[-1].replace(":", "_")

    def preview_id(*suffix: object) -> str:
        # Plan Tracer registers its semantic actors and their visible previews with
        # the same ids.  Reusing those ids during interaction refresh lets selected
        # faces/edges overwrite the normal blue preview instead of being hidden
        # underneath it by a second stale preview item.
        if family == "plan_trace_2d":
            extra = ":".join(str(part).replace(" ", "_") for part in suffix if str(part) != "")
            return f"{actor.id}:{extra}" if extra else str(actor.id)
        return self._id(family, "preview", local, *suffix)
    if kind_value == ActorKind.POINT.value and actor.points:
        handle_id = self._id(family, "handle", local)
        self.ctx.gizmos.create_handle(
            GizmoHandle(
                id=handle_id,
                owner_tool=self.owner_tool,
                position=actor.points[0],
                radius_px=visual.radius_px,
                color=visual.point_color,
                selected=selected,
                hover=hover,
                grabbed=grabbed,
                selectable=actor.selectable,
                kind=self._kind(family, kind_value, actor.interaction_mode.value),
                style_id=visual.point_style_id,
                base_radius_px=11,
                screen_locked=True,
            )
        )
        self._dirty_handle_ids.add(handle_id)
        return
    if kind_value == ActorKind.LINE.value and len(actor.points) >= 2:
        pid = preview_id()
        self.ctx.preview.show_line(pid, self.owner_tool, actor.points[0], actor.points[1], payload=visual.line_payload)
        self._dirty_preview_ids.add(pid)
        return
    if kind_value == ActorKind.CIRCLE.value and len(actor.points) >= 2:
        center, radius_pt = actor.points[0], actor.points[1]
        radius_world = max(1.0, hypot(radius_pt[0] - center[0], radius_pt[1] - center[1]))
        points = tuple((center[0] + cos(2.0 * pi * step / 64.0) * radius_world, center[1] + sin(2.0 * pi * step / 64.0) * radius_world, center[2]) for step in range(65))
        pid = preview_id()
        self.ctx.preview.show_circle(pid, self.owner_tool, points, payload=visual.line_payload)
        self._dirty_preview_ids.add(pid)
        handle_id = self._id(family, "handle", local, "center")
        self.ctx.gizmos.create_handle(
            GizmoHandle(
                id=handle_id,
                owner_tool=self.owner_tool,
                position=center,
                radius_px=max(7, visual.radius_px - 2),
                color=visual.point_color,
                selectable=False,
                kind=self._kind(family, kind_value, "center"),
                style_id=visual.point_style_id,
                base_radius_px=9,
                screen_locked=True,
            )
        )
        self._dirty_handle_ids.add(handle_id)
        return
    if actor.metadata.get("motif_kind") == "circle" and len(actor.points) >= 3:
        pid = preview_id()
        self.ctx.preview.show_circle(pid, self.owner_tool, tuple(actor.points), payload=visual.line_payload)
        self._dirty_preview_ids.add(pid)
        return
    if kind_value == ActorKind.ARC.value and len(actor.points) >= 3:
        pid = preview_id()
        self.ctx.preview.show_arc(pid, self.owner_tool, tuple(actor.points), payload=visual.line_payload)
        self._dirty_preview_ids.add(pid)
        return
    if actor.metadata.get("motif_kind") == "face" and len(actor.points) >= 3:
        pid = preview_id() if family == "plan_trace_2d" else preview_id("fill")
        holes = tuple(actor.metadata.get("filled_polygon_holes", ()) or ())
        payload = dict(visual.line_payload)
        if selected or hover or grabbed:
            payload.update({"face_color": "#f0a805", "face_opacity": 0.34, "outline_payload": dict(visual.line_payload)})
        else:
            payload.update({"face_color": "#80B7DA", "face_opacity": 0.26, "outline_payload": dict(visual.line_payload)})
        self.ctx.preview.show_face(pid, self.owner_tool, tuple(actor.points), holes=holes, payload=payload)
        self._dirty_preview_ids.add(pid)
        outline_id = preview_id("outline")
        self.ctx.preview.show_polyline(outline_id, self.owner_tool, tuple(actor.points), payload=visual.line_payload)
        self._dirty_preview_ids.add(outline_id)
        return
    if len(actor.points) >= 2:
        pid = preview_id()
        self.ctx.preview.show_polyline(pid, self.owner_tool, tuple(actor.points), payload=visual.line_payload)
        self._dirty_preview_ids.add(pid)


def _handle_position(self, handle_id: str) -> Point3 | None:
    direct_handle = getattr(self.ctx.gizmos, "handle", None)
    handle = direct_handle(handle_id, owner_tool=self.owner_tool) if callable(direct_handle) else next((h for h in self.ctx.gizmos.handles(owner_tool=self.owner_tool) if h.id == handle_id), None)
    return None if handle is None else handle.position


def _refresh_handle_dependencies(self, actor: ToolActor) -> None:
    """Refresh dependent line/circle/guide previews for one moved handle.

    This mirrors Tool Core Analysis HandleDemoBuilder.move_handle(): moving a
    handle updates the row primitives that depend on it, not the whole UI
    catalogue.
    """

    family = str(actor.metadata.get("motif_family", ""))
    if family == FAMILY_POINT_STYLES:
        prefix = f"{self.owner_tool}:{family}:"
        local = str(actor.id)[len(prefix):] if str(actor.id).startswith(prefix) else ""
        style_id = local.split(":", 1)[0] if local else ""
        if not style_id:
            return
        def hid(suffix: str) -> str:
            return self._id(family, f"{style_id}:{suffix}")
        def pos(suffix: str) -> Point3 | None:
            return self._handle_position(hid(suffix))
        fixed_a, fixed_b = pos("line_fixed:a"), pos("line_fixed:b")
        if fixed_a is not None and fixed_b is not None:
            pid = self._id(family, style_id, "line_fixed")
            self.ctx.preview.show_line(pid, self.owner_tool, fixed_a, fixed_b)
            self._dirty_preview_ids.add(pid)
        grab_a, grab_b = pos("line_grab:a"), pos("line_grab:b")
        if grab_a is not None and grab_b is not None:
            pid = self._id(family, style_id, "line_grab")
            self.ctx.preview.show_line(pid, self.owner_tool, grab_a, grab_b)
            self._dirty_preview_ids.add(pid)
        center, radius_pt = pos("circle:center"), pos("circle:radius")
        if center is not None and radius_pt is not None:
            radius_world = max(1.0, hypot(radius_pt[0] - center[0], radius_pt[1] - center[1]))
            circle = tuple((center[0] + cos((2.0 * pi * step) / 48.0) * radius_world, center[1] + sin((2.0 * pi * step) / 48.0) * radius_world, center[2]) for step in range(49))
            circle_id = self._id(family, style_id, "circle")
            radius_id = self._id(family, style_id, "circle_radius")
            self.ctx.preview.show_circle(circle_id, self.owner_tool, circle)
            self.ctx.preview.show_line(radius_id, self.owner_tool, center, radius_pt)
            self._dirty_preview_ids.update({circle_id, radius_id})
        return

    if family == FAMILY_PREVIEWS and str(actor.id).startswith(f"{self.owner_tool}:{family}:snap:"):
        points = tuple(
            point
            for suffix in ("snap:0", "snap:1", "snap:2", "snap:3")
            for point in (self._handle_position(self._id(family, suffix)),)
            if point is not None
        )
        if len(points) >= 2:
            pid = self._id(family, "snap", "guide")
            self.ctx.preview.show_polyline(pid, self.owner_tool, points, payload={"style_id": "guide"})
            self._dirty_preview_ids.add(pid)


def _build_actor_interaction_motifs(self) -> None:
    family = FAMILY_ACTOR_INTERACTIONS
    z = 0.42
    samples = (
        ("fixed", ActorInteraction.FIXED, (2.0, 44.0, z), (12.0, 44.0, z), "fixed"),
        ("selectable", ActorInteraction.SELECTABLE, (22.0, 44.0, z), (36.0, 44.0, z), "selectable"),
        ("grabbable", ActorInteraction.GRABBABLE, (47.0, 44.0, z), (66.0, 50.0, z), "grabbable"),
    )
    for label, interaction, p1, p2, line_style in samples:
        # The interaction family is not decorative.  The line itself is a
        # ToolActor, so users can select/grab the same object they see.
        actor = actors.line(
            self._id(family, label),
            p1,
            p2,
            owner_tool=self.owner_tool,
            interaction=interaction,
            point_style="solid",
            line_style=line_style,
            metadata={"motif_family": family},
            hit_radius_px=13.0,
        )
        actor = self._register_actor_motif(actor)
        self._render_actor_motif(actor, family)
        self._show_handle(
            family,
            f"{label}:anchor",
            actor.points[0],
            interaction=interaction,
            point_style="solid",
            line_style=line_style,
            selectable=interaction != ActorInteraction.FIXED,
            kind_suffix=label,
        )
        self._label(family, label, label, (actor.points[0][0] + 4.0, actor.points[0][1] - 4.0, z), size_px=11)

__all__ = ['_build_actor_kind_motifs', '_render_actor_motif', '_handle_position', '_refresh_handle_dependencies', '_build_actor_interaction_motifs']
