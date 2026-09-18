"""Analysis layer for GUI/gizmo benchmark reports.

This module turns raw benchmark numbers into production rules.  It is kept
renderer-independent so the same logic can be used from tests, the diagnostic
panel, or a report file sent back by a user.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ProbeMetric:
    label: str
    avg_ms: float
    actors_created: int = 0
    actors_removed: int = 0
    bugs: tuple[str, ...] = ()
    source: str = "report"

    @property
    def normalized_label(self) -> str:
        return self.label.casefold().strip()


@dataclass(frozen=True, slots=True)
class DiagFinding:
    severity: str
    code: str
    message: str
    evidence: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class DiagDecision:
    topic: str
    selected: str
    rationale: str
    use_for: tuple[str, ...] = ()
    avoid_for: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DiagAnalysis:
    metrics: tuple[ProbeMetric, ...]
    findings: tuple[DiagFinding, ...]
    decisions: tuple[DiagDecision, ...]
    summary: tuple[str, ...]

    @property
    def blockers(self) -> tuple[DiagFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "blocker")

    @property
    def warnings(self) -> tuple[DiagFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")

    def to_markdown(self) -> str:
        lines = ["# Tool Core benchmark analysis", ""]
        lines.extend(self.summary)
        lines.extend(["", "## Production decisions", ""])
        for decision in self.decisions:
            lines.append(f"### {decision.topic}")
            lines.append(f"- Selected: **{decision.selected}**")
            lines.append(f"- Why: {decision.rationale}")
            if decision.use_for:
                lines.append("- Use for: " + ", ".join(decision.use_for))
            if decision.avoid_for:
                lines.append("- Avoid for: " + ", ".join(decision.avoid_for))
            lines.append("")
        lines.extend(["## Findings", ""])
        if not self.findings:
            lines.append("- No blocker detected.")
        for finding in self.findings:
            lines.append(f"- **{finding.severity.upper()} / {finding.code}**: {finding.message}")
            lines.append(f"  - Evidence: {finding.evidence}")
            lines.append(f"  - Action: {finding.recommendation}")
        lines.extend(["", "## Parsed metrics", ""])
        lines.append("| Probe | Avg ms | Actors + / - | Bugs |")
        lines.append("|---|---:|---:|---|")
        for metric in self.metrics:
            bugs = "; ".join(metric.bugs) if metric.bugs else "-"
            lines.append(f"| {metric.label} | {metric.avg_ms:.3f} | {metric.actors_created}/{metric.actors_removed} | {bugs} |")
        return "\n".join(lines)


class BenchmarkMarkdownParser:
    """Parses the markdown report exported by the diagnostic tool."""

    _live_re = re.compile(
        r"^- \*\*(?P<label>.+?)\*\*: (?P<avg>[0-9]+(?:\.[0-9]+)?) ms/step, actors (?P<created>\d+)/(?P<removed>\d+), bugs: (?P<bugs>.*)$"
    )
    _table_re = re.compile(
        r"^\| (?P<label>[^|]+?) \| (?P<family>[^|]+?) \| (?P<avg>[0-9]+(?:\.[0-9]+)?) \| (?P<created>\d+)/(?P<removed>\d+) \|"
    )

    def parse(self, text: str) -> tuple[ProbeMetric, ...]:
        metrics: list[ProbeMetric] = []
        for raw in text.splitlines():
            line = raw.strip()
            live = self._live_re.match(line)
            if live:
                bug_text = live.group("bugs").strip()
                bugs = tuple(part.strip() for part in re.split(r"[,;]", bug_text) if part.strip() and part.strip().lower() != "none")
                metrics.append(
                    ProbeMetric(
                        live.group("label"),
                        float(live.group("avg")),
                        int(live.group("created")),
                        int(live.group("removed")),
                        bugs,
                        source="live",
                    )
                )
                continue
            table = self._table_re.match(line)
            if table and table.group("label") not in {"Approach", "---"}:
                metrics.append(
                    ProbeMetric(
                        table.group("label").strip(),
                        float(table.group("avg")),
                        int(table.group("created")),
                        int(table.group("removed")),
                        source="deterministic",
                    )
                )
        return tuple(metrics)


class BenchmarkAnalyzer:
    """Converts measured probes into rules for production tool rendering."""

    interactive_budget_ms = 8.0
    visible_lag_ms = 16.0
    actor_churn_ms = 50.0

    def analyze(self, metrics: Iterable[ProbeMetric]) -> DiagAnalysis:
        data = tuple(metrics)
        findings: list[DiagFinding] = []
        decisions: list[DiagDecision] = []

        point = self._best_match(data, ("point cloud", "batched polydata points"))
        glyph = self._best_match(data, ("glyph", "cached spheres"))
        lines = self._best_match(data, ("line polydata", "batched line"))
        labels = self._worst_match(data, ("label", "text"))
        churn = self._worst_match(data, ("actor churn", "remove/add"))

        if labels and labels.avg_ms >= self.visible_lag_ms:
            findings.append(
                DiagFinding(
                    "blocker",
                    "TEXT_LABELS_TOO_SLOW",
                    "Live viewport text labels are too slow for mouse-move interaction.",
                    f"{labels.label}: {labels.avg_ms:.3f} ms/step",
                    "Do not update PyVista/VTK labels during drag. Use hover-only labels, Qt overlay labels, or deferred labels updated on release.",
                )
            )
        if churn and (churn.avg_ms >= self.actor_churn_ms or churn.actors_removed > 0):
            findings.append(
                DiagFinding(
                    "blocker",
                    "ACTOR_CHURN_FORBIDDEN",
                    "Removing and recreating actors during interaction is catastrophic.",
                    f"{churn.label}: {churn.avg_ms:.3f} ms/step, actors {churn.actors_created}/{churn.actors_removed}",
                    "Production tools must reuse actor pools, update arrays in place, or hide actors instead of removing them.",
                )
            )
        if glyph and glyph.avg_ms <= 4.0:
            decisions.append(
                DiagDecision(
                    "3D handle rendering",
                    "vtkGlyph3DMapper cached glyphs",
                    f"The measured glyph probe is fast enough for 3D sphere handles ({glyph.avg_ms:.3f} ms/step) while keeping one actor.",
                    ("sphere handles", "snap points", "selected points", "medium/high point counts"),
                    ("text", "per-handle custom meshes recreated on drag"),
                )
            )
        elif point:
            decisions.append(
                DiagDecision(
                    "3D handle rendering",
                    "single batched point cloud fallback",
                    f"Glyphs were not clearly validated, but the point cloud probe is stable ({point.avg_ms:.3f} ms/step).",
                    ("fallback handles", "very dense point displays", "stress mode"),
                    ("premium sphere handles when glyphs are available",),
                )
            )
        if point:
            decisions.append(
                DiagDecision(
                    "Large point sets",
                    "single PolyData point cloud",
                    f"The point-cloud path has the lowest live overhead ({point.avg_ms:.3f} ms/step).",
                    ("background points", "preview anchors", "large unselected point sets"),
                    ("selected high-visibility 3D handles",),
                )
            )
        if lines:
            decisions.append(
                DiagDecision(
                    "Lines, arcs and circles",
                    "batched PolyData line cells",
                    f"Linework stays below the interaction budget ({lines.avg_ms:.3f} ms/step).",
                    ("sketch edges", "arc/circle sampling", "temporary previews", "snap guides"),
                    ("one actor per line",),
                )
            )
        decisions.append(
            DiagDecision(
                "Text rendering",
                "semantic / hover-only labels",
                "The benchmark policy treats live label rendering as the slow path, so text must not be part of raw mouse-move redraws.",
                ("single hover tooltip", "dimension label after release", "Qt side/overlay panel", "static annotations"),
                ("dozens of add_point_labels rebuilt in drag", "text actor churn"),
            )
        )
        decisions.append(
            DiagDecision(
                "Render scheduling",
                "light render during drag, full render on release",
                "The scoring penalizes full renders because they are a main source of perceived drag latency.",
                ("mouse move", "point drag", "preview drag"),
                ("full scene rebuild while dragging",),
            )
        )

        if not data:
            findings.append(
                DiagFinding(
                    "warning",
                    "NO_METRICS_PARSED",
                    "No benchmark metric could be parsed.",
                    "Empty or incompatible report format.",
                    "Run Deep bench + Live bench again, then export the report.",
                )
            )

        summary = self._summary(data, findings, decisions)
        return DiagAnalysis(data, tuple(findings), tuple(decisions), summary)

    def analyze_markdown(self, text: str) -> DiagAnalysis:
        return self.analyze(BenchmarkMarkdownParser().parse(text))

    @staticmethod
    def _best_match(metrics: tuple[ProbeMetric, ...], needles: tuple[str, ...]) -> ProbeMetric | None:
        candidates = [m for m in metrics if any(needle in m.normalized_label for needle in needles)]
        live = [m for m in candidates if m.source == "live"]
        if live:
            return min(live, key=lambda metric: metric.avg_ms, default=None)
        return min(candidates, key=lambda metric: metric.avg_ms, default=None)

    @staticmethod
    def _worst_match(metrics: tuple[ProbeMetric, ...], needles: tuple[str, ...]) -> ProbeMetric | None:
        candidates = [m for m in metrics if any(needle in m.normalized_label for needle in needles)]
        live = [m for m in candidates if m.source == "live"]
        if live:
            return max(live, key=lambda metric: metric.avg_ms, default=None)
        return max(candidates, key=lambda metric: metric.avg_ms, default=None)

    @staticmethod
    def _summary(metrics: tuple[ProbeMetric, ...], findings: list[DiagFinding], decisions: list[DiagDecision]) -> tuple[str, ...]:
        blockers = sum(1 for item in findings if item.severity == "blocker")
        return (
            f"Parsed {len(metrics)} benchmark metrics.",
            f"Detected {blockers} blocker(s) and {max(0, len(findings) - blockers)} warning(s).",
            f"Generated {len(decisions)} production rendering decision(s) for the shared tool-core layer.",
        )
