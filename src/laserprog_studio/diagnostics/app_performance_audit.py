
# -*- coding: utf-8 -*-
"""Global application performance audit.

The normal ToolProfiler is scoped to a ToolContext.  This module aggregates a
single application-wide timeline so a user can reproduce sluggish interactions
and send back one file: ``diagnostics/application_performance_audit.md``.
"""
from __future__ import annotations

import atexit
import json
import os
import platform
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Iterator


def _debug_enabled() -> bool:
    try:
        from laserprog_studio.services.debug_mode import is_debug_mode_enabled
        return bool(is_debug_mode_enabled())
    except Exception:
        return False



@dataclass(slots=True)
class AuditTimer:
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    last_ms: float = 0.0
    samples_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=4096))

    def add(self, elapsed_ms: float, *, max_samples: int = 4096) -> None:
        value = float(elapsed_ms)
        self.count += 1
        self.total_ms += value
        self.last_ms = value
        self.min_ms = value if self.count == 1 else min(self.min_ms, value)
        self.max_ms = max(self.max_ms, value)
        # Keep a bounded rolling sample without list slicing.  The previous list
        # implementation deleted one element on every hot mouse-move/event sample
        # once the cap was reached, which itself could become a hidden UI cost
        # during long sessions.  deque(maxlen=...) keeps percentile samples cheap.
        if getattr(self.samples_ms, "maxlen", None) != int(max_samples):
            self.samples_ms = deque(self.samples_ms, maxlen=int(max_samples))
        self.samples_ms.append(value)

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    def percentile_ms(self, percentile: float) -> float:
        if not self.samples_ms:
            return 0.0
        ordered = sorted(self.samples_ms)
        if len(ordered) == 1:
            return float(ordered[0])
        p = max(0.0, min(100.0, float(percentile)))
        index = int(round((p / 100.0) * (len(ordered) - 1)))
        return float(ordered[index])

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "total_ms": round(self.total_ms, 4),
            "avg_ms": round(self.avg_ms, 4),
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "last_ms": round(self.last_ms, 4),
            "p50_ms": round(self.percentile_ms(50.0), 4),
            "p90_ms": round(self.percentile_ms(90.0), 4),
            "p95_ms": round(self.percentile_ms(95.0), 4),
            "p99_ms": round(self.percentile_ms(99.0), 4),
        }


