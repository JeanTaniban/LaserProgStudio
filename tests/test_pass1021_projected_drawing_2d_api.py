# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from laserprog_studio.tool_api import projected_drawing as draw2d
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_GIZMO_CATALOG
from laserprog_studio.tooling.registry import get_studio_tool


def test_projected_drawing_factories_and_registry_have_clear_io() -> None:
    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("sample")
    primitives = (
        draw2d.point("p", (1, 2, 3), size_px=8),
        draw2d.line("l", (0, 0, 0), (4, 0, 0), width_px=2.5),
        draw2d.face("f", ((0, 0, 0), (4, 0, 0), (2, 3, 0)), fill_opacity=0.3),
    )

    snapshot = registry.replace_all(primitives, render=False)

    assert snapshot.owner_tool == "sample"
    assert len(snapshot.points) == 1
    assert len(snapshot.lines) == 1
    assert len(snapshot.faces) == 1
    assert snapshot.visible is True
    assert snapshot.revision == 1
    assert registry.snapshot() == snapshot

    updated = replace(snapshot.points[0], position=(9.0, 8.0, 7.0))
    registry.update(updated, render=False)
    assert registry.snapshot().points[0].position == (9.0, 8.0, 7.0)
    assert registry.set_visible(False, render=False) is True
    assert registry.snapshot().visible is False
    assert registry.remove("l", render=False) is True
    assert len(registry.snapshot().lines) == 0


def test_projected_drawing_validates_geometry_styles_and_duplicate_ids() -> None:
    with pytest.raises(Exception):
        draw2d.point("", (0, 0, 0))
    with pytest.raises(Exception):
        draw2d.line("bad", (0, 0), (1, 2, 3))
    with pytest.raises(Exception):
        draw2d.face("bad", ((0, 0, 0), (1, 0, 0)))
    with pytest.raises(Exception):
        draw2d.point("bad", (0, 0, 0), color="blue")
    with pytest.raises(Exception):
        draw2d.line("bad", (0, 0, 0), (1, 0, 0), width_px=0)

    registry = ToolContext().projected_drawing.for_tool("duplicates")
    registry.add(draw2d.point("same", (0, 0, 0)), render=False)
    with pytest.raises(ValueError):
        registry.add(draw2d.point("same", (1, 0, 0)), render=False)


def test_projected_drawing_compiler_batches_points_lines_and_indexed_concave_faces() -> None:
    from laserprog_studio.application.projected_drawing_2d import _compile_batches

    face = draw2d.face(
        "concave",
        ((0, 0, 0), (4, 0, 0), (4, 3, 0), (2, 1.5, 0), (0, 3, 0)),
        outline_color="#FFFFFF",
    )
    batches = _compile_batches(
        (
            face,
            draw2d.line("line", (0, 0, 0), (1, 1, 0)),
            draw2d.point("point", (0, 0, 0)),
        )
    )

    face_batch = next(batch for batch in batches if batch.key.kind == "faces")
    line_batches = tuple(batch for batch in batches if batch.key.kind == "lines")
    point_batch = next(batch for batch in batches if batch.key.kind == "points")

    assert len(face_batch.cells) == 3
    assert all(len(cell) == 3 for cell in face_batch.cells)
    assert {index for cell in face_batch.cells for index in cell} == {0, 1, 2, 3, 4}
    vertices_2d = tuple((point[0], point[1]) for point in face_batch.world_points)
    triangle_area = sum(
        abs(
            (vertices_2d[b][0] - vertices_2d[a][0]) * (vertices_2d[c][1] - vertices_2d[a][1])
            - (vertices_2d[b][1] - vertices_2d[a][1]) * (vertices_2d[c][0] - vertices_2d[a][0])
        ) * 0.5
        for a, b, c in face_batch.cells
    )
    assert triangle_area == pytest.approx(9.0)
    assert len(line_batches) == 2  # explicit line plus face outline style
    assert point_batch.cells == ((0,),)
    assert tuple(batch.key.layer for batch in batches) == tuple(sorted(batch.key.layer for batch in batches))


class _FakePoints:
    def __init__(self) -> None:
        self.values: list[tuple[float, float, float]] = []

    def SetNumberOfPoints(self, count: int) -> None:
        self.values = [(0.0, 0.0, 0.0)] * count

    def GetNumberOfPoints(self) -> int:
        return len(self.values)

    def SetPoint(self, index: int, x: float, y: float, z: float) -> None:
        self.values[index] = (float(x), float(y), float(z))

    def Modified(self) -> None:
        pass


class _FakeCells:
    def __init__(self) -> None:
        self.cells: list[list[int]] = []
        self._current: list[int] | None = None

    def Reset(self) -> None:
        self.cells.clear()

    def InsertNextCell(self, _count: int) -> None:
        self._current = []
        self.cells.append(self._current)

    def InsertCellPoint(self, index: int) -> None:
        assert self._current is not None
        self._current.append(int(index))

    def Modified(self) -> None:
        pass


