"""Diagnostic tool-core scenarios used by the GUI probe tool."""
from __future__ import annotations

from .analysis import BenchmarkAnalyzer, BenchmarkMarkdownParser, DiagAnalysis, DiagDecision, DiagFinding, ProbeMetric
from .bench import BenchReport, BenchResult, ToolCoreGuiBenchmark
from .gizmo_demo import HandleDemoBuilder, HandleDemoSnapshot, SelectionDemoBuilder, SelectionDemoSnapshot
from .runner import CoreDiagRunner, CoreDiagSnapshot
from .showcase import UiShowcaseBuilder, UiShowcaseSnapshot

__all__ = [
    "BenchmarkAnalyzer",
    "BenchmarkMarkdownParser",
    "BenchReport",
    "BenchResult",
    "DiagAnalysis",
    "DiagDecision",
    "DiagFinding",
    "HandleDemoBuilder",
    "HandleDemoSnapshot",
    "CoreDiagRunner",
    "CoreDiagSnapshot",
    "ProbeMetric",
    "SelectionDemoBuilder",
    "SelectionDemoSnapshot",
    "ToolCoreGuiBenchmark",
    "UiShowcaseBuilder",
    "UiShowcaseSnapshot",
]
