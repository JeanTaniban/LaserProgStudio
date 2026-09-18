# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import sys

import pytest

from laserprog_studio.application.projected_drawing_2d import _compile_batches
from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_core import ToolContext


def _triangle_area_xy(points, cells) -> float:
    total = 0.0
    for a, b, c in cells:
        p, q, r = points[a], points[b], points[c]
        total += abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])) * 0.5
    return total


def test_projected_face_holes_render_and_hit_test_as_real_holes() -> None:
    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("holes")
    primitive = draw2d.face(
        "plate",
        ((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)),
        holes=(((2, 2, 0), (2, 8, 0), (8, 8, 0), (8, 2, 0)),),
        interaction="selectable",
        outline_color=None,
    )
    registry.add(primitive, render=False)

    batch = next(item for item in _compile_batches((primitive,)) if item.key.kind == "faces")
    assert len(batch.world_points) == 8
    assert _triangle_area_xy(batch.world_points, batch.cells) == pytest.approx(64.0)

    identity = lambda point: (point[0], point[1])
    assert ctx.selection.hit_test((1.0, 1.0), identity, owner_tool="holes") is not None
    assert ctx.selection.hit_test((5.0, 5.0), identity, owner_tool="holes") is None


def test_text_triangle_mesh_and_owner_registry_cover_legacy_mutations() -> None:
    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("legacy")
    label = draw2d.text("label", "42 mm", (1, 2, 3), anchor="top_left", offset_px=(4, -3), bold=True)
    mesh = draw2d.triangle_mesh(
        "mesh",
        ((0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)),
        ((0, 1, 2), (0, 2, 3)),
    )
    registry.replace_all((label, mesh), render=False)

    snapshot = registry.snapshot()
    assert snapshot.texts == (label,)
    assert snapshot.meshes == (mesh,)
    assert registry.get("label") == label
    assert registry.hide("label", render=False) is True
    assert registry.update_positions({"label": (9, 8, 7), "mesh": (1, 1, 1)}, render=False) == 1
    moved = registry.get("label")
    assert moved is not None and moved.position == (9.0, 8.0, 7.0) and moved.visible is False
    assert registry.show("label", render=False) is True
    assert registry.remove_many(("label", "mesh", "missing"), render=False) == 2
    assert registry.items() == ()

    batches = _compile_batches((mesh,))
    fill = next(item for item in batches if item.key.kind == "faces")
    assert fill.cells == ((0, 1, 2), (0, 2, 3))


def test_composite_manipulators_replace_all_historical_gizmo_builders() -> None:
    manipulators = (
        draw2d.translate_gizmo("translate"),
        draw2d.rotate_gizmo("rotate"),
        draw2d.scale_gizmo("scale"),
        draw2d.plane_gizmo("plane"),
        draw2d.triad_gizmo("triad"),
        draw2d.box_bounds_gizmo("box", (0, 10, 0, 20, -2, 2)),
    )
    assert tuple(item.kind for item in manipulators) == ("translate", "rotate", "scale", "plane", "triad", "box_bounds")
    assert len(manipulators[0].handle_ids) == 4
    assert len(manipulators[1].handle_ids) == 3
    assert len(manipulators[2].handle_ids) == 4
    assert len(manipulators[3].handle_ids) == 2
    assert len(manipulators[4].handle_ids) == 3
    assert len(manipulators[5].handle_ids) == 8

    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("manipulators")
    added = registry.add_manipulator(manipulators[0], render=False)
    assert len(added) == 4
    constraints = {handle.constraint.value for handle in registry.snapshot().handles}
    assert {"axis_x", "axis_y", "axis_z", "plane_xy"} <= constraints


class _TextProperty:
    def __init__(self) -> None:
        self.size = 0
        self.color = ()
        self.opacity = 0.0
        self.bold = False
        self.italic = False
        self.justification = ""
        self.vertical = ""

    def SetColor(self, *value) -> None:
        self.color = value

    def SetOpacity(self, value) -> None:
        self.opacity = float(value)

    def SetFontSize(self, value) -> None:
        self.size = int(value)

    def SetBold(self, value) -> None:
        self.bold = bool(value)

    def SetItalic(self, value) -> None:
        self.italic = bool(value)

    def SetJustificationToLeft(self) -> None:
        self.justification = "left"

    def SetJustificationToRight(self) -> None:
        self.justification = "right"

    def SetJustificationToCentered(self) -> None:
        self.justification = "center"

    def SetVerticalJustificationToTop(self) -> None:
        self.vertical = "top"

    def SetVerticalJustificationToBottom(self) -> None:
        self.vertical = "bottom"

    def SetVerticalJustificationToCentered(self) -> None:
        self.vertical = "center"


class _TextActor:
    def __init__(self) -> None:
        self.prop = _TextProperty()
        self.text = ""
        self.position = (0, 0)
        self.visible = True
        self.pickable = True

    def SetInput(self, value) -> None:
        self.text = str(value)

    def GetTextProperty(self):
        return self.prop

    def SetDisplayPosition(self, x, y) -> None:
        self.position = (int(x), int(y))

    def SetVisibility(self, value) -> None:
        self.visible = bool(value)

    def SetPickable(self, value) -> None:
        self.pickable = bool(value)


class _Camera:
    def __init__(self) -> None:
        self.mtime = 1

    def GetMTime(self) -> int:
        return self.mtime


class _Renderer:
    def __init__(self) -> None:
        self.actors = []
        self.camera = _Camera()
        self.callbacks = {}
        self.next_id = 1

    def GetActiveCamera(self):
        return self.camera

    def AddObserver(self, _event, callback):
        value = self.next_id
        self.next_id += 1
        self.callbacks[value] = callback
        return value

    def RemoveObserver(self, value) -> None:
        self.callbacks.pop(value, None)

    def AddActor2D(self, actor) -> None:
        if actor not in self.actors:
            self.actors.append(actor)

    def RemoveActor2D(self, actor) -> None:
        if actor in self.actors:
            self.actors.remove(actor)


class _Plotter:
    def __init__(self) -> None:
        self.renderer = _Renderer()

    def width(self) -> int:
        return 800

    def height(self) -> int:
        return 600

    def render(self) -> None:
        pass


class _Owner:
    def __init__(self) -> None:
        self.plotter = _Plotter()
        self.scale = 1.0

    def _world_to_display(self, point):
        return (100.0 + point[0] * self.scale, 200.0 + point[1] * self.scale, 0.5)

    def request_render(self, *, reason: str) -> None:
        pass


def test_text_renderer_is_persistent_and_reprojects_with_camera(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(vtkCommand=SimpleNamespace(StartEvent="StartEvent"), vtkTextActor=_TextActor)
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _Owner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("text")
    registry.add(draw2d.text("label", "A", (2, 3, 0), offset_px=(4, -5), anchor="top_left"), render=False)

    actor = owner.plotter.renderer.actors[0]
    assert isinstance(actor, _TextActor)
    assert actor.position == (106, 198)
    assert actor.text == "A"
    assert actor.pickable is False
    assert actor.prop.justification == "left"
    assert actor.prop.vertical == "top"

    actors_before = tuple(owner.plotter.renderer.actors)
    owner.scale = 2.0
    owner.plotter.renderer.camera.mtime += 1
    callback = next(iter(owner.plotter.renderer.callbacks.values()))
    callback(owner.plotter.renderer, "StartEvent")
    assert actor.position == (108, 201)
    assert tuple(owner.plotter.renderer.actors) == actors_before

    registry.update(replace(registry.get("label"), text="B"), render=False)
    assert actor.text == "B"
    assert tuple(owner.plotter.renderer.actors) == actors_before
