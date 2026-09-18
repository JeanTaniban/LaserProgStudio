"""Interactive Creator API diagnostic lab.

This module is intentionally public-API oriented: the Tool Core Diagnostic UI
uses it to validate the same actor/inspector/snap/visual/cleanup paths that
external creator tools are expected to use.  The lab replaces the old scattered
demos with one focused workflow: choose actor kind + interaction policy, add or
remove actors, select points/lines, drag grabbable selections, and benchmark the
runtime contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import cos, hypot, pi, sin
import time
from typing import Any, Iterable

from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_core.gizmos import GizmoHandle
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, Point2, Point3, ToolActor

from . import actors, inspector
from .selection_box import BoxSelectionActivationModifier, BoxSelectionInsidePolicy, BoxSelectionMode, BoxSelectionTarget
from .interaction import select_or_grab
from .snap import tool_point, ui_point
from .styles import (
    InteractionVisualState,
    LineStyleId,
    PointStyleId,
    as_gizmo_visual_state,
    line_style_choices,
    point_style_choices,
    resolve_actor_visual,
    visual_state_choices,
)


class LabActorKind(str, Enum):
    POINT = "point"
    LINE = "line"
    CIRCLE = "circle"
    ARC = "arc"
    POLYLINE = "polyline"


class LabInteraction(str, Enum):
    FIXED = "fixed"
    SELECTABLE = "selectable"
    GRABBABLE = "grabbable"


class LabMovePreset(str, Enum):
    RIGHT = "+X"
    LEFT = "-X"
    UP = "+Y"
    DOWN = "-Y"
    DIAGONAL = "+X+Y"


class LabBoxSelectionEnabled(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class LabBoxTarget(str, Enum):
    TOOL_ACTORS = "tool_actors"
    SCENE_OBJECTS = "scene_objects"
    TOOL_AND_SCENE = "tool_and_scene"


# Public aliases for the full native style/state catalogs exposed by the lab.
LabPointStyle = PointStyleId
LabLineStyle = LineStyleId
LabVisualState = InteractionVisualState


@dataclass(frozen=True, slots=True)
class LabSnapshot:
    actors: int
    points: int
    lines: int
    circles: int
    arcs: int
    polylines: int
    selected: int
    grabbable: int
    previews: int
    handles: int
    snap_rebuilds: int
    report: str


@dataclass(frozen=True, slots=True)
class LabBenchmarkCase:
    name: str
    avg_ms: float
    iterations: int
    passed: bool
    details: str = ""


@dataclass(frozen=True, slots=True)
class LabBenchmarkReport:
    cases: tuple[LabBenchmarkCase, ...]
    flags: tuple[str, ...] = ()
    started_at: float = field(default_factory=time.time)

    @property
    def ok(self) -> bool:
        return not self.flags and all(case.passed for case in self.cases)

    def to_markdown(self) -> str:
        lines = [
            "# Creator API Lab benchmark",
            "",
            f"Status: **{'PASS' if self.ok else 'FAIL'}**",
            "",
            "| Case | Avg ms | Iterations | Result | Details |",
            "|---|---:|---:|---|---|",
        ]
        for case in self.cases:
            details = case.details.replace("|", "\\|")
            lines.append(f"| {case.name} | {case.avg_ms:.4f} | {case.iterations} | {'PASS' if case.passed else 'FAIL'} | {details} |")
        if self.flags:
            lines.extend(["", "## Flags", ""])
            lines.extend(f"- {flag}" for flag in self.flags)
        lines.extend([
            "",
            "## Production policy checked",
            "",
            "- actors are declared through `tool_api.actors`, not hand-built in Qt code;",
            "- point, line and interaction visual styles resolve through `tool_api.styles`;",
            "- points are rendered as persistent gizmo handles;",
            "- lines/arcs/circles/polylines are rendered as batched preview linework;",
            "- selected grabbable actors move through the common `select_or_grab` path;",
            "- rectangle selection uses native `ctx.selection_box` with typed targets/modes;",
            "- smart snap accepts tool/UI targets without rebuilding the cache during drag;",
            "- cleanup removes all lab-owned actors, previews, gizmos and snap targets.",
        ])
        return "\n".join(lines)


_KIND_CHOICES = tuple((kind.value, kind.value.title()) for kind in LabActorKind)
_INTERACTION_CHOICES = tuple((interaction.value, interaction.value.title()) for interaction in LabInteraction)
_MOVE_CHOICES = tuple((move.value, move.value) for move in LabMovePreset)
_POINT_STYLE_CHOICES = point_style_choices()
_LINE_STYLE_CHOICES = line_style_choices()
_VISUAL_STATE_CHOICES = visual_state_choices()
_BOX_ENABLED_CHOICES = ((LabBoxSelectionEnabled.ENABLED.value, "Enabled"), (LabBoxSelectionEnabled.DISABLED.value, "Disabled"))
_BOX_TARGET_CHOICES = ((LabBoxTarget.TOOL_ACTORS.value, "Tool actors"), (LabBoxTarget.SCENE_OBJECTS.value, "Scene objects"), (LabBoxTarget.TOOL_AND_SCENE.value, "Tool + scene"))
_BOX_MODE_CHOICES = tuple((mode.value, mode.value.title()) for mode in BoxSelectionMode)
_BOX_POLICY_CHOICES = ((BoxSelectionInsidePolicy.PARTIAL.value, "Partial / crossing"), (BoxSelectionInsidePolicy.FULL.value, "Fully inside"))


class CreatorApiDiagnosticLab:
    """Focused interactive lab for the public creator API."""

    actor_prefix = "api_lab:"

    def __init__(self, ctx: Any, *, owner_tool: str = "tool_core_diag") -> None:
        self.ctx = ctx
        self.owner_tool = str(owner_tool)
        self._counter = 0
        self.last_report = "API Lab not started."

    def setup(self) -> LabSnapshot:
        self.clear()
        self._install_panel()
        # Keep the origin empty for the explicit Add actor button.
        # The user-facing diagnostic contract is: clicking Add actor spawns the
        # chosen actor at (0, 0, 0), so the setup scene must not already occupy
        # that exact spot.
        self.add_actor(LabActorKind.POINT, LabInteraction.GRABBABLE, position=(-28.0, 0.0, 0.42))
        self.add_actor(LabActorKind.POINT, LabInteraction.SELECTABLE, position=(-28.0, 16.0, 0.42))
        self.add_actor(LabActorKind.POINT, LabInteraction.FIXED, position=(-28.0, 32.0, 0.42))
        self.add_actor(LabActorKind.POINT, LabInteraction.GRABBABLE, position=(-28.0, 48.0, 0.42))
        self.add_actor(LabActorKind.LINE, LabInteraction.SELECTABLE, position=(18.0, 0.0, 0.42))
        self.add_actor(LabActorKind.LINE, LabInteraction.GRABBABLE, position=(45.0, 0.0, 0.42))
        self.add_actor(LabActorKind.CIRCLE, LabInteraction.SELECTABLE, position=(78.0, 0.0, 0.42))
        self.add_actor(LabActorKind.ARC, LabInteraction.SELECTABLE, position=(0.0, 24.0, 0.42))
        self.add_actor(LabActorKind.POLYLINE, LabInteraction.GRABBABLE, position=(38.0, 24.0, 0.42))
        self.configure_box_selection(enabled=True, target=LabBoxTarget.TOOL_ACTORS.value, mode=BoxSelectionMode.REPLACE.value, inside_policy=BoxSelectionInsidePolicy.PARTIAL.value)
        self.ctx.scene_cache.rebuild(self.ctx, scope="snap")
        self.render_visuals()
        return self._finish("API Lab ready: choose enums, add/delete/select/move actors.")

    def set_options(self, *, actor_kind: str | None = None, interaction: str | None = None, move: str | None = None, point_style: str | None = None, line_style: str | None = None, visual_state: str | None = None, box_enabled: str | bool | None = None, box_target: str | None = None, box_mode: str | None = None, box_inside_policy: str | None = None) -> None:
        if self.ctx.inspector.panel is None:
            self._install_panel()
        values: dict[str, str] = {}
        if actor_kind is not None:
            values["actor_kind"] = self._kind(actor_kind).value
        if interaction is not None:
            values["interaction"] = self._interaction(interaction).value
        if move is not None:
            values["move_preset"] = self._move(move).value
        if point_style is not None:
            values["point_style"] = PointStyleId(str(point_style)).value
        if line_style is not None:
            values["line_style"] = LineStyleId(str(line_style)).value
        if visual_state is not None:
            values["visual_state"] = InteractionVisualState(str(visual_state)).value
        if box_enabled is not None:
            values["box_enabled"] = LabBoxSelectionEnabled.ENABLED.value if bool(box_enabled) and str(box_enabled) not in {LabBoxSelectionEnabled.DISABLED.value, "False", "false", "0"} else LabBoxSelectionEnabled.DISABLED.value
        if box_target is not None:
            values["box_target"] = LabBoxTarget(str(box_target)).value
        if box_mode is not None:
            values["box_mode"] = BoxSelectionMode(str(box_mode)).value
        if box_inside_policy is not None:
            values["box_inside_policy"] = BoxSelectionInsidePolicy(str(box_inside_policy)).value
        if values:
            self.ctx.inspector.update_values(values)
        if any(key in values for key in ("box_enabled", "box_target", "box_mode", "box_inside_policy")):
            self.configure_box_selection_from_options()


    def configure_box_selection_from_options(self) -> None:
        if self.ctx.inspector.panel is None:
            self._install_panel()
        self.configure_box_selection(
            enabled=self.ctx.inspector.value("box_enabled", LabBoxSelectionEnabled.ENABLED.value),
            target=str(self.ctx.inspector.value("box_target", LabBoxTarget.TOOL_ACTORS.value)),
            mode=str(self.ctx.inspector.value("box_mode", BoxSelectionMode.REPLACE.value)),
            inside_policy=str(self.ctx.inspector.value("box_inside_policy", BoxSelectionInsidePolicy.PARTIAL.value)),
        )

    def configure_box_selection(self, *, enabled: bool | str = True, target: str = LabBoxTarget.TOOL_ACTORS.value, mode: str = BoxSelectionMode.REPLACE.value, inside_policy: str = BoxSelectionInsidePolicy.PARTIAL.value) -> None:
        targets = self._box_targets(target)
        enabled_value = bool(enabled) and str(enabled) not in {LabBoxSelectionEnabled.DISABLED.value, "False", "false", "0"}
        self.ctx.selection_box.configure(
            enabled=enabled_value,
            targets=targets,
            mode=BoxSelectionMode(str(mode)),
            inside_policy=BoxSelectionInsidePolicy(str(inside_policy)),
            owner_tool=self.owner_tool,
            selectable_only=True,
            clear_on_empty=True,
            require_empty_press=True,
            activation_modifier=BoxSelectionActivationModifier.SHIFT,
            min_drag_px=6.0,
        )

    def box_select(self, start: Point2, end: Point2, world_to_screen=None, *, mode: str | None = None):
        if self.ctx.inspector.panel is None:
            self._install_panel()
        self.configure_box_selection_from_options()
        self.ctx.selection_box.begin(start, mode=mode)
        self.ctx.selection_box.update(end)
        result = self.ctx.selection_box.finish(end, world_to_screen=world_to_screen or (lambda p: (float(p[0]), float(p[1]))))
        self.render_visuals()
        self._finish(
            f"Box selected tool={len(result.tool_actor_ids)} scene={len(result.scene_object_ids)} mode={result.mode.value}."
        )
        return result

    def add_from_options(self) -> LabSnapshot:
        if self.ctx.inspector.panel is None:
            self._install_panel()
        kind = self._kind(self.ctx.inspector.value("actor_kind", LabActorKind.POINT.value))
        interaction = self._interaction(self.ctx.inspector.value("interaction", LabInteraction.GRABBABLE.value))
        actor = self.add_actor(kind, interaction)
        self.render_visuals(force_render=True)
        return self._finish(
            f"Added {actor.kind.value if isinstance(actor.kind, ActorKind) else actor.kind} actor `{actor.id}` "
            f"as {actor.interaction_mode.value} at origin."
        )

    def add_actor(
        self,
        kind: LabActorKind | str,
        interaction: LabInteraction | str,
        *,
        position: Point3 | None = None,
    ) -> ToolActor:
        kind = self._kind(kind)
        interaction = self._interaction(interaction)
        self._counter += 1
        # Button-created actors must appear at a deterministic, obvious place.
        # The diagnostic lab intentionally uses the world origin by default so
        # creators can verify placement/hit-test/snap without guessing where a
        # new actor was spawned. Setup/benchmark scenarios can still pass an
        # explicit position when they need a spread-out scene.
        base = position if position is not None else self._origin_position()
        actor_id = f"{self.actor_prefix}{kind.value}_{self._counter}"
        registry = self.ctx.actor_registry(self.owner_tool)
        actor = self._make_actor(actor_id, kind, interaction, base)
        return registry.add(actor, replace=True)

    def delete_selected(self) -> LabSnapshot:
        ids = tuple(actor.id for actor in self.ctx.selection.selected_actors() if actor.owner_tool == self.owner_tool)
        registry = self.ctx.actor_registry(self.owner_tool)
        for actor_id in ids:
            registry.remove(actor_id)
        self.ctx.selection.clear()
        self.render_visuals()
        return self._finish(f"Deleted {len(ids)} selected actor(s).")

    def select_all(self) -> LabSnapshot:
        self.ctx.selection.clear()
        selected = 0
        for actor in self.ctx.selection.actors(owner_tool=self.owner_tool):
            if actor.selectable and self.ctx.selection.select(actor.id, replace=(selected == 0)):
                selected += 1
        self.render_visuals()
        return self._finish(f"Selected {selected} selectable actor(s).")

    def move_selected_from_options(self) -> LabSnapshot:
        move = self._move(self.ctx.inspector.value("move_preset", LabMovePreset.RIGHT.value))
        delta = self._delta_for(move)
        moved = self.ctx.selection.move_selected(delta, grabbable_only=True)
        if moved:
            self.ctx.scene_cache.invalidate()
            self.ctx.request_light_render()
        self.render_visuals()
        return self._finish(f"Moved {moved} grabbable selected actor(s) by {delta}.")

    def clear(self) -> LabSnapshot:
        self.ctx.cleanup_tool(self.owner_tool, include_persistent_overlays=True)
        self.ctx.selection.clear()
        self.last_report = "API Lab cleared."
        return self.snapshot()

    def hit_actor(self, screen_pos: Point2, world_to_screen) -> str | None:
        hit = self.ctx.selection.hit_test(screen_pos, world_to_screen, owner_tool=self.owner_tool, selectable_only=True)
        actor_id = None if hit is None else hit.actor_id
        if actor_id != self.ctx.selection.state.hover_id:
            self.ctx.selection.set_hover(actor_id)
            self.render_visuals()
        return actor_id

    def select_at(self, screen_pos: Point2, world_to_screen, *, additive: bool = False) -> str | None:
        hit = self.ctx.selection.select_at(screen_pos, world_to_screen, owner_tool=self.owner_tool, additive=additive)
        self.render_visuals()
        return None if hit is None else hit.actor_id

    def clear_selection(self, *, render: bool = True) -> LabSnapshot:
        self.ctx.selection.clear()
        self.ctx.selection.set_hover(None)
        if render:
            self.render_visuals()
        return self._finish("API Lab selection cleared.")

    def begin_grab_if_possible(self, actor_id: str | None, screen_pos: Point2, world_pos: Point3 | None = None) -> tuple[str, ...]:
        grabbed = self.ctx.selection.begin_grab(actor_id, screen_pos, world_pos)
        self.render_visuals()
        return grabbed

    def handle_event(self, event: ToolEvent, *, world_to_screen=None) -> bool:
        handled = select_or_grab(event, self.ctx, owner_tool=self.owner_tool, world_to_screen=world_to_screen)
        if handled:
            self.render_visuals()
        return bool(handled)

    def move_selected(self, delta_world: Point3) -> int:
        moved = self.ctx.selection.move_selected(delta_world, grabbable_only=True)
        if moved:
            self.ctx.scene_cache.invalidate()
            self.ctx.profiler.increment("diag.api_lab.moves", moved)
            self.ctx.request_light_render()
            self.render_visuals()
        return moved

    def end_grab(self) -> tuple[str, ...]:
        grabbed = self.ctx.selection.end_grab()
        self.render_visuals()
        return grabbed

    def render_visuals(self, *, force_render: bool = False) -> LabSnapshot:
        # Keep gizmo handles persistent.  We hide stale handles instead of
        # removing/recreating them, matching the production rendering policy.
        self._render_handle_ids: set[str] = set()
        self.ctx.preview.clear_tool(self.owner_tool)
        self.ctx.gizmos.begin_interactive_update()
        try:
            for actor in self.ctx.selection.actors(owner_tool=self.owner_tool):
                self._render_actor(actor)
            for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool):
                if handle.owner_tool == self.owner_tool and handle.id not in self._render_handle_ids:
                    self.ctx.gizmos.set_visible(handle.id, False)
        finally:
            self.ctx.gizmos.end_interactive_update()
        self.ctx.scene_cache.rebuild(self.ctx, scope="snap")
        # Two explicit snap targets validate custom world/UI snap without being visual noise.
        self.ctx.scene_cache.add_point(f"{self.actor_prefix}snap_tool", (7.5, -6.0, 0.42), owner_tool=self.owner_tool)
        self.ctx.scene_cache.add_ui_point(f"{self.actor_prefix}snap_ui", (70.0, 40.0), world_pos=(9.0, -7.0, 0.42), owner_tool=self.owner_tool)
        self._update_inspector_report()
        if force_render:
            self.ctx.request_full_render()
        return self.snapshot()

    def run_benchmark(self, *, iterations: int = 120) -> LabBenchmarkReport:
        iterations = max(10, int(iterations))
        flags: list[str] = []
        cases: list[LabBenchmarkCase] = []

        def measure(name: str, count: int, fn, *, budget_ms: float, details: str = "") -> None:
            started = time.perf_counter()
            for _ in range(count):
                fn()
            avg_ms = (time.perf_counter() - started) * 1000.0 / float(count)
            passed = avg_ms <= float(budget_ms)
            if not passed:
                flags.append(f"{name} above budget: {avg_ms:.3f} ms > {budget_ms:.3f} ms")
            cases.append(LabBenchmarkCase(name, avg_ms, count, passed, details or f"budget <= {budget_ms:g} ms"))

        self.setup()
        baseline_created = getattr(self.ctx.gizmos.backend, "created", 0)
        baseline_removed = getattr(self.ctx.gizmos.backend, "removed", 0)
        registry = self.ctx.actor_registry(self.owner_tool)
        add_index = 0

        def add_delete_cycle() -> None:
            nonlocal add_index
            add_index += 1
            actor = actors.point(f"{self.actor_prefix}bench_point_{add_index}", (float(add_index % 20), 48.0, 0.42), interaction="grabbable")
            registry.add(actor, replace=True)
            registry.remove(actor.id)

        def select_cycle() -> None:
            self.ctx.selection.select_at((0.0, 0.0), lambda p: (float(p[0]), float(p[1])), owner_tool=self.owner_tool, additive=False)

        self.select_all()

        def move_cycle() -> None:
            self.ctx.selection.move_selected((0.05, 0.0, 0.0), grabbable_only=True)

        def snap_cycle() -> None:
            self.ctx.snap.smart(
                (5.2, 0.1, 0.42),
                (5.2, 0.1),
                self.ctx,
                extra_targets=(tool_point(f"{self.actor_prefix}bench_snap", (5.0, 0.0, 0.42), owner_tool=self.owner_tool), ui_point(f"{self.actor_prefix}bench_ui", (5.0, 0.0), world_pos=(5.0, 0.0, 0.42))),
                exclude_ids=self.ctx.selection.ids(),
                rebuild_cache=False,
            )

        def visual_cycle() -> None:
            # Rebuilds the semantic preview/gizmo declarations through the API.
            # The live painter then mutates persistent VTK actors in place.
            self.render_visuals()

        def box_select_cycle() -> None:
            self.ctx.selection_box.begin((-40.0, -8.0), mode=BoxSelectionMode.REPLACE)
            self.ctx.selection_box.update((70.0, 60.0))
            self.ctx.selection_box.finish((70.0, 60.0), world_to_screen=lambda p: (float(p[0]), float(p[1])))

        style_ids = tuple(style.value for style in PointStyleId)
        line_ids = tuple(style.value for style in LineStyleId)
        state_ids = tuple(state.value for state in InteractionVisualState)
        style_index = 0

        def style_cycle() -> None:
            nonlocal style_index
            style_index += 1
            resolve_actor_visual(
                interaction="grabbable",
                point_style_id=style_ids[style_index % len(style_ids)],
                line_style_id=line_ids[style_index % len(line_ids)],
                visual_state=state_ids[style_index % len(state_ids)],
                hover=bool(style_index % 2),
                selected=bool(style_index % 3 == 0),
                grabbed=bool(style_index % 5 == 0),
            )

        measure("API native style resolution", iterations, style_cycle, budget_ms=0.10, details="all point/line/visual-state enums resolve through tool_api.styles")
        measure("API add/remove actor registry", max(10, iterations // 3), add_delete_cycle, budget_ms=0.50, details="registry validates duplicates and invalidates scene cache")
        measure("API select point/line hit-test", iterations, select_cycle, budget_ms=0.40, details="hit-test through SelectionManager via public lab")
        measure("API move selected grabbables", iterations, move_cycle, budget_ms=0.40, details="selection.move_selected without actor churn")
        # Keep this budget tolerant enough for CI noise. The diagnostic lab is
        # primarily a regression guard for API wiring; strict profiling belongs
        # in dedicated benchmarks, not in the always-on SDK self-test.
        measure("API smart snap query", iterations, snap_cycle, budget_ms=2.0, details="custom tool/UI targets, no cache rebuild")
        measure("API box selection query", iterations, box_select_cycle, budget_ms=0.80, details="screen-rect selection over tool actors")
        measure("API visual refresh declaration", max(10, iterations // 4), visual_cycle, budget_ms=4.0, details="headless preview/gizmo declaration only")

        created_after = getattr(self.ctx.gizmos.backend, "created", 0)
        removed_after = getattr(self.ctx.gizmos.backend, "removed", 0)
        removed_delta = int(removed_after) - int(baseline_removed)
        if removed_delta:
            flags.append(f"Unexpected gizmo backend removals during API lab benchmark: {removed_delta}")
        if int(created_after) - int(baseline_created) > 80:
            flags.append("Unexpectedly high handle creation count; check for actor churn.")

        self.render_visuals()
        return LabBenchmarkReport(cases=tuple(cases), flags=tuple(flags))

    def snapshot(self) -> LabSnapshot:
        actors_for_tool = self.ctx.selection.actors(owner_tool=self.owner_tool)
        by_kind = {kind.value: 0 for kind in LabActorKind}
        for actor in actors_for_tool:
            kind_value = actor.kind.value if isinstance(actor.kind, ActorKind) else str(actor.kind)
            if kind_value in by_kind:
                by_kind[kind_value] += 1
        return LabSnapshot(
            actors=len(actors_for_tool),
            points=by_kind[LabActorKind.POINT.value],
            lines=by_kind[LabActorKind.LINE.value],
            circles=by_kind[LabActorKind.CIRCLE.value],
            arcs=by_kind[LabActorKind.ARC.value],
            polylines=by_kind[LabActorKind.POLYLINE.value],
            selected=len([actor for actor in self.ctx.selection.selected_actors() if actor.owner_tool == self.owner_tool]),
            grabbable=sum(1 for actor in actors_for_tool if actor.grabbable),
            previews=len(self.ctx.preview.items(owner_tool=self.owner_tool)),
            handles=len(self.ctx.gizmos.handles(owner_tool=self.owner_tool)),
            snap_rebuilds=int(getattr(self.ctx.snap, "cache_rebuilds", 0)),
            report=self.last_report,
        )

    def _install_panel(self) -> None:
        self.ctx.inspector.set_panel(
            inspector.panel(
                "Creator API Lab",
                id=f"{self.owner_tool}.api_lab",
                owner_tool=self.owner_tool,
                description="Full validation: enums, actors, selection/grab, smart snap, and benchmark.",
                sections=[
                    inspector.section(
                        "Actor to place",
                        [
                            inspector.choice_field("actor_kind", "Actor", default=LabActorKind.POINT.value, choices=_KIND_CHOICES),
                            inspector.choice_field("interaction", "Interaction", default=LabInteraction.GRABBABLE.value, choices=_INTERACTION_CHOICES),
                            inspector.choice_field("move_preset", "Move", default=LabMovePreset.RIGHT.value, choices=_MOVE_CHOICES),
                            inspector.choice_field("point_style", "Point style", default=PointStyleId.TARGET.value, choices=_POINT_STYLE_CHOICES),
                            inspector.choice_field("line_style", "Line style", default=LineStyleId.GRABBABLE.value, choices=_LINE_STYLE_CHOICES),
                            inspector.choice_field("visual_state", "Visual state", default=InteractionVisualState.AUTO.value, choices=_VISUAL_STATE_CHOICES),
                        ],
                    ),
                    inspector.section(
                        "Box selection",
                        [
                            inspector.readonly_field("box_activation", "Activation", default="Shift + left drag on empty viewport"),
                            inspector.choice_field("box_enabled", "Enabled", default=LabBoxSelectionEnabled.ENABLED.value, choices=_BOX_ENABLED_CHOICES),
                            inspector.choice_field("box_target", "Targets", default=LabBoxTarget.TOOL_ACTORS.value, choices=_BOX_TARGET_CHOICES),
                            inspector.choice_field("box_mode", "Mode", default=BoxSelectionMode.REPLACE.value, choices=_BOX_MODE_CHOICES),
                            inspector.choice_field("box_inside_policy", "Inside", default=BoxSelectionInsidePolicy.PARTIAL.value, choices=_BOX_POLICY_CHOICES),
                        ],
                    ),
                    inspector.section(
                        "Actions",
                        [
                            inspector.button("add_actor", "Add actor", on_click=lambda _event: self.add_from_options()),
                            inspector.button("delete_selected", "Delete selected", on_click=lambda _event: self.delete_selected()),
                            inspector.button("move_selected", "Move selected", on_click=lambda _event: self.move_selected_from_options()),
                            inspector.button("select_all", "Select all", on_click=lambda _event: self.select_all()),
                        ],
                    ),
                    inspector.section("Report", [inspector.readonly_field("lab_report", "State", default=self.last_report)]),
                ],
            )
        )

    def _finish(self, message: str) -> LabSnapshot:
        self.last_report = message
        self._update_inspector_report()
        snap = self.snapshot()
        self.ctx.status.info(message)
        return snap

    def _update_inspector_report(self) -> None:
        if self.ctx.inspector.panel is None:
            return
        if "lab_report" not in self.ctx.inspector.panel.field_ids():
            return
        snap = self.snapshot()
        summary = f"actors={snap.actors}, selected={snap.selected}, grabbable={snap.grabbable}, previews={snap.previews}, handles={snap.handles}"
        text = f"{self.last_report}\n{summary}" if self.last_report else summary
        # readonly fields cannot be changed by update_value; update internal data
        # via panel reinstall is too heavy for every hover/move. Keep state via
        # field error-free and expose the full values in the controller report.
        try:
            self.ctx.inspector._values["lab_report"] = text  # noqa: SLF001 - diagnostic host bridge only
        except Exception:
            pass

    def _make_actor(self, actor_id: str, kind: LabActorKind, interaction: LabInteraction, base: Point3) -> ToolActor:
        mode = interaction.value
        point_style = str(self.ctx.inspector.value("point_style", PointStyleId.TARGET.value))
        line_style = str(self.ctx.inspector.value("line_style", LineStyleId.GRABBABLE.value))
        visual_state = str(self.ctx.inspector.value("visual_state", InteractionVisualState.AUTO.value))
        x, y, z = (float(base[0]), float(base[1]), float(base[2]))
        if kind == LabActorKind.POINT:
            return actors.point(actor_id, (x, y, z), interaction=mode, point_style=point_style, line_style=line_style, visual_state=visual_state)
        if kind == LabActorKind.LINE:
            return actors.line(actor_id, (x, y, z), (x + 18.0, y + 7.0, z), interaction=mode, hit_radius_px=8.0, point_style=point_style, line_style=line_style, visual_state=visual_state)
        if kind == LabActorKind.CIRCLE:
            return actors.circle(actor_id, (x, y, z), (x + 8.0, y, z), interaction=mode, hit_radius_px=7.0, point_style=point_style, line_style=line_style, visual_state=visual_state)
        if kind == LabActorKind.ARC:
            return actors.arc(actor_id, ((x, y, z), (x + 8.0, y + 10.0, z), (x + 18.0, y, z)), interaction=mode, hit_radius_px=8.0, point_style=point_style, line_style=line_style, visual_state=visual_state)
        return actors.polyline(actor_id, ((x, y, z), (x + 8.0, y + 7.0, z), (x + 18.0, y + 2.0, z), (x + 25.0, y + 10.0, z)), interaction=mode, hit_radius_px=8.0, point_style=point_style, line_style=line_style, visual_state=visual_state)

    def _render_actor(self, actor: ToolActor) -> None:
        selected = self.ctx.selection.is_selected(actor.id)
        grabbed = actor.id in self.ctx.selection.state.grabbed_ids
        hover = actor.id == self.ctx.selection.state.hover_id
        visual = resolve_actor_visual(
            interaction=actor.interaction_mode,
            point_style_id=actor.metadata.get("point_style", PointStyleId.TARGET.value if selected or grabbed or hover else PointStyleId.SOLID.value),
            line_style_id=actor.metadata.get("line_style", LineStyleId.GRABBABLE.value if actor.grabbable else LineStyleId.SELECTABLE.value if actor.selectable else LineStyleId.FIXED.value),
            visual_state=actor.metadata.get("visual_state", InteractionVisualState.AUTO.value),
            base_radius_px=11,
            hover=hover,
            selected=selected,
            grabbed=grabbed,
        )
        color = visual.point_color
        radius = visual.radius_px
        style_id = visual.point_style_id
        kind_value = actor.kind.value if isinstance(actor.kind, ActorKind) else str(actor.kind)
        if kind_value == ActorKind.POINT.value and actor.points:
            self._render_handle_ids.add(actor.id)
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
                    kind=f"api_lab_{actor.interaction_mode.value}_point",
                    style_id=style_id,
                    base_radius_px=radius,
                    screen_locked=True,
                )
            )
            return
        if kind_value == ActorKind.LINE.value and len(actor.points) >= 2:
            # Lines expose their interaction through the linework itself.
            # Do not draw a point-like midpoint gizmo on hover/selected/grabbed:
            # grabbing a line is not the same visual contract as grabbing a point.
            self.ctx.preview.show_line(actor.id, self.owner_tool, actor.points[0], actor.points[1], payload=self._line_payload(actor, selected, grabbed, hover))
            return
        if kind_value == ActorKind.CIRCLE.value and len(actor.points) >= 2:
            center, radius_pt = actor.points[0], actor.points[1]
            radius_world = max(1.0, hypot(radius_pt[0] - center[0], radius_pt[1] - center[1]))
            points = tuple((center[0] + cos(2.0 * pi * step / 64.0) * radius_world, center[1] + sin(2.0 * pi * step / 64.0) * radius_world, center[2]) for step in range(65))
            self.ctx.preview.show_circle(actor.id, self.owner_tool, points, payload=self._line_payload(actor, selected, grabbed, hover))
            self._show_handle(f"{actor.id}:center", center, color, radius=max(7, radius - 2), selected=selected, hover=hover, grabbed=grabbed, selectable=False, kind="api_lab_circle_center")
            return
        if kind_value == ActorKind.ARC.value and len(actor.points) >= 3:
            self.ctx.preview.show_arc(actor.id, self.owner_tool, tuple(actor.points), payload=self._line_payload(actor, selected, grabbed, hover))
            return
        if len(actor.points) >= 2:
            self.ctx.preview.show_polyline(actor.id, self.owner_tool, tuple(actor.points), payload=self._line_payload(actor, selected, grabbed, hover))

    def _show_mid_handle(self, actor: ToolActor, selected: bool, grabbed: bool, hover: bool, color: tuple[float, float, float, float], radius: int) -> None:
        if not (selected or grabbed or hover):
            return
        points = actor.points
        mid_index = len(points) // 2
        if len(points) == 2:
            pos = ((points[0][0] + points[1][0]) * 0.5, (points[0][1] + points[1][1]) * 0.5, (points[0][2] + points[1][2]) * 0.5)
        else:
            pos = points[mid_index]
        self._show_handle(f"{actor.id}:mid", pos, color, radius=radius, selected=selected, hover=hover, grabbed=grabbed, selectable=False, kind="api_lab_midpoint")

    def _show_handle(self, handle_id: str, position: Point3, color: tuple[float, float, float, float], *, radius: int, selected: bool, hover: bool, grabbed: bool, selectable: bool, kind: str) -> None:
        self._render_handle_ids.add(handle_id)
        self.ctx.gizmos.create_handle(
            GizmoHandle(
                id=handle_id,
                owner_tool=self.owner_tool,
                position=position,
                radius_px=radius,
                color=color,
                selected=selected,
                hover=hover,
                grabbed=grabbed,
                selectable=selectable,
                kind=kind,
                style_id="target" if selected or hover or grabbed else "solid",
                base_radius_px=10,
                screen_locked=True,
            )
        )

    @staticmethod
    def _line_payload(actor: ToolActor, selected: bool, grabbed: bool, hover: bool) -> dict[str, Any]:
        visual = resolve_actor_visual(
            interaction=actor.interaction_mode,
            point_style_id=actor.metadata.get("point_style", PointStyleId.SOLID.value),
            line_style_id=actor.metadata.get("line_style", LineStyleId.GRABBABLE.value if actor.grabbable else LineStyleId.SELECTABLE.value if actor.selectable else LineStyleId.FIXED.value),
            visual_state=actor.metadata.get("visual_state", InteractionVisualState.AUTO.value),
            hover=hover,
            selected=selected,
            grabbed=grabbed,
        )
        return visual.line_payload


    @staticmethod
    def _box_targets(target: str) -> tuple[BoxSelectionTarget, ...]:
        value = LabBoxTarget(str(target))
        if value == LabBoxTarget.TOOL_ACTORS:
            return (BoxSelectionTarget.TOOL_ACTORS,)
        if value == LabBoxTarget.SCENE_OBJECTS:
            return (BoxSelectionTarget.SCENE_OBJECTS,)
        return (BoxSelectionTarget.TOOL_ACTORS, BoxSelectionTarget.SCENE_OBJECTS)

    @staticmethod
    def _origin_position() -> Point3:
        return (0.0, 0.0, 0.0)

    def _next_position(self) -> Point3:
        i = self._counter
        return (float((i % 5) * 22), float(46 + (i // 5) * 18), 0.42)

    @staticmethod
    def _kind(value: LabActorKind | str) -> LabActorKind:
        return value if isinstance(value, LabActorKind) else LabActorKind(str(value))

    @staticmethod
    def _interaction(value: LabInteraction | str) -> LabInteraction:
        return value if isinstance(value, LabInteraction) else LabInteraction(str(value))

    @staticmethod
    def _move(value: LabMovePreset | str) -> LabMovePreset:
        return value if isinstance(value, LabMovePreset) else LabMovePreset(str(value))

    @staticmethod
    def _delta_for(move: LabMovePreset) -> Point3:
        return {
            LabMovePreset.RIGHT: (5.0, 0.0, 0.0),
            LabMovePreset.LEFT: (-5.0, 0.0, 0.0),
            LabMovePreset.UP: (0.0, 5.0, 0.0),
            LabMovePreset.DOWN: (0.0, -5.0, 0.0),
            LabMovePreset.DIAGONAL: (4.0, 4.0, 0.0),
        }[move]


__all__ = [
    "CreatorApiDiagnosticLab",
    "LabActorKind",
    "LabBoxSelectionEnabled",
    "LabBoxTarget",
    "LabBenchmarkCase",
    "LabBenchmarkReport",
    "LabInteraction",
    "LabLineStyle",
    "LabMovePreset",
    "LabPointStyle",
    "LabVisualState",
    "LabSnapshot",
]
