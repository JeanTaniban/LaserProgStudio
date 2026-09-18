from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401
from laserprog_studio.application.planar_tool_controller import PlanarToolController
from laserprog_studio.planar_tools import (
    FixedPlanarView,
    PlanarRay,
    PlanarToolConfig,
    VentPathDraft,
    intersect_ray_with_locked_plane,
    make_locked_plane,
    resolve_pointer_on_plane,
    snap_plane_point,
)
from laserprog_studio.state.planar_tool_state import PlanarToolState
from laserprog_studio.tooling import TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

STUDIO = ROOT / "src" / "laserprog_studio"


def test_pass14_pointer_ray_plane_projection_and_snap_contract() -> None:
    plane = make_locked_plane(FixedPlanarView.TOP, depth=7.5)
    ray = PlanarRay(origin=(2.2, 3.7, 30.0), direction=(0.0, 0.0, -1.0))
    hit = intersect_ray_with_locked_plane(ray, plane)
    assert hit == (2.2, 3.7, 7.5)

    result = resolve_pointer_on_plane(
        (12.0, 34.0),
        ray,
        plane,
        PlanarToolConfig(grid_snap_enabled=True, smart_snap_enabled=True, grid_step=5.0, smart_snap_tolerance=0.4),
        anchor_points=((0.0, 3.8),),
    )
    assert result is not None
    assert result.raw_plane == (2.2, 3.7)
    assert result.snapped_plane == (0.0, 5.0)
    assert result.snapped_world == (0.0, 5.0, 7.5)
    assert "smart V" in str(result.snap_label)
    assert "grid 5" in str(result.snap_label)


def test_pass14_snap_plane_point_is_deterministic_without_qt() -> None:
    point, label = snap_plane_point(
        (9.8, 20.2),
        PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=True, smart_snap_tolerance=0.5),
        anchor_points=((10.0, 5.0), (100.0, 20.0)),
    )
    assert point == (10.0, 20.0)
    assert label == "smart U + smart V"


class _FakeOwner:
    def __init__(self) -> None:
        self.planar_tool_state = PlanarToolState()
        self.grid_snap_enabled = True
        self.smart_snap_enabled = False
        self.grid_snap_step = 2.0
        self.smart_snap_tolerance = 0.25
        self._camera_view_mode = "free"
        self.logs: list[str] = []

    def ui_log(self, message: str) -> None:
        self.logs.append(message)

    def _camera_forward_vector(self):
        return (0.0, 0.0, -1.0)

    def _set_fixed_orthographic_view(self, mode: str) -> None:
        self._camera_view_mode = mode


class _FakeContext(SimpleNamespace):
    def ui_log(self, message: str) -> None:
        self.owner.ui_log(message)


def test_pass14_planar_controller_claims_future_hooks_without_mainwindow_methods() -> None:
    owner = _FakeOwner()
    controller = PlanarToolController(_FakeContext(owner=owner))
    assert controller.handle_lifecycle_hook("_initialize_plan_trace_tool") is True
    assert owner.planar_tool_state.active is True
    assert owner.planar_tool_state.active_tool_id == TOOL_PLAN_TRACE
    assert owner._camera_view_mode == "top"
    assert owner.planar_tool_state.payload is not None
    controller.handle_lifecycle_hook("_clear_planar_tool_state")
    assert owner.planar_tool_state.active is False

    assert controller.handle_lifecycle_hook("_initialize_vent_generator_tool") is True
    assert owner.planar_tool_state.active_tool_id == TOOL_VENT_GENERATOR
    assert isinstance(owner.planar_tool_state.payload, VentPathDraft)


def test_pass14_sparse_panels_are_bound_to_registered_planar_tools() -> None:
    plan_panel = get_tool_panel_spec(TOOL_PLAN_TRACE)
    vent_panel = get_tool_panel_spec(TOOL_VENT_GENERATOR)
    assert plan_panel is not None and plan_panel.panel_index == 30
    assert vent_panel is not None and vent_panel.panel_index == 31
    assert plan_panel.builder == "panel_declarative_creator_tool"
    assert vent_panel.builder == "panel_declarative_creator_tool"
    assert get_tool_spec(TOOL_PLAN_TRACE) is not None
    assert get_tool_spec(TOOL_VENT_GENERATOR) is not None


def test_pass14_tool_panel_factory_supports_sparse_indices_and_planar_builders() -> None:
    factory = STUDIO / "ui" / "tool_panel_factory.py"
    source = factory.read_text(encoding="utf-8")
    assert "panel_reserved_slot" in source
    assert "max_index = max(specs_by_index.keys(), default=0)" in source
    assert "owner.tool_panel_index_by_key" in source
    assert "def panel_plan_trace_tool" not in source
    assert "panel_declarative_creator_tool" in source


def test_pass14_tool_lifecycle_routes_missing_hooks_to_planar_controller() -> None:
    source = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
    assert "handle_lifecycle_hook" in source
    assert "planar_tool_controller" in source
    assert "Missing lifecycle hook" in source


def test_pass14_architecture_docs_record_planar_interaction_contracts() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_14.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "PlanarPointerResult" in text
    assert "sparse panel indexes" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "PlanarToolController" in architecture_text
