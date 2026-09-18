# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from types import SimpleNamespace

from laserprog_studio.application.creator_scene_picking import bind_creator_scene_picking
from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core import ToolContext


class _Points:
    def __init__(self, values):
        self.values = tuple(values)

    def GetNumberOfPoints(self):
        return len(self.values)

    def GetPoint(self, index):
        return self.values[index]


class _Cell:
    def __init__(self, values):
        self.values = tuple(values)

    def GetPoints(self):
        return _Points(self.values)


class _Dataset:
    def GetCell(self, _index):
        return _Cell(((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0)))


class _Mapper:
    def GetInput(self):
        return _Dataset()


class _Actor:
    def GetVisibility(self):
        return 1

    def GetPickable(self):
        return 1

    def GetMapper(self):
        return _Mapper()

    def GetAddressAsString(self, _prefix):
        return "actor-exact"


class _OffsetOnlyPicker:
    def __init__(self, actor):
        self.actor = actor
        self.hit = False
        self.tolerance = None

    def SetTolerance(self, value):
        self.tolerance = float(value)

    def PickFromListOn(self):
        pass

    def AddPickList(self, _actor):
        pass

    def Pick(self, x, _y, _z, _renderer):
        self.hit = int(x) == 103
        return int(self.hit)

    def GetActor(self):
        return self.actor if self.hit else None

    def GetViewProp(self):
        return self.actor if self.hit else None

    def GetCellId(self):
        return 0 if self.hit else -1

    def GetPickPosition(self):
        return (3.0, 2.0, 0.0)

    def GetPickNormal(self):
        return (0.0, 0.0, 1.0)


class _VtkOffsetModule:
    def __init__(self, actor):
        self.actor = actor

    def vtkCellPicker(self):
        return _OffsetOnlyPicker(self.actor)

    def vtkPropPicker(self):
        return _OffsetOnlyPicker(self.actor)


def _simple_mesh() -> WorkMesh:
    return WorkMesh(
        name="Two triangles",
        vertices=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#778899",
    )


def test_exact_screen_pick_never_falls_back_to_neighbouring_pixels(monkeypatch) -> None:
    mesh = _simple_mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    actor = _Actor()
    owner = SimpleNamespace(
        actors_by_index={0: actor},
        plotter=SimpleNamespace(renderer=object(), height=lambda: 600.0),
        _qt_to_vtk_candidates=lambda _x, _y: [
            (100, 200, "exact"),
            (103, 200, "offset_plus_3"),
        ],
        _resolve_picked_actor=lambda picked: ("mesh", 0) if picked is actor else None,
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    monkeypatch.setitem(sys.modules, "vtk", _VtkOffsetModule(actor))
    assert bind_creator_scene_picking(ctx, owner)

    forgiving = ctx.pick.face_at((100.0, 100.0))
    exact = ctx.pick.face_at((100.0, 100.0), exact_screen=True)

    assert forgiving.hit
    assert not exact.hit


def test_face_pick_is_remapped_from_display_cell_geometry() -> None:
    mesh = _simple_mesh()
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(mesh)
    # Raw VTK cell id points to triangle 0, while displayed vertices and world
    # position unambiguously point to triangle 1.
    pick = SimpleNamespace(
        element_index=0,
        world_pos=(1.0, 8.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        metadata={
            "face_vertices": (
                (0.0, 0.0, 0.0),
                (10.0, 10.0, 0.0),
                (0.0, 10.0, 0.0),
            )
        },
    )

    assert surface_selection.face_index_from_pick(pick) == 0
    assert surface_selection.face_index_from_pick(pick, snapshot) == 1


def _grid_mesh(size: int = 3) -> WorkMesh:
    vertices = [(float(x), float(y), 0.0) for y in range(size + 1) for x in range(size + 1)]
    triangles = []
    stride = size + 1
    for y in range(size):
        for x in range(size):
            a = y * stride + x
            b = a + 1
            d = (y + 1) * stride + x
            c = d + 1
            triangles.extend(((a, b, c), (a, c, d)))
    return WorkMesh(name="Grid", vertices=vertices, triangles=triangles, color="#8899AA")


def test_logical_cache_is_opt_in_and_does_not_teach_boundary_faces() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_grid_mesh())
    profile = surface_selection.SurfaceSelectionProfile.exact_face()
    cache = surface_selection.SurfaceSelectionCache(logical_reuse=True)
    result = surface_selection.select_surface_region(snapshot, 8, 1.0, profile=profile)
    cache.put_auto(snapshot, 8, profile, (), (), result)

    boundary_result, kind = cache.get_auto(snapshot, 0, profile, (), ())

    assert surface_selection.SurfaceSelectionCache().logical_reuse is False
    assert boundary_result is None
    assert kind == "miss"


def test_surface_growth_does_not_wrap_onto_the_hidden_opposite_side() -> None:
    import math

    vertices = []
    for degrees in (0, 45, 90, 135, 180):
        angle = math.radians(degrees)
        x, z = math.sin(angle), math.cos(angle)
        vertices.extend(((x, 0.0, z), (x, 1.0, z)))
    triangles = []
    for segment in range(4):
        a = segment * 2
        d = a + 1
        b = a + 2
        c = a + 3
        triangles.extend(((a, b, c), (a, c, d)))
    mesh = WorkMesh(name="Rounded half shell", vertices=vertices, triangles=triangles, color="#778899")
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(mesh)

    result = surface_selection.select_surface_region(
        snapshot,
        0,
        1.0,
        profile=surface_selection.SurfaceSelectionProfile.cloth_support(),
    )

    assert set(result.face_indices) == {0, 1, 2, 3, 4, 5}
    assert 6 not in result.face_indices and 7 not in result.face_indices
    assert result.metrics.maximum_seed_angle_degrees <= 90.0
