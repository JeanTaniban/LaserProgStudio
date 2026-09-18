from __future__ import annotations

from types import SimpleNamespace
import sys

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.geometry_ops.planar_boolean_solid import (
    extrude_planar_regions_boolean_ready,
)
from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Error:
    NoError = "NoError"


class _NativeSolid:
    def status(self):
        return _Error.NoError

    def is_empty(self):
        return False

    def to_mesh64(self):
        return SimpleNamespace(
            vert_properties=[
                (0.0, 0.0, 0.0), (1.0, 0.0, 0.0),
                (1.0, 1.0, 0.0), (0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0), (1.0, 0.0, 1.0),
                (1.0, 1.0, 1.0), (0.0, 1.0, 1.0),
            ],
            tri_verts=[
                (0, 2, 1), (0, 3, 2),
                (4, 5, 6), (4, 6, 7),
                (0, 1, 5), (0, 5, 4),
                (1, 2, 6), (1, 6, 5),
                (2, 3, 7), (2, 7, 6),
                (3, 0, 4), (3, 4, 7),
            ],
        )


class _NativeCrossSection:
    def __init__(self, _contours):
        pass

    def is_empty(self):
        return False

    def extrude(self, _height):
        return _NativeSolid()


class _ExplodingMesh:
    def __init__(self, **_kwargs):
        raise AssertionError("a native CrossSection result must not be re-imported")


def test_native_cross_section_result_is_not_reimported(monkeypatch) -> None:
    fake_module = SimpleNamespace(
        CrossSection=_NativeCrossSection,
        Mesh=_ExplodingMesh,
        Mesh64=_ExplodingMesh,
        Error=_Error,
    )
    monkeypatch.setitem(sys.modules, "manifold3d", fake_module)

    mesh, report = extrude_planar_regions_boolean_ready(
        [(((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)), ())],
        plane=make_locked_plane("top"),
        depth=1.0,
    )

    assert report.backend == "manifold_cross_section"
    assert report.native_verified is True
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)


class _BrokenCrossSection:
    def __init__(self, _contours):
        raise TypeError("simulated binding mismatch")


class _BrokenMesh:
    def __init__(self, **_kwargs):
        raise RuntimeError("simulated Mesh API mismatch")


def test_optional_native_api_mismatch_does_not_disable_apply_generation(monkeypatch) -> None:
    fake_module = SimpleNamespace(
        CrossSection=_BrokenCrossSection,
        Mesh=_BrokenMesh,
        Mesh64=_BrokenMesh,
        Error=_Error,
    )
    monkeypatch.setitem(sys.modules, "manifold3d", fake_module)

    mesh, report = extrude_planar_regions_boolean_ready(
        [(((0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)), ())],
        plane=make_locked_plane("top"),
        depth=3.0,
    )

    assert report.native_verified is False
    assert "local_topology_verified" in report.backend
    assert report.manifold_status.startswith("verification_unavailable:")
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)


def _rectangle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    ids = [
        sketch.add_point((0.0, 0.0)).id,
        sketch.add_point((20.0, 0.0)).id,
        sketch.add_point((20.0, 10.0)).id,
        sketch.add_point((0.0, 10.0)).id,
    ]
    for first, second in zip(ids, ids[1:] + ids[:1]):
        sketch.add_line(first, second)
    sketch.compile(SketchCompileOptions(solve_faces=True))
    return sketch


def test_apply_failure_is_visible_inside_plan_tracer_status(monkeypatch) -> None:
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = make_locked_plane("top")
    tool._state.sketch = _rectangle_sketch()

    monkeypatch.setattr(
        tool._services.sketch_sync,
        "_compile_and_sync_sketch",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        tool,
        "_build_apply_mesh",
        lambda: (_ for _ in ()).throw(ValueError("simulated validation failure")),
    )

    errors: list[str] = []
    ctx = SimpleNamespace(
        status=SimpleNamespace(error=lambda text: errors.append(str(text))),
    )

    assert tool.on_apply(ctx) is False
    assert tool._state.apply_last_error == "simulated validation failure"
    assert "simulated validation failure" in tool._services.overlay._status_text(selection_text="0 selected")
    assert errors and "validation failed" in errors[-1].lower()


def test_add_commits_mesh_and_closes_tool_when_validation_succeeds(monkeypatch) -> None:
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = make_locked_plane("top")
    tool._state.sketch = _rectangle_sketch()
    tool._state.extrusion_depth = 3.0

    monkeypatch.setattr(
        tool._services.sketch_sync,
        "_compile_and_sync_sketch",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        tool._services.rendering,
        "_render",
        lambda *_args, **_kwargs: None,
    )

    added: list[object] = []
    closed: list[bool] = []
    infos: list[str] = []
    ctx = SimpleNamespace(
        document=SimpleNamespace(
            ensure=lambda: True,
            add_mesh=lambda mesh, **_kwargs: added.append(mesh),
        ),
        owner=SimpleNamespace(
            project_preferences=SimpleNamespace(
                laser=SimpleNamespace(default_board_thickness_mm=4.0),
            ),
            rebuild_scene=lambda **_kwargs: None,
            close_active_tool=lambda **_kwargs: closed.append(True),
        ),
        projected_drawing=SimpleNamespace(clear_tool=lambda *_args, **_kwargs: None),
        status=SimpleNamespace(
            info=lambda text: infos.append(str(text)),
            error=lambda text: infos.append(str(text)),
        ),
    )

    assert tool._apply_add_and_close(ctx) is True
    assert len(added) == 1
    assert closed == [True]
    assert tool._state.apply_last_error == ""
    assert added[0].metadata["boolean_ready"] is True
