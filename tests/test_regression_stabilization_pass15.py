# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from _light_transform_source import read_light_transform_source

from _path_setup import ROOT  # noqa: F401

STUDIO = ROOT / "src" / "laserprog_studio"


def test_tex_file_dialog_uses_qt_window_parent_not_controller() -> None:
    source = (STUDIO / "application" / "texture_projection_controller.py").read_text(encoding="utf-8")
    assert "parent = self.owner if hasattr(self, \"owner\") else None" in source
    assert "getOpenFileName(\n                parent," in source
    assert "getOpenFileName(\n                self," not in source


def test_tool_splitter_drag_does_not_persist_light_ui_or_run_overlay_sync() -> None:
    source = read_light_transform_source(ROOT)
    assert "tool_active = getattr(self, \"active_tool\", self.TOOL_NONE) != self.TOOL_NONE" in source
    assert "controller.note_user_splitter_drag(sizes)" in source
    assert "return\n            self._sync_ui_layout_state_from_splitter(save_full=True)" in source
    active_branch = source.split("if tool_active:", 1)[1].split("self._sync_ui_layout_state_from_splitter(save_full=True)", 1)[0]
    assert "self._schedule_light_transform_overlay_sync" not in active_branch


def test_layout_controller_keeps_tool_resize_interactive() -> None:
    source = (STUDIO / "application" / "layout_controller.py").read_text(encoding="utf-8")
    assert "def prepare_interactive_tool_resize" in source
    assert "minimums_for_current_state" in source
    assert "left pane" in source
    assert "right_collapsible=False" in source


def test_joint_tool_starts_boolean_backend_warmup_on_open() -> None:
    controller = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
    assert "boolean_backend_warmup" in controller
    assert "if tool_id == self.TOOL_JOINT" in controller
    warmup = (STUDIO / "application" / "boolean_backend_warmup.py").read_text(encoding="utf-8")
    assert "threading.Thread" in warmup
    assert "daemon=True" in warmup
    assert "boolean_mesh_3d" in warmup
    runtime = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "start_boolean_backend_warmup(self)" not in runtime

def test_stabilization_pass15_is_documented() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "regression_stabilization_pass_15.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "TEX file picker" in text
    assert "Splitter drag" in text
    assert "First Joint action latency" in text
    architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "quality_gate.py" in architecture
