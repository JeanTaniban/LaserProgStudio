from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DIAGNOSTICS = SRC / "laserprog_studio" / "diagnostics"


def test_shared_projected_overlay_diagnostic_modules_are_packaged_as_source() -> None:
    required = {
        "__init__.py",
        "app_performance_audit.py",
        "boolean_debug.py",
        "plan_trace_selection_length_debug.py",
        "projected_overlay_debug.py",
    }
    assert required <= {path.name for path in DIAGNOSTICS.iterdir() if path.is_file()}


def test_shared_projected_renderer_and_three_affected_tools_import_in_fresh_process() -> None:
    code = """
import importlib
modules = (
    'laserprog_studio.diagnostics.projected_overlay_debug',
    'laserprog_studio.application.projected_drawing_2d',
    'laserprog_studio.tooling.plan_trace_2d_tool',
    'laserprog_studio.tooling.split_tool',
    'laserprog_studio.tooling.cloth_tool',
    'laserprog_studio.tooling.plan_trace_2d.rendering',
    'laserprog_studio.tooling.cloth.rendering',
)
for module in modules:
    importlib.import_module(module)
"""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_runtime_diagnostic_cleanup_target_is_not_the_source_package() -> None:
    quality_gate = (ROOT / "scripts" / "quality_gate.py").read_text(encoding="utf-8")
    assert 'diagnostics = ROOT / "diagnostics"' in quality_gate
    assert 'SRC / "laserprog_studio" / "diagnostics"' in quality_gate
    assert "_verify_runtime_source_packages()" in quality_gate
