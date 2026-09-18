"""Deterministic scenarios that exercise the shared tool-core layers."""
from __future__ import annotations

from dataclasses import dataclass

from ..commands import FunctionCommand
from ..context import ToolContext
from ..events import MouseButton, ToolEvent, ToolEventType
from ..gizmos import GizmoHandle, MemoryGizmoBackend
from ..input import EventRouter
from ..overlay import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec, ToolPanelSpec
from ..selection import Selectable
from ..sketch import FaceSolveOptions, FaceSolver
from ..snap import PointSnapProvider, SegmentSnapProvider, SnapSource
from ..tools import ToolBase, ToolModeBase
from .analysis import BenchmarkAnalyzer, DiagAnalysis, ProbeMetric
from .bench import BenchReport, ToolCoreGuiBenchmark
from .gizmo_demo import HandleDemoBuilder, HandleDemoSnapshot, SelectionDemoBuilder, SelectionDemoSnapshot
from .showcase import UiShowcaseBuilder


@dataclass(frozen=True, slots=True)
class CoreDiagSnapshot:
    handles: int
    previews: int
    overlay_buttons: int
    selected: int
    faces: int
    commands_done: int
    snap_cache_rebuilds: int
    profiler_values: dict[str, int | float]


class _ProbeMode(ToolModeBase):
    id = "probe"
    label = "Probe"

    def on_event(self, event: ToolEvent, ctx: ToolContext) -> bool:
        if event.world_pos is None:
            return False
        if event.type == ToolEventType.MOUSE_MOVE:
            ctx.gizmos.update_positions_only({"diag:hover": event.world_pos})
            ctx.preview.show_line("diag:hover-line", "tool_core_diag", (0.0, 0.0, 0.0), event.world_pos)
            return True
        return event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT


class _ProbeTool(ToolBase):
    id = "tool_core_diag"
    default_mode_id = "probe"

    def __init__(self) -> None:
        super().__init__()
        self.register_mode(_ProbeMode())


