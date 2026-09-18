"""Diagnostics for Tool Core overlay window dragging.

The overlay layer uses this recorder to catch the usual Qt draggable-window
failures: a jump on the first move, widget/spec divergence, and geometry
collapse.  It stays toolkit-light: the Qt adapter feeds simple integer
coordinates and the diagnostic report can be exported by the test tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Iterable


@dataclass(slots=True)
class OverlayDragSample:
    event: str
    window_id: str
    pointer_global_px: tuple[int, int]
    widget_pos_px: tuple[int, int]
    spec_pos_px: tuple[int, int] | None = None
    size_px: tuple[int, int] | None = None
    note: str = ""
    t_ms: float = 0.0


@dataclass(slots=True)
class OverlayDragIssue:
    code: str
    message: str
    severity: str = "warning"


@dataclass(slots=True)
class OverlayDragReport:
    samples: list[OverlayDragSample] = field(default_factory=list)
    issues: list[OverlayDragIssue] = field(default_factory=list)

    @property
    def move_count(self) -> int:
        return sum(1 for sample in self.samples if sample.event == "move")

    def to_markdown(self) -> str:
        lines = [
            "# Tool Core Overlay Drag Diagnostics",
            "",
            "This report records draggable overlay pointer coordinates, widget positions and core spec positions.",
            "The expected behavior is a single global-position delta constraint: no local-coordinate feedback loop, no teleport on first move, and no widget/spec divergence.",
            "",
            "## Summary",
            "",
            f"- samples: {len(self.samples)}",
            f"- move samples: {self.move_count}",
            f"- issues: {len(self.issues)}",
        ]
        if self.issues:
            lines.extend(["", "## Issues", ""])
            for issue in self.issues:
                lines.append(f"- **{issue.code}** ({issue.severity}): {issue.message}")
        lines.extend(["", "## Samples", "", "| Event | Window | Global | Widget | Spec | Size | Note |", "|---|---|---:|---:|---:|---:|---|"])
        for sample in self.samples[-80:]:
            lines.append(
                "| "
                f"{sample.event} | {sample.window_id} | {sample.pointer_global_px} | "
                f"{sample.widget_pos_px} | {sample.spec_pos_px} | {sample.size_px} | {sample.note} |"
            )
        return "\n".join(lines) + "\n"


class OverlayDragDiagnostics:
    """Small recorder used by the overlay manager and Qt adapter."""

    def __init__(self, *, max_samples: int = 300) -> None:
        self.max_samples = int(max(20, max_samples))
        self.samples: list[OverlayDragSample] = []
        self.issues: list[OverlayDragIssue] = []
        self._start_t = perf_counter()
        self._last_by_window: dict[str, OverlayDragSample] = {}

    def clear(self) -> None:
        self.samples.clear()
        self.issues.clear()
        self._last_by_window.clear()
        self._start_t = perf_counter()

    def record(
        self,
        event: str,
        window_id: str,
        *,
        pointer_global_px: tuple[int, int],
        widget_pos_px: tuple[int, int],
        spec_pos_px: tuple[int, int] | None = None,
        size_px: tuple[int, int] | None = None,
        note: str = "",
    ) -> None:
        sample = OverlayDragSample(
            event=str(event),
            window_id=str(window_id),
            pointer_global_px=(int(pointer_global_px[0]), int(pointer_global_px[1])),
            widget_pos_px=(int(widget_pos_px[0]), int(widget_pos_px[1])),
            spec_pos_px=None if spec_pos_px is None else (int(spec_pos_px[0]), int(spec_pos_px[1])),
            size_px=None if size_px is None else (int(size_px[0]), int(size_px[1])),
            note=str(note),
            t_ms=(perf_counter() - self._start_t) * 1000.0,
        )
        self._detect_incremental_issues(sample)
        self.samples.append(sample)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples :]
        self._last_by_window[sample.window_id] = sample

    def _detect_incremental_issues(self, sample: OverlayDragSample) -> None:
        if sample.size_px is not None:
            w, h = sample.size_px
            if w < 80 or h < 36:
                self._add_issue("OVERLAY_GEOMETRY_COLLAPSE", f"{sample.window_id} size collapsed to {sample.size_px}", "blocker")
        if sample.spec_pos_px is not None:
            dx = abs(int(sample.widget_pos_px[0]) - int(sample.spec_pos_px[0]))
            dy = abs(int(sample.widget_pos_px[1]) - int(sample.spec_pos_px[1]))
            if dx > 2 or dy > 2:
                self._add_issue(
                    "OVERLAY_SPEC_WIDGET_DIVERGENCE",
                    f"{sample.window_id} widget/spec positions diverged by ({dx}, {dy}) px",
                    "warning",
                )
        previous = self._last_by_window.get(sample.window_id)
        if previous is not None and sample.event == "move":
            wx = abs(sample.widget_pos_px[0] - previous.widget_pos_px[0])
            wy = abs(sample.widget_pos_px[1] - previous.widget_pos_px[1])
            px = abs(sample.pointer_global_px[0] - previous.pointer_global_px[0])
            py = abs(sample.pointer_global_px[1] - previous.pointer_global_px[1])
            if max(wx, wy) > max(px, py) + 50:
                self._add_issue(
                    "OVERLAY_TELEPORT",
                    f"{sample.window_id} moved {max(wx, wy)} px while pointer moved {max(px, py)} px",
                    "blocker",
                )

    def _add_issue(self, code: str, message: str, severity: str) -> None:
        if any(issue.code == code and issue.message == message for issue in self.issues[-20:]):
            return
        self.issues.append(OverlayDragIssue(code=code, message=message, severity=severity))

    def report(self) -> OverlayDragReport:
        return OverlayDragReport(samples=list(self.samples), issues=list(self.issues))

    def extend_issues(self, issues: Iterable[OverlayDragIssue]) -> None:
        for issue in issues:
            self._add_issue(issue.code, issue.message, issue.severity)
