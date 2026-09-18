# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum
import math
from pathlib import Path
from typing import Any, Callable, Iterable

from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_GIZMO_CATALOG

Point3 = tuple[float, float, float]
SceneBuilder = Callable[[Any, Point3, float], tuple[tuple[Any, ...], str]]


class GizmoCatalogTest(str, Enum):
    """Explicit catalogue scenarios.

    Interactive scenes remain displayed until the user chooses another value;
    they are never replaced by an automatic carousel.
    """

    OVERVIEW = "overview"
    HANDLE_SHAPES = "handle_shapes"
    ACTOR_KINDS = "actor_kinds"
    INTERACTION_MODES = "interaction_modes"
    DRAG_ARROWS = "drag_arrows"
    DENSE_POINTS = "dense_points"
    DENSE_LINES = "dense_lines"
    DENSE_FACES = "dense_faces"
    DENSE_MIXED = "dense_mixed"

    @classmethod
    def choices(cls) -> tuple[tuple[str, str], ...]:
        return (
            (cls.OVERVIEW.value, "Overview"),
            (cls.HANDLE_SHAPES.value, "Handle shapes"),
            (cls.ACTOR_KINDS.value, "Actor kinds"),
            (cls.INTERACTION_MODES.value, "Interaction modes"),
            (cls.DRAG_ARROWS.value, "Drag arrows"),
            (cls.DENSE_POINTS.value, "Dense points"),
            (cls.DENSE_LINES.value, "Dense lines"),
            (cls.DENSE_FACES.value, "Dense faces"),
            (cls.DENSE_MIXED.value, "Dense mixed scene"),
        )


