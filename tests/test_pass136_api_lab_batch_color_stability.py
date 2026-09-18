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
        self.prop = type("Prop", (), {"color": None, "opacity": None, "point_size": None, "line_width": None})()

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


def _visible_actor_names(owner: _FakeOwner, prefix: str) -> list[str]:
    return sorted(name for name, actor in owner.plotter.actors.items() if name.startswith(prefix) and actor.visible)


def test_pass136_same_style_selectable_and_grabbable_points_do_not_share_one_batch(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyvista", types.SimpleNamespace(PolyData=_FakePolyData))
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diag")
    owner = _FakeOwner()
    painter = ToolCoreDiagScenePainter(owner)

    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.SELECTABLE.value, point_style="target")
    selectable = lab.add_actor(LabActorKind.POINT, LabInteraction.SELECTABLE, position=(0.0, 0.0, 0.0))
    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.GRABBABLE.value, point_style="target")
    grabbable = lab.add_actor(LabActorKind.POINT, LabInteraction.GRABBABLE, position=(20.0, 0.0, 0.0))

    lab.render_visuals()
    painter.render_context(ctx)
    idle_batches = _visible_actor_names(owner, "tool_core_diag_ui_handles_target_grabbable_11_")
    assert len(idle_batches) == 2

    ctx.selection.select(selectable.id, replace=True)
    lab.render_visuals()
    painter.render_context(ctx)
    assert any("tool_core_diag_ui_handles_target_selected_15_" in name for name in _visible_actor_names(owner, "tool_core_diag_ui_handles_target_selected_15_"))

    lab.clear_selection(render=True)
    painter.render_context(ctx)
    idle_batches_after_clear = _visible_actor_names(owner, "tool_core_diag_ui_handles_target_grabbable_11_")

    assert selectable.id != grabbable.id
    assert len(idle_batches_after_clear) == 2
    assert all(owner.plotter.actors[name].visible for name in idle_batches_after_clear)


def test_pass136_minimal_same_style_selectable_and_grabbable_dots_keep_two_visible_color_batches(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyvista", types.SimpleNamespace(PolyData=_FakePolyData))
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diag")
    owner = _FakeOwner()
    painter = ToolCoreDiagScenePainter(owner)

    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.SELECTABLE.value, point_style="minimal")
    selectable = lab.add_actor(LabActorKind.POINT, LabInteraction.SELECTABLE, position=(0.0, 0.0, 0.0))
    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.GRABBABLE.value, point_style="minimal")
    lab.add_actor(LabActorKind.POINT, LabInteraction.GRABBABLE, position=(20.0, 0.0, 0.0))

    lab.render_visuals()
    painter.render_context(ctx)
    idle_dot_batches = _visible_actor_names(owner, "tool_core_diag_ui_dotdisc_minimal_grabbable_2_")
    assert len(idle_dot_batches) == 2

    ctx.selection.select(selectable.id, replace=True)
    lab.render_visuals()
    painter.render_context(ctx)
    assert _visible_actor_names(owner, "tool_core_diag_ui_dotdisc_minimal_selected_3_")

    lab.clear_selection(render=True)
    painter.render_context(ctx)
    idle_dot_batches_after_clear = _visible_actor_names(owner, "tool_core_diag_ui_dotdisc_minimal_grabbable_2_")

    assert len(idle_dot_batches_after_clear) == 2
    assert all(owner.plotter.actors[name].visible for name in idle_dot_batches_after_clear)


def test_pass136_selectable_line_deselect_does_not_hide_same_style_point_batches(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "pyvista", types.SimpleNamespace(PolyData=_FakePolyData))
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diag")
    owner = _FakeOwner()
    painter = ToolCoreDiagScenePainter(owner)

    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.GRABBABLE.value, point_style="target", line_style="selectable")
    lab.add_actor(LabActorKind.POINT, LabInteraction.GRABBABLE, position=(0.0, 0.0, 0.0))
    lab.set_options(actor_kind=LabActorKind.LINE.value, interaction=LabInteraction.SELECTABLE.value, point_style="target", line_style="selectable")
    line = lab.add_actor(LabActorKind.LINE, LabInteraction.SELECTABLE, position=(20.0, 0.0, 0.0))

    ctx.selection.select(line.id, replace=True)
    lab.render_visuals()
    painter.render_context(ctx)
    assert _visible_actor_names(owner, "tool_core_diag_ui_handles_target_grabbable_11_")
    assert _visible_actor_names(owner, "tool_core_diag_ui_line_batch_")

    lab.clear_selection(render=True)
    painter.render_context(ctx)

    assert _visible_actor_names(owner, "tool_core_diag_ui_handles_target_grabbable_11_")
    assert _visible_actor_names(owner, "tool_core_diag_ui_line_batch_")
