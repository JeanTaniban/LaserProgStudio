from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def test_joint_ui_allows_negative_clearance() -> None:
    text = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    assert "owner.joint_clearance = owner._spin(-100, 100, 0.15, 0.05)" in text
    assert "Negative = tighter slot" in text


def test_joint_core_preserves_negative_clearance() -> None:
    text = (ROOT / "src" / "laserprog_studio" / "fabrication" / "joint_builder_core.py").read_text(encoding="utf-8")
    assert "clearance = float(clearance)" in text
    assert "clearance = float(max(0.0, clearance))" not in text
    assert "female_size_x_raw = float(joint_size + 2.0 * clearance)" in text
    assert "female_size_z_raw = float(face_width_z + 2.0 * clearance)" in text
    assert "Positive clearance loosens; negative clearance tightens" in text


def test_fabrication_joint_panel_validation_accepts_negative_clearance() -> None:
    text = (ROOT / "src" / "laserprog_studio" / "fabrication" / "joint_builder.py").read_text(encoding="utf-8")
    assert "or clearance < 0" not in text
    assert "joint_size + 2.0 * clearance < 0.2" in text