class _FakePolyData:
    def SetPoints(self, points) -> None:
        self.points = points

    def SetVerts(self, cells) -> None:
        self.cells = cells

    def SetLines(self, cells) -> None:
        self.cells = cells

    def SetPolys(self, cells) -> None:
        self.cells = cells

    def Modified(self) -> None:
        pass


class _FakeMapper:
    def SetInputData(self, data) -> None:
        self.data = data

    def SetTransformCoordinate(self, coordinate) -> None:
        self.coordinate = coordinate


class _FakeCoordinate:
    def SetCoordinateSystemToDisplay(self) -> None:
        self.display = True


class _FakeProperty:
    def SetColor(self, *_value) -> None:
        pass

    def SetOpacity(self, _value) -> None:
        pass

    def SetPointSize(self, _value) -> None:
        pass

    def SetLineWidth(self, _value) -> None:
        pass

    def SetDisplayLocationToForeground(self) -> None:
        self.foreground = True


class _FakeActor2D:
    def __init__(self) -> None:
        self.prop = _FakeProperty()
        self.pickable = True
        self.visible = True

    def SetMapper(self, mapper) -> None:
        self.mapper = mapper

    def GetProperty(self):
        return self.prop

    def SetPickable(self, value: bool) -> None:
        self.pickable = bool(value)

    def SetVisibility(self, value: bool) -> None:
        self.visible = bool(value)


class _FakeCamera:
    def __init__(self) -> None:
        self.mtime = 1

    def GetMTime(self) -> int:
        return self.mtime


class _FakeRenderer:
    def __init__(self) -> None:
        self.actors: list[_FakeActor2D] = []
        self.camera = _FakeCamera()
        self.callbacks: dict[int, object] = {}
        self.next_observer = 1
        self.add_calls = 0
        self.remove_calls = 0

    def GetActiveCamera(self):
        return self.camera

    def AddObserver(self, _event, callback) -> int:
        oid = self.next_observer
        self.next_observer += 1
        self.callbacks[oid] = callback
        return oid

    def RemoveObserver(self, oid: int) -> None:
        self.callbacks.pop(oid, None)

    def AddActor2D(self, actor) -> None:
        self.add_calls += 1
        if actor not in self.actors:
            self.actors.append(actor)

    def RemoveActor2D(self, actor) -> None:
        self.remove_calls += 1
        if actor in self.actors:
            self.actors.remove(actor)


class _FakePlotter:
    def __init__(self) -> None:
        self.renderer = _FakeRenderer()
        self.render_count = 0

    def width(self) -> int:
        return 800

    def height(self) -> int:
        return 600

    def render(self) -> None:
        self.render_count += 1


class _FakeOwner:
    def __init__(self) -> None:
        self.plotter = _FakePlotter()
        self.scale = 1.0
        self.render_reasons: list[str] = []
        self.projection_calls = 0

    def _world_to_display(self, point):
        self.projection_calls += 1
        return (100.0 + point[0] * self.scale, 200.0 + point[1] * self.scale, 0.5)

    def request_render(self, *, reason: str) -> None:
        self.render_reasons.append(reason)


