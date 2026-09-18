from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_TRACE = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d"
SHELL = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d_tool.py"


def test_plan_tracer_services_do_not_use_mixin_style_forwarding() -> None:
    services = (PLAN_TRACE / "services.py").read_text(encoding="utf-8")
    assert "def __getattr__" not in services
    assert "getattr(self._tool" not in services
    assert "def services(self)" in services


def test_plan_tracer_shell_is_not_a_delegate_dump() -> None:
    source = SHELL.read_text(encoding="utf-8")
    assert "class PlanTrace2DCreatorTool(CreatorTool):" in source
    assert "PlanTrace2DOverlayMixin" not in source
    assert "# Explicit service delegation" not in source
    # Only stable compatibility shims should remain on the shell.
    assert source.count("def _handle_") == 0
    assert source.count("def _rebuild_") == 0
    assert source.count("def _set_active_tool") == 1
    assert source.count("def resolve_drag_positions") == 1


def test_plan_tracer_service_dependencies_are_explicit() -> None:
    for path in PLAN_TRACE.glob("*.py"):
        if path.name in {"constants.py", "__init__.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        assert "from .constants import *" not in source
    combined = "\n".join(path.read_text(encoding="utf-8") for path in PLAN_TRACE.glob("*.py"))
    assert "self.services." in combined


def test_plan_tracer_uses_public_metric_and_arc_sampling_facades() -> None:
    metrics_source = (PLAN_TRACE / "metrics.py").read_text(encoding="utf-8")
    snap_source = (PLAN_TRACE / "snap.py").read_text(encoding="utf-8")
    api_metrics = (ROOT / "src" / "laserprog_studio" / "tool_api" / "metrics.py").read_text(encoding="utf-8")
    api_planar = (ROOT / "src" / "laserprog_studio" / "tool_api" / "planar_drawing.py").read_text(encoding="utf-8")

    assert "tool_core.metrics.geometry" not in metrics_source
    assert "tool_core.geometry" not in snap_source
    assert "rectangle_opposite_from_metrics" in api_metrics
    assert "def sample_plan_arc_xy" in api_planar
