# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source
from laserprog_studio.application.tool_core_diag_scene import (
    ToolCoreDiagScenePainter,
    clear_tool_core_diag_scene,
    clear_tool_core_ui_scene,
)
from laserprog_studio.application._tool_core_diag_scene_state import _ACTOR_PREFIX


def test_pass230_public_scene_module_is_small_facade() -> None:
    facade = Path("src/laserprog_studio/application/tool_core_diag_scene.py").read_text(encoding="utf-8")

    assert len(facade.splitlines()) <= 80
    assert "from ._tool_core_diag_scene_painter import ToolCoreDiagScenePainter" in facade
    assert "clear_tool_core_diag_scene" in facade
    assert ToolCoreDiagScenePainter is not None
    assert callable(clear_tool_core_diag_scene)
    assert callable(clear_tool_core_ui_scene)


def test_pass230_runtime_source_keeps_persistent_painter_contract() -> None:
    source = read_tool_core_diag_scene_runtime_source()

    assert _ACTOR_PREFIX == "tool_core_diag_ui_"
    assert "rendered_persistent" in source
    assert "minimal_dot_groups" in source
    assert "fast_update_context" in source
    assert "add_point_labels" in source
    assert "SetVisibility" in source
    assert "copy_from" in source or "DeepCopy" in source
