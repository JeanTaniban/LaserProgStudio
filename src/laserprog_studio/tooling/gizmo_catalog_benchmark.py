# -*- coding: utf-8 -*-
"""Visible, staged benchmark for the projected drawing 2D backend.

Each dataset is shown in the live viewport, held long enough to inspect, measured,
cleared, and followed by a short empty-scene pause.  The benchmark deliberately
uses a private owner so the catalog reference scene and the public API remain
untouched.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Callable, Iterable

from laserprog_studio.bootstrap import compute_paths
from laserprog_studio.tool_api.projected_drawing import (
    ProjectedFace,
    ProjectedFaceBatch,
    ProjectedLine,
    ProjectedPoint,
    ProjectedPointCloud,
    ProjectedPrimitive,
    ProjectedSegmentBatch,
)

from .ids import TOOL_GIZMO_CATALOG

Point3 = tuple[float, float, float]
_BENCHMARK_OWNER = f"{TOOL_GIZMO_CATALOG}:projected_drawing_benchmark"
_DIAGNOSTIC_FILENAME = "projected_drawing_2d_benchmark.json"
_FRAME_BUDGET_MS = 1000.0 / 60.0


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    name: str
    family: str
    count: int
    style_count: int = 1


BENCHMARK_CASES: tuple[BenchmarkCase, ...] = (
    *(BenchmarkCase(f"points_{count}", "points", count) for count in (50, 300, 1000, 3000, 10000)),
    *(BenchmarkCase(f"lines_{count}", "lines", count) for count in (50, 300, 1000, 3000)),
    *(BenchmarkCase(f"faces_{count}", "faces", count) for count in (10, 100, 300, 1000)),
    *(BenchmarkCase(f"concave_face_{count}_vertices", "complex_face", count) for count in (32, 128, 256)),
    BenchmarkCase("convex_face_2000_vertices", "convex_face", 2000),
    *(BenchmarkCase(f"mixed_{count}", "mixed", count) for count in (300, 1000, 3000)),
    *(BenchmarkCase(f"points_2000_styles_{styles}", "points", 2000, style_count=styles) for styles in (8, 32, 128)),
)


def diagnostic_path() -> Path:
    path = compute_paths().diagnostics_dir
    path.mkdir(parents=True, exist_ok=True)
    return path / _DIAGNOSTIC_FILENAME


def _stats(samples: Iterable[float]) -> dict[str, float | int]:
    values = sorted(float(value) for value in samples)
    if not values:
        return {"count": 0, "min_ms": 0.0, "median_ms": 0.0, "mean_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "max_ms": 0.0}

    def percentile(value: float) -> float:
        if len(values) == 1:
            return values[0]
        index = int(round((max(0.0, min(100.0, value)) / 100.0) * (len(values) - 1)))
        return values[index]

    return {
        "count": len(values),
        "min_ms": round(values[0], 6),
        "median_ms": round(statistics.median(values), 6),
        "mean_ms": round(statistics.fmean(values), 6),
        "p95_ms": round(percentile(95.0), 6),
        "p99_ms": round(percentile(99.0), 6),
        "max_ms": round(values[-1], 6),
    }


def _elapsed_ms(callback: Callable[[], Any]) -> tuple[float, Any]:
    started = time.perf_counter()
    result = callback()
    return ((time.perf_counter() - started) * 1000.0, result)


def _color(index: int) -> str:
    value = (0x4C8EB8 + int(index) * 0x45D9F3) & 0xFFFFFF
    return f"#{value:06X}"


def _grid_position(index: int, count: int, origin: Point3, unit: float, *, span_units: float = 76.0) -> Point3:
    side = max(1, int(math.ceil(math.sqrt(max(1, count)))))
    row, column = divmod(int(index), side)
    denominator = max(1, side - 1)
    x = (float(column) / denominator - 0.5) * span_units
    y = (float(row) / denominator - 0.5) * span_units
    return (origin[0] + unit * x, origin[1] + unit * y, 0.0)


def _radial_polygon(count: int, origin: Point3, unit: float, *, concave: bool) -> tuple[Point3, ...]:
    vertices: list[Point3] = []
    count = max(3, int(count))
    for index in range(count):
        angle = 2.0 * math.pi * float(index) / float(count)
        if concave:
            radius = unit * (31.0 if index % 2 == 0 else 21.0)
        else:
            radius = unit * 31.0
        vertices.append((origin[0] + radius * math.cos(angle), origin[1] + radius * math.sin(angle), 0.0))
    return tuple(vertices)


def build_case_primitives(draw2d: Any, case: BenchmarkCase, origin: Point3, unit: float) -> tuple[ProjectedPrimitive, ...]:
    """Build one deterministic ground-plane dataset for a visible benchmark pass."""

    count = max(0, int(case.count))
    style_count = max(1, int(case.style_count))
    primitives: list[ProjectedPrimitive] = []

    def style(index: int) -> str:
        return _color(index % style_count)

    if case.family == "points":
        positions = tuple(_grid_position(index, count, origin, unit) for index in range(count))
        if style_count == 1:
            return (
                draw2d.point_cloud(
                    "bench:p:cloud",
                    positions,
                    color=style(0),
                    size_px=5.0,
                    layer=20,
                ),
            )
        groups: list[list[Point3]] = [[] for _index in range(style_count)]
        for index, position in enumerate(positions):
            groups[index % style_count].append(position)
        return tuple(
            draw2d.point_cloud(
                f"bench:p:cloud:{style_index}",
                group,
                color=style(style_index),
                size_px=5.0,
                layer=20,
            )
            for style_index, group in enumerate(groups)
            if group
        )

    if case.family == "lines":
        half = unit * 0.32
        centers = tuple(_grid_position(index, count, origin, unit) for index in range(count))
        segments = tuple(
            ((center[0] - half, center[1], 0.0), (center[0] + half, center[1], 0.0))
            for center in centers
        )
        if style_count == 1:
            return (
                draw2d.segment_batch(
                    "bench:l:batch",
                    segments,
                    color=style(0),
                    width_px=1.5,
                    layer=10,
                ),
            )
        return tuple(
            draw2d.line(
                f"bench:l:{index}",
                segment[0],
                segment[1],
                color=style(index),
                width_px=1.5,
                layer=10,
            )
            for index, segment in enumerate(segments)
        )

    if case.family == "faces":
        half = unit * 0.28
        polygons = tuple(
            (
                (center[0] - half, center[1] - half, 0.0),
                (center[0] + half, center[1] - half, 0.0),
                (center[0] + half, center[1] + half, 0.0),
                (center[0] - half, center[1] + half, 0.0),
            )
            for center in (_grid_position(index, count, origin, unit) for index in range(count))
        )
        if style_count == 1:
            return (
                draw2d.face_batch(
                    "bench:f:batch",
                    polygons,
                    fill_color=style(0),
                    fill_opacity=0.30,
                    outline_color="#DCE7F2",
                    outline_width_px=1.0,
                    layer=0,
                ),
            )
        return tuple(
            draw2d.face(
                f"bench:f:{index}",
                polygon,
                fill_color=style(index),
                fill_opacity=0.30,
                outline_color="#DCE7F2",
                outline_width_px=1.0,
                layer=0,
            )
            for index, polygon in enumerate(polygons)
        )

    if case.family in {"complex_face", "convex_face"}:
        return (
            draw2d.face(
                f"bench:{case.family}",
                _radial_polygon(count, origin, unit, concave=case.family == "complex_face"),
                fill_color="#326A91" if case.family == "convex_face" else "#7357A6",
                fill_opacity=0.42,
                outline_color="#D8F1FF",
                outline_width_px=1.5,
                layer=0,
            ),
        )

    if case.family == "mixed":
        point_count = int(round(count * 0.50))
        line_count = int(round(count * 0.35))
        face_count = max(0, count - point_count - line_count)
        for prefix, items in (
            ("m:p", build_case_primitives(draw2d, BenchmarkCase("p", "points", point_count, style_count), origin, unit)),
            ("m:l", build_case_primitives(draw2d, BenchmarkCase("l", "lines", line_count, style_count), origin, unit)),
            ("m:f", build_case_primitives(draw2d, BenchmarkCase("f", "faces", face_count, style_count), origin, unit)),
        ):
            primitives.extend(replace(item, id=f"bench:{prefix}:{index}") for index, item in enumerate(items))
        return tuple(primitives)

    raise ValueError(f"Unsupported benchmark family: {case.family!r}")


def _mutate_one(primitive: ProjectedPrimitive, delta: float) -> ProjectedPrimitive:
    if isinstance(primitive, ProjectedPoint):
        x, y, z = primitive.position
        return replace(primitive, position=(x + delta, y, z))
    if isinstance(primitive, ProjectedLine):
        points = list(primitive.points)
        x, y, z = points[0]
        points[0] = (x + delta, y, z)
        return replace(primitive, points=tuple(points))
    if isinstance(primitive, ProjectedFace):
        vertices = list(primitive.vertices)
        x, y, z = vertices[0]
        vertices[0] = (x + delta, y, z)
        return replace(primitive, vertices=tuple(vertices))
    if isinstance(primitive, ProjectedPointCloud) and primitive.positions:
        positions = list(primitive.positions)
        x, y, z = positions[0]
        positions[0] = (x + delta, y, z)
        return replace(primitive, positions=tuple(positions))
    if isinstance(primitive, ProjectedSegmentBatch) and primitive.segments:
        segments = list(primitive.segments)
        first = list(segments[0])
        x, y, z = first[0]
        first[0] = (x + delta, y, z)
        segments[0] = (first[0], first[1])
        return replace(primitive, segments=tuple(segments))
    if isinstance(primitive, ProjectedFaceBatch) and primitive.polygons:
        polygons = list(primitive.polygons)
        vertices = list(polygons[0])
        x, y, z = vertices[0]
        vertices[0] = (x + delta, y, z)
        polygons[0] = tuple(vertices)
        return replace(primitive, polygons=tuple(polygons))
    return primitive



def _mutate_many_in_primitive(primitive: ProjectedPrimitive, delta: float, limit: int) -> tuple[ProjectedPrimitive, int]:
    """Move up to ``limit`` visual elements while preserving style/topology."""

    count = max(0, int(limit))
    if count == 0:
        return primitive, 0
    if isinstance(primitive, ProjectedPointCloud):
        positions = list(primitive.positions)
        touched = min(count, len(positions))
        for index in range(touched):
            x, y, z = positions[index]
            positions[index] = (x + delta, y, z)
        return replace(primitive, positions=tuple(positions)), touched
    if isinstance(primitive, ProjectedSegmentBatch):
        segments = list(primitive.segments)
        touched = min(count, len(segments))
        for index in range(touched):
            start, end = segments[index]
            segments[index] = ((start[0] + delta, start[1], start[2]), end)
        return replace(primitive, segments=tuple(segments)), touched
    if isinstance(primitive, ProjectedFaceBatch):
        polygons = list(primitive.polygons)
        touched = min(count, len(polygons))
        for index in range(touched):
            vertices = list(polygons[index])
            first = vertices[0]
            vertices[0] = (first[0] + delta, first[1], first[2])
            polygons[index] = tuple(vertices)
        return replace(primitive, polygons=tuple(polygons)), touched
    return _mutate_one(primitive, delta), 1


def _element_counts(primitives: Iterable[ProjectedPrimitive]) -> tuple[int, int, int]:
    points = lines = faces = 0
    for primitive in primitives:
        if isinstance(primitive, ProjectedPoint):
            points += 1
        elif isinstance(primitive, ProjectedPointCloud):
            points += len(primitive.positions)
        elif isinstance(primitive, ProjectedLine):
            lines += 1
        elif isinstance(primitive, ProjectedSegmentBatch):
            lines += len(primitive.segments)
        elif isinstance(primitive, ProjectedFace):
            faces += 1
        elif isinstance(primitive, ProjectedFaceBatch):
            faces += len(primitive.polygons)
    return points, lines, faces

def _sync_breakdown(metrics: dict[str, Any], total_ms: float) -> dict[str, Any]:
    return {
        "total_ms": round(float(total_ms), 6),
        "compile_ms": round(float(metrics.get("last_compile_ms", 0.0) or 0.0), 6),
        "incremental_update_ms": round(float(metrics.get("last_incremental_update_ms", 0.0) or 0.0), 6),
        "incremental_points": int(metrics.get("last_incremental_points", 0) or 0),
        "rebuild_ms": round(float(metrics.get("last_rebuild_ms", 0.0) or 0.0), 6),
        "rebuild_remove_ms": round(float(metrics.get("last_rebuild_remove_ms", 0.0) or 0.0), 6),
        "actor_create_ms": round(float(metrics.get("last_actor_create_ms", 0.0) or 0.0), 6),
        "topology_ms": round(float(metrics.get("last_topology_ms", 0.0) or 0.0), 6),
        "actor_reorder_ms": round(float(metrics.get("last_actor_reorder_ms", 0.0) or 0.0), 6),
        "projection_ms": round(float(metrics.get("last_projection_ms", 0.0) or 0.0), 6),
        "projected_points": int(metrics.get("last_projected_points", 0) or 0),
        "projected_batches": int(metrics.get("last_projected_batches", 0) or 0),
        "signature_ms": round(float(metrics.get("last_signature_ms", 0.0) or 0.0), 6),
        "sync_ms": round(float(metrics.get("last_sync_ms", 0.0) or 0.0), 6),
        "actors_created": int(metrics.get("last_actors_created", 0) or 0),
        "actors_removed": int(metrics.get("last_actors_removed", 0) or 0),
        "topology_updates": int(metrics.get("last_topology_updates", 0) or 0),
    }


def _renderer_for(owner: Any, owner_tool: str) -> Any | None:
    store = getattr(owner, "_laserprog_projected_drawing_2d_renderers", None)
    return store.get(str(owner_tool)) if isinstance(store, dict) else None


def _camera_snapshot(owner: Any) -> dict[str, Any]:
    try:
        camera = owner.plotter.renderer.GetActiveCamera()
        return {
            "position": [float(value) for value in camera.GetPosition()],
            "focal_point": [float(value) for value in camera.GetFocalPoint()],
            "view_up": [float(value) for value in camera.GetViewUp()],
            "parallel_projection": bool(camera.GetParallelProjection()),
            "parallel_scale": float(camera.GetParallelScale()),
            "view_angle": float(camera.GetViewAngle()),
            "clipping_range": [float(value) for value in camera.GetClippingRange()],
            "mtime": int(camera.GetMTime()) if hasattr(camera, "GetMTime") else None,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _viewport_snapshot(owner: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        plotter = owner.plotter
        result["width_px"] = int(plotter.width())
        result["height_px"] = int(plotter.height())
    except Exception as exc:
        result["error"] = str(exc)
    try:
        result["device_pixel_ratio"] = float(owner.devicePixelRatioF())
    except Exception:
        result["device_pixel_ratio"] = None
    return result


def _source_fingerprint() -> str:
    root = compute_paths().root
    digest = hashlib.sha256()
    for relative in (
        "src/laserprog_studio/application/projected_drawing_2d.py",
        "src/laserprog_studio/application/projected_face_triangulation.py",
        "src/laserprog_studio/tool_core/projected_drawing.py",
        "src/laserprog_studio/tool_api/projected_drawing.py",
        "src/laserprog_studio/tooling/gizmo_catalog_benchmark.py",
    ):
        path = root / relative
        try:
            digest.update(relative.encode("utf-8"))
            digest.update(path.read_bytes())
        except Exception:
            continue
    return digest.hexdigest()


def _environment() -> dict[str, Any]:
    result: dict[str, Any] = {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "process_id": os.getpid(),
        "executable": sys.executable,
        "perf_counter_resolution_s": time.get_clock_info("perf_counter").resolution,
    }
    try:
        import vtk

        result["vtk"] = vtk.vtkVersion.GetVTKVersion()
    except Exception as exc:
        result["vtk"] = f"unavailable: {exc}"
    try:
        import PySide6

        result["pyside6"] = str(PySide6.__version__)
    except Exception as exc:
        result["pyside6"] = f"unavailable: {exc}"
    return result


def _filtered_audit_snapshot() -> dict[str, Any]:
    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        snapshot = audit.snapshot()
        return {
            category: {
                key: value
                for key, value in dict(snapshot.get(category, {}) or {}).items()
                if str(key).startswith("projected_drawing_2d.")
            }
            for category in ("timers", "counters", "values")
        }
    except Exception as exc:
        return {"error": str(exc)}


def _case_work(case: dict[str, Any]) -> int:
    return int(case.get("renderer", {}).get("world_points", 0) or case.get("requested_count", 0) or 0)


def _first_over_budget(cases: list[dict[str, Any]], key_path: tuple[str, ...]) -> dict[str, Any] | None:
    candidates: list[tuple[int, dict[str, Any], float]] = []
    for case in cases:
        value: Any = case
        for key in key_path:
            value = value.get(key, {}) if isinstance(value, dict) else {}
        try:
            elapsed = float(value)
        except Exception:
            continue
        if elapsed > _FRAME_BUDGET_MS:
            candidates.append((_case_work(case), case, elapsed))
    if not candidates:
        return None
    work, case, elapsed = min(candidates, key=lambda item: item[0])
    return {"case": case.get("name"), "world_points": work, "elapsed_ms": round(elapsed, 6)}


def _summary(cases: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "frame_budget_ms_at_60hz": round(_FRAME_BUDGET_MS, 6),
        "case_count": len(cases),
        "baseline_viewport_render_median_ms": baseline.get("viewport_render", {}).get("median_ms", 0.0),
        "first_cold_sync_over_budget": _first_over_budget(cases, ("cold_replace_all", "total_ms")),
        "first_camera_reprojection_over_budget": _first_over_budget(cases, ("camera_reprojection_sync", "p95_ms")),
        "first_single_update_over_budget": _first_over_budget(cases, ("single_update", "total_ms")),
        "first_bulk_update_over_budget": _first_over_budget(cases, ("bulk_update_many", "total_ms")),
        "largest_world_point_case": max(
            (
                {
                    "case": case.get("name"),
                    "world_points": int(case.get("renderer", {}).get("world_points", 0) or 0),
                    "batches": int(case.get("renderer", {}).get("batches", 0) or 0),
                }
                for case in cases
            ),
            key=lambda row: row["world_points"],
            default=None,
        ),
    }


class ProjectedDrawingBenchmarkRunner:
    """Run visible show → measure → clear passes in separate Qt turns."""

    SHOW_HOLD_MS = 500
    AFTER_MEASURE_HOLD_MS = 180
    EMPTY_HOLD_MS = 180
    MEASURE_GAP_MS = 16

    def __init__(
        self,
        ctx: Any,
        *,
        origin: Point3,
        unit: float,
        on_progress: Callable[[str], None] | None = None,
        on_complete: Callable[[Path | None, dict[str, Any]], None] | None = None,
        render_repeats: int = 5,
        cases: Iterable[BenchmarkCase] | None = None,
    ) -> None:
        self.ctx = ctx
        self.owner = getattr(ctx, "owner", None)
        self.origin = (float(origin[0]), float(origin[1]), 0.0)
        self.unit = max(1.0e-9, float(unit))
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.render_repeats = max(2, int(render_repeats))
        self.cases = tuple(cases) if cases is not None else BENCHMARK_CASES
        if not self.cases:
            raise ValueError("ProjectedDrawingBenchmarkRunner requires at least one case.")
        self.cancelled = False
        self._started_at = time.perf_counter()
        self._index = 0
        self._phase = "baseline_show"
        self._baseline: dict[str, Any] = {}
        self._results: list[dict[str, Any]] = []
        self._errors: list[dict[str, Any]] = []
        self._current: dict[str, Any] | None = None
        self._sample_values: list[float] = []
        self._sample_index = 0
        self._compile_samples: list[float] = []
        self._catalog_was_visible = True

    @property
    def live(self) -> bool:
        return self.owner is not None and getattr(self.owner, "plotter", None) is not None

    def start(self) -> bool:
        if not self.live:
            self._notify_complete(None, {"status": "skipped", "reason": "No live viewport owner."})
            return False
        self.cancelled = False
        self._started_at = time.perf_counter()
        self._index = 0
        self._phase = "baseline_show"
        self._baseline = {}
        self._results = []
        self._errors = []
        self._current = None
        self._sample_values = []
        self._sample_index = 0
        self._compile_samples = []
        try:
            catalog = self.ctx.projected_drawing.for_tool(TOOL_GIZMO_CATALOG)
            self._catalog_was_visible = bool(catalog.snapshot().visible)
            catalog.set_visible(False, render=False)
        except Exception:
            self._catalog_was_visible = True
        self._schedule(0)
        return True

    def cancel(self) -> None:
        self.cancelled = True
        try:
            self.ctx.projected_drawing.clear_tool(_BENCHMARK_OWNER, render=False)
        except Exception:
            pass
        self._restore_catalog()

    def _restore_catalog(self) -> None:
        try:
            catalog = self.ctx.projected_drawing.for_tool(TOOL_GIZMO_CATALOG)
            catalog.set_visible(self._catalog_was_visible, render=False)
            catalog.render(render=False)
            self._render_now()
        except Exception:
            pass

    def _schedule(self, delay_ms: int) -> None:
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(max(0, int(delay_ms)), self._step)
        except Exception:
            self._step()

    def _active(self) -> bool:
        if self.cancelled or not self.live:
            return False
        active_tool = getattr(self.owner, "active_tool", None)
        return active_tool is None or str(active_tool) == TOOL_GIZMO_CATALOG

    def _render_now(self) -> None:
        plotter = self.owner.plotter
        try:
            render_window = getattr(plotter, "ren_win", None) or getattr(plotter, "render_window", None)
            callback = getattr(render_window, "Render", None)
            if callable(callback):
                callback()
            else:
                plotter.render()
        except Exception:
            try:
                plotter.render()
            except Exception:
                pass

    def _reset_samples(self) -> None:
        self._sample_values = []
        self._sample_index = 0

    def _step(self) -> None:
        if not self._active():
            self.cancel()
            return
        try:
            if self._phase == "baseline_show":
                self.ctx.projected_drawing.clear_tool(_BENCHMARK_OWNER, render=False)
                self._notify_progress("2D benchmark — empty reference scene")
                self._render_now()
                self._reset_samples()
                self._phase = "baseline_render_sample"
                self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "baseline_render_sample":
                elapsed, _ = _elapsed_ms(self._render_now)
                self._sample_values.append(elapsed)
                self._sample_index += 1
                if self._sample_index < self.render_repeats:
                    self._schedule(self.MEASURE_GAP_MS)
                else:
                    self._baseline = {"viewport_render": _stats(self._sample_values)}
                    self._phase = "case_prepare"
                    self._schedule(self.EMPTY_HOLD_MS)
                return

            if self._phase == "case_prepare":
                if self._index >= len(self.cases):
                    self._finish(status="completed")
                    return
                case = self.cases[self._index]
                self._notify_progress(
                    f"Passe {self._index + 1}/{len(self.cases)} — preparing {case.name}"
                )
                self._current = self._prepare_case(case)
                self._phase = "case_precompile"
                self._schedule(0)
                return

            if self._phase == "case_precompile":
                assert self._current is not None
                from laserprog_studio.application.projected_drawing_2d import _compile_batches

                elapsed, compiled = _elapsed_ms(lambda: _compile_batches(self._current["primitives"]))
                self._current["pure_compile_cold_ms"] = elapsed
                self._current["pure_compile_batches"] = len(compiled)
                self._phase = "case_show"
                self._schedule(0)
                return

            if self._phase == "case_show":
                assert self._current is not None
                case = self._current["case"]
                self._notify_progress(
                    f"Passe {self._index + 1}/{len(self.cases)} — displaying {case.name}"
                )
                self._display_current()
                self._compile_samples = []
                self._sample_index = 0
                self._phase = "case_compile_warm"
                self._schedule(self.SHOW_HOLD_MS)
                return

            if self._phase == "case_compile_warm":
                assert self._current is not None
                from laserprog_studio.application.projected_drawing_2d import _compile_batches

                elapsed, _ = _elapsed_ms(lambda: _compile_batches(self._current["primitives"]))
                self._compile_samples.append(elapsed)
                self._sample_index += 1
                if self._sample_index < 3:
                    self._schedule(self.MEASURE_GAP_MS)
                else:
                    self._current["result"]["pure_compile_warm"] = _stats(self._compile_samples)
                    self._reset_samples()
                    self._phase = "case_steady_sync"
                    self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "case_steady_sync":
                assert self._current is not None
                renderer = self._current["renderer"]
                elapsed, _ = _elapsed_ms(lambda: renderer.sync_from_manager(force=False, render=False))
                self._sample_values.append(elapsed)
                self._sample_index += 1
                if self._sample_index < self.render_repeats:
                    self._schedule(self.MEASURE_GAP_MS)
                else:
                    self._current["result"]["steady_sync"] = _stats(self._sample_values)
                    self._reset_samples()
                    self._phase = "case_camera_sync"
                    self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "case_camera_sync":
                assert self._current is not None
                renderer = self._current["renderer"]
                camera = self.owner.plotter.renderer.GetActiveCamera()
                camera.Modified()
                elapsed, _ = _elapsed_ms(lambda: renderer.sync_from_manager(force=False, render=False))
                self._sample_values.append(elapsed)
                self._sample_index += 1
                if self._sample_index < self.render_repeats:
                    self._schedule(self.MEASURE_GAP_MS)
                else:
                    self._current["result"]["camera_reprojection_sync"] = _stats(self._sample_values)
                    self._reset_samples()
                    self._phase = "case_render_sample"
                    self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "case_render_sample":
                elapsed, _ = _elapsed_ms(self._render_now)
                self._sample_values.append(elapsed)
                self._sample_index += 1
                if self._sample_index < self.render_repeats:
                    self._schedule(self.MEASURE_GAP_MS)
                else:
                    assert self._current is not None
                    self._current["result"]["viewport_render"] = _stats(self._sample_values)
                    self._phase = "case_single_update"
                    self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "case_single_update":
                assert self._current is not None
                registry = self._current["registry"]
                renderer = self._current["renderer"]
                primitives = self._current["primitives"]
                result = self._current["result"]
                if primitives:
                    update_ms, updated = _elapsed_ms(
                        lambda: self._patch_one(registry, primitives[0], self.unit * 0.05)
                    )
                    result["single_update"] = {
                        **_sync_breakdown(renderer.diagnostic_snapshot(), update_ms),
                        "update_mode": "coordinate_patch",
                        "updated_elements": int(updated),
                    }
                else:
                    result["single_update"] = _sync_breakdown({}, 0.0)
                self._phase = "case_bulk_update"
                self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "case_bulk_update":
                assert self._current is not None
                registry = self._current["registry"]
                renderer = self._current["renderer"]
                primitives = self._current["primitives"]
                result = self._current["result"]
                if primitives:
                    update_ms, updated = _elapsed_ms(
                        lambda: self._patch_many(registry, primitives[0], self.unit * 0.025, 64)
                    )
                    result["bulk_update_many"] = {
                        **_sync_breakdown(renderer.diagnostic_snapshot(), update_ms),
                        "update_mode": "coordinate_patch",
                        "updated_primitives": 1,
                        "updated_elements": int(updated),
                    }
                else:
                    result["bulk_update_many"] = {
                        **_sync_breakdown({}, 0.0),
                        "updated_primitives": 0,
                        "updated_elements": 0,
                    }
                self._phase = "case_same_replace"
                self._schedule(self.MEASURE_GAP_MS)
                return

            if self._phase == "case_same_replace":
                assert self._current is not None
                registry = self._current["registry"]
                renderer = self._current["renderer"]
                primitives = self._current["primitives"]
                elapsed, _ = _elapsed_ms(lambda: registry.replace_all(primitives, render=False))
                self._current["result"]["same_geometry_replace_all"] = _sync_breakdown(
                    renderer.diagnostic_snapshot(), elapsed
                )
                self._render_now()
                self._phase = "case_clear"
                self._schedule(self.AFTER_MEASURE_HOLD_MS)
                return

            if self._phase == "case_clear":
                assert self._current is not None
                case = self._current["case"]
                registry = self.ctx.projected_drawing.for_tool(_BENCHMARK_OWNER)
                dispose_ms, _ = _elapsed_ms(lambda: registry.clear(render=False))
                self._current["result"]["dispose_ms"] = round(dispose_ms, 6)
                self._results.append(self._current["result"])
                self._notify_progress(
                    f"Passe {self._index + 1}/{len(self.cases)} — scene cleared after {case.name}"
                )
                self._render_now()
                self._current = None
                self._index += 1
                self._phase = "case_prepare"
                self._schedule(self.EMPTY_HOLD_MS)
                return
        except Exception as exc:
            self._errors.append({"stage": self._phase, "case_index": self._index, "error": repr(exc)})
            self._finish(status="failed")

    def _viewport_render_samples(self) -> list[float]:
        samples: list[float] = []
        for _index in range(self.render_repeats):
            elapsed, _ = _elapsed_ms(self._render_now)
            samples.append(elapsed)
        return samples

    def _run_baseline(self) -> dict[str, Any]:
        return {"viewport_render": _stats(self._viewport_render_samples())}

    def _prepare_case(self, case: BenchmarkCase) -> dict[str, Any]:
        """Build public API declarations without touching VTK.

        This deliberately runs in a separate Qt turn from actor/topology
        synchronization, so a large Python input build and a cold VTK upload do
        not combine into one visible frame hitch.
        """

        import laserprog_studio.tool_api.projected_drawing as draw2d

        registry = self.ctx.projected_drawing.for_tool(_BENCHMARK_OWNER)
        build_ms, primitives = _elapsed_ms(lambda: build_case_primitives(draw2d, case, self.origin, self.unit))
        return {
            "case": case,
            "registry": registry,
            "renderer": None,
            "primitives": primitives,
            "build_ms": build_ms,
            "result": {},
        }

    def _display_current(self) -> None:
        """Synchronize and show the prepared case with no duplicate compiles."""

        assert self._current is not None
        case: BenchmarkCase = self._current["case"]
        registry = self._current["registry"]
        primitives: tuple[ProjectedPrimitive, ...] = self._current["primitives"]
        cold_ms, snapshot = _elapsed_ms(lambda: registry.replace_all(primitives, render=False))
        renderer = _renderer_for(self.owner, _BENCHMARK_OWNER)
        if renderer is None:
            raise RuntimeError("Projected drawing benchmark renderer was not created.")
        cold_renderer = renderer.diagnostic_snapshot()
        self._render_now()
        point_count, line_count, face_count = _element_counts(snapshot.primitives)
        result = {
            "name": case.name,
            "family": case.family,
            "requested_count": int(case.count),
            "style_count": int(case.style_count),
            "primitive_count": len(snapshot.primitives),
            "point_count": point_count,
            "line_count": line_count,
            "face_count": face_count,
            "python_build_ms": round(float(self._current["build_ms"]), 6),
            "pure_compile_cold_ms": round(float(self._current.get("pure_compile_cold_ms", 0.0)), 6),
            "pure_compile_batches": int(self._current.get("pure_compile_batches", 0)),
            "cold_replace_all": _sync_breakdown(cold_renderer, cold_ms),
            "visual_hold_ms": self.SHOW_HOLD_MS,
            "renderer": {
                "batches": int(cold_renderer.get("batches", 0) or 0),
                "actors": int(cold_renderer.get("actors", 0) or 0),
                "batches_by_kind": dict(cold_renderer.get("batches_by_kind", {}) or {}),
                "world_points": int(cold_renderer.get("world_points", 0) or 0),
                "cells": int(cold_renderer.get("cells", 0) or 0),
                "vector_projection_count": int(cold_renderer.get("vector_projection_count", 0) or 0),
                "scalar_projection_count": int(cold_renderer.get("scalar_projection_count", 0) or 0),
                "projection_groups": int(cold_renderer.get("last_projection_groups", 0) or 0),
            },
        }
        self._current["renderer"] = renderer
        self._current["result"] = result

    def _sync_samples(self, renderer: Any, *, dirty_camera: bool) -> list[float]:
        samples: list[float] = []
        camera = self.owner.plotter.renderer.GetActiveCamera()
        for _index in range(self.render_repeats):
            if dirty_camera:
                camera.Modified()
            elapsed, _ = _elapsed_ms(lambda: renderer.sync_from_manager(force=False, render=False))
            samples.append(elapsed)
        return samples

    @staticmethod
    def _patch_one(registry: Any, primitive: ProjectedPrimitive, delta: float) -> int:
        if isinstance(primitive, ProjectedPointCloud) and primitive.positions:
            point = primitive.positions[0]
            registry.patch_point_cloud(primitive.id, ((0, (point[0] + delta, point[1], point[2])),), render=False)
            return 1
        if isinstance(primitive, ProjectedSegmentBatch) and primitive.segments:
            start, end = primitive.segments[0]
            registry.patch_segment_batch(
                primitive.id,
                ((0, ((start[0] + delta, start[1], start[2]), end)),),
                render=False,
            )
            return 1
        if isinstance(primitive, ProjectedFaceBatch) and primitive.polygons:
            polygon = list(primitive.polygons[0])
            first = polygon[0]
            polygon[0] = (first[0] + delta, first[1], first[2])
            registry.patch_face_batch(primitive.id, ((0, tuple(polygon)),), render=False)
            return 1
        if isinstance(primitive, ProjectedFace) and primitive.vertices:
            first = primitive.vertices[0]
            registry.patch_face(primitive.id, ((0, (first[0] + delta, first[1], first[2])),), render=False)
            return 1
        registry.update(_mutate_one(primitive, delta), render=False)
        return 1

    @staticmethod
    def _patch_many(registry: Any, primitive: ProjectedPrimitive, delta: float, limit: int) -> int:
        count = max(0, int(limit))
        if isinstance(primitive, ProjectedPointCloud):
            touched = min(count, len(primitive.positions))
            updates = tuple(
                (index, (primitive.positions[index][0] + delta, primitive.positions[index][1], primitive.positions[index][2]))
                for index in range(touched)
            )
            registry.patch_point_cloud(primitive.id, updates, render=False)
            return touched
        if isinstance(primitive, ProjectedSegmentBatch):
            touched = min(count, len(primitive.segments))
            updates = tuple(
                (
                    index,
                    (
                        (primitive.segments[index][0][0] + delta, primitive.segments[index][0][1], primitive.segments[index][0][2]),
                        primitive.segments[index][1],
                    ),
                )
                for index in range(touched)
            )
            registry.patch_segment_batch(primitive.id, updates, render=False)
            return touched
        if isinstance(primitive, ProjectedFaceBatch):
            touched = min(count, len(primitive.polygons))
            updates = []
            for index in range(touched):
                polygon = list(primitive.polygons[index])
                first = polygon[0]
                polygon[0] = (first[0] + delta, first[1], first[2])
                updates.append((index, tuple(polygon)))
            registry.patch_face_batch(primitive.id, tuple(updates), render=False)
            return touched
        if isinstance(primitive, ProjectedFace) and primitive.vertices:
            touched = min(count, len(primitive.vertices))
            updates = tuple(
                (index, (primitive.vertices[index][0] + delta, primitive.vertices[index][1], primitive.vertices[index][2]))
                for index in range(touched)
            )
            registry.patch_face(primitive.id, updates, render=False)
            return touched
        registry.update(_mutate_one(primitive, delta), render=False)
        return 1

    def _measure_current(self) -> None:
        current = self._current
        assert current is not None
        registry = current["registry"]
        renderer = current["renderer"]
        primitives: tuple[ProjectedPrimitive, ...] = current["primitives"]
        result = current["result"]
        if renderer is None:
            raise RuntimeError("Projected drawing benchmark renderer was not created.")

        result["steady_sync"] = _stats(self._sync_samples(renderer, dirty_camera=False))
        result["camera_reprojection_sync"] = _stats(self._sync_samples(renderer, dirty_camera=True))
        result["viewport_render"] = _stats(self._viewport_render_samples())

        if primitives:
            update_ms, updated_one = _elapsed_ms(
                lambda: self._patch_one(registry, primitives[0], self.unit * 0.05)
            )
            result["single_update"] = {
                **_sync_breakdown(renderer.diagnostic_snapshot(), update_ms),
                "update_mode": "coordinate_patch",
                "updated_elements": int(updated_one),
            }

            bulk_ms, updated_elements = _elapsed_ms(
                lambda: self._patch_many(registry, primitives[0], self.unit * 0.025, 64)
            )
            result["bulk_update_many"] = {
                **_sync_breakdown(renderer.diagnostic_snapshot(), bulk_ms),
                "update_mode": "coordinate_patch",
                "updated_primitives": 1,
                "updated_elements": int(updated_elements),
            }
        else:
            result["single_update"] = _sync_breakdown({}, 0.0)
            result["bulk_update_many"] = {**_sync_breakdown({}, 0.0), "updated_primitives": 0, "updated_elements": 0}

        same_replace_ms, _ = _elapsed_ms(lambda: registry.replace_all(primitives, render=False))
        result["same_geometry_replace_all"] = _sync_breakdown(renderer.diagnostic_snapshot(), same_replace_ms)

    def _finish(self, *, status: str) -> None:
        try:
            self.ctx.projected_drawing.clear_tool(_BENCHMARK_OWNER, render=False)
        except Exception:
            pass
        self._restore_catalog()
        report = {
            "schema_version": 4,
            "status": status,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_ms": round((time.perf_counter() - self._started_at) * 1000.0, 6),
            "source_fingerprint_sha256": _source_fingerprint(),
            "environment": _environment(),
            "viewport": _viewport_snapshot(self.owner),
            "camera": _camera_snapshot(self.owner),
            "ground_plane": {"origin": list(self.origin), "normal": [0.0, 0.0, 1.0], "unit_world": self.unit},
            "configuration": {
                "render_repeats": self.render_repeats,
                "pure_compile_warm_repeats": 3,
                "show_hold_ms": self.SHOW_HOLD_MS,
                "after_measure_hold_ms": self.AFTER_MEASURE_HOLD_MS,
                "empty_hold_ms": self.EMPTY_HOLD_MS,
                "measure_gap_ms": self.MEASURE_GAP_MS,
                "frame_budget_ms_at_60hz": round(_FRAME_BUDGET_MS, 6),
                "cases": [
                    {"name": case.name, "family": case.family, "count": case.count, "style_count": case.style_count}
                    for case in self.cases
                ],
            },
            "baseline": self._baseline,
            "cases": self._results,
            "summary": _summary(self._results, self._baseline),
            "projected_drawing_audit": _filtered_audit_snapshot(),
            "errors": self._errors,
            "interpretation_notes": [
                "Each case is visibly shown, held, measured, cleared and followed by an empty-scene pause.",
                "camera_reprojection_sync measures the actual renderer CPU path after camera.Modified().",
                "single_update and bulk_update_many use explicit coordinate patches and must remain proportional to changed coordinates, not scene size.",
                "Filled faces use stable indexed triangles. Concave loops are triangulated once with constrained Delaunay; coordinate patches keep that topology.",
                "Python declaration build, cold VTK upload and repeated measurement samples run in separate Qt turns to avoid artificial compounded stalls.",
                "same_geometry_replace_all intentionally measures the slower declarative rebuild path.",
                "style_count controls actor/batch fragmentation.",
                "All benchmark geometry lies on world XY at Z=0.",
            ],
        }
        output: Path | None = None
        try:
            output = diagnostic_path()
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(output)
            self._notify_progress(f"2D benchmark complete — {output.name}")
        except Exception as exc:
            self._errors.append({"stage": "write", "error": repr(exc)})
            report["errors"] = self._errors
            output = None
        self._notify_complete(output, report)

    def _notify_progress(self, message: str) -> None:
        if self.on_progress is not None:
            try:
                self.on_progress(str(message))
            except Exception:
                pass

    def _notify_complete(self, output: Path | None, report: dict[str, Any]) -> None:
        if self.on_complete is not None:
            try:
                self.on_complete(output, report)
            except Exception:
                pass


__all__ = [
    "BENCHMARK_CASES",
    "BenchmarkCase",
    "ProjectedDrawingBenchmarkRunner",
    "build_case_primitives",
    "diagnostic_path",
]
