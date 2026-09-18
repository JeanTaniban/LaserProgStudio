# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from laserprog_studio.application.transform_gizmo_renderer import TransformGizmoRenderer
from laserprog_studio.application.transform_gizmo_diagnostics import transform_gizmo_diagnostics_path


class _Collection:
    def __init__(self, values):
        self.values = values

    def GetNumberOfItems(self):
        return len(self.values)


class _Camera:
    def GetDirectionOfProjection(self):
        return (0.0, 0.0, -1.0)

    def GetClippingRange(self):
        return (0.1, 1000.0)

    def GetPosition(self):
        return (0.0, 0.0, 10.0)

    def GetFocalPoint(self):
        return (0.0, 0.0, 0.0)


class _Renderer:
    def __init__(self, layer=0):
        self.props = []
        self.layer = layer
        self.camera = _Camera()
        self.reset_calls = 0

    def AddViewProp(self, prop):
        self.props.append(prop)

    def RemoveViewProp(self, prop):
        if prop in self.props:
            self.props.remove(prop)

    AddActor = AddViewProp
    RemoveActor = RemoveViewProp

    def GetViewProps(self):
        return _Collection(self.props)

    def GetLayer(self):
        return self.layer

    def SetLayer(self, value):
        self.layer = value

    def GetInteractive(self):
        return False

    def SetInteractive(self, _value):
        pass

    def GetPreserveDepthBuffer(self):
        return False

    def SetPreserveDepthBuffer(self, _value):
        pass

    def GetErase(self):
        return False

    def SetErase(self, _value):
        pass

    def GetViewport(self):
        return (0.0, 0.0, 1.0, 1.0)

    def GetActiveCamera(self):
        return self.camera

    def ResetCameraClippingRange(self):
        self.reset_calls += 1


class _Property:
    def __init__(self):
        self.color = (1.0, 1.0, 1.0)
        self.opacity = 1.0
        self.line_width = 1.0
        self.point_size = 1.0

    def SetColor(self, *value): self.color = tuple(value)
    def GetColor(self): return self.color
    def SetOpacity(self, value): self.opacity = value
    def GetOpacity(self): return self.opacity
    def SetAmbient(self, _value): pass
    def SetDiffuse(self, _value): pass
    def SetSpecular(self, _value): pass
    def LightingOff(self): pass
    def SetLineWidth(self, value): self.line_width = value
    def GetLineWidth(self): return self.line_width
    def SetPointSize(self, value): self.point_size = value
    def GetPointSize(self): return self.point_size
    def SetRenderLinesAsTubes(self, _value): pass
    def SetRenderPointsAsSpheres(self, _value): pass


class _Mapper:
    def SetInputData(self, mesh): self.mesh = mesh
    def Update(self): pass


class _Actor:
    def __init__(self):
        self.prop = _Property()
        self.use_bounds = None
        self.visible = False

    def SetMapper(self, mapper): self.mapper = mapper
    def GetProperty(self): return self.prop
    def SetVisibility(self, value): self.visible = bool(value)
    def GetVisibility(self): return self.visible
    def SetPickable(self, _value): pass
    def SetUseBounds(self, value): self.use_bounds = bool(value)


class _Assembly:
    def __init__(self):
        self.parts = []
        self.use_bounds = None
        self.visible = False
        self.position = (0.0, 0.0, 0.0)

    def AddPart(self, actor): self.parts.append(actor)
    def GetParts(self): return _Collection(self.parts)
    def SetPickable(self, _value): pass
    def SetUseBounds(self, value): self.use_bounds = bool(value)
    def SetVisibility(self, value): self.visible = bool(value)
    def GetVisibility(self): return self.visible
    def SetPosition(self, *value): self.position = tuple(value)
    def GetBounds(self): return (-1.0, 1.0, -1.0, 1.0, -1.0, 1.0)


class _PolyData:
    def __init__(self, points):
        self.points = np.asarray(points)
        self.lines = None


class _Owner:
    def __init__(self):
        self.overlay = _Renderer(layer=1)
        self.plotter = SimpleNamespace(renderer=_Renderer(layer=0))
        self.gizmo_overlay_renderer = self.overlay
        self.gizmo_actors = {}
        self.selected_indices = [0]
        self.active_index = 0
        self.transform_mode = "translate"
        self.active_tool = ""

    def _ensure_gizmo_overlay_renderer(self):
        return self.overlay


def test_pass1014_line_point_renderer_attaches_visible_overlay_and_main_fallback(monkeypatch, tmp_path) -> None:
    fake_vtk = SimpleNamespace(vtkPolyDataMapper=_Mapper, vtkActor=_Actor, vtkAssembly=_Assembly)
    fake_pv = SimpleNamespace(PolyData=_PolyData)
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    monkeypatch.setitem(sys.modules, "pyvista", fake_pv)
    monkeypatch.chdir(tmp_path)

    owner = _Owner()
    renderer = TransformGizmoRenderer(owner)
    snapshot = SimpleNamespace(
        mode="translate",
        center=(0.0, 0.0, 0.0),
        length=10.0,
        axes=("x", "y", "z"),
        positions={"x": (10.0, 0.0, 0.0), "y": (0.0, 10.0, 0.0), "z": (0.0, 0.0, 10.0)},
        lines={"x": ((0.0, 0.0, 0.0), (8.6, 0.0, 0.0)), "y": ((0.0, 0.0, 0.0), (0.0, 8.6, 0.0)), "z": ((0.0, 0.0, 0.0), (0.0, 0.0, 8.6))},
        rings={},
        axis_vectors={"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)},
        colors={"x": "#ff0000", "y": "#00ff00", "z": "#0000ff"},
    )

    assert renderer.sync(snapshot, render=False)
    assert renderer.overlay_assembly in owner.overlay.props
    assert renderer.main_assembly in owner.plotter.renderer.props
    assert renderer.overlay_assembly.GetVisibility()
    assert renderer.main_assembly.GetVisibility()
    assert renderer.overlay_assembly.GetParts().GetNumberOfItems() > 0
    assert renderer.main_assembly.GetParts().GetNumberOfItems() > 0
    assert owner.overlay.reset_calls == 1

    overlay_actors = [visual.actor for group in renderer.groups.values() for visual in group.actors if visual.layer == "overlay"]
    main_actors = [visual.actor for group in renderer.groups.values() for visual in group.actors if visual.layer == "main"]
    assert overlay_actors and all(actor.use_bounds is True for actor in overlay_actors)
    assert main_actors and all(actor.use_bounds is False for actor in main_actors)

    entries = [json.loads(line) for line in transform_gizmo_diagnostics_path().read_text(encoding="utf-8").splitlines()]
    assert any(entry["event"] == "renderer.sync_success" for entry in entries)


def test_pass1014_visibility_fix_and_diagnostic_contract_are_documented_in_source() -> None:
    renderer = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")
    diagnostics = Path("src/laserprog_studio/application/transform_gizmo_diagnostics.py").read_text(encoding="utf-8")

    assert "actor.SetUseBounds(bool(use_bounds))" in renderer
    assert "overlay.SetErase(False)" in renderer
    assert "LPS_TRANSFORM_GIZMO_MAIN_FALLBACK" in renderer
    assert "transform_gizmo_debug.jsonl" in diagnostics
    assert "renderer.sync_success" in renderer
