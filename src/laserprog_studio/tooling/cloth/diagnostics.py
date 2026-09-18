# -*- coding: utf-8 -*-
"""Buffered, preference-gated diagnostics for the Cloth workflow.

No recorder is created during normal optimized use. When Debug diagnostics is
explicitly enabled in Preferences, high-level interaction, picking, Close
analysis, overlay synchronization and renderer stages are buffered and exported
as JSONL, JSON and Markdown. There are no hot-path disk writes.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import time
import traceback
from typing import Any, Callable

_STEM = "cloth_workflow_debug"
_MAX_EVENTS = int(os.environ.get("LASERPROG_CLOTH_DIAG_MAX", "12000") or "12000")


def diagnostics_enabled(owner: Any | None = None) -> bool:
    try:
        from laserprog_studio.services.debug_mode import debug_mode_source, should_record_diagnostics
        if not should_record_diagnostics(owner):
            return False
        # Pytest enables the historical diagnostic gate automatically. Cloth
        # diagnostics must follow the user's explicit Preferences setting and
        # therefore stay off for ordinary test runs.
        return debug_mode_source() != "pytest"
    except Exception:
        return False


def _diagnostics_dir() -> Path:
    try:
        from laserprog_studio.bootstrap import compute_paths
        path = compute_paths().diagnostics_dir
    except Exception:
        path = Path.cwd() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def diagnostics_paths() -> tuple[Path, Path, Path]:
    root = _diagnostics_dir()
    return root / f"{_STEM}.jsonl", root / f"{_STEM}.json", root / f"{_STEM}.md"


def _safe(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if depth >= 5:
        return repr(value)
    if isinstance(value, dict):
        return {str(k): _safe(v, depth=depth + 1) for k, v in list(value.items())[:160]}
    if isinstance(value, (list, tuple, set, frozenset, deque)):
        return [_safe(v, depth=depth + 1) for v in list(value)[:240]]
    try:
        return str(value.value)
    except Exception:
        return repr(value)


def _enum(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def overlay_snapshot(ctx: Any | None, window_id: str = "cloth.workflow") -> dict[str, Any]:
    if ctx is None:
        return {"available": False, "reason": "no_context"}
    manager = getattr(ctx, "overlay", None)
    if manager is None:
        return {"available": False, "reason": "no_overlay_manager"}
    try:
        window = manager.window(window_id)
    except Exception as exc:
        return {"available": False, "reason": "window_lookup_failed", "error": repr(exc)}
    if window is None:
        return {"available": True, "present": False, "window_id": window_id}
    buttons = []
    for button in tuple(getattr(window, "buttons", ()) or ()):
        buttons.append({
            "id": str(getattr(button, "id", "") or ""),
            "label": str(getattr(button, "display_label", getattr(button, "label", "")) or ""),
            "enabled": bool(getattr(button, "enabled", False)),
            "style": str(getattr(button, "style", "") or ""),
        })
    return {
        "available": True,
        "present": True,
        "window_id": str(getattr(window, "id", window_id) or window_id),
        "title": str(getattr(window, "title", "") or ""),
        "accent_color": str(getattr(window, "accent_color", "") or ""),
        "persistent": bool(getattr(window, "persistent", False)),
        "buttons": buttons,
    }


def tool_snapshot(tool: Any, ctx: Any | None = None) -> dict[str, Any]:
    workspace = getattr(tool, "_workspace", None)
    interaction = getattr(tool, "_interaction", None)
    session = getattr(tool, "_session", None)
    document = getattr(session, "document", None)
    smart_session = getattr(getattr(tool, "_geometry_trace", None), "smart_session", None)
    groups = tuple(getattr(tool, "_selected_textile_groups", ()) or ())
    proposals = tuple(getattr(interaction, "join_proposals", ()) or ())
    persistent_groups = []
    if document is not None:
        registry = dict(getattr(document, "metadata", {}).get("cloth_textile_groups_v1") or {})
        for group_id, raw in registry.items():
            record = dict(raw or {}) if isinstance(raw, dict) else {}
            persistent_groups.append({
                "group_id": str(group_id),
                "patch_ids": list(record.get("patch_ids") or ()),
                "origin": str(record.get("origin") or ""),
                "parent_group_ids": list(record.get("parent_group_ids") or ()),
            })
    try:
        validation_report = tool._validation_report() if document is not None and getattr(document, "patches", None) else None
    except Exception as exc:
        validation_report = None
        validation_error = repr(exc)
    else:
        validation_error = ""
    try:
        can_apply = bool(tool.can_apply(ctx))
    except Exception as exc:
        can_apply = False
        can_apply_error = repr(exc)
    else:
        can_apply_error = ""
    return {
        "apply": {
            "can_apply": can_apply,
            "can_apply_error": can_apply_error,
            "pending_draw_points": len(getattr(getattr(tool, "_drawing", None), "pending_world_points", ()) or ()),
            "validation_present": validation_report is not None,
            "validation_can_apply": bool(getattr(validation_report, "can_apply", False)) if validation_report is not None else False,
            "validation_errors": [str(getattr(issue, "message", issue)) for issue in tuple(getattr(validation_report, "errors", ()) or ())],
            "validation_warnings": [str(getattr(issue, "message", issue)) for issue in tuple(getattr(validation_report, "warnings", ()) or ())],
            "validation_error": validation_error,
            "source_mesh_id": getattr(session, "source_mesh_id", None),
            "source_flat_scene_id": getattr(interaction, "source_flat_scene_id", None),
            "editing_existing": bool(getattr(session, "editing_existing", False)),
        },
        "workspace": {
            "overlay_mode": _enum(getattr(workspace, "overlay_mode", "")),
            "phase": _enum(getattr(workspace, "phase", "")),
            "can_take_face": bool(getattr(workspace, "can_take_face", False)),
            "can_close": bool(getattr(workspace, "can_close", False)),
            "can_apply_close": bool(getattr(workspace, "can_apply_close", False)),
            "selected_source_regions": int(getattr(workspace, "selected_source_regions", 0) or 0),
            "selected_source_meshes": int(getattr(workspace, "selected_source_meshes", 0) or 0),
            "selected_textile_faces": int(getattr(workspace, "selected_textile_faces", 0) or 0),
            "selected_textile_edges": int(getattr(workspace, "selected_textile_edges", 0) or 0),
            "close_proposal_count": int(getattr(workspace, "close_proposal_count", 0) or 0),
            "close_proposal_index": int(getattr(workspace, "close_proposal_index", 0) or 0),
            "message": str(getattr(workspace, "message", "") or ""),
        },
        "interaction": {
            "stage": _enum(getattr(interaction, "stage", "")),
            "proposal_count": len(proposals),
            "proposal_index": int(getattr(interaction, "join_proposal_index", 0) or 0),
            "hovered_patch_id": getattr(interaction, "hovered_patch_id", None),
            "hovered_patch_group_ids": list(getattr(interaction, "hovered_patch_group_ids", ()) or ()),
        },
        "session": {
            "phase": _enum(getattr(session, "phase", "")),
            "edit_mode": _enum(getattr(session, "edit_mode", "")),
            "selected_patch_ids": list(getattr(session, "selected_patch_ids", ()) or ()),
            "selected_curve_ids": list(getattr(session, "selected_curve_ids", ()) or ()),
            "selected_point_ids": list(getattr(session, "selected_point_ids", ()) or ()),
            "dirty": bool(getattr(session, "dirty", False)),
        },
        "document": {
            "revision": int(getattr(document, "revision", 0) or 0),
            "points": len(getattr(document, "points", {}) or {}),
            "curves": len(getattr(document, "curves", {}) or {}),
            "patches": len(getattr(document, "patches", {}) or {}),
            "layers": len(getattr(document, "layers", {}) or {}),
        },
        "selection": {
            "tracked_textile_groups": [sorted(str(v) for v in group) for group in groups],
            "persistent_textile_groups": persistent_groups,
            "smart_selected_regions": int(getattr(smart_session, "selected_region_count", 0) or 0),
            "smart_selected_meshes": int(getattr(smart_session, "selected_mesh_count", 0) or 0),
        },
        "overlay": overlay_snapshot(ctx),
    }


def close_input_snapshot(tool: Any) -> dict[str, Any]:
    session = getattr(tool, "_session", None)
    document = getattr(session, "document", None)
    groups = tuple(tool._selected_textile_patch_groups()) if hasattr(tool, "_selected_textile_patch_groups") else ()
    group_payload = []
    patches = getattr(document, "patches", {}) or {}
    for index, group in enumerate(groups):
        entries = []
        for patch_id in sorted(group):
            patch = patches.get(patch_id)
            if patch is None:
                entries.append({"patch_id": patch_id, "missing": True})
                continue
            metadata = dict(getattr(patch, "metadata", {}) or {})
            entries.append({
                "patch_id": patch_id,
                "outer_curve_ids": list(getattr(patch, "outer_curve_ids", ()) or ()),
                "hole_curve_loops": [list(loop) for loop in tuple(getattr(patch, "hole_curve_loops", ()) or ())],
                "function": _enum(getattr(patch, "function", "")),
                "layer_id": str(getattr(patch, "layer_id", "") or ""),
                "source_object_id": metadata.get("cloth_source_object_id"),
                "source_faces": metadata.get("cloth_source_faces"),
                "logical_group_id": metadata.get("cloth_logical_group_id") or metadata.get("cloth_creation_group_id"),
                "creation_kind": metadata.get("cloth_creation_kind"),
            })
        group_payload.append({"index": index, "patch_ids": sorted(group), "patches": entries})
    return {
        "groups": group_payload,
        "curve_ids": list(getattr(session, "selected_curve_ids", ()) or ()),
        "anchor_count": len(groups) + len(getattr(session, "selected_curve_ids", ()) or ()),
    }


def proposal_snapshot(proposals: Any) -> list[dict[str, Any]]:
    result = []
    for proposal in tuple(proposals or ()):
        result.append({
            "id": str(getattr(proposal, "id", "") or ""),
            "patch_ids": list(getattr(proposal, "patch_ids", ()) or ()),
            "curve_ids": list(getattr(proposal, "curve_ids", ()) or ()),
            "pair_count": len(getattr(proposal, "pairs", ()) or ()),
            "cap_count": len(getattr(proposal, "caps", ()) or ()),
            "panel_count": int(getattr(proposal, "panel_count", 0) or 0),
            "preview_triangle_count": len(getattr(proposal, "triangle_preview", ()) or ()),
            "confidence": float(getattr(proposal, "confidence", 0.0) or 0.0),
            "score": float(getattr(proposal, "score", 0.0) or 0.0),
            "message": str(getattr(proposal, "message", "") or ""),
            "pairs": [
                {
                    "first_anchor": str(getattr(pair, "first_patch_id", "") or ""),
                    "second_anchor": str(getattr(pair, "second_patch_id", "") or ""),
                    "strategy": str(getattr(pair, "strategy", "") or ""),
                    "segments": int(getattr(pair, "segment_count", 0) or 0),
                    "coverage": float(getattr(pair, "coverage", 0.0) or 0.0),
                    "coverage_first": float(getattr(pair, "coverage_first", 0.0) or 0.0),
                    "coverage_second": float(getattr(pair, "coverage_second", 0.0) or 0.0),
                    "mean_width_mm": float(getattr(pair, "mean_width_mm", 0.0) or 0.0),
                    "max_width_mm": float(getattr(pair, "max_width_mm", 0.0) or 0.0),
                    "twist_score": float(getattr(pair, "twist_score", 0.0) or 0.0),
                }
                for pair in tuple(getattr(proposal, "pairs", ()) or ())
            ],
        })
    return result


@dataclass(slots=True)
class ClothDiagnosticOperation:
    recorder: "ClothWorkflowDiagnostics"
    operation_id: int
    kind: str
    started: float
    closed: bool = False

    def stage(self, name: str, *, tool: Any | None = None, ctx: Any | None = None, **payload: Any) -> None:
        self.recorder.record(f"{self.kind}.{name}", operation_id=self.operation_id, tool=tool, ctx=ctx, **payload)

    def finish(self, *, outcome: str = "ok", tool: Any | None = None, ctx: Any | None = None, **payload: Any) -> float:
        if self.closed:
            return 0.0
        self.closed = True
        elapsed_ms = (time.perf_counter() - self.started) * 1000.0
        self.recorder.record(
            f"{self.kind}.end", operation_id=self.operation_id, tool=tool, ctx=ctx,
            elapsed_ms=elapsed_ms, outcome=outcome, **payload,
        )
        return elapsed_ms


class ClothWorkflowDiagnostics:
    def __init__(self, *, owner: Any | None = None, max_events: int = _MAX_EVENTS) -> None:
        self.owner = owner
        self.enabled = diagnostics_enabled(owner)
        self.max_events = max(100, int(max_events))
        self.events: deque[dict[str, Any]] = deque()
        self.sequence = 0
        self.operation_sequence = 0
        self.dropped_events = 0
        self.started_perf = time.perf_counter()
        self.started_wall = time.time()

    def reset(self, *, reason: str, tool: Any | None = None, ctx: Any | None = None) -> None:
        if not self.enabled:
            return
        self.events.clear()
        self.sequence = 0
        self.operation_sequence = 0
        self.dropped_events = 0
        self.started_perf = time.perf_counter()
        self.started_wall = time.time()
        self.record("session.start", tool=tool, ctx=ctx, reason=reason)

    def begin(self, kind: str, *, tool: Any | None = None, ctx: Any | None = None, **payload: Any) -> ClothDiagnosticOperation | None:
        if not self.enabled:
            return None
        self.operation_sequence += 1
        op = ClothDiagnosticOperation(self, self.operation_sequence, str(kind), time.perf_counter())
        self.record(f"{kind}.start", operation_id=op.operation_id, tool=tool, ctx=ctx, **payload)
        return op

    def record(self, stage: str, *, operation_id: int = 0, tool: Any | None = None, ctx: Any | None = None, **payload: Any) -> None:
        if not self.enabled:
            return
        self.sequence += 1
        entry = {
            "seq": self.sequence,
            "at_ms": round((time.perf_counter() - self.started_perf) * 1000.0, 4),
            "operation_id": int(operation_id),
            "stage": str(stage),
        }
        if tool is not None:
            entry["state"] = tool_snapshot(tool, ctx)
        entry.update({str(k): _safe(v) for k, v in payload.items()})
        if len(self.events) >= self.max_events:
            self.events.popleft()
            self.dropped_events += 1
        self.events.append(entry)

    def exception(self, stage: str, exc: BaseException, *, operation_id: int = 0, tool: Any | None = None, ctx: Any | None = None, **payload: Any) -> None:
        self.record(
            stage, operation_id=operation_id, tool=tool, ctx=ctx,
            error_type=type(exc).__name__, error=repr(exc), traceback="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            **payload,
        )

    def sink(self, operation: ClothDiagnosticOperation | None, prefix: str) -> Callable[[str, dict[str, Any]], None] | None:
        if operation is None:
            return None
        def callback(stage: str, payload: dict[str, Any]) -> None:
            operation.stage(f"{prefix}.{stage}", **dict(payload or {}))
        return callback

    def export(self, *, reason: str, tool: Any | None = None, ctx: Any | None = None) -> tuple[Path, Path, Path] | None:
        if not self.enabled:
            return None
        self.record("session.export", tool=tool, ctx=ctx, reason=reason)
        jsonl_path, json_path, md_path = diagnostics_paths()
        stages = Counter(str(event.get("stage", "")) for event in self.events)
        errors = [event for event in self.events if event.get("error") or event.get("outcome") == "error"]
        close_events = [event for event in self.events if str(event.get("stage", "")).startswith("close.")]
        pick_events = [event for event in self.events if str(event.get("stage", "")).startswith("pick.")]
        apply_events = [event for event in self.events if str(event.get("stage", "")).startswith("apply.")]
        action_events = [event for event in self.events if str(event.get("stage", "")).startswith("action.")]
        payload = {
            "schema_version": 2,
            "session": {
                "started_unix": self.started_wall,
                "elapsed_s": time.perf_counter() - self.started_perf,
                "event_count": len(self.events),
                "dropped_events": self.dropped_events,
                "export_reason": reason,
            },
            "stage_counts": dict(sorted(stages.items())),
            "error_count": len(errors),
            "errors": errors[-30:],
            "latest_state": tool_snapshot(tool, ctx) if tool is not None else {},
            "latest_close_events": close_events[-80:],
            "latest_pick_events": pick_events[-80:],
            "latest_apply_events": apply_events[-120:],
            "latest_action_events": action_events[-60:],
        }
        try:
            jsonl_path.write_text("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in self.events), encoding="utf-8")
            json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            lines = [
                "# Cloth workflow diagnostics", "",
                f"- Export reason: `{reason}`",
                f"- Captured events: **{len(self.events)}**",
                f"- Dropped events: **{self.dropped_events}**",
                f"- Errors captured: **{len(errors)}**", "",
                "## Stage counts", "", "| Stage | Count |", "|---|---:|",
            ]
            lines.extend(f"| `{name}` | {count} |" for name, count in sorted(stages.items()))
            lines.extend(["", "## Latest state", "", "```json", json.dumps(payload["latest_state"], ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
            if apply_events:
                lines.extend([
                    "## Latest Apply events", "", "```json",
                    json.dumps(apply_events[-40:], ensure_ascii=False, indent=2, sort_keys=True),
                    "```", "",
                ])
            if errors:
                lines.extend(["## Errors", "", "```json", json.dumps(errors[-10:], ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
            lines.extend([
                "## Files to send", "",
                "- `diagnostics/cloth_workflow_debug.jsonl`",
                "- `diagnostics/cloth_workflow_debug.json`",
                "- `diagnostics/cloth_workflow_debug.md`",
                "- the normal LaserProg application log from the same session",
                "",
            ])
            md_path.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            pass
        return jsonl_path, json_path, md_path


__all__ = [
    "ClothWorkflowDiagnostics", "ClothDiagnosticOperation", "close_input_snapshot",
    "diagnostics_enabled", "diagnostics_paths", "overlay_snapshot", "proposal_snapshot", "tool_snapshot",
]
