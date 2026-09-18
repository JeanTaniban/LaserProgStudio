# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_runtime_diagnostics_contains_no_historical_pass_reports() -> None:
    diagnostics = Path("diagnostics")
    assert diagnostics.exists()
    assert not list(diagnostics.glob("*.md"))


def test_quality_gate_and_product_guard_exist() -> None:
    quality_gate = Path("scripts/quality_gate.py").read_text(encoding="utf-8")
    product_guard = Path("scripts/product_tree_guard.py").read_text(encoding="utf-8")
    assert "compileall" in quality_gate
    assert "verify_refactor_structure.py" in quality_gate
    assert "audit_architecture_health.py" in quality_gate
    assert "Move historical diagnostics reports" in product_guard


def test_packaging_metadata_keeps_assets_and_presets() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    manifest = Path("MANIFEST.in").read_text(encoding="utf-8")
    spec = Path("packaging/pyinstaller/laserprog_studio.spec").read_text(encoding="utf-8")

    assert "laserprog-studio" in pyproject
    assert "assets/toolbar_icons/*.png" in pyproject
    assert "src/laserprog_studio/engraving/presets *.json" in manifest
    assert "src/laserprog_studio/fabrication/settings *.json" in manifest
    assert "collect_tree(\"assets\")" in spec
    assert "console=False" in spec
