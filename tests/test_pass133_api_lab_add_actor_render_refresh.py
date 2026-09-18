# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import types

from laserprog_studio.application.tool_core_diag_scene import ToolCoreDiagScenePainter
from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabInteraction
from laserprog_studio.tool_core import ToolContext


class _FakePolyData:
    def __init__(self, points=None, faces=None):
        self.points = points
        self.faces = faces
        self.lines = None

    def Modified(self) -> None:  # noqa: N802 - VTK-style fake
        pass

    def copy_from(self, other) -> None:
        self.points = getattr(other, "points", None)
        self.faces = getattr(other, "faces", None)
        self.lines = getattr(other, "lines", None)



class _FakeActor:
    def __init__(self) -> None:
        self.visible = True
        self.prop = type("Prop", (), {"color": None, "opacity": None, "point_size": None})()

    def SetVisibility(self, visible: bool) -> None:  # noqa: N802 - VTK-style fake
        self.visible = bool(visible)

    def GetProperty(self):  # noqa: N802 - VTK-style fake
        return self.prop


class _FakePlotter:
    def __init__(self) -> None:
        self.actors: dict[str, _FakeActor] = {}
        self.render_count = 0
        self.camera = None

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
        self.actors.pop(name, None)

    def render(self) -> None:
        self.render_count += 1


class _FakeOwner:
    def __init__(self) -> None:
        self.plotter = _FakePlotter()


def test_pass133_add_actor_button_requests_full_refresh_and_keeps_origin_visible(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyvista", types.SimpleNamespace(PolyData=_FakePolyData))
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diag")

    lab.setup()
    setup_origin_actors = [actor for actor in ctx.selection.actors(owner_tool="tool_core_diag") if actor.points and actor.points[0] == (0.0, 0.0, 0.0)]
    assert setup_origin_actors == []

    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.GRABBABLE.value, point_style="target")
    snap = lab.add_from_options()

    assert snap.points >= 2
    actor = next(actor for actor in ctx.selection.actors(owner_tool="tool_core_diag") if actor.id.startswith("api_lab:point_") and actor.points[0] == (0.0, 0.0, 0.0))
    assert actor.points == ((0.0, 0.0, 0.0),)
    assert ctx.viewport.scheduler.stats.full_requests >= 1

    owner = _FakeOwner()
    stats = ToolCoreDiagScenePainter(owner).render_context(ctx)

    assert stats["status"] == "rendered_persistent"
    assert stats["handles"] >= 1
    assert owner.plotter.render_count >= 1
    assert any(name.startswith("tool_core_diag_ui_handles_") for name in owner.plotter.actors)
    # API Lab target/ring/arrow/etc. point styles must also render their guide
    # geometry now; previously those guides were limited to legacy demo handles.
    assert any(name.startswith("tool_core_diag_ui_guide_") for name in owner.plotter.actors)
