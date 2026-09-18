# -*- coding: utf-8 -*-
"""Live viewport probes for the Tool Core Diagnostic benchmark.

The probes are deliberately capped so they can run inside the application
without freezing the UI. They complement the deterministic tool-core benchmark
with real PyVista/VTK calls when the renderer is available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from ..studio_log import log_exception

_PREFIX = "tool_core_diag_bench_"


@dataclass(slots=True)
class LiveBenchResult:
    label: str
    status: str
    total_ms: float = 0.0
    avg_ms: float = 0.0
    actors_created: int = 0
    actors_removed: int = 0
    notes: list[str] = field(default_factory=list)
    bugs: list[str] = field(default_factory=list)


def clear_tool_core_bench_scene(owner: Any) -> int:
    plotter = getattr(owner, "plotter", None)
    if plotter is None:
        return 0
    names = list(getattr(owner, "_tool_core_bench_actor_names", []) or [])
    try:
        actors = getattr(plotter, "actors", {}) or {}
        names.extend(str(name) for name in actors if str(name).startswith(_PREFIX))
    except Exception:
        pass
    removed = 0
    for name in sorted(set(names)):
        try:
            plotter.remove_actor(name, render=False)
            removed += 1
        except Exception:
            pass
    try:
        owner._tool_core_bench_actor_names = []
    except Exception:
        pass
    try:
        plotter.render()
    except Exception:
        pass
    return removed


class LiveViewportBenchmark:
    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.actor_names: list[str] = []

    def run(self) -> dict[str, Any]:
        plotter = getattr(self.owner, "plotter", None)
        if plotter is None:
            return {"status": "no_plotter", "results": []}
        try:
            import numpy as np  # noqa: F401
            import pyvista as pv  # noqa: F401
        except Exception:
            log_exception("tool_core_live_bench_import")
            return {"status": "missing_pyvista", "results": []}

        before = self._actor_count(plotter)
        clear_tool_core_bench_scene(self.owner)
        results = [
            self._safe("batched PolyData points", self._bench_point_cloud),
            self._safe("vtkGlyph3DMapper cached spheres", self._bench_vtk_glyphs),
            self._safe("cached glyphs interactive LOD", self._bench_vtk_glyphs_lod),
            self._safe("batched line PolyData", self._bench_line_batch),
            self._safe("single hover text label", self._bench_single_hover_label),
            self._safe("limited text labels", self._bench_text_labels),
            self._safe("actor churn canary", self._bench_actor_churn),
        ]
        removed = clear_tool_core_bench_scene(self.owner)
        after = self._actor_count(plotter)
        leaks = max(0, after - before)
        bugs = [bug for result in results for bug in result.bugs]
        if leaks:
            bugs.append(f"Actor leak suspected: before={before}, after={after}")
        try:
            self.owner._tool_core_bench_actor_names = []
        except Exception:
            pass
        return {
            "status": "rendered",
            "before_actors": before,
            "after_actors": after,
            "removed": removed,
            "results": results,
            "bugs": bugs,
        }

    def _safe(self, label: str, func: Callable[[], LiveBenchResult]) -> LiveBenchResult:
        try:
            return func()
        except Exception as exc:  # pragma: no cover - defensive GUI path
            log_exception(f"tool_core_live_bench_{label.replace(' ', '_')}")
            return LiveBenchResult(label, "failed", bugs=[f"Exception: {exc.__class__.__name__}"])

    def _bench_point_cloud(self) -> LiveBenchResult:
        import numpy as np
        import pyvista as pv

        plotter = self.owner.plotter
        count = 700
        steps = 80
        points = np.zeros((count, 3), dtype=float)
        points[:, 0] = np.arange(count) % 70
        points[:, 1] = np.arange(count) // 70
        cloud = pv.PolyData(points)
        name = self._add_name("points")
        plotter.add_mesh(cloud, name=name, render_points_as_spheres=True, point_size=16, color="deepskyblue", pickable=False, render=False)
        start = perf_counter()
        for step in range(steps):
            index = step % count
            points[index, 2] = 0.15 + (step % 8) * 0.02
            cloud.points = points
            try:
                cloud.GetPoints().Modified()
                cloud.Modified()
            except Exception:
                pass
            if step % 12 == 0:
                plotter.render()
        total = self._elapsed(start)
        return self._result("batched PolyData points", total, steps, 1, 0, "One actor; point array updated in place.")

    def _bench_vtk_glyphs(self) -> LiveBenchResult:
        try:
            import vtk
        except Exception:
            return LiveBenchResult("vtkGlyph3DMapper cached spheres", "skipped", bugs=["VTK module unavailable"])
        plotter = self.owner.plotter
        count = 700
        steps = 80
        vtk_points = vtk.vtkPoints()
        vtk_points.SetDataTypeToFloat()
        vtk_points.SetNumberOfPoints(count)
        for i in range(count):
            vtk_points.SetPoint(i, float(i % 70), float(i // 70) + 14.0, 0.0)
        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk_points)
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(0.18)
        sphere.SetThetaResolution(10)
        sphere.SetPhiResolution(8)
        mapper = vtk.vtkGlyph3DMapper()
        mapper.SetInputData(poly)
        mapper.SetSourceConnection(sphere.GetOutputPort())
        mapper.ScalingOff()
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        try:
            actor.GetProperty().SetColor(0.1, 0.75, 1.0)
        except Exception:
            pass
        name = self._add_name("glyphs")
        try:
            plotter.add_actor(actor, name=name, pickable=False, render=False)
        except TypeError:
            plotter.add_actor(actor, name=name, render=False)
        start = perf_counter()
        for step in range(steps):
            index = step % count
            vtk_points.SetPoint(index, float(index % 70), float(index // 70) + 14.0, 0.2 + (step % 7) * 0.03)
            vtk_points.Modified()
            poly.Modified()
            if step % 12 == 0:
                plotter.render()
        total = self._elapsed(start)
        result = self._result("vtkGlyph3DMapper cached spheres", total, steps, 1, 0, "GPU glyph mapper; cached sphere source; vtkPoints updated only.")
        if result.avg_ms > 4.0:
            result.bugs.append("Glyph mapper update is slower than expected on this renderer")
        return result

    def _bench_vtk_glyphs_lod(self) -> LiveBenchResult:
        try:
            import vtk
        except Exception:
            return LiveBenchResult("cached glyphs interactive LOD", "skipped", bugs=["VTK module unavailable"])
        plotter = self.owner.plotter
        count = 700
        steps = 80
        vtk_points = vtk.vtkPoints()
        vtk_points.SetDataTypeToFloat()
        vtk_points.SetNumberOfPoints(count)
        for i in range(count):
            vtk_points.SetPoint(i, float(i % 70), float(i // 70) + 21.0, 0.0)
        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk_points)
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(0.18)
        sphere.SetThetaResolution(6)
        sphere.SetPhiResolution(5)
        mapper = vtk.vtkGlyph3DMapper()
        mapper.SetInputData(poly)
        mapper.SetSourceConnection(sphere.GetOutputPort())
        mapper.ScalingOff()
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        try:
            actor.GetProperty().SetColor(0.25, 0.95, 0.75)
        except Exception:
            pass
        name = self._add_name("glyphs_lod")
        try:
            plotter.add_actor(actor, name=name, pickable=False, render=False)
        except TypeError:
            plotter.add_actor(actor, name=name, render=False)
        start = perf_counter()
        for step in range(steps):
            index = step % count
            vtk_points.SetPoint(index, float(index % 70), float(index // 70) + 21.0, 0.18 + (step % 7) * 0.025)
            vtk_points.Modified()
            poly.Modified()
            if step % 16 == 0:
                plotter.render()
        # Simulate release quality restoration once, not during raw mouse move.
        sphere.SetThetaResolution(12)
        sphere.SetPhiResolution(8)
        sphere.Modified()
        plotter.render()
        total = self._elapsed(start)
        result = self._result("cached glyphs interactive LOD", total, steps, 1, 0, "One glyph actor; low-detail during drag, quality restored once on release.")
        if result.avg_ms > 4.0:
            result.bugs.append("Interactive LOD glyph update is slower than expected on this renderer")
        return result

    def _bench_line_batch(self) -> LiveBenchResult:
        import numpy as np
        import pyvista as pv

        plotter = self.owner.plotter
        line_count = 350
        steps = 60
        points: list[tuple[float, float, float]] = []
        cells: list[int] = []
        for i in range(line_count):
            start = len(points)
            points.extend([(float(i % 70), float(i // 70) + 28.0, 0.05), (float(i % 70) + 0.75, float(i // 70) + 28.0, 0.05)])
            cells.extend([2, start, start + 1])
        arr = np.asarray(points, dtype=float)
        mesh = pv.PolyData(arr)
        mesh.lines = np.asarray(cells, dtype=np.int64)
        name = self._add_name("lines")
        plotter.add_mesh(mesh, name=name, color="white", line_width=2, pickable=False, render=False)
        start = perf_counter()
        for step in range(steps):
            idx = (step % line_count) * 2 + 1
            arr[idx, 2] = 0.1 + (step % 6) * 0.02
            mesh.points = arr
            if step % 15 == 0:
                plotter.render()
        total = self._elapsed(start)
        return self._result("batched line PolyData", total, steps, 1, 0, "One line-cell mesh for all sketch preview edges.")

    def _bench_single_hover_label(self) -> LiveBenchResult:
        plotter = self.owner.plotter
        steps = 60
        name = self._add_name("hover_label")
        start = perf_counter()
        try:
            actor = plotter.add_text("Hover P0", position="upper_right", name=name, font_size=12, color="white", render=False)
        except TypeError:
            actor = plotter.add_text("Hover P0", position="upper_right", name=name, font_size=12, color="white")
        updates = 1
        for step in range(steps):
            if step % 20 == 0:
                try:
                    actor.SetInput(f"Hover P{step // 20}")
                except Exception:
                    try:
                        actor.GetTextProperty()
                    except Exception:
                        pass
                plotter.render()
                updates += 1
        total = self._elapsed(start)
        result = self._result("single hover text label", total, steps, 1, 0, "One overlay label; text changes only when hovered target changes.")
        if result.avg_ms > 4.0:
            result.bugs.append("Even hover-only text is slow; prefer Qt-side label outside the VTK scene")
        result.notes.append(f"semantic_updates={updates}, raw_steps={steps}")
        return result

    def _bench_text_labels(self) -> LiveBenchResult:
        import numpy as np

        plotter = self.owner.plotter
        count = 45
        points = np.asarray([(float(i % 15) * 4.0, float(i // 15) * 3.0 + 40.0, 0.2) for i in range(count)], dtype=float)
        labels = [f"P{i}" for i in range(count)]
        name = self._add_name("labels")
        start = perf_counter()
        plotter.add_point_labels(points, labels, name=name, font_size=12, point_size=0, shape=None, pickable=False, render=False)
        plotter.render()
        total = self._elapsed(start)
        result = self._result("limited text labels", total, 1, 1, 0, "Text is created once; avoid per-mouse-move label updates.")
        if total > 100.0:
            result.bugs.append("Text labels are expensive on this renderer; keep counts very low")
        return result

    def _bench_actor_churn(self) -> LiveBenchResult:
        import numpy as np
        import pyvista as pv

        plotter = self.owner.plotter
        steps = 10
        per_step = 24
        created = 0
        removed = 0
        names: list[str] = []
        start = perf_counter()
        for step in range(steps):
            for name in names:
                try:
                    plotter.remove_actor(name, render=False)
                    removed += 1
                except Exception:
                    pass
            names = []
            for i in range(per_step):
                name = self._add_name(f"churn_{step}_{i}")
                cloud = pv.PolyData(np.asarray([[float(i), float(step), 0.0]], dtype=float))
                plotter.add_mesh(cloud, name=name, render_points_as_spheres=True, point_size=12, color="tomato", pickable=False, render=False)
                names.append(name)
                created += 1
            plotter.render()
        total = self._elapsed(start)
        result = self._result("actor churn canary", total, max(1, steps), created, removed, "Bad reference: recreates actors repeatedly.")
        result.bugs.append("Actor churn detected by design; production tools must avoid this pattern")
        return result

    def _result(self, label: str, total_ms: float, steps: int, created: int, removed: int, note: str) -> LiveBenchResult:
        avg = total_ms / max(1, steps)
        result = LiveBenchResult(label, "ok", total_ms, avg, created, removed, notes=[note])
        if removed > 0 and "churn" not in label:
            result.bugs.append("Unexpected actor removal")
        if created > 5 and "churn" not in label:
            result.bugs.append("Too many actors created for an optimized path")
        if avg > 16.0 and "churn" not in label:
            result.bugs.append("Average step above 16 ms; likely visible lag")
        return result

    def _add_name(self, suffix: str) -> str:
        name = f"{_PREFIX}{suffix}"
        self.actor_names.append(name)
        try:
            names = list(getattr(self.owner, "_tool_core_bench_actor_names", []) or [])
            names.append(name)
            self.owner._tool_core_bench_actor_names = names
        except Exception:
            pass
        return name

    @staticmethod
    def _elapsed(start: float) -> float:
        return max(0.0001, (perf_counter() - start) * 1000.0)

    @staticmethod
    def _actor_count(plotter: Any) -> int:
        try:
            return len(getattr(plotter, "actors", {}) or {})
        except Exception:
            return 0
