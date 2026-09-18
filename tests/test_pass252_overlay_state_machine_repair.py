# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import types

from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui
from laserprog_studio.application.tool_core_diag_scene import ToolCoreDiagScenePainter
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

    def SetLineWidth(self, *_args) -> None:  # noqa: N802
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
        self.add_count = 0

    def height(self) -> int:
        return 800

    def add_mesh(self, mesh, *, name: str, **kwargs):
        actor = _FakeActor()
        actor.mesh = mesh
        actor.kwargs = dict(kwargs)
        self.actors[name] = actor
        self.add_count += 1
        return actor

    def add_point_labels(self, points, labels, *, name: str, **kwargs):
        actor = _FakeActor()
        actor.points = points
        actor.labels = labels
        actor.kwargs = dict(kwargs)
        self.actors[name] = actor
        self.add_count += 1
        return actor

    def remove_actor(self, name: str, *, render: bool = False) -> None:
        self.actors.pop(str(name), None)

    def render(self) -> None:
        self.render_count += 1


class _FakeOwner:
    def __init__(self) -> None:
        self.plotter = _FakePlotter()
        self.gizmo_actors: dict[str, object] = {}


def _install_fake_pyvista(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyvista", types.SimpleNamespace(PolyData=_FakePolyData))


def test_pass252_creator_ui_recreates_missing_handle_actor_after_scene_rebuild(monkeypatch) -> None:
    _install_fake_pyvista(monkeypatch)
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
    names = [name for name in owner.plotter.actors if name.startswith("creator_ui_plan_trace_")]
    assert names
    first_actor_ids = {name: id(actor) for name, actor in owner.plotter.actors.items()}

    # Simulate a PyVista scene rebuild that silently clears actors while the
    # painter's Python state still believes they are alive.
    owner.plotter.actors.clear()

    render_creator_viewport_ui(owner, ctx, "plan_trace", render=False, sync_overlays=False)

    assert any(name.startswith("creator_ui_plan_trace_") for name in owner.plotter.actors)
    assert any(id(actor) != first_actor_ids.get(name) for name, actor in owner.plotter.actors.items())


def test_pass252_diag_painter_recreates_missing_line_actor_after_scene_rebuild(monkeypatch) -> None:
    _install_fake_pyvista(monkeypatch)
    owner = _FakeOwner()
    ctx = ToolContext()
    ctx.preview.show_polyline(
        "texture_projection:frame",
        "texture_projection",
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)),
    )
    painter = ToolCoreDiagScenePainter(
        owner,
        owner_tool="texture_projection",
        actor_prefix="creator_ui_texture_projection_",
        state_attr="_creator_ui_scene_state_texture_projection",
        actor_names_attr="_creator_ui_actor_names_texture_projection",
        draw_guides_for_all=True,
    )

    painter.render_context(ctx, render=False)
    assert any(name.startswith("creator_ui_texture_projection_line_batch") for name in owner.plotter.actors)

    owner.plotter.actors.clear()
    painter.render_context(ctx, render=False)

    assert any(name.startswith("creator_ui_texture_projection_line_batch") for name in owner.plotter.actors)


def test_pass252_fast_update_refuses_detached_cached_actor(monkeypatch) -> None:
    _install_fake_pyvista(monkeypatch)
    owner = _FakeOwner()
    ctx = ToolContext()
    handle_id = "plan_trace:test-fast"
    ctx.gizmos.create_handle(
        GizmoHandle(
            id=handle_id,
            owner_tool="plan_trace",
            position=(1.0, 2.0, 3.0),
            kind="plan_trace:point",
            style_id="target",
            radius_px=11,
            base_radius_px=11,
        )
    )
    painter = ToolCoreDiagScenePainter(
        owner,
        owner_tool="plan_trace",
        actor_prefix="creator_ui_plan_trace_",
        state_attr="_creator_ui_scene_state_plan_trace",
        actor_names_attr="_creator_ui_actor_names_plan_trace",
        draw_guides_for_all=True,
    )
    painter.render_context(ctx, render=False)
    assert owner.plotter.actors

    owner.plotter.actors.clear()
    ctx.gizmos.update_handle(handle_id, position=(2.0, 2.0, 3.0))

    assert painter.fast_update_context(ctx, handle_ids=(handle_id,), render=False) is False