def test_projected_drawing_renderer_reprojects_on_each_vtk_frame_without_recreating_actors(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("live")

    registry.replace_all(
        (
            draw2d.point("p", (2, 3, 0)),
            draw2d.line("l", (0, 0, 0), (4, 5, 0)),
            draw2d.face("f", ((0, 0, 0), (3, 0, 0), (0, 3, 0))),
        ),
        render=False,
    )

    store = getattr(owner, "_laserprog_projected_drawing_2d_renderers")
    renderer = store["live"]
    actors_before = tuple(owner.plotter.renderer.actors)
    point_visual = next(visual for visual in renderer._visuals.values() if visual.key.kind == "points")
    assert point_visual.points.values[0] == (102.0, 203.0, 0.0)
    assert all(actor.pickable is False for actor in actors_before)

    callback = next(iter(owner.plotter.renderer.callbacks.values()))
    calls_before = owner.projection_calls
    callback(owner.plotter.renderer, "StartEvent")
    assert owner.projection_calls == calls_before  # unchanged camera uses cached projection

    owner.scale = 2.0
    owner.plotter.renderer.camera.mtime += 1
    callback(owner.plotter.renderer, "StartEvent")

    assert owner.projection_calls > calls_before
    assert point_visual.points.values[0] == (104.0, 206.0, 0.0)
    assert tuple(owner.plotter.renderer.actors) == actors_before


def test_gizmo_catalog_contains_only_the_new_projected_drawing_api() -> None:
    ctx = ToolContext()
    runtime = get_studio_tool(TOOL_GIZMO_CATALOG)
    app_ctx = SimpleNamespace(tool_context=ctx, active_scene=None, owner=None)

    # Seed stale historical state to prove on_open empties the owner scope.
    ctx.preview.show_line(
        "legacy-preview",
        TOOL_GIZMO_CATALOG,
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    )

    runtime.on_open(app_ctx)

    snapshot = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert len(snapshot.points) == 1
    assert len(snapshot.lines) == 2
    assert len(snapshot.faces) == 1
    assert len(snapshot.handles) == 3
    assert snapshot.visible is True

    assert ctx.gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.transform_gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.preview.items(owner_tool=TOOL_GIZMO_CATALOG) == ()
    selection_actors = ctx.selection.actors(owner_tool=TOOL_GIZMO_CATALOG)
    assert len(selection_actors) == len(snapshot.primitives)
    assert any(actor.grabbable for actor in selection_actors)
    assert not any(window.owner_tool == TOOL_GIZMO_CATALOG for window in ctx.overlay.windows.values())

    field_ids = set(ctx.inspector.panel.field_ids())
    assert {"catalog_test", "show_projected_drawing_2d", "interaction_report", "benchmark_actions"} <= field_ids
    assert "catalog_view" not in field_ids
    assert not any(field_id.startswith("show_point_styles") for field_id in field_ids)

    ctx.inspector.update_value("catalog_test", "handle_shapes")
    shape_snapshot = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert len(shape_snapshot.handles) == 11
    assert all(actor.grabbable for actor in ctx.selection.actors(owner_tool=TOOL_GIZMO_CATALOG))

    ctx.inspector.update_value("show_projected_drawing_2d", False)
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).visible is False
    ctx.inspector.trigger("show_all")
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).visible is True

    runtime.on_close(app_ctx)
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).primitives == ()


def test_public_projected_drawing_module_hides_backend_dependencies() -> None:
    public_source = Path("src/laserprog_studio/tool_api/projected_drawing.py").read_text(encoding="utf-8")
    renderer_source = Path("src/laserprog_studio/application/projected_drawing_2d.py").read_text(encoding="utf-8")

    assert "import vtk" not in public_source
    assert "import pyvista" not in public_source.lower()
    assert "PySide" not in public_source
    assert "vtkActor2D" in renderer_source
    assert "SetPickable(False)" in renderer_source


