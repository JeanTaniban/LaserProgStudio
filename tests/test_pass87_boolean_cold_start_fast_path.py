# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

import _path_setup  # noqa: F401

from laserprog_studio.boolean_ops import _mesh_needs_heavy_boolean_repair, _repair_for_boolean
from laserprog_studio.geometry_ops import mesh_repair
from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box


def _box():
    return build_box(PrimitiveBuildRequest("box", {"size_x": 10, "size_y": 12, "size_z": 14}, 1))


def test_closed_generated_mesh_skips_heavy_boolean_repair_import_path() -> None:
    mesh = _box()
    sys.modules.pop("laserprog_studio.geometry_ops.mesh_repair", None)

    needs_repair, reason = _mesh_needs_heavy_boolean_repair(mesh)

    assert needs_repair is False
    assert reason == "closed"
    assert _repair_for_boolean(mesh, label="box") is mesh
    assert "laserprog_studio.geometry_ops.mesh_repair" not in sys.modules


def test_lightweight_repair_mode_does_not_call_trimesh_or_pyvista(monkeypatch) -> None:
    mesh = _box()

    def forbidden_trimesh(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("trimesh repair should not run in lightweight boolean cleanup")

    def forbidden_pyvista(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("PyVista repair should not run in lightweight boolean cleanup")

    monkeypatch.setattr(mesh_repair, "_trimesh_repair_vertices_triangles", forbidden_trimesh)
    monkeypatch.setattr(mesh_repair, "_pyvista_repair_vertices_triangles", forbidden_pyvista)

    out, report = mesh_repair.repair_work_mesh(
        mesh,
        tolerance_mm=0.002,
        fill_holes=False,
        remove_tiny_faces=True,
        optional_backends=False,
    )

    assert len(out.vertices) == len(mesh.vertices)
    assert len(out.triangles) == len(mesh.triangles)
    assert report.trimesh_repair_used is False


def test_startup_boolean_warmup_is_global_and_exercises_difference() -> None:
    app_source = (__import__("pathlib").Path(__file__).parents[1] / "src" / "laserprog_studio" / "app.py").read_text(encoding="utf-8")
    warmup_source = (__import__("pathlib").Path(__file__).parents[1] / "src" / "laserprog_studio" / "application" / "boolean_backend_warmup.py").read_text(encoding="utf-8")

    assert "start_boolean_backend_warmup()" in app_source
    assert "Preparing boolean engine" in app_source
    assert 'for operation in ("union", "difference")' in warmup_source
    assert "_state = \"ready\"" in warmup_source
