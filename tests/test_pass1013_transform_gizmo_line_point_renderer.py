# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_pass1013_native_transform_renderer_uses_only_pyvista_lines_and_points() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")

    assert "pv.PolyData" in source
    assert "mesh.lines" in source
    assert "SetLineWidth" in source
    assert "SetPointSize" in source
    assert "SetRenderLinesAsTubes(False)" in source
    assert "SetRenderPointsAsSpheres(False)" in source

    forbidden = (
        "pv.Cone(",
        "pv.Cylinder(",
        "pv.Sphere(",
        "pv.Cube(",
        ".tube(",
        "vtkSphereSource",
        "vtkConeSource",
        "vtkCylinderSource",
    )
    for token in forbidden:
        assert token not in source


def test_pass1013_transform_renderer_has_explicit_leak_free_lifecycle() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")

    assert "def _remove_assembly" in source
    assert "RemoveViewProp" in source
    assert "self.groups.clear()" in source
    assert "self._all_actors.clear()" in source
    assert "def clear(" in source
    assert "clear_creator_viewport_ui" in source


def test_pass1013_native_picker_does_not_fall_through_to_legacy_invisible_actors() -> None:
    source = Path("src/laserprog_studio/controllers/interaction_picking.py").read_text(encoding="utf-8")

    assert 'if bool(getattr(self, "_native_transform_gizmo_active", False)):' in source
    assert "return native_hit" in source
    assert "invisible/stale hit targets" in source


def test_pass1013_translate_arrowhead_is_constructed_from_strokes() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")

    assert "wing_a" in source
    assert "wing_b" in source
    assert "((center, tip), (tip, wing_a), (tip, wing_b))" in source