def test_projected_drawing_bulk_factories_and_update_many_are_clear() -> None:
    points = draw2d.points("p", ((0, 0, 0), (1, 0, 0), (2, 0, 0)), color="#112233")
    lines = draw2d.line_segments(
        "l",
        (((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (2, 0, 0))),
        color="#445566",
    )
    faces = draw2d.faces(
        "f",
        (
            ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
            ((2, 0, 0), (3, 0, 0), (2, 1, 0)),
        ),
        fill_color="#778899",
    )

    assert tuple(item.id for item in points) == ("p:0", "p:1", "p:2")
    assert tuple(item.id for item in lines) == ("l:0", "l:1")
    assert tuple(item.id for item in faces) == ("f:0", "f:1")
    assert points[0].style is points[1].style

    registry = ToolContext().projected_drawing.for_tool("bulk")
    registry.replace_all((*points, *lines, *faces), render=False)
    changed = tuple(replace(item, position=(item.position[0], 2.0, 0.0)) for item in points[:2])
    registry.update_many(changed, render=False)
    snapshot = registry.snapshot()
    assert snapshot.points[0].position[1] == 2.0
    assert snapshot.points[1].position[1] == 2.0


def test_projected_drawing_incremental_update_projects_only_changed_points(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("incremental")
    primitives = draw2d.points("p", ((float(index), 0.0, 0.0) for index in range(100)))
    registry.replace_all(primitives, render=False)
    renderer = getattr(owner, "_laserprog_projected_drawing_2d_renderers")["incremental"]

    owner.projection_calls = 0
    registry.update(replace(primitives[37], position=(37.0, 5.0, 0.0)), render=False)
    metrics = renderer.diagnostic_snapshot()
    assert owner.projection_calls == 1
    assert metrics["last_projected_points"] == 1
    assert metrics["last_compile_ms"] == 0.0

    owner.projection_calls = 0
    updates = tuple(replace(primitives[index], position=(float(index), 3.0, 0.0)) for index in range(5))
    registry.update_many(updates, render=False)
    metrics = renderer.diagnostic_snapshot()
    assert owner.projection_calls == 5
    assert metrics["last_projected_points"] == 5

    owner.projection_calls = 0
    owner.plotter.renderer.camera.mtime += 1
    callback = next(iter(owner.plotter.renderer.callbacks.values()))
    callback(owner.plotter.renderer, "StartEvent")
    assert owner.projection_calls == 100
    assert renderer.diagnostic_snapshot()["last_projected_points"] == 100


def test_vector_projection_uses_camera_matrix_instead_of_scalar_owner_calls(monkeypatch) -> None:
    class Matrix:
        def GetElement(self, row: int, column: int) -> float:
            return 1.0 if row == column else 0.0

    class Camera(_FakeCamera):
        def GetCompositeProjectionTransformMatrix(self, _aspect, _near, _far):
            return Matrix()

    class Renderer(_FakeRenderer):
        def __init__(self) -> None:
            super().__init__()
            self.camera = Camera()

        def GetTiledAspectRatio(self) -> float:
            return 800.0 / 600.0

        def GetOrigin(self):
            return (0, 0)

        def GetSize(self):
            return (800, 600)

    class Plotter(_FakePlotter):
        def __init__(self) -> None:
            self.renderer = Renderer()
            self.render_count = 0

    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    owner.plotter = Plotter()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("matrix")
    registry.replace_all(draw2d.points("p", ((0.0, 0.0, 0.0), (0.5, 0.5, 0.0))), render=False)

    renderer = getattr(owner, "_laserprog_projected_drawing_2d_renderers")["matrix"]
    visual = next(iter(renderer._visuals.values()))
    assert owner.projection_calls == 0
    assert visual.points.values[0] == (400.0, 300.0, 0.0)
    assert visual.points.values[1] == (600.0, 450.0, 0.0)
    assert renderer.diagnostic_snapshot()["vector_projection_count"] >= 1


def test_packed_dense_scene_primitives_compile_to_minimal_batches() -> None:
    from laserprog_studio.application.projected_drawing_2d import _compile_batches

    cloud = draw2d.point_cloud("cloud", ((float(index), 0.0, 0.0) for index in range(1000)))
    segments = draw2d.segment_batch(
        "segments",
        (((float(index), 1.0, 0.0), (float(index) + 0.5, 1.0, 0.0)) for index in range(500)),
    )
    face_batch = draw2d.face_batch(
        "faces",
        (
            (
                (float(index), 2.0, 0.0),
                (float(index) + 0.8, 2.0, 0.0),
                (float(index) + 0.8, 2.8, 0.0),
                (float(index), 2.8, 0.0),
            )
            for index in range(100)
        ),
    )
    batches = _compile_batches((cloud, segments, face_batch))

    assert len(batches) == 4  # point, segment, face fill and face outline
    point_batch = next(batch for batch in batches if batch.key.kind == "points")
    assert len(point_batch.world_points) == 1000
    assert len(point_batch.cells) == 1  # one poly-vertex cell, not 1000 cells
    assert len(point_batch.cells[0]) == 1000

    snapshot = ToolContext().projected_drawing.for_tool("packed").replace_all(
        (cloud, segments, face_batch), render=False
    )
    assert snapshot.point_clouds == (cloud,)
    assert snapshot.segment_batches == (segments,)
    assert snapshot.face_batches == (face_batch,)


def test_packed_point_cloud_update_projects_only_changed_coordinates(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("packed-live")
    cloud = draw2d.point_cloud("cloud", ((float(index), 0.0, 0.0) for index in range(1000)))
    registry.replace_all((cloud,), render=False)
    renderer = getattr(owner, "_laserprog_projected_drawing_2d_renderers")["packed-live"]

    positions = list(cloud.positions)
    positions[421] = (421.0, 9.0, 0.0)
    owner.projection_calls = 0
    registry.update(replace(cloud, positions=tuple(positions)), render=False)

    metrics = renderer.diagnostic_snapshot()
    assert owner.projection_calls == 1
    assert metrics["last_projected_points"] == 1
    assert metrics["last_compile_ms"] == 0.0


def test_dense_coordinate_patch_methods_update_snapshot_and_renderer_without_full_compare(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("patches")
    cloud = draw2d.point_cloud(
        "cloud",
        ((float(index), 0.0, 0.0) for index in range(1000)),
        item_ids=(f"point-{index}" for index in range(1000)),
    )
    segments = draw2d.segment_batch(
        "segments",
        (((float(index), 1.0, 0.0), (float(index) + 0.5, 1.0, 0.0)) for index in range(100)),
    )
    face = draw2d.face(
        "face",
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0), (1.0, 1.0, 0.0), (0.0, 2.0, 0.0)),
    )
    registry.replace_all((cloud, segments, face), render=False)
    renderer = getattr(owner, "_laserprog_projected_drawing_2d_renderers")["patches"]

    registry.patch_point_cloud("cloud", (("point-421", (421.0, 9.0, 0.0)),), render=False)
    assert registry.snapshot().point_clouds[0].positions[421] == (421.0, 9.0, 0.0)
    metrics = renderer.diagnostic_snapshot()
    assert metrics["last_incremental_points"] == 1
    assert metrics["last_projected_points"] == 1
    assert metrics["last_compile_ms"] == 0.0

    registry.patch_segment_batch(
        "segments",
        ((3, ((3.0, 4.0, 0.0), (3.5, 4.0, 0.0))),),
        render=False,
    )
    assert registry.snapshot().segment_batches[0].segments[3][0] == (3.0, 4.0, 0.0)
    assert renderer.diagnostic_snapshot()["last_projected_points"] == 2

    registry.patch_face("face", ((3, (1.0, 0.5, 0.0)),), render=False)
    assert registry.snapshot().faces[0].vertices[3] == (1.0, 0.5, 0.0)
    assert renderer.diagnostic_snapshot()["last_projected_points"] == 2  # fill + outline
    face_visual = next(visual for key, visual in renderer._visuals.items() if key.kind == "faces")
    assert len(face_visual.topology) == 3
    assert all(len(cell) == 3 for cell in face_visual.topology)


def test_camera_reprojection_coalesces_fragmented_style_batches(monkeypatch) -> None:
    class Matrix:
        def GetElement(self, row: int, column: int) -> float:
            return 1.0 if row == column else 0.0

    class Camera(_FakeCamera):
        def GetCompositeProjectionTransformMatrix(self, _aspect, _near, _far):
            return Matrix()

    class Renderer(_FakeRenderer):
        def __init__(self) -> None:
            super().__init__()
            self.camera = Camera()

        def GetTiledAspectRatio(self) -> float:
            return 1.0

        def GetOrigin(self):
            return (0, 0)

        def GetSize(self):
            return (800, 600)

    class Plotter(_FakePlotter):
        def __init__(self) -> None:
            self.renderer = Renderer()
            self.render_count = 0

    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    owner.plotter = Plotter()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("fragmented")
    clouds = tuple(
        draw2d.point_cloud(
            f"cloud-{index}",
            ((float(index), float(point), 0.0) for point in range(10)),
            color=f"#{index:02X}{(255-index):02X}80",
        )
        for index in range(32)
    )
    registry.replace_all(clouds, render=False)
    renderer = getattr(owner, "_laserprog_projected_drawing_2d_renderers")["fragmented"]
    snapshot_before = renderer.diagnostic_snapshot()
    before = snapshot_before["vector_projection_count"]
    compile_count_before = snapshot_before["compile_count"]
    owner.plotter.renderer.camera.mtime += 1
    renderer.sync_from_manager(force=False, render=False)
    metrics = renderer.diagnostic_snapshot()
    assert metrics["last_projected_batches"] == 32
    assert metrics["last_projection_groups"] == 1
    assert metrics["vector_projection_count"] == before + 1
    # A camera-only pan/zoom/orbit must reproject existing batches, never
    # rebuild face topology or rerun triangulation.
    assert metrics["compile_count"] == compile_count_before


def test_concave_radial_face_uses_clean_non_overlapping_indexed_triangles() -> None:
    import math
    from laserprog_studio.application.projected_face_triangulation import triangulate_polygon_cells

    count = 128
    vertices = tuple(
        (
            (31.0 if index % 2 == 0 else 21.0) * math.cos(2.0 * math.pi * index / count),
            (31.0 if index % 2 == 0 else 21.0) * math.sin(2.0 * math.pi * index / count),
            0.0,
        )
        for index in range(count)
    )
    cells = triangulate_polygon_cells(vertices)
    assert len(cells) == count - 2
    polygon_area = abs(
        sum(
            vertices[index][0] * vertices[(index + 1) % count][1]
            - vertices[(index + 1) % count][0] * vertices[index][1]
            for index in range(count)
        )
        * 0.5
    )
    triangle_area = sum(
        abs(
            (vertices[b][0] - vertices[a][0]) * (vertices[c][1] - vertices[a][1])
            - (vertices[b][1] - vertices[a][1]) * (vertices[c][0] - vertices[a][0])
        )
        * 0.5
        for a, b, c in cells
    )
    assert triangle_area == pytest.approx(polygon_area, rel=1.0e-10, abs=1.0e-8)


def test_cold_scene_does_not_remove_and_readd_new_actors(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    registry = ToolContext(owner=owner).projected_drawing.for_tool("cold-order")
    registry.replace_all(
        (
            draw2d.point("p", (0.0, 0.0, 0.0)),
            draw2d.line("l", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
            draw2d.face("f", ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))),
        ),
        render=False,
    )
    renderer = owner.plotter.renderer
    assert len(renderer.actors) == 4  # fill, outline, line and points
    assert renderer.add_calls == 4
    assert renderer.remove_calls == 0


def test_face_batch_triangle_indices_stay_inside_each_polygon_span() -> None:
    from laserprog_studio.application.projected_drawing_2d import _compile_batches

    first = ((0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (4.0, 3.0, 0.0), (2.0, 1.5, 0.0), (0.0, 3.0, 0.0))
    second = tuple((x + 10.0, y, z) for x, y, z in first)
    primitive = draw2d.face_batch("faces", (first, second), outline_color=None)
    fill = next(batch for batch in _compile_batches((primitive,)) if batch.key.kind == "faces")

    assert len(fill.cells) == 6
    assert all(all(0 <= index < 5 for index in cell) for cell in fill.cells[:3])
    assert all(all(5 <= index < 10 for index in cell) for cell in fill.cells[3:])


def test_projected_drawing_interactive_factories_cover_old_actor_and_handle_catalog() -> None:
    from laserprog_studio.tool_core.projected_drawing import (
        ProjectedActorKind,
        ProjectedHandleShape,
        ProjectedInteraction,
    )

    handle_shapes = tuple(
        draw2d.handle(f"h:{shape.value}", (float(index), 0.0, 0.0), shape=shape)
        for index, shape in enumerate(ProjectedHandleShape)
    )
    assert {handle.shape for handle in handle_shapes} == set(ProjectedHandleShape)
    assert all(handle.interaction == ProjectedInteraction.GRABBABLE for handle in handle_shapes)

    actors = (
        draw2d.point("actor:p", (0, 0, 0), interaction="selectable"),
        draw2d.line("actor:l", (0, 0, 0), (1, 0, 0), interaction="grabbable"),
        draw2d.circle("actor:c", (0, 0, 0), (2, 0, 0), interaction="grabbable"),
        draw2d.arc("actor:a", ((0, 0, 0), (1, 1, 0), (2, 0, 0)), interaction="selectable"),
        draw2d.polyline("actor:pl", ((0, 0, 0), (1, 1, 0), (2, 0, 0)), interaction="grabbable"),
        draw2d.face("actor:f", ((0, 0, 0), (2, 0, 0), (1, 2, 0)), interaction="selectable"),
    )
    ctx = ToolContext()
    ctx.projected_drawing.for_tool("actors").replace_all((*actors, *handle_shapes), render=False)
    registered = {actor.id: actor for actor in ctx.selection.actors(owner_tool="actors")}
    assert registered["actor:p"].kind.value == ProjectedActorKind.POINT.value
    assert registered["actor:l"].kind.value == ProjectedActorKind.LINE.value
    assert registered["actor:c"].kind.value == ProjectedActorKind.CIRCLE.value
    assert registered["actor:a"].kind.value == ProjectedActorKind.ARC.value
    assert registered["actor:pl"].kind.value == ProjectedActorKind.POLYLINE.value
    assert registered["actor:f"].metadata["filled_polygon_hit"] is True
    assert registered["actor:c"].points == ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0))


def test_projected_drag_arrow_uses_native_hover_select_and_axis_constraint() -> None:
    from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
    from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType
    from laserprog_studio.tool_core.projected_drawing import ProjectedVisualState

    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("drag")
    registry.replace_all(
        (
            draw2d.drag_arrow(
                "drag:x",
                (0.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                constraint="axis_x",
            ),
        ),
        render=False,
    )
    world_to_screen = lambda point: (point[0], point[1])
    resolver = lambda event, _ctx: registry.resolve_drag_positions(event)

    press = handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, (0.0, 0.0), (0.0, 0.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="drag",
        world_to_screen=world_to_screen,
        render=False,
        drag_position_resolver=resolver,
    )
    assert press.action == "grab"
    assert registry.snapshot().handles[0].visual_state == ProjectedVisualState.GRABBED

    move = handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, (8.0, 12.0), (8.0, 12.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="drag",
        world_to_screen=world_to_screen,
        render=False,
        drag_position_resolver=resolver,
    )
    assert move.moved == 1
    assert registry.snapshot().handles[0].position == (8.0, 0.0, 0.0)

    handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, (8.0, 12.0), (8.0, 12.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="drag",
        world_to_screen=world_to_screen,
        render=False,
        drag_position_resolver=resolver,
    )
    assert registry.snapshot().handles[0].visual_state in {ProjectedVisualState.SELECTED, ProjectedVisualState.HOVER}


def test_projected_regular_actor_drag_delegates_to_native_free_delta() -> None:
    from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
    from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType

    ctx = ToolContext()
    registry = ctx.projected_drawing.for_tool("free")
    registry.replace_all((draw2d.point("free:p", (0.0, 0.0, 0.0), interaction="grabbable"),), render=False)
    projector = lambda point: (point[0], point[1])
    resolver = lambda event, _ctx: registry.resolve_drag_positions(event)
    handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, (0.0, 0.0), (0.0, 0.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="free",
        world_to_screen=projector,
        render=False,
        drag_position_resolver=resolver,
    )
    handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, (5.0, 7.0), (5.0, 7.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="free",
        world_to_screen=projector,
        render=False,
        drag_position_resolver=resolver,
    )
    assert registry.snapshot().points[0].position == (5.0, 7.0, 0.0)


def test_projected_handle_renderer_keeps_persistent_non_pickable_actor(monkeypatch) -> None:
    fake_vtk = SimpleNamespace(
        vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
        vtkPoints=_FakePoints,
        vtkCellArray=_FakeCells,
        vtkPolyData=_FakePolyData,
        vtkPolyDataMapper2D=_FakeMapper,
        vtkCoordinate=_FakeCoordinate,
        vtkActor2D=_FakeActor2D,
    )
    monkeypatch.setitem(sys.modules, "vtk", fake_vtk)
    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("handles")
    handle = draw2d.handle("h", (2.0, 3.0, 0.0), shape="translate_arrow", direction=(1.0, 0.0, 0.0))
    registry.replace_all((handle,), render=False)
    renderer = getattr(owner, "_laserprog_projected_drawing_2d_renderers")["handles"]
    visual = renderer._handle_visuals["h"]
    actor_before = visual.actor
    points_before = tuple(visual.points.values)
    assert actor_before.pickable is False
    assert len(points_before) >= 5

    registry.update(replace(handle, position=(7.0, 3.0, 0.0)), render=False)
    visual_after = renderer._handle_visuals["h"]
    assert visual_after.actor is actor_before
    assert tuple(visual_after.points.values) != points_before


def test_projected_z_drag_arrow_uses_screen_axis_when_pointer_world_stays_on_ground() -> None:
    from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
    from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType

    ctx = ToolContext()
    # Simulate a camera where world Z projects vertically on screen while the
    # pointer's world fallback remains constrained to the XY ground plane.
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[2]))
    registry = ctx.projected_drawing.for_tool("drag-z")
    registry.replace_all(
        (
            draw2d.drag_arrow(
                "drag:z",
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                constraint="axis_z",
            ),
        ),
        render=False,
    )
    resolver = lambda event, _ctx: registry.resolve_drag_positions(event)
    projector = ctx.viewport.world_to_screen

    handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, (0.0, 0.0), (0.0, 0.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="drag-z",
        world_to_screen=projector,
        render=False,
        drag_position_resolver=resolver,
    )
    move = handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, (0.0, 12.0), (0.0, 0.0, 0.0), MouseButton.LEFT),
        ctx,
        owner_tool="drag-z",
        world_to_screen=projector,
        render=False,
        drag_position_resolver=resolver,
    )

    assert move.moved == 1
    assert registry.snapshot().handles[0].position == (0.0, 0.0, 12.0)


