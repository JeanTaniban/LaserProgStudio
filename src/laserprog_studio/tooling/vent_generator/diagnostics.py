# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime
import csv
import json
import platform
from pathlib import Path
from typing import Any


def measure_perf(ctx: Any, name: str) -> Any:
    profiler = getattr(ctx, "profiler", None)
    measure = getattr(profiler, "measure", None)
    if callable(measure):
        try:
            return measure(str(name))
        except Exception:
            pass
    return nullcontext()


def increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if callable(increment):
        try:
            increment(str(name), int(value))
        except Exception:
            pass


def set_perf_value(ctx: Any, name: str, value: Any) -> None:
    profiler = getattr(ctx, "profiler", None)
    setter = getattr(profiler, "set_value", None)
    if callable(setter):
        try:
            setter(str(name), value)
        except Exception:
            pass


def profiler_snapshot(ctx: Any) -> dict[str, Any]:
    profiler = getattr(ctx, "profiler", None)
    snapshot = getattr(profiler, "snapshot", None)
    if callable(snapshot):
        try:
            return dict(snapshot())
        except Exception:
            return {}
    return {}


def profiler_detailed(ctx: Any) -> dict[str, Any]:
    profiler = getattr(ctx, "profiler", None)
    detailed = getattr(profiler, "snapshot_detailed", None)
    if callable(detailed):
        try:
            return dict(detailed())
        except Exception:
            return {}
    return {}


def vent_perf_summary_text(ctx: Any) -> str:
    snapshot = profiler_snapshot(ctx)
    if not snapshot:
        return "No timing samples yet."
    keys = (
        ("move", "vent.event.mouse_move.total.avg_ms"),
        ("p95", "vent.event.mouse_move.total.p95_ms"),
        ("resolve", "vent.pointer.resolve.avg_ms"),
        ("snap", "vent.pointer.smart_snap.avg_ms"),
        ("sync", "vent.visual.sync.avg_ms"),
        ("render", "vent.visual.render.avg_ms"),
        ("apply", "vent.apply.total.avg_ms"),
    )
    parts: list[str] = []
    for label, key in keys:
        value = snapshot.get(key)
        if isinstance(value, (int, float)) and float(value) > 0.0:
            parts.append(f"{label} {float(value):.2f} ms")
    moves = snapshot.get("vent.event.mouse_move")
    if isinstance(moves, (int, float)) and int(moves) > 0:
        parts.append(f"moves {int(moves)}")
    return " · ".join(parts) if parts else "Timing enabled; move the cursor to collect samples."


def _scene_cache_summary(ctx: Any) -> dict[str, Any]:
    try:
        summary = ctx.scene_cache.summary()
        return {
            "version": int(getattr(summary, "version", 0)),
            "valid": bool(getattr(summary, "valid", False)),
            "scope": str(getattr(summary, "scope", "")),
            "points": int(getattr(summary, "points", 0)),
            "segments": int(getattr(summary, "segments", 0)),
            "bounds": int(getattr(summary, "bounds", 0)),
            "extra_targets": int(getattr(summary, "extra_targets", 0)),
            "tool_points": int(getattr(summary, "tool_points", 0)),
            "tool_segments": int(getattr(summary, "tool_segments", 0)),
            "ui_targets": int(getattr(summary, "ui_targets", 0)),
        }
    except Exception:
        return {}


def vent_diagnostic_context(ctx: Any, payload: Any, *, reason: str) -> dict[str, Any]:
    owner = getattr(ctx, "owner", None)
    state = getattr(owner, "planar_tool_state", None) if owner is not None else None
    waypoints = tuple(getattr(payload, "waypoints", ()) or ()) if payload is not None else ()
    selected = getattr(payload, "selected_index", None) if payload is not None else None
    try:
        selected = int(selected) if selected is not None else None
    except Exception:
        selected = None
    mode = str(getattr(getattr(payload, "mode", None), "value", getattr(payload, "mode", "?"))) if payload is not None else "?"
    return {
        "reason": str(reason),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "mode": mode,
        "plane_locked": getattr(payload, "plane", None) is not None if payload is not None else False,
        "waypoints": len(waypoints),
        "segments": max(0, len(waypoints) - 1),
        "selected_index": selected,
        "pending_plane_point": getattr(state, "pending_plane_point", None) if state is not None else None,
        "pointer_drag_active": bool(getattr(state, "pointer_drag_active", False)) if state is not None else False,
        "pointer_drag_mode": getattr(state, "pointer_drag_mode", None) if state is not None else None,
        "last_warning": str(getattr(state, "last_edit_warning", "") or "") if state is not None else "",
        "scene_cache": _scene_cache_summary(ctx),
    }


