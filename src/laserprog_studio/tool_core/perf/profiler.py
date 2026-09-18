"""Lightweight counters for viewport tool performance diagnostics."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


def _debug_enabled() -> bool:
    try:
        from laserprog_studio.services.debug_mode import is_debug_mode_enabled
        return bool(is_debug_mode_enabled())
    except Exception:
        return False


def _global_audit():
    if not _debug_enabled():
        return None
    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT
        return GLOBAL_APP_PERFORMANCE_AUDIT
    except Exception:
        return None


@dataclass(slots=True)
class PerfCounter:
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    min_ms: float = 0.0
    last_ms: float = 0.0
    samples_ms: list[float] = field(default_factory=list)

    def add(self, elapsed_ms: float) -> None:
        value = float(elapsed_ms)
        self.count += 1
        self.total_ms += value
        self.last_ms = value
        self.max_ms = max(self.max_ms, value)
        self.min_ms = value if self.count == 1 else min(self.min_ms, value)
        # Keep a bounded reservoir of the most recent samples.  It is intentionally
        # simple and deterministic because these counters run inside mouse-move
        # loops; p95/p99 are approximate but good enough to identify jitter.
        self.samples_ms.append(value)
        if len(self.samples_ms) > 256:
            del self.samples_ms[: len(self.samples_ms) - 256]

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    def percentile_ms(self, percentile: float) -> float:
        if not self.samples_ms:
            return 0.0
        ordered = sorted(self.samples_ms)
        if len(ordered) == 1:
            return ordered[0]
        clamped = max(0.0, min(float(percentile), 100.0))
        index = int(round((clamped / 100.0) * (len(ordered) - 1)))
        return float(ordered[index])

    def as_dict(self) -> dict[str, float | int]:
        return {
            "count": self.count,
            "total_ms": self.total_ms,
            "avg_ms": self.avg_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "last_ms": self.last_ms,
            "p50_ms": self.percentile_ms(50.0),
            "p95_ms": self.percentile_ms(95.0),
            "p99_ms": self.percentile_ms(99.0),
        }


@dataclass(slots=True)
class ToolProfiler:
    counters: dict[str, PerfCounter] = field(default_factory=dict)
    values: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float | int | str] = field(default_factory=dict)
    slow_events: list[dict[str, Any]] = field(default_factory=list)
    slow_threshold_ms: float = 8.0
    max_slow_events: int = 80
    started_at: float = field(default_factory=time.time)

    @property
    def enabled(self) -> bool:
        return _debug_enabled()

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            self.record_timing(name, elapsed)

    def record_timing(self, name: str, elapsed_ms: float, *, details: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        key = str(name)
        value = float(elapsed_ms)
        self.counters.setdefault(key, PerfCounter()).add(value)
        audit = _global_audit()
        if audit is not None:
            try:
                audit.record_timing(f"toolctx.{key}", value, details=details)
            except Exception:
                pass
        if value >= float(self.slow_threshold_ms):
            event = {
                "name": key,
                "elapsed_ms": value,
                "at_s": round(time.time() - self.started_at, 3),
            }
            if details:
                event["details"] = dict(details)
            self.slow_events.append(event)
            if len(self.slow_events) > int(self.max_slow_events):
                del self.slow_events[: len(self.slow_events) - int(self.max_slow_events)]

    def increment(self, name: str, value: int = 1) -> None:
        if not self.enabled:
            return
        key = str(name)
        self.values[key] = self.values.get(key, 0) + int(value)
        audit = _global_audit()
        if audit is not None:
            try:
                audit.increment(f"toolctx.{key}", int(value))
            except Exception:
                pass

    def set_value(self, name: str, value: float | int | str) -> None:
        if not self.enabled:
            return
        key = str(name)
        self.gauges[key] = value
        audit = _global_audit()
        if audit is not None:
            try:
                audit.set_value(f"toolctx.{key}", value)
            except Exception:
                pass

    def max_value(self, name: str, value: float | int) -> None:
        if not self.enabled:
            return
        key = str(name)
        numeric = float(value)
        current = self.gauges.get(key)
        if not isinstance(current, (int, float)) or numeric > float(current):
            self.gauges[key] = numeric
            audit = _global_audit()
            if audit is not None:
                try:
                    audit.max_value(f"toolctx.{key}", numeric)
                except Exception:
                    pass

    def snapshot(self) -> dict[str, float | int | str]:
        data: dict[str, float | int | str] = dict(self.values)
        data.update(self.gauges)
        for name, counter in self.counters.items():
            data[f"{name}.count"] = counter.count
            data[f"{name}.avg_ms"] = counter.avg_ms
            data[f"{name}.max_ms"] = counter.max_ms
            data[f"{name}.last_ms"] = counter.last_ms
            data[f"{name}.p95_ms"] = counter.percentile_ms(95.0)
        return data

    def snapshot_detailed(self) -> dict[str, Any]:
        return {
            "elapsed_session_s": round(time.time() - self.started_at, 3),
            "values": dict(sorted(self.values.items())),
            "gauges": dict(sorted(self.gauges.items())),
            "counters": {name: counter.as_dict() for name, counter in sorted(self.counters.items())},
            "slow_events": list(self.slow_events),
        }

    def reset(self) -> None:
        self.counters.clear()
        self.values.clear()
        self.gauges.clear()
        self.slow_events.clear()
        self.started_at = time.time()

    def to_json(self) -> str:
        return json.dumps(self.snapshot_detailed(), indent=2, sort_keys=True, default=str)