class AppPerformanceAudit:
    """Thread-safe application-wide profiler, active only in Debug Mode."""

    def __init__(self, *, slow_threshold_ms: float = 16.0, max_slow_events: int = 800, max_timeline_events: int = 1200) -> None:
        self.started_at = time.time()
        self.slow_threshold_ms = float(slow_threshold_ms)
        self.max_slow_events = int(max_slow_events)
        self.max_timeline_events = int(max_timeline_events)
        self._lock = threading.RLock()
        self.timers: dict[str, AuditTimer] = {}
        self.counters: dict[str, int] = {}
        self.values: dict[str, float | int | str | bool | None] = {}
        self.slow_events: Deque[dict[str, Any]] = deque(maxlen=int(max_slow_events))
        self.timeline: Deque[dict[str, Any]] = deque(maxlen=int(max_timeline_events))
        self._last_export_path: str | None = None

    @contextmanager
    def measure(self, name: str, **details: Any) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record_timing(name, (time.perf_counter() - start) * 1000.0, details=details or None)

    @property
    def enabled(self) -> bool:
        return _debug_enabled()

    def record_timing(self, name: str, elapsed_ms: float, *, details: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        key = str(name)
        value = float(elapsed_ms)
        now = time.time()
        with self._lock:
            self.timers.setdefault(key, AuditTimer()).add(value)
            event = {
                "at_s": round(now - self.started_at, 3),
                "name": key,
                "elapsed_ms": round(value, 4),
            }
            if details:
                event["details"] = _safe_json(details)
            # Keep the timeline useful without making it the bottleneck.  Hot
            # sub-frame events update their aggregate timer every time, but the
            # human-readable timeline only keeps slow samples plus occasional
            # breadcrumbs.
            timer_count = self.timers[key].count
            keep_timeline = value >= self.slow_threshold_ms or timer_count <= 3 or (timer_count % 64 == 0)
            if keep_timeline:
                self.timeline.append(event)
            if value >= self.slow_threshold_ms:
                self.slow_events.append(event)

    def increment(self, name: str, value: int = 1) -> None:
        if not self.enabled:
            return
        with self._lock:
            self.counters[str(name)] = int(self.counters.get(str(name), 0)) + int(value)

    def set_value(self, name: str, value: float | int | str | bool | None) -> None:
        if not self.enabled:
            return
        with self._lock:
            self.values[str(name)] = _safe_scalar(value)

    def max_value(self, name: str, value: float | int) -> None:
        if not self.enabled:
            return
        key = str(name)
        numeric = float(value)
        with self._lock:
            current = self.values.get(key)
            if not isinstance(current, (int, float)) or numeric > float(current):
                self.values[key] = numeric

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            timers = {name: timer.as_dict() for name, timer in sorted(self.timers.items())}
            return {
                "metadata": self._metadata(),
                "timers": timers,
                "counters": dict(sorted(self.counters.items())),
                "values": dict(sorted(self.values.items())),
                "slow_events": list(self.slow_events),
                "timeline_tail": list(self.timeline),
                "top_total_ms": _top_timers(timers, "total_ms", 60),
                "top_p95_ms": _top_timers(timers, "p95_ms", 60),
                "top_count": _top_timers(timers, "count", 60),
            }

    def reset(self) -> None:
        with self._lock:
            self.started_at = time.time()
            self.timers.clear()
            self.counters.clear()
            self.values.clear()
            self.slow_events.clear()
            self.timeline.clear()

    def export_markdown(self, output_path: str | Path | None = None, *, reason: str = "manual") -> Path:
        output = Path(output_path) if output_path is not None else Path.cwd() / "diagnostics" / "application_performance_audit.md"
        output.parent.mkdir(parents=True, exist_ok=True)
        snapshot = self.snapshot()
        if not self.enabled and not (snapshot.get("timers") or snapshot.get("counters") or snapshot.get("values")):
            output.write_text(_disabled_markdown(reason=reason), encoding="utf-8")
        else:
            output.write_text(_markdown(snapshot, reason=reason), encoding="utf-8")
        with self._lock:
            self._last_export_path = str(output)
        return output

    def _metadata(self) -> dict[str, Any]:
        return {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "elapsed_session_s": round(time.time() - self.started_at, 3),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "process_id": os.getpid(),
            "cwd": str(Path.cwd()),
            "slow_threshold_ms": self.slow_threshold_ms,
            "last_export_path": self._last_export_path,
        }


def _safe_scalar(value: Any) -> float | int | str | bool | None:
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def _safe_json(value: Any) -> Any:
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return str(value)


def _top_timers(timers: dict[str, dict[str, Any]], key: str, limit: int) -> list[dict[str, Any]]:
    rows = []
    for name, data in timers.items():
        row = {"name": name}
        row.update(data)
        rows.append(row)
    rows.sort(key=lambda row: float(row.get(key, 0.0) or 0.0), reverse=True)
    return rows[: int(limit)]


def _table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    if not rows:
        return ["_No data yet._", ""]
    lines = []
    lines.append("| " + " | ".join(label for _key, label in columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        cells = []
        for key, _label in columns:
            value = row.get(key, "")
            if isinstance(value, float):
                cells.append(f"{value:.3f}")
            else:
                cells.append(str(value).replace("\n", " ")[:180])
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def _disabled_markdown(*, reason: str) -> str:
    return "\n".join([
        "# LaserProg Studio — application performance audit",
        "",
        f"Reason: `{reason}`",
        "",
        "Debug Mode is OFF. Application-wide timing samples, counters and JSONL diagnostics are disabled in normal optimized mode.",
        "Enable View > Performance / Debug > Debug diagnostics mode before reproducing a performance issue.",
        "",
    ])


def _markdown(snapshot: dict[str, Any], *, reason: str) -> str:
    metadata = snapshot.get("metadata", {})
    timers = snapshot.get("timers", {})
    counters = snapshot.get("counters", {})
    values = snapshot.get("values", {})
    slow_events = snapshot.get("slow_events", [])
    timeline = snapshot.get("timeline_tail", [])
    lines: list[str] = []
    lines.append("# LaserProg Studio — application performance audit")
    lines.append("")
    lines.append(f"Reason: `{reason}`")
    lines.append("")
    lines.append("## Session")
    lines.extend(_table([metadata], [
        ("generated_at", "Generated"),
        ("elapsed_session_s", "Elapsed s"),
        ("python", "Python"),
        ("platform", "Platform"),
        ("process_id", "PID"),
        ("slow_threshold_ms", "Slow threshold ms"),
    ]))
    lines.append("## Top timers by total time")
    lines.extend(_table(snapshot.get("top_total_ms", []), _TIMER_COLUMNS))
    lines.append("## Top timers by p95")
    lines.extend(_table(snapshot.get("top_p95_ms", []), _TIMER_COLUMNS))
    lines.append("## Top timers by call count")
    lines.extend(_table(snapshot.get("top_count", []), _TIMER_COLUMNS))
    lines.append("## All timers")
    all_rows = []
    for name, data in sorted(timers.items()):
        row = {"name": name}
        row.update(data)
        all_rows.append(row)
    lines.extend(_table(all_rows, _TIMER_COLUMNS))
    lines.append("## Counters")
    counter_rows = [{"name": name, "value": value} for name, value in counters.items()]
    lines.extend(_table(counter_rows, [("name", "Counter"), ("value", "Value")]))
    lines.append("## Last values / gauges")
    value_rows = [{"name": name, "value": value} for name, value in values.items()]
    lines.extend(_table(value_rows, [("name", "Value"), ("value", "Last")]))
    lines.append("## Slow events")
    lines.extend(_table(list(reversed(slow_events[-200:])), [
        ("at_s", "At s"),
        ("name", "Name"),
        ("elapsed_ms", "Elapsed ms"),
        ("details", "Details"),
    ]))
    lines.append("## Timeline tail")
    lines.extend(_table(list(reversed(timeline[-200:])), [
        ("at_s", "At s"),
        ("name", "Name"),
        ("elapsed_ms", "Elapsed ms"),
        ("details", "Details"),
    ]))
    lines.append("## Raw JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(snapshot, indent=2, sort_keys=True, default=str))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


_TIMER_COLUMNS = [
    ("name", "Timer"),
    ("count", "Count"),
    ("total_ms", "Total ms"),
    ("avg_ms", "Avg ms"),
    ("p50_ms", "P50 ms"),
    ("p95_ms", "P95 ms"),
    ("p99_ms", "P99 ms"),
    ("max_ms", "Max ms"),
    ("last_ms", "Last ms"),
]


GLOBAL_APP_PERFORMANCE_AUDIT = AppPerformanceAudit()


def measure(name: str, **details: Any):
    return GLOBAL_APP_PERFORMANCE_AUDIT.measure(name, **details)


def record_timing(name: str, elapsed_ms: float, *, details: dict[str, Any] | None = None) -> None:
    GLOBAL_APP_PERFORMANCE_AUDIT.record_timing(name, elapsed_ms, details=details)


def increment(name: str, value: int = 1) -> None:
    GLOBAL_APP_PERFORMANCE_AUDIT.increment(name, value)


def set_value(name: str, value: float | int | str | bool | None) -> None:
    GLOBAL_APP_PERFORMANCE_AUDIT.set_value(name, value)


def export_application_performance_audit(output_path: str | Path | None = None, *, reason: str = "manual") -> Path:
    return GLOBAL_APP_PERFORMANCE_AUDIT.export_markdown(output_path, reason=reason)


def _export_at_exit() -> None:
    try:
        if not GLOBAL_APP_PERFORMANCE_AUDIT.enabled:
            return
        if GLOBAL_APP_PERFORMANCE_AUDIT.timers or GLOBAL_APP_PERFORMANCE_AUDIT.counters or GLOBAL_APP_PERFORMANCE_AUDIT.values:
            GLOBAL_APP_PERFORMANCE_AUDIT.export_markdown(reason="process_exit")
    except Exception:
        pass


atexit.register(_export_at_exit)
