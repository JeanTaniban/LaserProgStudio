"""Focused handle/gizmo demo scenarios for the shared tool-core layer.

The demo is intentionally smaller than the old broad showcase. It concentrates
on the primitives every viewport tool needs before migration: fixed handles,
grabbable handles, hover/grabbed states, point-to-point linework and circles.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, pi, sin
from typing import Iterable

from ..context import ToolContext
from ..gizmos import DEFAULT_POINT_STYLES, GizmoHandle, GizmoVisualState, get_point_style
from ..overlay import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec, ToolPanelSpec
from ..selection import ActorInteraction, ActorKind, ToolActor

Point3 = tuple[float, float, float]
DEMO_HANDLE_RADIUS_PX = 12


@dataclass(frozen=True, slots=True)
class HandleDemoRow:
    label: str
    radius_px: int
    y: float
    style_id: str


@dataclass(frozen=True, slots=True)
class HandleDemoSnapshot:
    rows: int
    handles: int
    fixed_handles: int
    grabbable_handles: int
    hover_handles: int
    grabbed_handles: int
    previews: int
    labels: int
    notes: tuple[str, ...]


class HandleDemoBuilder:
    """Builds and updates the diagnostic handle demo scene.

    The builder writes only through ToolContext services. It never touches Qt,
    PyVista or VTK directly, so the same data can be tested without a viewport.
    """

    owner_tool = "tool_core_diag"
    base_radius_px = DEMO_HANDLE_RADIUS_PX
    rows: tuple[HandleDemoRow, ...] = tuple(
        HandleDemoRow(f"S / {style.label}", DEMO_HANDLE_RADIUS_PX, float(idx) * 14.0, style_id)
        for idx, (style_id, style) in enumerate(DEFAULT_POINT_STYLES.items())
    )

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.notes: list[str] = []

    def reset_visuals(self) -> None:
        self.ctx.gizmos.clear_tool(self.owner_tool)
        self.ctx.preview.clear_tool(self.owner_tool)
        self.notes.clear()
        backend = self.ctx.gizmos.backend
        if hasattr(backend, "handles"):
            try:
                backend.handles = {key: value for key, value in backend.handles.items() if value.owner_tool != self.owner_tool}
            except Exception:
                pass
        for attr in ("created", "position_updates", "visibility_updates", "removed", "light_renders", "full_renders"):
            if hasattr(backend, attr):
                try:
                    setattr(backend, attr, 0)
                except Exception:
                    pass

    def build_demo(self, *, hover_id: str | None = None, grabbed_id: str | None = None) -> HandleDemoSnapshot:
        self.reset_visuals()
        self._build_overlay()
        for idx, row in enumerate(self.rows):
            self._build_row(idx, row, hover_id=hover_id, grabbed_id=grabbed_id)
        self._refresh_dependent_primitives()
        self.notes.append("Focused demo: fixed points, grabbable points, point-to-point lines and circles using one readable S size.")
        self.notes.append("Grabbable points use official Tool Core styles, including target, minimal dots, transform-style arrows, axes, chevrons and triads.")
        self.notes.append("Hover/grab state is updated through GizmoManager.update_interaction_state, not by rebuilding the demo.")
        self.notes.append("All rows use the same S radius; minimal dot radius is adjustable with normal and hover/grab sliders.")
        return self.snapshot()

    def apply_hover(self, handle_id: str | None) -> HandleDemoSnapshot:
        self._set_interaction_state(hover_id=handle_id, grabbed_id=None)
        return self.snapshot()

    def apply_grabbed(self, handle_id: str | None) -> HandleDemoSnapshot:
        self._set_interaction_state(hover_id=None, grabbed_id=handle_id)
        return self.snapshot()

    def move_handle(self, handle_id: str, position: Point3) -> bool:
        handle = self._handles_by_id().get(handle_id)
        if handle is None or not self.is_grabbable(handle):
            return False
        self.ctx.gizmos.begin_interactive_update()
        try:
            self.ctx.gizmos.update_positions_only({handle_id: tuple(float(v) for v in position)})
            self._refresh_dependent_primitives()
            self.ctx.profiler.increment("diag.handle_demo.position_updates")
        finally:
            self.ctx.gizmos.end_interactive_update()
        return True

    def nearest_grabbable(self, screen_pos: tuple[float, float], world_to_screen, *, max_extra_px: float = 8.0) -> str | None:
        sx, sy = float(screen_pos[0]), float(screen_pos[1])
        best_id: str | None = None
        best_dist = 1.0e18
        for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool):
            if not handle.visible or not self.is_grabbable(handle):
                continue
            hx, hy = world_to_screen(handle.position)
            dist = hypot(float(hx) - sx, float(hy) - sy)
            radius = max(float(handle.radius_px), 8.0) + float(max_extra_px)
            if dist <= radius and dist < best_dist:
                best_id = handle.id
                best_dist = dist
        return best_id

    @staticmethod
    def is_grabbable(handle: GizmoHandle) -> bool:
        return bool(handle.selectable and str(handle.kind).startswith("demo_grab"))

    def _build_overlay(self) -> None:
        self.ctx.overlay.show_panel(
            ToolPanelSpec(
                "diag.handle_demo.panel",
                "Handle / Gizmo Demo",
                [
                    ToolButtonSpec("diag.demo.modify", "Modify", icon="cursor", checkable=True, checked=True, group="diag.demo.mode", shortcut="Esc"),
                    ToolButtonSpec("diag.demo.hover", "Hover", icon="point", checkable=False, tooltip="Simulate or inspect hover state"),
                    ToolButtonSpec("diag.demo.grab", "Grab", icon="hand", checkable=False, tooltip="Simulate or inspect grabbed state"),
                    ToolButtonSpec("diag.demo.clear", "Clear", icon="trash", checkable=False),
                ],
            )
        )
        self.ctx.overlay.show_window(
            OverlayWindowSpec(
                id="diag.handle_demo.window",
                title="Handle states",
                owner_tool=self.owner_tool,
                fields=[
                    OverlayFieldSpec("diag.handle_demo.window.mode", "Mode", "persistent actors", kind="info"),
                    OverlayFieldSpec("diag.handle_demo.window.camera", "Camera sizing", "live/end refresh supported", kind="info"),
                    OverlayFieldSpec("diag.handle_demo.window.rule", "Rule", "hover/grab changes never rebuild the scene", kind="info"),
                ],
                buttons=[ToolButtonSpec("diag.handle_demo.window.close", "Close", icon="close")],
                anchor="viewport_top_right",
                overlay_kind="inspector",
                width_px=300,
                close_on_click_outside=True,
            )
        )

    def _build_row(self, idx: int, row: HandleDemoRow, *, hover_id: str | None, grabbed_id: str | None) -> None:
        y = float(row.y)
        z = 0.35
        radius = int(row.radius_px)
        ids = {
            "fixed": f"demo:{idx}:fixed",
            "grab": f"demo:{idx}:grab",
            "line_fixed_a": f"demo:{idx}:line_fixed:a",
            "line_fixed_b": f"demo:{idx}:line_fixed:b",
            "line_grab_a": f"demo:{idx}:line_grab:a",
            "line_grab_b": f"demo:{idx}:line_grab:b",
            "circle_center": f"demo:{idx}:circle:center",
            "circle_radius": f"demo:{idx}:circle:radius",
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
        style = get_point_style(row.style_id)

        def add(handle_key: str, *, grabbable: bool, kind_suffix: str) -> None:
            hid = ids[handle_key]
            hover = hid == hover_id
            grabbed = hid == grabbed_id
            state = (
                GizmoVisualState.GRABBED
                if grabbed
                else GizmoVisualState.HOVER
                if hover
                else GizmoVisualState.GRABBABLE
                if grabbable
                else GizmoVisualState.FIXED
            )
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=hid,
                    owner_tool=self.owner_tool,
                    position=points[handle_key],
                    radius_px=self.ctx.gizmos.radius_for_style(row.style_id, radius, state),
                    color=style.color_for(state),
                    hover=hover,
                    grabbed=grabbed,
                    selectable=grabbable,
                    kind=("demo_grab_" if grabbable else "demo_fixed_") + kind_suffix,
                    style_id=row.style_id,
                    base_radius_px=radius,
                    screen_locked=True,
                )
            )

        add("fixed", grabbable=False, kind_suffix="single")
        add("grab", grabbable=True, kind_suffix="single")
        add("line_fixed_a", grabbable=False, kind_suffix="line_end")
        add("line_fixed_b", grabbable=False, kind_suffix="line_end")
        add("line_grab_a", grabbable=True, kind_suffix="line_end")
        add("line_grab_b", grabbable=True, kind_suffix="line_end")
        add("circle_center", grabbable=False, kind_suffix="circle_center")
        add("circle_radius", grabbable=True, kind_suffix="circle_radius")

        self.ctx.preview.show_line(f"demo:{idx}:standalone_line", self.owner_tool, (30.0, y, z), (43.0, y + 0.35 * idx, z))
        self.ctx.preview.show_text(f"demo:{idx}:label:size", self.owner_tool, row.label, (-10.0, y, z), size_px=12)

    def _refresh_dependent_primitives(self) -> None:
        handles = self._handles_by_id()
        for idx, _row in enumerate(self.rows):
            self._refresh_row(idx, handles)

    def _refresh_row(self, idx: int, handles: dict[str, GizmoHandle]) -> None:
        def pos(suffix: str) -> Point3 | None:
            handle = handles.get(f"demo:{idx}:{suffix}")
            return handle.position if handle is not None else None

        fixed_a = pos("line_fixed:a")
        fixed_b = pos("line_fixed:b")
        if fixed_a is not None and fixed_b is not None:
            self.ctx.preview.show_line(f"demo:{idx}:line_fixed", self.owner_tool, fixed_a, fixed_b)
        grab_a = pos("line_grab:a")
        grab_b = pos("line_grab:b")
        if grab_a is not None and grab_b is not None:
            self.ctx.preview.show_line(f"demo:{idx}:line_grab", self.owner_tool, grab_a, grab_b)
        center = pos("circle:center")
        radius_pt = pos("circle:radius")
        if center is not None and radius_pt is not None:
            radius = max(1.0, hypot(radius_pt[0] - center[0], radius_pt[1] - center[1]))
            circle = tuple(
                (center[0] + cos((2.0 * pi * step) / 48.0) * radius, center[1] + sin((2.0 * pi * step) / 48.0) * radius, center[2])
                for step in range(49)
            )
            self.ctx.preview.show_circle(f"demo:{idx}:circle", self.owner_tool, circle)
            self.ctx.preview.show_line(f"demo:{idx}:circle_radius", self.owner_tool, center, radius_pt)

    def _set_interaction_state(self, *, hover_id: str | None, grabbed_id: str | None) -> None:
        # Central API: every production tool should use this semantic update path
        # instead of rebuilding actors when hover/grab changes.
        self.ctx.gizmos.update_interaction_state(
            self.owner_tool,
            hover_id=hover_id,
            grabbed_id=grabbed_id,
            kind_prefix="demo_",
        )

    def _handles_by_id(self) -> dict[str, GizmoHandle]:
        return {handle.id: handle for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool)}

    def snapshot(self) -> HandleDemoSnapshot:
        handles = [h for h in self.ctx.gizmos.handles(owner_tool=self.owner_tool) if str(h.kind).startswith("demo_")]
        previews = [p for p in self.ctx.preview.items(owner_tool=self.owner_tool) if str(p.id).startswith("demo:")]
        labels = sum(1 for p in previews if getattr(p.kind, "value", p.kind) == "text")
        return HandleDemoSnapshot(
            rows=len(self.rows),
            handles=len(handles),
            fixed_handles=sum(1 for h in handles if str(h.kind).startswith("demo_fixed")),
            grabbable_handles=sum(1 for h in handles if self.is_grabbable(h)),
            hover_handles=sum(1 for h in handles if h.hover),
            grabbed_handles=sum(1 for h in handles if h.grabbed),
            previews=len(previews),
            labels=labels,
            notes=tuple(self.notes),
        )



@dataclass(frozen=True, slots=True)
class SelectionDemoSnapshot:
    actors: int
    fixed_actors: int
    selectable_actors: int
    grabbable_actors: int
    selected_actors: int
    notes: tuple[str, ...]


class SelectionDemoBuilder:
    """Selection/grab demo built on the public Tool Core actor contract."""

    owner_tool = "tool_core_diag"
    actor_prefix = "selection_demo:"

    def __init__(self, ctx: ToolContext) -> None:
        self.ctx = ctx
        self.notes: list[str] = []

    def build_demo(self) -> SelectionDemoSnapshot:
        self.reset_visuals()
        self._register_default_actors()
        self._build_overlay()
        self.render_visuals()
        self.notes.append("Selection demo: fixed actors ignore clicks; selectable actors can be selected; grabbable actors move only after selection.")
        self.notes.append("Shift/additive selection is handled by SelectionManager.select_at(additive=True), not by per-tool ad-hoc lists.")
        self.notes.append("Points, lines and the circle sample are registered as ToolActor objects with one interaction policy.")
        return self.snapshot()

    def reset_visuals(self) -> None:
        self.ctx.gizmos.clear_tool(self.owner_tool)
        self.ctx.preview.clear_tool(self.owner_tool)
        self.ctx.selection.clear_tool(self.owner_tool)
        self.ctx.selection.clear()
        self.notes.clear()
        backend = self.ctx.gizmos.backend
        if hasattr(backend, "handles"):
            try:
                backend.handles = {key: value for key, value in backend.handles.items() if value.owner_tool != self.owner_tool}
            except Exception:
                pass

    def _register_default_actors(self) -> None:
        z = 0.42
        actors = [
            ToolActor(
                f"{self.actor_prefix}point_fixed",
                ActorKind.POINT,
                self.owner_tool,
                ((0.0, 0.0, z),),
                ActorInteraction.FIXED,
                hit_radius_px=13.0,
                metadata={"label": "fixed point"},
            ),
            ToolActor(
                f"{self.actor_prefix}point_selectable",
                ActorKind.POINT,
                self.owner_tool,
                ((18.0, 0.0, z),),
                ActorInteraction.SELECTABLE,
                hit_radius_px=14.0,
                metadata={"label": "selectable point"},
            ),
            ToolActor(
                f"{self.actor_prefix}point_grabbable",
                ActorKind.POINT,
                self.owner_tool,
                ((36.0, 0.0, z),),
                ActorInteraction.GRABBABLE,
                hit_radius_px=15.0,
                metadata={"label": "grabbable point"},
            ),
            ToolActor(
                f"{self.actor_prefix}line_selectable",
                ActorKind.LINE,
                self.owner_tool,
                ((5.0, 18.0, z), (31.0, 18.0, z)),
                ActorInteraction.SELECTABLE,
                hit_radius_px=8.0,
                metadata={"label": "selectable line"},
            ),
            ToolActor(
                f"{self.actor_prefix}line_grabbable",
                ActorKind.LINE,
                self.owner_tool,
                ((45.0, 18.0, z), (74.0, 26.0, z)),
                ActorInteraction.GRABBABLE,
                hit_radius_px=8.0,
                metadata={"label": "grabbable line"},
            ),
            ToolActor(
                f"{self.actor_prefix}circle_selectable",
                ActorKind.CIRCLE,
                self.owner_tool,
                ((91.0, 18.0, z), (101.0, 18.0, z)),
                ActorInteraction.SELECTABLE,
                hit_radius_px=7.0,
                metadata={"label": "selectable circle"},
            ),
        ]
        for actor in actors:
            self.ctx.selection.register_actor(actor)

    def _build_overlay(self) -> None:
        self.ctx.overlay.show_window(
            OverlayWindowSpec(
                id="diag.selection_demo.window",
                title="Selection contract",
                owner_tool=self.owner_tool,
                fields=[
                    OverlayFieldSpec("diag.selection_demo.rule1", "Fixed", "no hit, no selection, no grab", kind="info"),
                    OverlayFieldSpec("diag.selection_demo.rule2", "Selectable", "click selects; Shift adds", kind="info"),
                    OverlayFieldSpec("diag.selection_demo.rule3", "Grabbable", "selected actors move together", kind="info"),
                ],
                buttons=[ToolButtonSpec("diag.selection_demo.window.close", "Close", icon="close")],
                anchor="viewport_top_right",
                overlay_kind="inspector",
                width_px=325,
                close_on_click_outside=True,
            )
        )

    def render_visuals(self) -> SelectionDemoSnapshot:
        self.ctx.gizmos.clear_tool(self.owner_tool)
        self.ctx.preview.clear_tool(self.owner_tool)
        self._build_overlay()
        for actor in self.ctx.selection.actors(owner_tool=self.owner_tool):
            self._render_actor(actor)
        self.ctx.preview.show_text(
            f"{self.actor_prefix}label",
            self.owner_tool,
            "Click: select · Shift+click: multi-select · drag selected grabbable actors",
            (10.0, -10.0, 0.42),
            size_px=12,
            anchor="left",
        )
        return self.snapshot()

    def _render_actor(self, actor: ToolActor) -> None:
        selected = self.ctx.selection.is_selected(actor.id)
        grabbed = actor.id in self.ctx.selection.state.grabbed_ids
        hover = actor.id == self.ctx.selection.state.hover_id
        state = (
            GizmoVisualState.GRABBED
            if grabbed
            else GizmoVisualState.HOVER
            if hover
            else GizmoVisualState.SELECTED
            if selected
            else GizmoVisualState.GRABBABLE
            if actor.grabbable
            else GizmoVisualState.GRABBABLE
            if actor.selectable
            else GizmoVisualState.FIXED
        )
        style_id = "target" if selected or grabbed else "solid"
        style = get_point_style(style_id)
        color = style.color_for(state)
        radius = self.ctx.gizmos.radius_for_style(style_id, 11, state)
        kind = actor.kind.value if isinstance(actor.kind, ActorKind) else str(actor.kind)
        if kind == ActorKind.POINT.value and actor.points:
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=actor.id,
                    owner_tool=self.owner_tool,
                    position=actor.points[0],
                    radius_px=radius,
                    color=color,
                    selected=selected,
                    hover=hover,
                    grabbed=grabbed,
                    selectable=actor.selectable,
                    kind=f"selection_{actor.interaction_mode.value}_point",
                    style_id=style_id,
                    base_radius_px=11,
                    screen_locked=True,
                )
            )
            return
        if kind == ActorKind.LINE.value and len(actor.points) >= 2:
            payload = {
                "color": "#f0a805" if selected else "#0b4f86" if actor.grabbable else "#263445",
                "line_width": 6.0 if selected or grabbed else 4.0,
            }
            self.ctx.preview.show_line(actor.id, self.owner_tool, actor.points[0], actor.points[1], payload=payload)
            if selected or grabbed:
                mid = _midpoint(actor.points[0], actor.points[1])
                self.ctx.gizmos.create_handle(
                    GizmoHandle(
                        id=f"{actor.id}:selection_midpoint",
                        owner_tool=self.owner_tool,
                        position=mid,
                        radius_px=radius,
                        color=color,
                        selected=selected,
                        grabbed=grabbed,
                        selectable=False,
                        kind="selection_line_midpoint",
                        style_id="target",
                        base_radius_px=10,
                        screen_locked=True,
                    )
                )
            return
        if kind == ActorKind.CIRCLE.value and len(actor.points) >= 2:
            center, radius_pt = actor.points[0], actor.points[1]
            radius_world = max(1.0, hypot(radius_pt[0] - center[0], radius_pt[1] - center[1]))
            circle = tuple(
                (center[0] + cos((2.0 * pi * step) / 64.0) * radius_world, center[1] + sin((2.0 * pi * step) / 64.0) * radius_world, center[2])
                for step in range(65)
            )
            self.ctx.preview.show_circle(
                actor.id,
                self.owner_tool,
                circle,
                payload={"color": "#f0a805" if selected else "#263445", "line_width": 5.0 if selected else 3.0},
            )
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=f"{actor.id}:center",
                    owner_tool=self.owner_tool,
                    position=center,
                    radius_px=max(7, radius - 2),
                    color=color,
                    selected=selected,
                    selectable=False,
                    kind="selection_circle_center",
                    style_id=style_id,
                    base_radius_px=9,
                    screen_locked=True,
                )
            )

    def hit_actor(self, screen_pos: tuple[float, float], world_to_screen) -> str | None:
        hit = self.ctx.selection.hit_test(screen_pos, world_to_screen, owner_tool=self.owner_tool, selectable_only=True)
        self.ctx.selection.set_hover(None if hit is None else hit.actor_id)
        return None if hit is None else hit.actor_id

    def select_at(self, screen_pos: tuple[float, float], world_to_screen, *, additive: bool = False) -> str | None:
        hit = self.ctx.selection.select_at(screen_pos, world_to_screen, owner_tool=self.owner_tool, additive=additive)
        return None if hit is None else hit.actor_id

    def begin_grab_if_possible(self, actor_id: str | None, screen_pos: tuple[float, float]) -> tuple[str, ...]:
        return self.ctx.selection.begin_grab(actor_id, screen_pos)

    def move_selected(self, delta_world: Point3) -> int:
        changed = self.ctx.selection.move_selected(delta_world, grabbable_only=True)
        if changed:
            self.ctx.profiler.increment("diag.selection_demo.moves")
        return changed

    def snapshot(self) -> SelectionDemoSnapshot:
        actors = self.ctx.selection.actors(owner_tool=self.owner_tool)
        return SelectionDemoSnapshot(
            actors=len(actors),
            fixed_actors=sum(1 for actor in actors if actor.interaction_mode == ActorInteraction.FIXED),
            selectable_actors=sum(1 for actor in actors if actor.interaction_mode == ActorInteraction.SELECTABLE),
            grabbable_actors=sum(1 for actor in actors if actor.interaction_mode == ActorInteraction.GRABBABLE),
            selected_actors=len(self.ctx.selection.selected_actors()),
            notes=tuple(self.notes),
        )


def _midpoint(a: Point3, b: Point3) -> Point3:
    return ((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5, (float(a[2]) + float(b[2])) * 0.5)
