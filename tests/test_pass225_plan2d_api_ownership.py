from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL_API = ROOT / "src" / "laserprog_studio" / "tool_api"
PLAN2D = TOOL_API / "plan2d"
PLAN_TRACE = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d"
SHELL = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d_tool.py"


def test_plan2d_submodules_own_their_public_logic() -> None:
    for module in ("plane.py", "actors.py", "snap.py", "dimensions.py", "metrics.py"):
        source = (PLAN2D / module).read_text(encoding="utf-8")
        assert "tool_api import planar_drawing" not in source
        assert "tool_api.planar_drawing" not in source

    assert "def pick_plan_anchor_by_raycast" in (PLAN2D / "plane.py").read_text(encoding="utf-8")
    assert "def smart_snap_on_plan" in (PLAN2D / "snap.py").read_text(encoding="utf-8")
    assert "def register_plan_line" in (PLAN2D / "actors.py").read_text(encoding="utf-8")
    assert "class DimensionSpec" in (PLAN2D / "dimensions.py").read_text(encoding="utf-8")
    assert "def build_metric_edit_window" in (PLAN2D / "metrics.py").read_text(encoding="utf-8")


def test_legacy_facades_are_compatibility_only() -> None:
    planar = (TOOL_API / "planar_drawing.py").read_text(encoding="utf-8")
    dimensions = (TOOL_API / "dimensions.py").read_text(encoding="utf-8")
    metrics = (TOOL_API / "metrics.py").read_text(encoding="utf-8")

    assert "Stable alias module" in planar
    assert len(planar.splitlines()) < 40
    assert "from laserprog_studio.tool_api.plan2d.actors import *" in planar
    assert "from laserprog_studio.tool_api.plan2d.dimensions import *" in dimensions
    assert "from laserprog_studio.tool_api.plan2d.metrics import *" in metrics


def test_plan_tracer_prefers_plan2d_metrics_and_dimensions() -> None:
    combined = "\n".join(
        [SHELL.read_text(encoding="utf-8")]
        + [path.read_text(encoding="utf-8") for path in PLAN_TRACE.glob("*.py") if path.name != "__init__.py"]
    )
    assert "from laserprog_studio.tool_api import metrics as metric_api" not in combined
    assert "from laserprog_studio.tool_api import dimensions as dimension_api" not in combined
    assert "from laserprog_studio.tool_api.plan2d import metrics as metric_api" in combined
    assert "from laserprog_studio.tool_api.plan2d import dimensions as dimension_api" in combined