def write_vent_timing_markdown(output_path: Path, detailed: dict[str, Any], snapshot: dict[str, Any], *, reason: str) -> None:
    prefixes = ("vent.", "plan2d.", "snap.", "scene_cache.", "creator.ui.", "document.bind", "render.")
    counters = dict(detailed.get("counters", {}) or {})
    values = dict(detailed.get("values", {}) or {})
    gauges = dict(detailed.get("gauges", {}) or {})
    slow_events = list(detailed.get("slow_events", []) or [])
    context = dict(detailed.get("vent_generator", {}) or {})
    scene_cache = dict(context.get("scene_cache", {}) or {})
    hot = [(name, data) for name, data in counters.items() if any(str(name).startswith(prefix) for prefix in prefixes)]
    hot_by_total = sorted(hot, key=lambda item: float(item[1].get("total_ms", 0.0) or 0.0), reverse=True)[:30]
    hot_by_p95 = sorted(hot, key=lambda item: float(item[1].get("p95_ms", 0.0) or 0.0), reverse=True)[:20]
    lines = [
        "# Vent Generator diagnostic report",
        "",
        f"- reason: {reason}",
        f"- exported_at: {context.get('exported_at', '?')}",
        f"- mode: {context.get('mode', '?')}",
        f"- plane_locked: {context.get('plane_locked', '?')}",
        f"- waypoints: {context.get('waypoints', '?')}",
        f"- segments: {context.get('segments', '?')}",
        f"- selected_index: {context.get('selected_index', None)}",
        f"- pointer_drag_active: {context.get('pointer_drag_active', False)}",
        f"- pointer_drag_mode: {context.get('pointer_drag_mode', None)}",
        "",
        "## Scene cache",
        "",
    ]
    if scene_cache:
        lines.extend(f"- {key}: {value}" for key, value in scene_cache.items())
    else:
        lines.append("- no scene-cache context")
    lines.extend([
        "",
        "## Most expensive counters by total time",
        "",
        "| counter | count | total ms | avg ms | p95 ms | max ms |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    if hot_by_total:
        for name, data in hot_by_total:
            lines.append(
                f"| `{name}` | {int(data.get('count', 0) or 0)} | "
                f"{float(data.get('total_ms', 0.0) or 0.0):.3f} | "
                f"{float(data.get('avg_ms', 0.0) or 0.0):.3f} | "
                f"{float(data.get('p95_ms', 0.0) or 0.0):.3f} | "
                f"{float(data.get('max_ms', 0.0) or 0.0):.3f} |"
            )
    else:
        lines.append("| no samples | 0 | 0 | 0 | 0 | 0 |")
    lines.extend(["", "## Worst jitter by p95", "", "| counter | count | p95 ms | max ms | last ms |", "|---|---:|---:|---:|---:|"])
    if hot_by_p95:
        for name, data in hot_by_p95:
            lines.append(
                f"| `{name}` | {int(data.get('count', 0) or 0)} | "
                f"{float(data.get('p95_ms', 0.0) or 0.0):.3f} | "
                f"{float(data.get('max_ms', 0.0) or 0.0):.3f} | "
                f"{float(data.get('last_ms', 0.0) or 0.0):.3f} |"
            )
    else:
        lines.append("| no samples | 0 | 0 | 0 | 0 |")
    lines.extend(["", "## Slow events", ""])
    filtered_slow = [event for event in slow_events if any(str(event.get("name", "")).startswith(prefix) for prefix in prefixes)]
    if filtered_slow:
        for event in filtered_slow[-40:]:
            lines.append(f"- `{event.get('name')}`: {float(event.get('elapsed_ms', 0.0) or 0.0):.3f} ms at +{event.get('at_s', '?')} s")
    else:
        lines.append("- no slow event above profiler threshold")
    lines.extend(["", "## Values and gauges", ""])
    raw_keys = sorted(key for key in {**values, **gauges, **snapshot} if any(str(key).startswith(prefix) for prefix in prefixes))
    if raw_keys:
        for key in raw_keys:
            if key in values:
                value = values[key]
            elif key in gauges:
                value = gauges[key]
            else:
                value = snapshot[key]
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- no values")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_vent_timing_csv(output_path: Path, detailed: dict[str, Any]) -> None:
    counters = dict(detailed.get("counters", {}) or {})
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["counter", "count", "total_ms", "avg_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms", "last_ms"])
        for name, data in sorted(counters.items(), key=lambda item: float(item[1].get("total_ms", 0.0) or 0.0), reverse=True):
            writer.writerow([
                name,
                int(data.get("count", 0) or 0),
                float(data.get("total_ms", 0.0) or 0.0),
                float(data.get("avg_ms", 0.0) or 0.0),
                float(data.get("p50_ms", 0.0) or 0.0),
                float(data.get("p95_ms", 0.0) or 0.0),
                float(data.get("p99_ms", 0.0) or 0.0),
                float(data.get("max_ms", 0.0) or 0.0),
                float(data.get("last_ms", 0.0) or 0.0),
            ])


def export_vent_timings(ctx: Any, payload: Any, *, reason: str = "manual") -> Path | None:
    try:
        output_dir = Path.cwd() / "diagnostics"
        output_dir.mkdir(parents=True, exist_ok=True)
        base = output_dir / "vent_generator_timings"
        detailed = profiler_detailed(ctx)
        snapshot = profiler_snapshot(ctx)
        detailed.setdefault("vent_generator", {})
        detailed["vent_generator"].update(vent_diagnostic_context(ctx, payload, reason=reason))
        markdown = base.with_suffix(".md")
        json_path = base.with_suffix(".json")
        csv_path = base.with_suffix(".csv")
        write_vent_timing_markdown(markdown, detailed, snapshot, reason=reason)
        json_path.write_text(json.dumps(detailed, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        write_vent_timing_csv(csv_path, detailed)
        try:
            ctx.status.info(f"Vent Generator diagnostics exported: {markdown} + JSON/CSV")
        except Exception:
            pass
        return markdown
    except Exception as exc:
        try:
            ctx.status.info(f"Vent Generator timing export failed: {exc}")
        except Exception:
            pass
        return None


__all__ = [
    "export_vent_timings",
    "increment_perf",
    "measure_perf",
    "profiler_detailed",
    "profiler_snapshot",
    "set_perf_value",
    "vent_perf_summary_text",
]
