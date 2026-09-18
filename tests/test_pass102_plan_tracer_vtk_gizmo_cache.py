# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_pass102_uses_persistent_vtk_glyph_mapper_for_gizmos() -> None:
    cache_source = Path("src/laserprog_studio/application/planar_gizmo_cache.py").read_text(encoding="utf-8")
    preview_source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")

    assert "vtkGlyph3DMapper" in cache_source
    assert "SetPoint" in cache_source
    assert "record.points.Modified()" in cache_source
    assert "record.polydata.Modified()" in cache_source
    assert "hide_all" in cache_source
    assert "_planar_gizmo_actor_cache" in preview_source
    assert "cloud.glyph(geom=sphere" in preview_source  # fallback remains available


def test_pass102_preview_clear_keeps_cached_gizmo_actors_alive() -> None:
    source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")

    assert "Cached VTK glyph gizmos stay in the renderer" in source
    assert "self._gizmo_cache.hide_all" in source
    assert "if str(name) in gizmo_names" in source
