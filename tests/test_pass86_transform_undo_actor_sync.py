# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import types
from types import SimpleNamespace


def _install_qt_stubs() -> None:
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = SimpleNamespace(UserRole=32)
    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    class QListWidgetItem:
        def __init__(self, text: str = "") -> None:
            self.text = text
            self.data_by_role = {}

        def setData(self, role, value) -> None:  # noqa: N802 - Qt naming
            self.data_by_role[role] = value

    qtwidgets.QListWidgetItem = QListWidgetItem
    pyside = types.ModuleType("PySide6")
    sys.modules.setdefault("PySide6", pyside)
    sys.modules.setdefault("PySide6.QtCore", qtcore)
    sys.modules.setdefault("PySide6.QtWidgets", qtwidgets)


_install_qt_stubs()

from laserprog_studio.rendering import incremental_scene as inc


class _FakePoly:
    def __init__(self, points):
        self.points = [tuple(p) for p in points]
        self.modified_count = 0

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_cells(self) -> int:
        return 2

    def modified(self) -> None:
        self.modified_count += 1


class _FakeActor:
    _next_addr = 1

    def __init__(self, name: str) -> None:
        self.name = name
        self.addr = f"Addr={_FakeActor._next_addr}"
        _FakeActor._next_addr += 1

    def GetAddressAsString(self, _prefix: str = "") -> str:  # noqa: N802 - VTK naming
        return self.addr


class _FakePlotter:
    def __init__(self) -> None:
        self.actors_by_name: dict[str, _FakeActor] = {}

    def add_mesh(self, _poly, **kwargs):
        actor = _FakeActor(str(kwargs.get("name") or ""))
        self.actors_by_name[actor.name] = actor
        return actor

    def remove_actor(self, actor, **_kwargs) -> None:
        for name, current in list(self.actors_by_name.items()):
            if current is actor:
                del self.actors_by_name[name]
                return

    def clear(self) -> None:
        self.actors_by_name.clear()


def _mesh(name: str, z: float):
    return SimpleNamespace(
        name=name,
        color="#B8B8B8",
        vertices=[(0.0, 0.0, z), (1.0, 0.0, z), (0.0, 1.0, z), (1.0, 1.0, z)],
        triangles=[(0, 1, 2), (1, 3, 2)],
        uvs=[],
        texture_projections=[],
        material=None,
        engraving=None,
    )


def _window(meshes):
    return SimpleNamespace(
        current_meshes=lambda: meshes,
        plotter=_FakePlotter(),
        actors_by_index={},
        polydata_by_index={},
        actor_key_by_vtk={},
        actor_key_by_addr={},
        _scene_mesh_render_signatures={},
        _scene_incremental_rebuild_enabled=True,
        _active_pyvista_textures=[],
        material_floor_actor=None,
        _material_floor_signature=None,
        material_shadow_actors={},
        _material_shadow_signature=None,
        _material_shadow_pass_enabled=False,
        _material_key_light=None,
        _material_fill_light=None,
        floor_grid_actor=None,
        show_floor_grid=False,
        show_edges=True,
        has_preview=lambda: False,
        _is_render_camera_mesh=lambda _m: False,
        _engraving_role_from_color=lambda _c: "cut",
        _clear_gizmo_actors=lambda: None,
    )


def test_incremental_undo_resyncs_reused_actor_polydata_when_signature_cache_is_stale(monkeypatch) -> None:
    monkeypatch.setattr(inc, "workmesh_to_polydata", lambda mesh: _FakePoly(mesh.vertices))
    monkeypatch.setattr(inc, "pyvista_texture_for_mesh", lambda _w, _mesh: None)

    initial = _mesh("acoustic_diffuser_core", 0.0)
    meshes = [initial]
    w = _window(meshes)
    inc._full_rebuild(w, meshes)
    actor_before = w.actors_by_index[0]

    # Simulate the historical bug: a live gizmo drag changed VTK points in-place,
    # but the render signature cache still describes the pre-drag mesh.  Undo then
    # rebuilds to the pre-drag mesh and used to keep the visually moved actor.
    moved_points = [(x, y, z + 12.5) for x, y, z in initial.vertices]
    w.polydata_by_index[0].points = list(moved_points)

    inc._incremental_rebuild(w, meshes)

    assert w.actors_by_index[0] is actor_before
    assert [tuple(p) for p in w.polydata_by_index[0].points] == initial.vertices
    assert w.polydata_by_index[0].modified_count == 1


def test_live_transform_finish_refreshes_render_signature_cache_statically() -> None:
    source = open("src/laserprog_studio/controllers/transform_drag.py", encoding="utf-8").read()
    assert "sync_mesh_render_signatures(self, dragged_indices)" in source
    assert "dragged_indices = list(self._drag_mesh_indices" in source