class CoreDiagRunner:
    """Runs isolated scenarios without depending on Qt or a live VTK renderer."""

    owner_tool = "tool_core_diag"

    def __init__(self, ctx: ToolContext | None = None) -> None:
        self.ctx = ctx or ToolContext()
        self.log: list[str] = []
        self.last_bench_report: BenchReport | None = None
        self.last_diag_analysis: DiagAnalysis | None = None
        self.last_api_test_report = None
        self.last_api_lab_benchmark = None
        from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab
        self.api_lab = CreatorApiDiagnosticLab(self.ctx, owner_tool=self.owner_tool)
        self.router = EventRouter(self.ctx)
        self.tool = _ProbeTool()
        self.router.set_tool(self.tool)
        self.tool.activate(self.ctx)

    def reset(self) -> CoreDiagSnapshot:
        self.ctx = ToolContext()
        self.router = EventRouter(self.ctx)
        self.tool = _ProbeTool()
        self.router.set_tool(self.tool)
        self.tool.activate(self.ctx)
        self.log = ["Reset shared tool-core context"]
        self.last_bench_report = None
        self.last_diag_analysis = None
        self.last_api_test_report = None
        self.last_api_lab_benchmark = None
        from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab
        self.api_lab = CreatorApiDiagnosticLab(self.ctx, owner_tool=self.owner_tool)
        return self.snapshot()

    def run_overlay(self) -> CoreDiagSnapshot:
        group = f"{self.owner_tool}.modes"
        self.ctx.overlay.show_panel(
            ToolPanelSpec(
                "diag.panel",
                "Tool Core Diagnostic",
                [
                    ToolButtonSpec("diag.modify", "Modify", checkable=True, checked=True, group=group),
                    ToolButtonSpec("diag.draw", "Draw", checkable=True, group=group),
                    ToolButtonSpec("diag.delete", "Delete", enabled=False),
                ],
            )
        )
        self.ctx.overlay.show_window(
            OverlayWindowSpec(
                id="diag.window",
                title="Diagnostic overlay",
                owner_tool=self.owner_tool,
                fields=[OverlayFieldSpec("diag.window.status", "Status", "ready", kind="info")],
                buttons=[ToolButtonSpec("diag.window.close", "Close")],
                anchor="cursor",
                close_on_click_outside=True,
            )
        )
        self.ctx.overlay.toggle_button("diag.draw")
        self.ctx.overlay.set_button_enabled("diag.delete", True)
        self.ctx.overlay.update_field("diag.window", "diag.window.status", "overlay window active")
        self.log.append("Overlay: exclusive buttons, checked state, enabled state and floating window state")
        return self.snapshot()

    def run_overlay_types(self, cursor_px: tuple[int, int] = (340, 160)) -> CoreDiagSnapshot:
        """Create representative overlay types for the Qt adapter and tests."""
        self.ctx.overlay.show_window(
            OverlayWindowSpec(
                id="diag.overlay.palette",
                title="Movable palette",
                owner_tool=self.owner_tool,
                fields=[OverlayFieldSpec("diag.overlay.palette.info", "Type", "draggable palette", kind="info")],
                buttons=[ToolButtonSpec("diag.overlay.palette.close", "Close")],
                anchor="viewport_top_left",
                overlay_kind="palette",
                width_px=240,
                movable=True,
                persistent=True,
            )
        )
        self.ctx.overlay.show_window(
            OverlayWindowSpec(
                id="diag.overlay.inspector",
                title="Inspector",
                owner_tool=self.owner_tool,
                fields=[OverlayFieldSpec("diag.overlay.inspector.value", "Selection", "handle demo", kind="info")],
                anchor="viewport_top_right",
                overlay_kind="inspector",
                width_px=260,
                movable=True,
                close_on_click_outside=False,
            )
        )
        self.ctx.overlay.show_popover_at_cursor(
            "diag.overlay.cursor_popover",
            owner_tool=self.owner_tool,
            title="Cursor popover",
            cursor_px=cursor_px,
            fields=[OverlayFieldSpec("diag.overlay.cursor_popover.info", "Spawn", "under mouse", kind="info")],
            buttons=[ToolButtonSpec("diag.overlay.cursor_popover.close", "Close")],
            width_px=250,
            movable=False,
            close_on_click_outside=True,
        )
        self.ctx.overlay.show_tooltip(
            "diag.overlay.tooltip",
            owner_tool=self.owner_tool,
            text="Tooltip overlay: lightweight, non-draggable, close-on-click-away.",
            cursor_px=(int(cursor_px[0]) + 280, int(cursor_px[1])),
        )
        self.log.append("Overlay types: stable movable palette, inspector, non-draggable cursor popover and tooltip created")
        return self.snapshot()

    def run_gizmos(self, count: int = 12) -> CoreDiagSnapshot:
        for i in range(max(1, int(count))):
            self.ctx.gizmos.create_handle(
                GizmoHandle(
                    id=f"diag:p{i}",
                    owner_tool=self.owner_tool,
                    position=(float(i), float(i % 4), 0.0),
                    radius_px=16,
                    color=(0.15, 0.75, 1.0, 1.0),
                )
            )
        self.ctx.gizmos.create_handle(GizmoHandle("diag:hover", self.owner_tool, (0.0, 0.0, 0.0), radius_px=20))
        self.log.append(f"Gizmos: created {count} pooled handles")
        return self.snapshot()

    def run_drag_burst(self, steps: int = 80) -> CoreDiagSnapshot:
        if not self.ctx.gizmos.handles(owner_tool=self.owner_tool):
            self.run_gizmos(8)
        if not any(handle.id == "diag:hover" for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool)):
            self.ctx.gizmos.create_handle(GizmoHandle("diag:hover", self.owner_tool, (0.0, 0.0, 0.0), radius_px=20))
        self.ctx.begin_drag()
        for i in range(max(1, int(steps))):
            updates = {"diag:hover": (float(i) * 0.5, 4.0, 0.0)}
            self.ctx.gizmos.update_positions_only(updates)
            self.ctx.profiler.increment("diag.drag.steps")
        self.ctx.end_drag()
        backend = self.ctx.gizmos.backend
        created = getattr(backend, "created", 0)
        updates = getattr(backend, "position_updates", 0)
        self.log.append(f"Drag: {steps} position-only updates, created={created}, updates={updates}")
        return self.snapshot()

    def run_snap_preview(self) -> CoreDiagSnapshot:
        sketch = self.ctx.sketch
        a = sketch.add_point((0.0, 0.0), point_id="diag:a")
        b = sketch.add_point((20.0, 0.0), point_id="diag:b")
        sketch.add_line(a.id, b.id, line_id="diag:ab")
        self.ctx.snap.add_provider(PointSnapProvider(SnapSource.SKETCH_POINT, lambda c: c.sketch.sketch_points_for_snap(), priority=10))
        self.ctx.snap.add_provider(SegmentSnapProvider(SnapSource.SKETCH_EDGE, lambda c: c.sketch.sketch_segments_for_snap(), priority=60))
        self.ctx.snap.set_smart_snap(True)
        self.ctx.snap.set_grid_snap(True)
        self.ctx.snap.grid_provider.grid_size = 5.0
        self.ctx.snap.rebuild_cache(self.ctx)
        result = self.ctx.snap.query((19.2, 0.4, 0.0), (20.0, 0.0), self.ctx)
        self.ctx.preview.show_line("diag.snap-line", self.owner_tool, (0.0, 0.0, 0.0), result.position)
        self.log.append(f"Snap: {result.source.value} -> {tuple(round(v, 3) for v in result.position)}")
        return self.snapshot()

    def run_face_command(self) -> CoreDiagSnapshot:
        s = self.ctx.sketch
        ids = []
        for idx, point in enumerate([(0, 0), (30, 0), (30, 15), (0, 15)]):
            ids.append(s.add_point(point, point_id=f"diag:f{idx}").id)
        for a, b in zip(ids, ids[1:] + ids[:1]):
            s.add_line(a, b)
        faces = FaceSolver(FaceSolveOptions(join_tolerance=0.05)).solve(s)
        if faces:
            self.ctx.preview.show_face("diag.face", self.owner_tool, s.faces[faces[0]].polygon_points)
        store: list[str] = []
        self.ctx.commands.execute(FunctionCommand("diag-add", lambda: store.append("x"), lambda: store.pop()))
        self.ctx.commands.undo()
        self.ctx.commands.redo()
        self.log.append(f"Faces/commands: faces={len(faces)}, undo/redo OK")
        return self.snapshot()



    def run_selection_demo(self) -> CoreDiagSnapshot:
        demo = SelectionDemoBuilder(self.ctx)
        snapshot = demo.build_demo()
        self.log.append(
            f"Selection demo: actors={snapshot.actors}, selectable={snapshot.selectable_actors}, grabbable={snapshot.grabbable_actors}, selected={snapshot.selected_actors}"
        )
        self.log.extend(snapshot.notes[-3:])
        return self.snapshot()


    def run_api_lab_setup(self) -> CoreDiagSnapshot:
        snap = self.api_lab.setup()
        self.log.append(
            f"API Lab setup: actors={snap.actors}, points={snap.points}, lines={snap.lines}, selected={snap.selected}"
        )
        self.ctx.profiler.increment("diag.api_lab.setup")
        return self.snapshot()

    def api_lab_set_options(self, *, actor_kind: str | None = None, interaction: str | None = None, move: str | None = None, point_style: str | None = None, line_style: str | None = None, visual_state: str | None = None, box_enabled: str | bool | None = None, box_target: str | None = None, box_mode: str | None = None, box_inside_policy: str | None = None) -> CoreDiagSnapshot:
        self.api_lab.set_options(actor_kind=actor_kind, interaction=interaction, move=move, point_style=point_style, line_style=line_style, visual_state=visual_state, box_enabled=box_enabled, box_target=box_target, box_mode=box_mode, box_inside_policy=box_inside_policy)
        self.log.append("API Lab options updated")
        return self.snapshot()

    def api_lab_add_actor(self) -> CoreDiagSnapshot:
        snap = self.api_lab.add_from_options()
        self.log.append(snap.report)
        self.ctx.profiler.increment("diag.api_lab.add")
        return self.snapshot()

    def api_lab_delete_selected(self) -> CoreDiagSnapshot:
        snap = self.api_lab.delete_selected()
        self.log.append(snap.report)
        self.ctx.profiler.increment("diag.api_lab.delete")
        return self.snapshot()

    def api_lab_select_all(self) -> CoreDiagSnapshot:
        snap = self.api_lab.select_all()
        self.log.append(snap.report)
        self.ctx.profiler.increment("diag.api_lab.select_all")
        return self.snapshot()

    def api_lab_move_selected(self) -> CoreDiagSnapshot:
        snap = self.api_lab.move_selected_from_options()
        self.log.append(snap.report)
        self.ctx.profiler.increment("diag.api_lab.move_button")
        return self.snapshot()

    def api_lab_clear(self) -> CoreDiagSnapshot:
        snap = self.api_lab.clear()
        self.log.append(snap.report)
        self.ctx.profiler.increment("diag.api_lab.clear")
        return self.snapshot()

    def run_api_lab_benchmark(self, iterations: int = 120) -> CoreDiagSnapshot:
        report = self.api_lab.run_benchmark(iterations=iterations)
        self.last_api_lab_benchmark = report
        self.log.append(f"API Lab benchmark: cases={len(report.cases)}, status={'PASS' if report.ok else 'FAIL'}")
        for case in report.cases:
            self.log.append(f"API bench {'OK' if case.passed else 'FAIL'}: {case.name} {case.avg_ms:.4f} ms")
        self.ctx.profiler.increment("diag.api_lab.benchmark")
        return self.snapshot()

    def run_full_api_validation(self) -> CoreDiagSnapshot:
        self.run_creator_api_tests()
        self.run_api_lab_benchmark()
        self.run_gui_benchmark()
        self.log.append("Full API validation completed")
        return self.snapshot()

    def run_creator_api_demo(self) -> CoreDiagSnapshot:
        """Exercise the public creator API in one compact, headless scenario."""

        from laserprog_studio.tool_api import actors, inspector, snap

        owner = self.owner_tool
        applied: list[str] = []
        self.ctx.inspector.set_panel(
            inspector.panel(
                "Creator API Demo",
                id=owner,
                owner_tool=owner,
                description="Declarative inspector, actors, SceneCache and custom smart snap in one example.",
                sections=[
                    inspector.section(
                        "Geometry",
                        [
                            inspector.float_field("length", "Length", default=60.0, min_value=5.0, max_value=300.0, unit="mm"),
                            inspector.bool_field("snap", "Smart snap", default=True),
                        ],
                    ),
                    inspector.section("Actions", [inspector.button("apply", "Apply", on_click=lambda event: applied.append(event.action_id))]),
                ],
            )
        )
        length = float(self.ctx.inspector.value("length", 60.0))
        self.ctx.selection.clear_tool(owner)
        self.ctx.selection.register_actor(actors.point("creator.p1", (0.0, 0.0, 0.0), owner_tool=owner, interaction="grabbable"))
        self.ctx.selection.register_actor(actors.point("creator.p2", (length, 0.0, 0.0), owner_tool=owner, interaction="grabbable"))
        self.ctx.selection.register_actor(actors.line("creator.edge", (0.0, 0.0, 0.0), (length, 0.0, 0.0), owner_tool=owner, interaction="selectable"))
        self.ctx.scene_cache.rebuild(self.ctx, scope="snap", exclude_ids=("creator.p2",))
        result = self.ctx.snap.smart(
            (length * 0.5, 0.0, 0.0),
            (length * 0.5, 0.0),
            self.ctx,
            extra_targets=[
                snap.point("creator.midpoint", (length * 0.5, 0.0, 0.0), priority=8),
                snap.ui_point("creator.ui.handle", (length * 0.5, 0.0), world_pos=(length * 0.5, 0.0, 0.0), priority=6),
            ],
            exclude_ids=("creator.p2",),
        )
        self.ctx.preview.show_line("creator.preview", owner, (0.0, 0.0, 0.0), result.position)
        self.ctx.inspector.trigger("apply")
        self.ctx.commands.execute(FunctionCommand("creator-api-apply", lambda: applied.append("done"), lambda: applied.pop()))
        summary = self.ctx.scene_cache.summary()
        self.log.append(
            "Creator API demo: "
            f"fields={len(self.ctx.inspector.panel.fields() if self.ctx.inspector.panel else ())}, "
            f"cache={summary.points}p/{summary.segments}s, snap={result.source.value}:{result.source_id}, actions={len(applied)}"
        )
        return self.snapshot()

    def run_creator_api_tests(self) -> CoreDiagSnapshot:
        """Run the broad public Creator API self-test suite used by the UI."""

        from laserprog_studio.tool_api.diagnostics import run_creator_api_self_test

        report = run_creator_api_self_test(self.ctx, owner_tool=self.owner_tool)
        self.last_api_test_report = report
        self.log.append(report.summary_line())
        for case in report.cases:
            prefix = "OK" if case.passed else "FAIL"
            self.log.append(f"API test {prefix}: {case.category} / {case.name} - {case.details}")
        self.ctx.profiler.increment("diag.creator_api_tests.runs")
        if report.failed:
            self.ctx.profiler.increment("diag.creator_api_tests.failures", report.failed)
        return self.snapshot()

    def run_handle_demo(self) -> CoreDiagSnapshot:
        demo = HandleDemoBuilder(self.ctx)
        snapshot = demo.build_demo()
        self.log.append(
            f"Handle demo: rows={snapshot.rows}, fixed={snapshot.fixed_handles}, grabbable={snapshot.grabbable_handles}, previews={snapshot.previews}"
        )
        self.log.extend(snapshot.notes[-3:])
        return self.snapshot()

    def run_handle_demo_hover(self) -> CoreDiagSnapshot:
        demo = HandleDemoBuilder(self.ctx)
        if not any(str(handle.kind).startswith("demo_") for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool)):
            demo.build_demo()
        demo.apply_hover("demo:2:grab")
        self.log.append("Handle demo: hover state applied to a medium grabbable point")
        return self.snapshot()

    def run_handle_demo_grabbed(self) -> CoreDiagSnapshot:
        demo = HandleDemoBuilder(self.ctx)
        if not any(str(handle.kind).startswith("demo_") for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool)):
            demo.build_demo()
        demo.apply_grabbed("demo:2:line_grab:a")
        self.log.append("Handle demo: grabbed state applied to a line endpoint")
        return self.snapshot()

    def run_ui_showcase(self) -> CoreDiagSnapshot:
        showcase = UiShowcaseBuilder(self.ctx)
        snapshot = showcase.build_full_showcase()
        self.log.append(
            f"UI showcase: handles={snapshot.handles}, previews={snapshot.previews}, labels={snapshot.labels}, drag_updates={snapshot.drag_updates}"
        )
        self.log.extend(snapshot.notes[-4:])
        return self.snapshot()

    def run_ui_handles(self) -> CoreDiagSnapshot:
        showcase = UiShowcaseBuilder(self.ctx)
        showcase.reset_visuals()
        showcase.build_handle_states()
        self.log.extend(showcase.snapshot().notes)
        return self.snapshot()

    def run_ui_primitives(self) -> CoreDiagSnapshot:
        showcase = UiShowcaseBuilder(self.ctx)
        showcase.reset_visuals()
        showcase.build_primitives()
        showcase.build_snap_guides()
        self.log.extend(showcase.snapshot().notes)
        return self.snapshot()

    def run_ui_text(self) -> CoreDiagSnapshot:
        showcase = UiShowcaseBuilder(self.ctx)
        showcase.reset_visuals()
        showcase.build_text_examples()
        self.log.extend(showcase.snapshot().notes)
        return self.snapshot()

    def run_ui_stress(self) -> CoreDiagSnapshot:
        showcase = UiShowcaseBuilder(self.ctx)
        showcase.reset_visuals()
        showcase.run_drag_stress(handle_count=160, steps=120)
        self.log.extend(showcase.snapshot().notes)
        return self.snapshot()


    def run_gui_benchmark(self) -> CoreDiagSnapshot:
        report = ToolCoreGuiBenchmark().run()
        self.last_bench_report = report
        self.last_diag_analysis = BenchmarkAnalyzer().analyze(
            ProbeMetric(
                result.label,
                result.avg_ms,
                result.actors_created,
                result.actors_deleted,
                tuple(result.bugs),
                source="deterministic",
            )
            for result in report.results
        )
        best = report.best()
        if best is not None:
            self.log.append(f"GUI benchmark: best={best.label}, score={best.score:.2f}, avg={best.avg_ms:.4f} ms")
        self.log.append(f"GUI benchmark: detected {len(report.bugs)} diagnostic flags")
        if self.last_diag_analysis is not None:
            self.log.append(f"Analysis: blockers={len(self.last_diag_analysis.blockers)}, decisions={len(self.last_diag_analysis.decisions)}")
        self.ctx.profiler.increment("diag.gui_benchmark.runs")
        return self.snapshot()

    def run_benchmark_analysis(self) -> CoreDiagSnapshot:
        if self.last_bench_report is None:
            self.run_gui_benchmark()
        if self.last_bench_report is not None:
            self.last_diag_analysis = BenchmarkAnalyzer().analyze(
                ProbeMetric(
                    result.label,
                    result.avg_ms,
                    result.actors_created,
                    result.actors_deleted,
                    tuple(result.bugs),
                    source="deterministic",
                )
                for result in self.last_bench_report.results
            )
        self.ctx.profiler.increment("diag.benchmark_analysis.runs")
        self.log.append("Benchmark analysis: production rendering policy refreshed")
        return self.snapshot()

    def run_selection_events(self) -> CoreDiagSnapshot:
        self.ctx.selection.register(Selectable("diag:p0", "handle", self.owner_tool, (0.0, 0.0, 0.0)))
        self.ctx.selection.select("diag:p0")
        self.router.route(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 1.0), world_pos=(1.0, 1.0, 0.0), button=MouseButton.LEFT))
        self.router.route(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(3.0, 3.0), world_pos=(3.0, 3.0, 0.0)))
        self.router.route(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(3.0, 3.0), world_pos=(3.0, 3.0, 0.0), button=MouseButton.LEFT))
        self.log.append(f"Events: routed={self.router.event_count}, handled={self.router.handled_count}")
        return self.snapshot()

    def run_all(self) -> CoreDiagSnapshot:
        # Pass130: the diagnostic validates the public Creator API only.
        # Older scattered demos remain importable for regression tests, but
        # the production diagnostic flow is the API Lab + self-tests + benchmark.
        self.run_api_lab_setup()
        self.api_lab_select_all()
        self.api_lab_move_selected()
        self.run_creator_api_tests()
        self.run_api_lab_benchmark(80)
        self.run_gui_benchmark()
        self.log.append("All Creator API diagnostic scenarios completed")
        return self.snapshot()

    def snapshot(self) -> CoreDiagSnapshot:
        return CoreDiagSnapshot(
            handles=len(self.ctx.gizmos.handles(owner_tool=self.owner_tool)),
            previews=len(self.ctx.preview.items(owner_tool=self.owner_tool)),
            overlay_buttons=len(self.ctx.overlay.buttons),
            selected=len(self.ctx.selection.get_selected()),
            faces=len(self.ctx.sketch.faces),
            commands_done=self.ctx.commands.undo_count,
            snap_cache_rebuilds=int(self.ctx.snap.cache_rebuilds),
            profiler_values=self.ctx.profiler.snapshot(),
        )

    def backend_stats(self) -> dict[str, int]:
        backend = self.ctx.gizmos.backend
        if isinstance(backend, MemoryGizmoBackend):
            return {
                "created": backend.created,
                "position_updates": backend.position_updates,
                "visibility_updates": backend.visibility_updates,
                "removed": backend.removed,
                "light_renders": backend.light_renders,
                "full_renders": backend.full_renders,
            }
        return {}