def test_projected_drawing_batch_defers_renderer_sync_and_keeps_selection_live(monkeypatch) -> None:
    ctx = ToolContext()
    manager = ctx.projected_drawing
    registry = manager.for_tool("batched")
    calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(
        manager,
        "_render_tool_now",
        lambda owner, *, render: calls.append((str(owner), bool(render))) or True,
    )

    with registry.batch():
        registry.add(draw2d.point("p1", (0.0, 0.0, 0.0)), render=False)
        assert ctx.selection.actor("p1") is not None
        with registry.batch():
            registry.add(draw2d.line("l1", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)), render=False)
            registry.render(render=True)
        assert calls == []

    assert calls == [("batched", True)]
    assert {primitive.id for primitive in registry.items()} == {"p1", "l1"}


def test_projected_drawing_nested_batch_does_not_swallow_exceptions() -> None:
    registry = ToolContext().projected_drawing.for_tool("batch-errors")
    with pytest.raises(RuntimeError, match="keep-me"):
        with registry.batch():
            with registry.batch():
                raise RuntimeError("keep-me")


def _install_fake_vtk(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules,
        "vtk",
        SimpleNamespace(
            vtkCommand=SimpleNamespace(StartEvent="StartEvent"),
            vtkPoints=_FakePoints,
            vtkCellArray=_FakeCells,
            vtkPolyData=_FakePolyData,
            vtkPolyDataMapper2D=_FakeMapper,
            vtkCoordinate=_FakeCoordinate,
            vtkActor2D=_FakeActor2D,
        ),
    )


