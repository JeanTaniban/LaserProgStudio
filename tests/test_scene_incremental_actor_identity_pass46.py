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
    n_points = 4
    n_cells = 2


class _FakeActor:
    _next_addr = 1

    def __init__(self, name: str) -> None:
        self.name = name
        self.addr = f"Addr={_FakeActor._next_addr}"
        _FakeActor._next_addr += 1

    def GetAddressAsString(self, _prefix: str = "") -> str:  # noqa: N802 - VTK naming
        return self.addr


class _FakePlotter:
    """Tiny PyVista-like plotter that replaces actors with duplicate names."""

    def __init__(self) -> None:
        self.actors_by_name: dict[str, _FakeActor] = {}

    def add_mesh(self, _poly, **kwargs):
        name = str(kwargs.get("name") or "")
        if name in self.actors_by_name:
            # PyVista's add_mesh(name=...) behavior replaces the previous actor.
            del self.actors_by_name[name]
        actor = _FakeActor(name)
        self.actors_by_name[name] = actor
        return actor

    def remove_actor(self, actor, **_kwargs) -> None:
        for name, current in list(self.actors_by_name.items()):
            if current is actor:
                del self.actors_by_name[name]
                return

    def clear(self) -> None:
        self.actors_by_name.clear()


def _mesh(name: str, x: float):
    return SimpleNamespace(
        name=name,
        color="#B8B8B8",
        vertices=[(x, 0.0, 0.0), (x + 1.0, 0.0, 0.0), (x, 1.0, 0.0), (x + 1.0, 1.0, 0.0)],
        triangles=[(0, 1, 2), (1, 3, 2)],
        uvs=[],
        texture_projections=[],
        material=None,
        engraving=None,
    )


def _window():
    return SimpleNamespace(
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


def test_pass46_incremental_delete_then_add_does_not_replace_unrelated_shifted_actor(monkeypatch) -> None:
    monkeypatch.setattr(inc, "workmesh_to_polydata", lambda _mesh: _FakePoly())
    monkeypatch.setattr(inc, "pyvista_texture_for_mesh", lambda _w, _mesh: None)

    w = _window()
    original = [_mesh("A", 0), _mesh("B", 10), _mesh("C", 20), _mesh("D", 30), _mesh("E", 40)]
    inc._full_rebuild(w, original)
    assert len(w.plotter.actors_by_name) == 5

    after_delete = [original[0], original[2], original[3], original[4]]
    inc._incremental_rebuild(w, after_delete)
    assert len(w.plotter.actors_by_name) == 4
    actor_for_last_after_shift = w.actors_by_index[3]
    assert actor_for_last_after_shift in set(w.plotter.actors_by_name.values())

    after_add = after_delete + [_mesh("F", 50)]
    inc._incremental_rebuild(w, after_add)

    # Regression: with index-based actor names, adding new index 4 replaced the
    # shifted actor that used to be old index 4, making an unrelated object vanish.
    rendered = set(w.plotter.actors_by_name.values())
    assert len(rendered) == 5
    assert actor_for_last_after_shift in rendered
    assert all(actor in rendered for actor in w.actors_by_index.values())


def test_pass46_mesh_actor_names_are_not_index_based(monkeypatch) -> None:
    monkeypatch.setattr(inc, "workmesh_to_polydata", lambda _mesh: _FakePoly())
    monkeypatch.setattr(inc, "pyvista_texture_for_mesh", lambda _w, _mesh: None)

    w = _window()
    actor_a, *_ = inc._add_mesh_actor(w, 0, _mesh("A", 0))
    actor_b, *_ = inc._add_mesh_actor(w, 0, _mesh("B", 10))

    assert actor_a.name != actor_b.name
    assert not actor_a.name.endswith("_0")
    assert not actor_b.name.endswith("_0")
    assert len(w.plotter.actors_by_name) == 2
