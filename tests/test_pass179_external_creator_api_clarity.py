# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

from laserprog_studio.tool_api.core import CreatorTool
from laserprog_studio.tool_api.gizmos import creator_ui_direction_markdown
from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _load_example_tool():
    path = Path("examples/tool_creator/minimal_point_line_tool.py")
    spec = importlib.util.spec_from_file_location("minimal_point_line_tool_pass179", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pass179_external_quickstart_has_native_creator_tool_path() -> None:
    docs = _read("docs/tool_creator/00_external_tool_quickstart.md")

    assert "class NativeTwoPointsTool(CreatorTool)" in docs
    assert "register_tool(" in docs and "runtime=create_tool()" in docs
    assert "does not implement a mouse state machine" in docs
    assert "Do not call these from normal tool code" in docs
    assert "refresh_creator_ui_drag" in docs
    assert "hover_select_grab_actors" in docs


def test_pass179_readme_minimal_shape_does_not_teach_manual_interaction() -> None:
    docs = _read("docs/tool_creator/README.md")
    minimal = docs.split("## Minimal shape", 1)[1].split("The root `laserprog_studio.tool_api`", 1)[0]

    assert "class MyTool(CreatorTool)" in minimal
    assert "runtime=create_tool()" in minimal
    assert "hover_select_grab_actors" not in minimal
    assert "handle_native_creator_ui_event" not in minimal
    assert "refresh_creator_ui_" not in minimal


def test_pass179_minimal_example_is_creator_tool_and_not_manual_runtime() -> None:
    module = _load_example_tool()
    tool = module.create_tool()
    source = Path("examples/tool_creator/minimal_point_line_tool.py").read_text(encoding="utf-8")

    assert isinstance(tool, CreatorTool)
    assert "hover_select_grab_actors" not in source
    assert "handle_native_creator_ui_event" not in source
    assert "refresh_creator_ui_" not in source
    assert "point_style=\"target\"" in source


def test_pass179_adapter_runs_native_runtime_before_tool_event() -> None:
    source = inspect.getsource(CreatorStudioToolAdapter.on_event)

    assert source.index("self._handle_native_creator_ui_event") < source.index("self.creator.on_event")


def test_pass179_generated_direction_explains_author_boundary() -> None:
    markdown = creator_ui_direction_markdown()

    assert "Tool Core Analysis -> tool_api.ui_catalog / tool_api.ui_motifs -> Gizmo catalog -> Creator tools" in markdown
    assert "tool authors do not call refresh helpers" in markdown
    assert "low-level interaction helpers are for diagnostics/tests/adapters" in markdown
    assert "making tools compute camera-facing GUI axes" in markdown