def test_projected_drawing_backend_binds_when_owner_is_attached_after_context_creation(monkeypatch) -> None:
    """Plan Tracer opens through an AppContext whose ToolContext can pre-exist.

    The v74 API-boundary cleanup made the renderer backend injectable.  This
    regression test protects the late-owner path: a context that started
    headless must still materialise the 2D overlay once the Qt owner is attached.
    """

    _install_fake_vtk(monkeypatch)
    owner = _FakeOwner()
    ctx = ToolContext()

    ctx.attach_owner(owner)
    ctx.projected_drawing.for_tool("late-owner").add(draw2d.point("p", (2, 3, 0)), render=False)

    store = getattr(owner, "_laserprog_projected_drawing_2d_renderers")
    assert "late-owner" in store
    assert owner.plotter.renderer.actors, "the live projected overlay should create VTK 2D actors"


def test_projected_drawing_lazy_repairs_plain_owner_assignment(monkeypatch) -> None:
    """Keep compatibility with older code that still does ``ctx.owner = owner``."""

    _install_fake_vtk(monkeypatch)
    owner = _FakeOwner()
    ctx = ToolContext()
    ctx.owner = owner

    rendered = ctx.projected_drawing.for_tool("plain-setattr").add(draw2d.point("p", (2, 3, 0)), render=False)

    assert rendered.id == "p"
    store = getattr(owner, "_laserprog_projected_drawing_2d_renderers")
    assert "plain-setattr" in store
    assert owner.plotter.renderer.actors, "lazy repair should restore the projected overlay backend"


