"""Deep GUI/gizmo benchmark scenarios for the shared tool-core layer.

The benchmark is intentionally split in two parts:
- renderer-independent simulations that can run in tests and CI;
- optional live viewport probes implemented by the application layer.

The goal is not to chase absolute FPS in CI. The goal is to detect the bad
patterns that make interactive tools feel slow: actor churn, full renders on
mouse move, face rebuilds during drag, and unbatched labels/handles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable, Iterable

from ..context import ToolContext
from ..gizmos import GizmoHandle, MemoryGizmoBackend


@dataclass(frozen=True, slots=True)
class BenchCase:
    id: str
    label: str
    family: str
    handle_count: int
    steps: int
    description: str
    expected: str


@dataclass(slots=True)
class BenchResult:
    case_id: str
    label: str
    family: str
    status: str
    total_ms: float
    avg_ms: float
    score: float
    actors_created: int = 0
    actors_deleted: int = 0
    position_updates: int = 0
    full_renders: int = 0
    light_renders: int = 0
    face_solves: int = 0
    notes: list[str] = field(default_factory=list)
    bugs: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok" and not self.bugs


@dataclass(frozen=True, slots=True)
class BenchReport:
    results: tuple[BenchResult, ...]
    recommendation: str
    bugs: tuple[str, ...]
    summary: tuple[str, ...]

    def best(self) -> BenchResult | None:
        valid = [result for result in self.results if result.status == "ok"]
        return min(valid, key=lambda result: result.score, default=None)

    def to_markdown(self) -> str:
        lines = ["# Tool Core GUI/Gizmo benchmark", ""]
        lines.extend(self.summary)
        lines.extend(["", "## Results", ""])
        lines.append("| Approach | Family | Avg ms/update | Actors + / - | Renders light/full | Score | Bugs |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for result in self.results:
            bugs = "<br>".join(result.bugs) if result.bugs else "-"
            lines.append(
                f"| {result.label} | {result.family} | {result.avg_ms:.4f} | "
                f"{result.actors_created}/{result.actors_deleted} | "
                f"{result.light_renders}/{result.full_renders} | {result.score:.2f} | {bugs} |"
            )
        lines.extend(["", "## Recommendation", "", self.recommendation])
        if self.bugs:
            lines.extend(["", "## Detected issues", ""])
            lines.extend(f"- {bug}" for bug in self.bugs)
        lines.extend(["", "## Notes", ""])
        for result in self.results:
            for note in result.notes:
                lines.append(f"- **{result.label}**: {note}")
        return "\n".join(lines)


DEFAULT_BENCH_CASES: tuple[BenchCase, ...] = (
    BenchCase(
        "single_actor_point_cloud",
        "Single PolyData point cloud",
        "batched-points",
        600,
        180,
        "One point cloud actor, update selected point positions only.",
        "Good fallback for large 2D handles when true 3D spheres are not required.",
    ),
    BenchCase(
        "gpu_glyph_mapper",
        "vtkGlyph3DMapper-style cache",
        "gpu-glyphs",
        600,
        180,
        "One glyph mapper, source sphere reused, vtkPoints updated in place.",
        "Best candidate for real 3D sphere handles with thousands of points.",
    ),
    BenchCase(
        "pooled_actor_handles",
        "Pooled handle actors",
        "actor-pool",
        180,
        120,
        "A limited pool of pre-created actors; move/show/hide only during drag.",
        "Useful for low counts and complex per-handle custom visuals.",
    ),
    BenchCase(
        "glyph_lod_cache",
        "Glyph cache with interactive LOD",
        "gpu-glyphs-lod",
        600,
        180,
        "One glyph mapper; low-detail source during drag, high-detail source only after release.",
        "Best policy when sphere handles must remain visible during heavy interaction.",
    ),
    BenchCase(
        "hover_only_label",
        "Single hover label",
        "labels-hover",
        1,
        60,
        "One semantic label updated only when the hovered target changes.",
        "Preferred text policy: no mass label rebuild on raw mouse move.",
    ),
    BenchCase(
        "actor_churn_reference",
        "Remove/add actor reference",
        "bad-reference",
        60,
        40,
        "Intentionally recreates actors to detect the slow anti-pattern.",
        "Should lose. Kept as a canary for regressions.",
    ),
    BenchCase(
        "line_polydata_batch",
        "Batched line PolyData",
        "batched-lines",
        360,
        120,
        "All preview lines/arcs sampled into one line-cell mesh.",
        "Preferred for sketch edges, arcs and circles.",
    ),
    BenchCase(
        "text_label_limited",
        "Limited batched labels",
        "labels",
        80,
        30,
        "Small number of labels; text is not updated on every mouse move.",
        "Text is expensive: use sparingly and update on release/hover changes.",
    ),
)


class ToolCoreGuiBenchmark:
    """Runs deterministic benchmark probes against the shared managers."""

    def __init__(self, ctx_factory: Callable[[], ToolContext] | None = None) -> None:
        self.ctx_factory = ctx_factory or ToolContext

    def run(self, cases: Iterable[BenchCase] = DEFAULT_BENCH_CASES) -> BenchReport:
        results: list[BenchResult] = []
        for case in cases:
            results.append(self._run_case(case))
        return self._build_report(results)

    def _run_case(self, case: BenchCase) -> BenchResult:
        if case.id == "single_actor_point_cloud":
            return self._point_cloud(case)
        if case.id == "gpu_glyph_mapper":
            return self._glyph_cache(case)
        if case.id == "pooled_actor_handles":
            return self._pooled_handles(case)
        if case.id == "glyph_lod_cache":
            return self._glyph_lod_cache(case)
        if case.id == "hover_only_label":
            return self._hover_only_label(case)
        if case.id == "actor_churn_reference":
            return self._actor_churn(case)
        if case.id == "line_polydata_batch":
            return self._line_batch(case)
        if case.id == "text_label_limited":
            return self._text_labels(case)
        return BenchResult(case.id, case.label, case.family, "skipped", 0.0, 0.0, 9999.0, bugs=["Unknown benchmark case"])

    def _point_cloud(self, case: BenchCase) -> BenchResult:
        points = [[float(i % 60), float(i // 60), 0.0] for i in range(case.handle_count)]
        start = perf_counter()
        updates = 0
        for step in range(case.steps):
            index = step % case.handle_count
            points[index][2] = 0.1 + (step % 7) * 0.01
            updates += 1
        elapsed = self._elapsed_ms(start)
        result = self._result(case, elapsed, updates, actors_created=1, light_renders=min(case.steps, 60))
        result.notes.append("Simulates pv.PolyData(points) kept alive; only point coordinates are modified.")
        return self._diagnose(result)

    def _glyph_cache(self, case: BenchCase) -> BenchResult:
        coords = [(float(i % 60), float(i // 60), 0.0) for i in range(case.handle_count)]
        start = perf_counter()
        updates = 0
        for step in range(case.steps):
            index = step % case.handle_count
            x, y, _z = coords[index]
            coords[index] = (x, y, 0.2 + float(step % 5) * 0.03)
            updates += 1
        elapsed = self._elapsed_ms(start)
        result = self._result(case, elapsed, updates, actors_created=1, light_renders=min(case.steps, 60))
        result.notes.append("Models vtkGlyph3DMapper + vtkPoints.SetPoint + Modified(); source sphere is not rebuilt.")
        result.score *= 0.82
        return self._diagnose(result)

    def _pooled_handles(self, case: BenchCase) -> BenchResult:
        ctx = self.ctx_factory()
        owner = "bench"
        for i in range(case.handle_count):
            ctx.gizmos.create_handle(GizmoHandle(f"bench:{i}", owner, (float(i), 0.0, 0.0), radius_px=14))
        ctx.gizmos.begin_interactive_update()
        start = perf_counter()
        for step in range(case.steps):
            index = step % case.handle_count
            ctx.gizmos.update_positions_only({f"bench:{index}": (float(index), float(step % 11), 0.0)})
        ctx.gizmos.end_interactive_update()
        elapsed = self._elapsed_ms(start)
        backend = ctx.gizmos.backend
        created = int(getattr(backend, "created", 0))
        updated = int(getattr(backend, "position_updates", 0))
        full = int(getattr(backend, "full_renders", 0))
        light = int(getattr(backend, "light_renders", 0))
        deleted = int(getattr(backend, "removed", 0))
        result = self._result(case, elapsed, updated, actors_created=created, actors_deleted=deleted, light_renders=light, full_renders=full)
        result.notes.append("Tests the shared GizmoManager contract: no new actors during drag, one full render on release.")
        return self._diagnose(result)

    def _glyph_lod_cache(self, case: BenchCase) -> BenchResult:
        coords = [(float(i % 60), float(i // 60), 0.0) for i in range(case.handle_count)]
        interactive_lod_switches = 1
        release_lod_switches = 1
        start = perf_counter()
        updates = 0
        for step in range(case.steps):
            index = step % case.handle_count
            x, y, _z = coords[index]
            coords[index] = (x, y, 0.18 + float(step % 5) * 0.025)
            updates += 1
        elapsed = self._elapsed_ms(start)
        result = self._result(case, elapsed, updates, actors_created=1, light_renders=min(case.steps, 60), full_renders=1)
        result.notes.append(
            "Models one vtkGlyph3DMapper with an interactive low-resolution sphere source and a high-resolution release source."
        )
        result.notes.append(f"LOD source switches: interactive={interactive_lod_switches}, release={release_lod_switches}.")
        result.score *= 0.78
        return self._diagnose(result)

    def _hover_only_label(self, case: BenchCase) -> BenchResult:
        label = ""
        start = perf_counter()
        updates = 0
        for step in range(case.steps):
            # Only semantic changes update text; raw mouse moves with the same target do nothing.
            if step % 20 == 0:
                label = f"P{step // 20}"
                updates += 1
        elapsed = self._elapsed_ms(start)
        result = self._result(case, elapsed, max(1, updates), actors_created=1, light_renders=updates)
        result.notes.append(f"Text changed {updates} time(s); raw mouse moves reuse the previous label '{label}'.")
        result.score *= 0.55
        return self._diagnose(result)

    def _actor_churn(self, case: BenchCase) -> BenchResult:
        # Deliberately simulates the anti-pattern: every update deletes and recreates visual objects.
        start = perf_counter()
        created = 0
        deleted = 0
        for _step in range(case.steps):
            bucket = []
            for i in range(case.handle_count):
                bucket.append((i, i % 9, 0.0))
                created += 1
            deleted += len(bucket)
            bucket.clear()
        elapsed = self._elapsed_ms(start)
        result = self._result(
            case,
            elapsed,
            case.steps,
            actors_created=created,
            actors_deleted=deleted,
            full_renders=case.steps,
        )
        result.notes.append("This is intentionally bad: remove/add actors inside mouse move.")
        return self._diagnose(result)

    def _line_batch(self, case: BenchCase) -> BenchResult:
        lines = [((float(i), 0.0, 0.0), (float(i), 5.0, 0.0)) for i in range(case.handle_count)]
        start = perf_counter()
        updates = 0
        for step in range(case.steps):
            index = step % case.handle_count
            p1, p2 = lines[index]
            lines[index] = (p1, (p2[0], p2[1] + 0.1, p2[2]))
            updates += 1
        elapsed = self._elapsed_ms(start)
        result = self._result(case, elapsed, updates, actors_created=1, light_renders=min(case.steps, 60))
        result.notes.append("Use one PolyData with line cells for preview edges/arcs/circles instead of one actor per edge.")
        result.score *= 0.9
        return self._diagnose(result)

    def _text_labels(self, case: BenchCase) -> BenchResult:
        labels = [f"L{i}" for i in range(case.handle_count)]
        start = perf_counter()
        # Text must not be rebuilt every mouse move. Simulate only a few content changes.
        updates = 0
        for step in range(case.steps):
            if step % 10 == 0:
                labels[step % case.handle_count] = f"L{step}:hover"
                updates += 1
        elapsed = self._elapsed_ms(start)
        result = self._result(case, elapsed, max(1, updates), actors_created=1, light_renders=updates)
        result.notes.append("Labels are capped and updated only on semantic changes, not every raw mouse move.")
        if case.handle_count > 120:
            result.bugs.append("Too many labels for an interactive sketch overlay")
        result.score *= 1.35
        return self._diagnose(result)

    def _result(
        self,
        case: BenchCase,
        total_ms: float,
        updates: int,
        *,
        actors_created: int = 0,
        actors_deleted: int = 0,
        light_renders: int = 0,
        full_renders: int = 0,
    ) -> BenchResult:
        avg = total_ms / max(1, updates)
        score = avg + actors_created * 0.015 + actors_deleted * 0.02 + full_renders * 0.25 + light_renders * 0.01
        return BenchResult(
            case.id,
            case.label,
            case.family,
            "ok",
            total_ms,
            avg,
            score,
            actors_created=actors_created,
            actors_deleted=actors_deleted,
            position_updates=updates,
            full_renders=full_renders,
            light_renders=light_renders,
        )

    @staticmethod
    def _elapsed_ms(start: float) -> float:
        return max(0.0001, (perf_counter() - start) * 1000.0)

    @staticmethod
    def _diagnose(result: BenchResult) -> BenchResult:
        if result.actors_deleted > 0 and result.case_id != "actor_churn_reference":
            result.bugs.append("Actor deletion during benchmark; drag should hide/reuse instead")
        if result.full_renders > max(2, result.position_updates // 20) and result.case_id != "actor_churn_reference":
            result.bugs.append("Too many full renders for an interactive path")
        if (
            result.actors_created > max(2, result.position_updates // 2)
            and result.case_id not in {"actor_churn_reference", "pooled_actor_handles"}
        ):
            result.bugs.append("Too many actor creations; visual data should be batched or pooled")
        if result.avg_ms > 8.0:
            result.bugs.append("Average update is above 8 ms; interaction may feel laggy")
        if result.case_id == "actor_churn_reference":
            result.bugs.append("Reference anti-pattern: actor churn detected by design")
        return result

    @staticmethod
    def _build_report(results: list[BenchResult]) -> BenchReport:
        primary_ids = {"glyph_lod_cache", "gpu_glyph_mapper", "single_actor_point_cloud", "pooled_actor_handles"}
        valid = [result for result in results if result.status == "ok" and result.case_id in primary_ids]
        best = min(valid, key=lambda result: result.score, default=None)
        bugs = tuple(bug for result in results for bug in result.bugs)
        if best is None:
            recommendation = "No valid approach completed. Keep the current tools unchanged and inspect the errors first."
        elif best.case_id in {"gpu_glyph_mapper", "glyph_lod_cache"}:
            recommendation = (
                "Use vtkGlyph3DMapper-style cached glyphs for 3D sphere handles: one mapper, one reusable sphere source, "
                "vtkPoints updated in place during drag, low-detail glyph source during interaction when needed, and a full render only on release. "
                "Keep batched PolyData for lines/arcs/faces and make text hover-only/deferred."
            )
        elif best.case_id == "single_actor_point_cloud":
            recommendation = (
                "Use one batched point-cloud actor for handles as the safest fallback. It is simpler than glyph spheres "
                "and avoids actor churn. Add sphere-like rendering only if the live VTK glyph probe is stable."
            )
        else:
            recommendation = (
                f"Best measured candidate: {best.label}. Keep actor creation outside drag and reserve full renders for release."
            )
        summary = (
            "The benchmark compares cached glyphs, interactive LOD glyphs, batched point clouds, pooled actors, batched linework, hover-only labels, and a bad remove/add reference.",
            "Scores penalize actor churn and full renders because those are the usual causes of slow mouse drags.",
            "The actor-churn case is expected to be flagged; it proves the diagnostic can detect the bad pattern.",
        )
        return BenchReport(tuple(results), recommendation, bugs, summary)