class GizmoCatalogCreatorTool(CreatorTool):
    """Interactive reference catalogue for the Projected Drawing 2D API."""

    id = TOOL_GIZMO_CATALOG
    label = "Gizmo catalog"

    def __init__(self) -> None:
        super().__init__()
        self._current_test = GizmoCatalogTest.OVERVIEW
        self._benchmark_runner: Any | None = None

    def _inspector_api(self):
        import laserprog_studio.tool_api.inspector as inspector

        return inspector

    def _projected_drawing_api(self):
        import laserprog_studio.tool_api.projected_drawing as projected_drawing

        return projected_drawing

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step(
                    "inspect",
                    "Choose and inspect a Projected Drawing 2D scenario",
                    help="Hover, select and drag the interactive actors. Dense tests are selectable from the inspector.",
                ),
            ),
        )
        ctx.inspector.set_panel(self._panel(ctx))
        self._select_test(ctx, GizmoCatalogTest.OVERVIEW, render=True)
        ctx.status.info("Projected Drawing 2D catalogue ready. Choose a test in the inspector. 🙂")

    def on_close(self, ctx: Any) -> None:
        self._cancel_benchmark()
        try:
            ctx.projected_drawing.clear_tool(f"{self.id}:projected_drawing_benchmark", render=False)
        except Exception:
            pass
        ctx.inspector.clear()

    def on_event(self, event: Any, ctx: Any) -> bool:  # noqa: ARG002
        # Hover/select/grab are handled by CreatorStudioToolAdapter's native
        # ToolActor runtime before this callback.
        return False

    def on_cancel(self, ctx: Any) -> bool:  # noqa: ARG002
        return False

    def on_apply(self, ctx: Any) -> bool:  # noqa: ARG002
        return False

    def resolve_drag_positions(self, event: Any, ctx: Any) -> dict[str, Point3] | None:
        """Apply handle axis/plane constraints through the public registry."""

        return ctx.projected_drawing.for_tool(self.id).resolve_drag_positions(event)

    def on_native_interaction_result(self, event: Any, ctx: Any, result: Any) -> None:  # noqa: ARG002
        self._update_interaction_report(ctx, action=str(getattr(result, "action", "idle")))

    def _panel(self, ctx: Any):
        inspector = self._inspector_api()
        return inspector.Panel(
            "Projected drawing 2D",
            id="gizmo.catalog",
            owner_tool=self.id,
            description="Selectable scenarios built exclusively with the new projected drawing API.",
            sections=(
                inspector.Section(
                    "Scenario",
                    fields=(
                        inspector.ChoiceField(
                            "catalog_test",
                            "Test",
                            default=self._current_test.value,
                            choices=GizmoCatalogTest.choices(),
                            tooltip="Keep one scene active for visual inspection and interaction.",
                            on_change=lambda _field, value: self._select_test(ctx, value, render=True),
                        ),
                        inspector.BoolField(
                            "show_projected_drawing_2d",
                            "Show scene",
                            default=True,
                            on_change=lambda _field, value: self._set_visible(ctx, bool(value)),
                        ),
                        inspector.ReadonlyField(
                            "projected_drawing_report",
                            "Content",
                            default="Waiting for scene.",
                        ),
                        inspector.ReadonlyField(
                            "interaction_report",
                            "Interaction",
                            default="Hover, click or drag an actor.",
                        ),
                        inspector.ReadonlyField(
                            "visible_report",
                            "Visibility",
                            default="Projected scene visible.",
                        ),
                    ),
                ),
                inspector.Section(
                    "Actions",
                    fields=(
                        inspector.ButtonRow(
                            "catalog_actions",
                            "Scene",
                            buttons=(
                                ("rebuild", "Rebuild"),
                                ("show_all", "Show"),
                                ("hide_all", "Hide"),
                            ),
                            callbacks={
                                "rebuild": lambda _event: self._select_test(ctx, self._current_test, render=True),
                                "show_all": lambda _event: self._set_visible(ctx, True),
                                "hide_all": lambda _event: self._set_visible(ctx, False),
                            },
                        ),
                        inspector.ButtonRow(
                            "benchmark_actions",
                            "Performance",
                            buttons=(
                                ("benchmark_selected", "Benchmark selected"),
                                ("benchmark_all", "Benchmark all"),
                                ("benchmark_cancel", "Stop"),
                            ),
                            callbacks={
                                "benchmark_selected": lambda _event: self._start_benchmark(ctx, selected_only=True),
                                "benchmark_all": lambda _event: self._start_benchmark(ctx, selected_only=False),
                                "benchmark_cancel": lambda _event: self._stop_benchmark(ctx),
                            },
                        ),
                        inspector.ReadonlyField(
                            "benchmark_report",
                            "Benchmark",
                            default="Idle. Benchmarks are started manually.",
                        ),
                        inspector.ReadonlyField(
                            "benchmark_file",
                            "Diagnostic",
                            default="diagnostics/projected_drawing_2d_benchmark.json",
                        ),
                    ),
                ),
            ),
        )

    @staticmethod
    def _coerce_test(value: GizmoCatalogTest | str) -> GizmoCatalogTest:
        if isinstance(value, GizmoCatalogTest):
            return value
        try:
            return GizmoCatalogTest(str(value))
        except Exception:
            return GizmoCatalogTest.OVERVIEW

    def _select_test(self, ctx: Any, value: GizmoCatalogTest | str, *, render: bool) -> None:
        test = self._coerce_test(value)
        self._cancel_benchmark()
        self._current_test = test
        origin, unit = self._ground_frame(ctx)
        primitives, description = self._build_scene(test, origin, unit)
        registry = ctx.projected_drawing.for_tool(self.id)
        registry.replace_all(primitives, render=False)
        registry.set_visible(True, render=False)
        try:
            ctx.inspector.update_value("catalog_test", test.value, notify=False)
            ctx.inspector.update_value("show_projected_drawing_2d", True, notify=False)
            ctx.inspector.set_display_value("projected_drawing_report", description)
            ctx.inspector.set_display_value("visible_report", "Projected scene visible.")
            ctx.inspector.set_display_value("benchmark_report", "Idle. Benchmarks are started manually.")
        except Exception:
            pass
        self._update_interaction_report(ctx, action="scenario_changed")
        registry.render(render=render)

    def _build_scene(self, test: GizmoCatalogTest, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        builders: dict[GizmoCatalogTest, SceneBuilder] = {
            GizmoCatalogTest.OVERVIEW: self._scene_overview,
            GizmoCatalogTest.HANDLE_SHAPES: self._scene_handle_shapes,
            GizmoCatalogTest.ACTOR_KINDS: self._scene_actor_kinds,
            GizmoCatalogTest.INTERACTION_MODES: self._scene_interaction_modes,
            GizmoCatalogTest.DRAG_ARROWS: self._scene_drag_arrows,
            GizmoCatalogTest.DENSE_POINTS: self._scene_dense_points,
            GizmoCatalogTest.DENSE_LINES: self._scene_dense_lines,
            GizmoCatalogTest.DENSE_FACES: self._scene_dense_faces,
            GizmoCatalogTest.DENSE_MIXED: self._scene_dense_mixed,
        }
        return builders[test](self._projected_drawing_api(), origin, unit)

    @staticmethod
    def _world(origin: Point3, unit: float, x: float, y: float) -> Point3:
        return (origin[0] + unit * float(x), origin[1] + unit * float(y), 0.0)

    def _scene_overview(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        w = lambda x, y: self._world(origin, unit, x, y)
        arc_points = tuple(w(-4.0 + 9.0 * math.cos(math.pi * index / 24.0), 17.0 + 9.0 * math.sin(math.pi * index / 24.0)) for index in range(25))
        primitives = (
            draw2d.face(
                "catalog:overview:face",
                (w(-34, -18), w(-12, -18), w(-9, -2), w(-23, 5), w(-37, -4)),
                fill_color="#326A91",
                fill_opacity=0.34,
                outline_color="#8FD4FF",
                interaction="grabbable",
                metadata={"catalog_label": "grabbable face"},
            ),
            draw2d.point(
                "catalog:overview:point",
                w(-28, 19),
                color="#FFD36B",
                size_px=12,
                interaction="grabbable",
                metadata={"catalog_label": "grabbable point"},
            ),
            draw2d.line(
                "catalog:overview:line",
                w(-17, 25),
                w(7, 25),
                color="#7FC8FF",
                width_px=4,
                interaction="grabbable",
                metadata={"catalog_label": "grabbable line"},
            ),
            draw2d.arc(
                "catalog:overview:arc",
                arc_points,
                color="#C5AEFF",
                width_px=3,
                interaction="selectable",
                metadata={"catalog_label": "selectable arc"},
            ),
            draw2d.drag_arrow(
                "catalog:overview:x",
                w(16, -8),
                (1, 0, 0),
                constraint="axis_x",
                color="#F26D6D",
                size_px=34,
                metadata={"catalog_label": "X drag"},
            ),
            draw2d.drag_arrow(
                "catalog:overview:y",
                w(16, -8),
                (0, 1, 0),
                constraint="axis_y",
                color="#63C987",
                size_px=34,
                metadata={"catalog_label": "Y drag"},
            ),
            draw2d.handle(
                "catalog:overview:free",
                w(34, 17),
                shape="target",
                color="#FFD36B",
                size_px=24,
                constraint="plane_xy",
                metadata={"catalog_label": "free XY drag"},
            ),
        )
        return primitives, "Overview · face, point, line, arc and three grabbable handles · all on world XY"

    def _scene_handle_shapes(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        w = lambda x, y: self._world(origin, unit, x, y)
        shapes = (
            "solid",
            "ring",
            "target",
            "diamond",
            "square",
            "arrow",
            "axis",
            "chevron",
            "triad",
            "minimal",
            "translate_arrow",
        )
        colors = ("#7FC8FF", "#7FE0B8", "#FFD36B", "#FF9DCB", "#C5AEFF")
        primitives = []
        for index, shape in enumerate(shapes):
            row, column = divmod(index, 4)
            x = -31 + column * 21
            y = 23 - row * 22
            primitives.append(
                draw2d.handle(
                    f"catalog:shape:{shape}",
                    w(x, y),
                    shape=shape,
                    direction=(1.0, 0.35, 0.0),
                    size_px=24 if shape != "translate_arrow" else 34,
                    color=colors[index % len(colors)],
                    interaction="grabbable",
                    constraint="plane_xy",
                    metadata={"catalog_label": shape},
                )
            )
        return tuple(primitives), "11 historical point/handle styles · every handle can be hovered, selected and dragged"

    def _scene_actor_kinds(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        w = lambda x, y: self._world(origin, unit, x, y)
        arc_points = tuple(w(7 + 10 * math.cos(math.radians(20 + index * 7)), 18 + 10 * math.sin(math.radians(20 + index * 7))) for index in range(21))
        primitives = (
            draw2d.point(
                "catalog:actor:point",
                w(-33, 22),
                color="#FFD36B",
                size_px=13,
                interaction="grabbable",
                metadata={"catalog_label": "point"},
            ),
            draw2d.line(
                "catalog:actor:line",
                w(-20, 22),
                w(-2, 22),
                color="#7FC8FF",
                width_px=4,
                interaction="grabbable",
                metadata={"catalog_label": "line"},
            ),
            draw2d.circle(
                "catalog:actor:circle",
                w(26, 20),
                w(35, 20),
                color="#7FE0B8",
                width_px=3,
                interaction="grabbable",
                metadata={"catalog_label": "circle"},
            ),
            draw2d.arc(
                "catalog:actor:arc",
                arc_points,
                color="#C5AEFF",
                width_px=3,
                interaction="grabbable",
                metadata={"catalog_label": "arc"},
            ),
            draw2d.polyline(
                "catalog:actor:polyline",
                (w(-35, -18), w(-25, -6), w(-14, -16), w(-3, -4)),
                color="#FF9DCB",
                width_px=3,
                interaction="grabbable",
                metadata={"catalog_label": "polyline"},
            ),
            draw2d.face(
                "catalog:actor:face",
                (w(8, -20), w(35, -20), w(31, -1), w(20, -7), w(10, -1)),
                fill_color="#7357A6",
                fill_opacity=0.38,
                outline_color="#D8F1FF",
                outline_width_px=2,
                interaction="grabbable",
                metadata={"catalog_label": "face"},
            ),
        )
        return primitives, "Actor kinds · point, line, circle, arc, polyline and filled face · all grabbable"

    def _scene_interaction_modes(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        w = lambda x, y: self._world(origin, unit, x, y)
        interactions = (("fixed", "#697386"), ("selectable", "#7FC8FF"), ("grabbable", "#FFD36B"))
        primitives: list[Any] = []
        for column, (mode, color) in enumerate(interactions):
            x = -28 + column * 28
            primitives.extend(
                (
                    draw2d.handle(
                        f"catalog:interaction:{mode}:handle",
                        w(x, 22),
                        shape="target" if mode != "fixed" else "ring",
                        color=color,
                        interaction=mode,
                        constraint="plane_xy",
                        size_px=24,
                        metadata={"catalog_label": f"{mode} handle"},
                    ),
                    draw2d.line(
                        f"catalog:interaction:{mode}:line",
                        w(x - 8, 2),
                        w(x + 8, 2),
                        color=color,
                        width_px=4,
                        interaction=mode,
                        metadata={"catalog_label": f"{mode} line"},
                    ),
                    draw2d.face(
                        f"catalog:interaction:{mode}:face",
                        (w(x - 8, -25), w(x + 8, -25), w(x + 10, -10), w(x, -5), w(x - 10, -10)),
                        fill_color=color,
                        fill_opacity=0.32,
                        outline_color="#DCE7F2",
                        interaction=mode,
                        metadata={"catalog_label": f"{mode} face"},
                    ),
                )
            )
        return tuple(primitives), "Interaction contract · fixed, selectable and grabbable handles, lines and faces"

    def _scene_drag_arrows(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        w = lambda x, y: self._world(origin, unit, x, y)
        primitives: list[Any] = [
            draw2d.line("catalog:drag:guide:x", w(-36, 0), w(36, 0), color="#D56A6A", width_px=1.2, opacity=0.55),
            draw2d.line("catalog:drag:guide:y", w(0, -30), w(0, 30), color="#61B879", width_px=1.2, opacity=0.55),
            draw2d.drag_arrow(
                "catalog:drag:x",
                w(0, 0),
                (1, 0, 0),
                constraint="axis_x",
                color="#F26D6D",
                size_px=40,
                metadata={"catalog_label": "translate X"},
            ),
            draw2d.drag_arrow(
                "catalog:drag:y",
                w(0, 0),
                (0, 1, 0),
                constraint="axis_y",
                color="#63C987",
                size_px=40,
                metadata={"catalog_label": "translate Y"},
            ),
            draw2d.drag_arrow(
                "catalog:drag:z",
                w(24, -19),
                (0, 0, 1),
                constraint="axis_z",
                color="#6FA8FF",
                size_px=40,
                metadata={"catalog_label": "translate Z"},
            ),
            draw2d.handle(
                "catalog:drag:free",
                w(-24, 18),
                shape="target",
                color="#FFD36B",
                size_px=28,
                interaction="grabbable",
                constraint="plane_xy",
                metadata={"catalog_label": "free XY"},
            ),
            draw2d.handle(
                "catalog:drag:axis-shape",
                w(25, 18),
                shape="axis",
                direction=(1, 0, 0),
                color="#7FC8FF",
                size_px=30,
                interaction="grabbable",
                constraint="axis_x",
                metadata={"catalog_label": "axis handle"},
            ),
            draw2d.handle(
                "catalog:drag:triad",
                w(0, -22),
                shape="triad",
                color="#C5AEFF",
                size_px=30,
                interaction="grabbable",
                constraint="plane_xy",
                metadata={"catalog_label": "triad free XY"},
            ),
        ]
        return tuple(primitives), "Drag constraints · screen-projected X, Y and Z axes plus free XY handles"

    def _scene_dense_points(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        count = 5000
        positions = tuple(self._grid_position(index, count, origin, unit, span=72) for index in range(count))
        return (
            draw2d.point_cloud("catalog:dense:points", positions, color="#7FC8FF", size_px=4.0),
        ), f"Dense point cloud · {count:,} points · one declaration, one batch, one actor"

    def _scene_dense_lines(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        count = 1800
        half = unit * 0.25
        centers = tuple(self._grid_position(index, count, origin, unit, span=72) for index in range(count))
        segments = tuple(((x - half, y, z), (x + half, y, z)) for x, y, z in centers)
        return (
            draw2d.segment_batch("catalog:dense:lines", segments, color="#7FE0B8", width_px=1.2),
        ), f"Dense segment batch · {count:,} lines · one declaration, one batch, one actor"

    def _scene_dense_faces(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        count = 350
        half = unit * 0.28
        polygons = []
        for x, y, _z in (self._grid_position(index, count, origin, unit, span=70) for index in range(count)):
            polygons.append(((x - half, y - half, 0.0), (x + half, y - half, 0.0), (x + half, y + half, 0.0), (x - half, y + half, 0.0)))
        return (
            draw2d.face_batch(
                "catalog:dense:faces",
                tuple(polygons),
                fill_color="#7357A6",
                fill_opacity=0.28,
                outline_color="#C5AEFF",
                outline_width_px=1.0,
            ),
        ), f"Dense face batch · {count:,} quads · stable indexed triangles"

    def _scene_dense_mixed(self, draw2d: Any, origin: Point3, unit: float) -> tuple[tuple[Any, ...], str]:
        point_scene, _ = self._scene_dense_points(draw2d, origin, unit)
        line_scene, _ = self._scene_dense_lines(draw2d, origin, unit)
        face_scene, _ = self._scene_dense_faces(draw2d, origin, unit)
        # Keep ids unique and use separate layers/styles, matching a typical
        # Plan Tracer split between committed geometry and dynamic overlays.
        return (*point_scene, *line_scene, *face_scene), "Dense mixed scene · 5,000 points, 1,800 lines and 350 faces"

    @staticmethod
    def _grid_position(index: int, count: int, origin: Point3, unit: float, *, span: float) -> Point3:
        side = max(1, int(math.ceil(math.sqrt(max(1, count)))))
        row, column = divmod(int(index), side)
        denominator = max(1, side - 1)
        return (
            origin[0] + unit * ((column / denominator) - 0.5) * span,
            origin[1] + unit * ((row / denominator) - 0.5) * span,
            0.0,
        )

    def _set_visible(self, ctx: Any, visible: bool) -> None:
        registry = ctx.projected_drawing.for_tool(self.id)
        registry.set_visible(bool(visible), render=True)
        try:
            ctx.inspector.update_value("show_projected_drawing_2d", bool(visible), notify=False)
            ctx.inspector.set_display_value(
                "visible_report",
                "Projected scene visible." if visible else "Projected scene hidden.",
            )
        except Exception:
            pass
        self._update_interaction_report(ctx, action="shown" if visible else "hidden")

    def _update_interaction_report(self, ctx: Any, *, action: str) -> None:
        try:
            selected = tuple(
                actor.id
                for actor in ctx.selection.selected_actors()
                if actor.owner_tool == self.id
            )
            hover = ctx.selection.state.hover_id
            hover = hover if hover and ctx.selection.actor(hover) and ctx.selection.actor(hover).owner_tool == self.id else None
            grabbed = tuple(
                actor_id
                for actor_id in tuple(ctx.selection.state.grabbed_ids or ())
                if ctx.selection.actor(actor_id) is not None and ctx.selection.actor(actor_id).owner_tool == self.id
            )
            message = f"{action} · hover={hover or '—'} · selected={', '.join(selected) or '—'} · grabbed={', '.join(grabbed) or '—'}"
            ctx.inspector.set_display_value("interaction_report", message)
        except Exception:
            pass

    def _cancel_benchmark(self) -> None:
        runner = self._benchmark_runner
        if runner is not None:
            try:
                runner.cancel()
            except Exception:
                pass
        self._benchmark_runner = None

    def _stop_benchmark(self, ctx: Any) -> None:
        self._cancel_benchmark()
        self._benchmark_progress(ctx, "Benchmark stopped.")

    def _benchmark_case_for_test(self):
        from .gizmo_catalog_benchmark import BENCHMARK_CASES

        names = {
            GizmoCatalogTest.OVERVIEW: "mixed_300",
            GizmoCatalogTest.HANDLE_SHAPES: "points_2000_styles_32",
            GizmoCatalogTest.ACTOR_KINDS: "mixed_300",
            GizmoCatalogTest.INTERACTION_MODES: "mixed_300",
            GizmoCatalogTest.DRAG_ARROWS: "points_2000_styles_8",
            GizmoCatalogTest.DENSE_POINTS: "points_10000",
            GizmoCatalogTest.DENSE_LINES: "lines_3000",
            GizmoCatalogTest.DENSE_FACES: "faces_1000",
            GizmoCatalogTest.DENSE_MIXED: "mixed_3000",
        }
        name = names[self._current_test]
        return next(case for case in BENCHMARK_CASES if case.name == name)

    def _start_benchmark(self, ctx: Any, *, selected_only: bool) -> None:
        from .gizmo_catalog_benchmark import ProjectedDrawingBenchmarkRunner

        self._cancel_benchmark()
        origin, unit = self._ground_frame(ctx)
        cases = (self._benchmark_case_for_test(),) if selected_only else None
        runner = ProjectedDrawingBenchmarkRunner(
            ctx,
            origin=origin,
            unit=unit,
            cases=cases,
            on_progress=lambda message: self._benchmark_progress(ctx, message),
            on_complete=lambda path, report: self._benchmark_complete(ctx, path, report),
        )
        self._benchmark_runner = runner
        if runner.start():
            label = self._current_test.value if selected_only else "all cases"
            self._benchmark_progress(ctx, f"Benchmark started: {label}.")
        else:
            self._benchmark_progress(ctx, "Benchmark skipped: no live VTK viewport.")

    @staticmethod
    def _benchmark_progress(ctx: Any, message: str) -> None:
        try:
            ctx.inspector.set_display_value("benchmark_report", str(message))
        except Exception:
            pass

    def _benchmark_complete(self, ctx: Any, path: Path | None, report: dict[str, Any]) -> None:
        self._benchmark_runner = None
        status = str(report.get("status", "unknown"))
        summary = dict(report.get("summary", {}) or {})
        case_count = int(summary.get("case_count", 0) or 0)
        if path is not None and status == "completed":
            message = f"Completed: {case_count} case(s). Diagnostic: {path.name}."
            try:
                ctx.inspector.set_display_value("benchmark_file", str(path))
                ctx.status.info(f"Projected drawing benchmark exported: {path}")
            except Exception:
                pass
        elif status == "skipped":
            message = str(report.get("reason", "Benchmark skipped."))
        else:
            message = f"Benchmark {status}. Inspect the partial diagnostic."
        self._benchmark_progress(ctx, message)

    @staticmethod
    def _ground_frame(ctx: Any) -> tuple[Point3, float]:
        fallback = ((0.0, 0.0, 0.0), 1.0)
        try:
            plotter = getattr(getattr(ctx, "owner", None), "plotter", None)
            camera = getattr(plotter, "camera", None)
            if camera is None:
                renderer = getattr(plotter, "renderer", None)
                camera = renderer.GetActiveCamera() if renderer is not None else None
            if camera is None:
                return fallback
            position = tuple(float(v) for v in camera.GetPosition())
            focal = tuple(float(v) for v in camera.GetFocalPoint())
            if bool(camera.GetParallelProjection()):
                visible_height = max(1.0e-6, 2.0 * float(camera.GetParallelScale()))
            else:
                distance = max(1.0e-6, _length(_sub(position, focal)))
                angle = math.radians(max(1.0e-3, float(camera.GetViewAngle())))
                visible_height = 2.0 * distance * math.tan(angle * 0.5)
            return ((focal[0], focal[1], 0.0), max(1.0e-6, visible_height / 90.0))
        except Exception:
            return fallback


class GizmoCatalogTool(CreatorStudioToolAdapter):
    """Runtime adapter for the Projected Drawing 2D catalogue."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=GizmoCatalogCreatorTool())


def _sub(a: Iterable[float], b: Iterable[float]) -> Point3:
    av = tuple(float(v) for v in a)
    bv = tuple(float(v) for v in b)
    return (av[0] - bv[0], av[1] - bv[1], av[2] - bv[2])


def _length(value: Iterable[float]) -> float:
    vector = tuple(float(v) for v in value)
    return math.sqrt(vector[0] * vector[0] + vector[1] * vector[1] + vector[2] * vector[2])


__all__ = ["GizmoCatalogCreatorTool", "GizmoCatalogTest", "GizmoCatalogTool"]
