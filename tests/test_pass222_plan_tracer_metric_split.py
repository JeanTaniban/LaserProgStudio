from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_TRACE = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d"


def test_metric_rebuilders_are_split_from_overlay_session_service() -> None:
    services = (PLAN_TRACE / "services.py").read_text(encoding="utf-8")
    metrics = (PLAN_TRACE / "metrics.py").read_text(encoding="utf-8")
    rebuilders = (PLAN_TRACE / "metric_rebuilders.py").read_text(encoding="utf-8")

    assert "PlanTrace2DMetricRebuilderService" in rebuilders
    assert "metric_rebuilders: Any" in services
    assert "metric_rebuilders=PlanTrace2DMetricRebuilderService(tool)" in services
    assert "return self.services.metric_rebuilders.rebuild_metric_draft_geometry" in metrics

    # Shape-specific rebuild policy should not creep back into the overlay/session service.
    assert "def _rebuild_line_metric_draft" not in metrics
    assert "def _rebuild_circle_metric_draft" not in metrics
    assert "def _rebuild_rectangle_metric_draft" not in metrics
    assert "def _rebuild_half_circle_metric_draft" not in metrics
    assert "def _rebuild_arc_metric_draft" not in metrics
    assert "def _rebuild_arc_metric_draft" in rebuilders


def test_metric_field_policy_is_split_from_metric_overlay_service() -> None:
    metrics = (PLAN_TRACE / "metrics.py").read_text(encoding="utf-8")
    policy = (PLAN_TRACE / "metric_field_policy.py").read_text(encoding="utf-8")

    assert "apply_metric_field_update" in policy
    assert "apply_metric_field_update(draft, field_id, value_text)" in metrics
    assert "def _sync_arc_metric_pair" not in metrics
    assert "def _sync_arc_metric_pair" in policy