def test_projected_drawing_projection_falls_back_when_vector_projection_is_offscreen() -> None:
    import numpy as np
    from laserprog_studio.application.projected_drawing_2d import ProjectedDrawingOverlay2D

    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    renderer = ProjectedDrawingOverlay2D(owner, ctx.projected_drawing, "live")
    matrix = np.eye(4, dtype=np.float64)
    matrix[0, 3] = 1000.0  # valid homogeneous points, but far outside the viewport.
    world = np.asarray(((0.0, 0.0, 0.0), (1.0, 2.0, 0.0)), dtype=np.float64)

    projected = renderer._project_array(world, (matrix, 0.0, 0.0, 800.0, 600.0))

    assert owner.projection_calls == 2
    assert tuple(projected[0]) == (100.0, 200.0, 0.0)
    assert tuple(projected[1]) == (101.0, 202.0, 0.0)
    assert renderer.diagnostic_snapshot()["last_projection_backend"] == "scalar_fallback"
    assert renderer.diagnostic_snapshot()["scalar_fallback_count"] == 1


def test_projected_drawing_reattaches_cached_actors_after_renderer_prop_clear(monkeypatch) -> None:
    """A global scene rebuild can clear VTK props without disposing the overlay.

    The ProjectedDrawingOverlay2D cache must then re-add its existing actors
    even when the projected registry revision and camera signature are
    unchanged.  Otherwise Plan Tracer 2D / Texture Projection keep live
    primitives internally but nothing is visible in the viewport.
    """

    _install_fake_vtk(monkeypatch)
    owner = _FakeOwner()
    ctx = ToolContext(owner=owner)
    registry = ctx.projected_drawing.for_tool("live")
    registry.replace_all(
        (
            draw2d.point("p", (2, 3, 0)),
            draw2d.handle("h", (2, 3, 0)),
        ),
        render=False,
    )
    store = getattr(owner, "_laserprog_projected_drawing_2d_renderers")
    renderer = store["live"]
    actors_before = tuple(owner.plotter.renderer.actors)
    assert len(actors_before) >= 2

    # Simulate PyVista rebuilding the scene and clearing all props directly.
    owner.plotter.renderer.actors.clear()
    changed = renderer.sync_from_manager(force=False, render=False)

    assert changed is True
    assert set(owner.plotter.renderer.actors) == set(actors_before)
    snapshot = renderer.diagnostic_snapshot()
    assert snapshot["last_renderer_reattached_actors"] == len(actors_before)
    assert snapshot["renderer_reattach_count"] >= len(actors_before)


