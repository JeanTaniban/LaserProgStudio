# -*- coding: utf-8 -*-
"""Buffered performance diagnostics for the smart-surface selection test tool.

The recorder deliberately keeps mouse-move samples in memory.  Disk writes only
happen when the user exports, closes the test tool, or the bounded buffer is
explicitly flushed.  This prevents the diagnostic itself from becoming the
main source of viewport stutter.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from typing import Any, Callable, Iterable

_DIAG_STEM = "smart_surface_selection_performance"
_MAX_EVENTS = int(os.environ.get("LASERPROG_SURFACE_SELECTION_DIAG_MAX", "12000") or "12000")


def _diagnostics_dir() -> Path:
    path = Path.cwd() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def diagnostics_paths() -> tuple[Path, Path, Path]:
    root = _diagnostics_dir()
    return (
        root / f"{_DIAG_STEM}.jsonl",
        root / f"{_DIAG_STEM}.json",
        root / f"{_DIAG_STEM}.md",
    )


def _safe(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            return repr(value)
        return value
    if depth >= 4:
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _safe(item, depth=depth + 1) for key, item in list(value.items())[:120]}
    if isinstance(value, (tuple, list, set, frozenset, deque)):
        return [_safe(item, depth=depth + 1) for item in list(value)[:160]]
    try:
        return int(value)
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        pass
    return repr(value)


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    index = int(round(max(0.0, min(100.0, float(percentile))) / 100.0 * (len(ordered) - 1)))
    return ordered[index]


@dataclass(slots=True)
class DiagnosticOperation:
    recorder: "SurfaceSelectionPerformanceRecorder"
    operation_id: int
    kind: str
    started: float
    context: dict[str, Any] = field(default_factory=dict)
    closed: bool = False

    def sink(self, stage: str, payload: dict[str, Any] | None = None, **extra: Any) -> None:
        merged = dict(payload or {})
        merged.update(extra)
        self.recorder.record(self.operation_id, self.kind, stage, **merged)

    def finish(self, *, outcome: str = "ok", **payload: Any) -> float:
        if self.closed:
            return 0.0
        self.closed = True
        elapsed_ms = (time.perf_counter() - self.started) * 1000.0
        self.recorder.record(
            self.operation_id,
            self.kind,
            "operation.end",
            elapsed_ms=elapsed_ms,
            outcome=outcome,
            **payload,
        )
        return elapsed_ms


@dataclass(slots=True)
class SurfaceSelectionPerformanceRecorder:
    enabled: bool = True
    max_events: int = _MAX_EVENTS
    events: deque[dict[str, Any]] = field(default_factory=deque)
    started_perf: float = field(default_factory=time.perf_counter)
    started_wall: float = field(default_factory=time.time)
    sequence: int = 0
    operation_sequence: int = 0
    dropped_events: int = 0
    exports: int = 0

    def reset(self, *, reason: str = "manual") -> None:
        self.events.clear()
        self.started_perf = time.perf_counter()
        self.started_wall = time.time()
        self.sequence = 0
        self.operation_sequence = 0
        self.dropped_events = 0
        self.record(
            0,
            "session",
            "session.start",
            reason=str(reason),
            python=sys.version.split()[0],
            platform=platform.platform(),
            process_id=os.getpid(),
            max_events=self.max_events,
        )

    def begin(self, kind: str, **context: Any) -> DiagnosticOperation:
        self.operation_sequence += 1
        operation = DiagnosticOperation(self, self.operation_sequence, str(kind), time.perf_counter(), dict(context))
        self.record(operation.operation_id, operation.kind, "operation.start", **context)
        return operation

    def record(self, operation_id: int, kind: str, stage: str, **payload: Any) -> None:
        if not self.enabled:
            return
        self.sequence += 1
        entry = {
            "seq": self.sequence,
            "at_ms": round((time.perf_counter() - self.started_perf) * 1000.0, 4),
            "operation_id": int(operation_id),
            "kind": str(kind),
            "stage": str(stage),
        }
        entry.update({str(key): _safe(value) for key, value in payload.items()})
        if len(self.events) >= self.max_events:
            self.events.popleft()
            self.dropped_events += 1
        self.events.append(entry)

    def core_sink(self, operation: DiagnosticOperation) -> Callable[[str, dict[str, Any]], None]:
        def sink(stage: str, payload: dict[str, Any]) -> None:
            operation.sink(f"core.{stage}", payload)

        return sink

    def summary(self) -> dict[str, Any]:
        stage_values: dict[str, list[float]] = defaultdict(list)
        operation_values: dict[str, list[float]] = defaultdict(list)
        cache_hits = 0
        cache_misses = 0
        reused_hover = 0
        skipped_same_face = 0
        auto_cache_exact = 0
        auto_cache_logical = 0
        auto_cache_misses = 0
        auto_field_hits = 0
        auto_field_misses = 0
        incremental_auto_solves = 0
        legacy_auto_solves = 0
        meshes: dict[str, dict[str, Any]] = {}
        slow_operations: list[dict[str, Any]] = []
        for entry in self.events:
            elapsed = entry.get("elapsed_ms")
            if isinstance(elapsed, (int, float)):
                stage_values[str(entry.get("stage"))].append(float(elapsed))
                if entry.get("stage") == "operation.end":
                    operation_values[str(entry.get("kind"))].append(float(elapsed))
                    slow_operations.append(entry)
            stage = str(entry.get("stage"))
            if stage == "snapshot.cache":
                cache_hits += int(bool(entry.get("hit")))
                cache_misses += int(not bool(entry.get("hit")))
            elif stage == "click.selection":
                reused_hover += int(bool(entry.get("reused_hover")))
            elif stage == "hover.skip":
                skipped_same_face += 1
            elif stage == "core.auto.solve":
                cache_kind = str(entry.get("cache_kind", "miss") or "miss")
                if cache_kind == "exact":
                    auto_cache_exact += 1
                elif cache_kind == "logical":
                    auto_cache_logical += 1
                else:
                    auto_cache_misses += 1
                if bool(entry.get("field_cache_hit")):
                    auto_field_hits += 1
                elif bool(entry.get("incremental")):
                    auto_field_misses += 1
                if bool(entry.get("incremental")):
                    incremental_auto_solves += 1
                else:
                    legacy_auto_solves += 1
            object_id = entry.get("object_id")
            if object_id is not None and any(key in entry for key in ("mesh_faces", "mesh_vertices")):
                meshes[str(object_id)] = {
                    "name": entry.get("object_name", ""),
                    "faces": entry.get("mesh_faces", 0),
                    "vertices": entry.get("mesh_vertices", 0),
                    "revision": entry.get("revision", ""),
                }

        def stats(values: list[float]) -> dict[str, Any]:
            if not values:
                return {"count": 0, "avg_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
            return {
                "count": len(values),
                "avg_ms": statistics.fmean(values),
                "p50_ms": _percentile(values, 50.0),
                "p95_ms": _percentile(values, 95.0),
                "max_ms": max(values),
            }

        slow_operations.sort(key=lambda entry: float(entry.get("elapsed_ms", 0.0)), reverse=True)
        return {
            "schema_version": 2,
            "session": {
                "started_unix": self.started_wall,
                "elapsed_s": time.perf_counter() - self.started_perf,
                "event_count": len(self.events),
                "dropped_events": self.dropped_events,
                "exports": self.exports,
            },
            "operations": {name: stats(values) for name, values in sorted(operation_values.items())},
            "stages": {name: stats(values) for name, values in sorted(stage_values.items())},
            "cache": {"hits": cache_hits, "misses": cache_misses},
            "interaction": {"hover_results_reused_on_click": reused_hover, "same_face_hover_skips": skipped_same_face},
            "selection_cache": {
                "auto_exact_hits": auto_cache_exact,
                "auto_logical_hits": auto_cache_logical,
                "auto_misses": auto_cache_misses,
                "field_hits": auto_field_hits,
                "field_misses": auto_field_misses,
                "incremental_auto_solves": incremental_auto_solves,
                "legacy_auto_solves": legacy_auto_solves,
            },
            "meshes": meshes,
            "slowest_operations": slow_operations[:30],
        }

    def export(self, *, reason: str = "manual") -> tuple[Path, Path, Path]:
        if not self.enabled:
            return diagnostics_paths()
        self.record(0, "session", "session.export", reason=str(reason), buffered_events=len(self.events))
        self.exports += 1
        jsonl_path, json_path, markdown_path = diagnostics_paths()
        payload = self.summary()
        try:
            jsonl_path.write_text(
                "".join(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n" for entry in self.events),
                encoding="utf-8",
            )
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            markdown_path.write_text(self._markdown(payload, reason=reason), encoding="utf-8")
        except Exception:
            pass
        return jsonl_path, json_path, markdown_path

    @staticmethod
    def _markdown(payload: dict[str, Any], *, reason: str) -> str:
        session = payload.get("session", {})
        operations = payload.get("operations", {})
        stages = payload.get("stages", {})
        cache = payload.get("cache", {})
        interaction = payload.get("interaction", {})
        selection_cache = payload.get("selection_cache", {})
        lines = [
            "# Smart Surface Selection performance diagnostics",
            "",
            f"- Export reason: `{reason}`",
            f"- Captured events: **{session.get('event_count', 0)}**",
            f"- Dropped events: **{session.get('dropped_events', 0)}**",
            f"- Session duration: **{float(session.get('elapsed_s', 0.0)):.2f} s**",
            f"- Snapshot cache: **{cache.get('hits', 0)} hit(s)** / **{cache.get('misses', 0)} miss(es)**",
            f"- Hover result reused on click: **{interaction.get('hover_results_reused_on_click', 0)}**",
            (
                "- Auto cache: "
                f"**{selection_cache.get('auto_exact_hits', 0)} exact** / "
                f"**{selection_cache.get('auto_logical_hits', 0)} logical** / "
                f"**{selection_cache.get('auto_misses', 0)} miss(es)**"
            ),
            (
                "- Accessibility fields: "
                f"**{selection_cache.get('field_hits', 0)} hit(s)** / "
                f"**{selection_cache.get('field_misses', 0)} miss(es)**"
            ),
            "",
            "## End-to-end operations",
            "",
            "| Operation | Count | Average | P95 | Maximum |",
            "|---|---:|---:|---:|---:|",
        ]
        for name, stats in sorted(operations.items()):
            lines.append(
                f"| `{name}` | {stats.get('count', 0)} | {float(stats.get('avg_ms', 0.0)):.2f} ms | "
                f"{float(stats.get('p95_ms', 0.0)):.2f} ms | {float(stats.get('max_ms', 0.0)):.2f} ms |"
            )
        lines.extend([
            "",
            "## Slow stages",
            "",
            "| Stage | Count | Average | P95 | Maximum |",
            "|---|---:|---:|---:|---:|",
        ])
        ordered_stages = sorted(stages.items(), key=lambda item: float(item[1].get("max_ms", 0.0)), reverse=True)
        for name, stats in ordered_stages[:35]:
            lines.append(
                f"| `{name}` | {stats.get('count', 0)} | {float(stats.get('avg_ms', 0.0)):.2f} ms | "
                f"{float(stats.get('p95_ms', 0.0)):.2f} ms | {float(stats.get('max_ms', 0.0)):.2f} ms |"
            )
        lines.extend([
            "",
            "## Slowest operations",
            "",
            "```json",
            json.dumps(payload.get("slowest_operations", [])[:15], ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Files to send",
            "",
            "- `diagnostics/smart_surface_selection_performance.jsonl`",
            "- `diagnostics/smart_surface_selection_performance.json`",
            "- `diagnostics/smart_surface_selection_performance.md`",
            "- the normal LaserProg application log from the same run",
            "",
        ])
        return "\n".join(lines)


__all__ = [
    "DiagnosticOperation",
    "SurfaceSelectionPerformanceRecorder",
    "diagnostics_paths",
]
