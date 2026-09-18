# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from laserprog_studio.application.creator_viewport_ui import clear_creator_viewport_ui, render_creator_viewport_ui
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.gizmos import GizmoHandle


class _FakePolyData:
    def __init__(self, points=None, faces=None):
        self.points = points
        self.faces = faces
        self.lines = None

    def Modified(self) -> None:  # noqa: N802
        pass

    def copy_from(self, other) -> None:
        self.points = getattr(other, "points", None)
        self.faces = getattr(other, "faces", None)
        self.lines = getattr(other, "lines", None)


class _FakeProperty:
    def SetColor(self, *_args) -> None:  # noqa: N802
        pass

    def SetOpacity(self, *_args) -> None:  # noqa: N802
        pass

    def SetPointSize(self, *_args) -> None:  # noqa: N802
        pass


class _FakeActor:
    def __init__(self) -> None:
        self.visible = True
        self.prop = _FakeProperty()

    def SetVisibility(self, value: bool) -> None:  # noqa: N802
        self.visible = bool(value)

    def GetProperty(self):  # noqa: N802
        return self.prop


class _FakePlotter:
    def __init__(self) -> None:
        self.actors: dict[str, _FakeActor] = {}
        self.camera = None
        self.render_count = 0

    def height(self) -> int:
        return 800

    def add_mesh(self, mesh, *, name: str, **kwargs):
        actor = _FakeActor()
        actor.mesh = mesh
        actor.kwargs = dict(kwargs)
        self.actors[name] = actor
        return actor

    def add_point_labels(self, points, labels, *, name: str, **kwargs):
        actor = _FakeActor()
        actor.points = points
        actor.labels = labels
        actor.kwargs = dict(kwargs)
        self.actors[name] = actor
        return actor

    def remove_actor(self, name: str, *, render: bool = False) -> None:
        self.actors.pop(str(name), None)

    def render(self) -> None:
        self.render_count += 1


class _FakeOwner:
    def __init__(self) -> None:
        self.plotter = _FakePlotter()
        self.gizmo_actors: dict[str, object] = {}


def test_pass1016_plan_tracer_generic_gizmos_render_and_clear_without_sphere_fallback(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyvista", types.SimpleNamespace(PolyData=_FakePolyData))

    # The old fallback creates heavy Sphere/Cube meshes.  It must never run when
    # the historical generic painter is healthy.
    import laserprog_studio.application.creator_viewport_ui as creator_ui

    def _forbidden_fallback(*_args, **_kwargs):
        raise AssertionError("legacy sphere/cube fallback was used")

    monkeypatch.setattr(creator_ui, "_handle_mesh", _forbidden_fallback)

    owner = _FakeOwner()
    ctx = ToolContext()
    ctx.gizmos.create_handle(
        GizmoHandle(
            id="plan_trace:test-point",
            owner_tool="plan_trace",
            position=(12.0, 34.0, 0.75),
            kind="plan_trace:point",
            style_id="minimal",
            radius_px=6,
            base_radius_px=6,
        )
    )

    render_creator_viewport_ui(owner, ctx, "plan_trace", render=False, sync_overlays=False)

    assert any(name.startswith("creator_ui_plan_trace_") for name in owner.plotter.actors)
    assert not owner.gizmo_actors

    clear_creator_viewport_ui(owner, "plan_trace", render=False)
    assert not any(name.startswith("creator_ui_plan_trace_") for name in owner.plotter.actors)


def test_pass1016_transform_renderer_never_calls_generic_creator_cleanup() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")
    assert "clear_creator_viewport_ui" not in source
    assert "clear_tool_core_ui_scene" not in source
    assert "_cleanup_transform_legacy_actors" in source


def test_pass1016_transform_manager_is_not_exported_from_generic_gizmo_api() -> None:
    import laserprog_studio.tool_core.gizmos as generic_gizmos

    assert not hasattr(generic_gizmos, "TransformGizmoManager")
    from laserprog_studio.tool_core.transform_gizmos import TransformGizmoManager

    assert TransformGizmoManager.__module__ == "laserprog_studio.tool_core.transform_gizmos"


def test_pass1016_packaged_plan_tracer_settings_are_safe_defaults() -> None:
    payload = json.loads(Path("settings/studio_tool_parameters.json").read_text(encoding="utf-8"))
    values = payload["tools"]["plan_trace"]
    assert 0.01 <= float(values["plan_trace_2d.grid_step"]) <= 100.0
    assert 0.01 <= float(values["plan_trace_2d.pattern_cell_size"]) <= 1000.0
    assert 0.0 <= float(values["plan_trace_2d.pattern_margin"]) <= 100.0