def test_projected_drawing_uses_layered_foreground_renderer_when_available(monkeypatch) -> None:
    """Projected Drawing 2D should share the robust foreground layer path.

    User diagnostics from v85 showed actors attached and visible in the main
    renderer, but not composed into the viewport on Windows/VTK.  The transform
    gizmo already solves this by drawing helper overlays in a layer-1 renderer;
    projected drawing must prefer that renderer when the live owner exposes it.
    """

    _install_fake_vtk(monkeypatch)

    class OwnerWithForeground(_FakeOwner):
        def __init__(self) -> None:
            super().__init__()
            self.foreground_renderer = _FakeRenderer()
            self.ensure_foreground_calls = 0

        def _ensure_gizmo_overlay_renderer(self):
            self.ensure_foreground_calls += 1
            return self.foreground_renderer

    owner = OwnerWithForeground()
    ctx = ToolContext(owner=owner)
    ctx.projected_drawing.for_tool("foreground").add(draw2d.handle("h", (2, 3, 0)), render=False)

    store = getattr(owner, "_laserprog_projected_drawing_2d_renderers")
    renderer = store["foreground"]
    assert renderer.renderer is owner.foreground_renderer
    assert owner.ensure_foreground_calls >= 1
    assert owner.foreground_renderer.actors, "visible overlay actors should go to the layer-1 foreground renderer"
    assert not owner.plotter.renderer.actors, "the main scene renderer is only used for projection/camera state"
