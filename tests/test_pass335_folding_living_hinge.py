# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.folding.geometry import arbitrary_face_plane, deform_vertices, sample_curve
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingFixedSide, FoldingMode, FoldingPhase
from laserprog_studio.tooling.folding.preview_debounce import FoldingPreviewDebouncer
from laserprog_studio.tooling.folding.serialization import attach_folding_source, restore_folding_source
from laserprog_studio.tooling.folding.workflow_overlay import FOLDING_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool


def _plane():
    return arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def _living_curve(*, angle: float = 90.0, fixed_side: str = "start") -> FoldingCurve:
    return FoldingCurve(
        start=(0.0, 0.0, 0.0),
        end=(10.0, 0.0, 0.0),
        mode=FoldingMode.LIVING_HINGE.value,
        fold_angle_deg=angle,
        fixed_side=fixed_side,
    )


def _mesh() -> WorkMesh:
    # Dense enough along X to show the curved hinge band.
    vertices = []
    for x in (-5.0, 0.0, 2.5, 5.0, 7.5, 10.0, 12.0, 15.0):
        vertices.extend(((x, -2.0, 0.0), (x, 2.0, 0.0), (x, -2.0, 1.0), (x, 2.0, 1.0)))
    triangles = []
    for section in range(7):
        a = section * 4
        b = (section + 1) * 4
        triangles.extend(((a, b, a + 1), (a + 1, b, b + 1), (a + 2, a + 3, b + 2), (a + 3, b + 3, b + 2)))
    return WorkMesh(name="living hinge", vertices=vertices, triangles=triangles, color="#AACCEE")


def test_living_hinge_keeps_fixed_region_and_moves_other_region_rigidly() -> None:
    vertices = [
        (-4.0, -2.0, 0.0),
        (-2.0, 3.0, 1.0),
        (12.0, -2.0, 0.0),
        (15.0, 3.0, 1.0),
    ]
    result = deform_vertices(vertices, _plane(), _living_curve(angle=120.0))
    assert result[0] == pytest.approx(vertices[0], abs=1.0e-10)
    assert result[1] == pytest.approx(vertices[1], abs=1.0e-10)
    assert math.dist(result[2], result[3]) == pytest.approx(math.dist(vertices[2], vertices[3]), rel=1.0e-10, abs=1.0e-10)
    assert result[2] != pytest.approx(vertices[2])


def test_second_side_can_be_kept_fixed() -> None:
    vertices = [(-5.0, 0.0, 0.0), (-2.0, 2.0, 1.0), (12.0, 0.0, 0.0), (15.0, 2.0, 1.0)]
    result = deform_vertices(vertices, _plane(), _living_curve(angle=-135.0, fixed_side=FoldingFixedSide.END.value))
    assert result[2] == pytest.approx(vertices[2], abs=1.0e-10)
    assert result[3] == pytest.approx(vertices[3], abs=1.0e-10)
    assert math.dist(result[0], result[1]) == pytest.approx(math.dist(vertices[0], vertices[1]), rel=1.0e-10, abs=1.0e-10)


def test_hinge_neutral_line_keeps_its_original_length() -> None:
    curve = _living_curve(angle=180.0)
    points = sample_curve(_plane(), curve, count=20_001)
    polyline_length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    assert polyline_length == pytest.approx(10.0, rel=2.0e-8)
    assert points[0] == pytest.approx(curve.start)
    assert points[-1][2] > 6.0  # a real out-of-plane fold, not an in-plane warp


def test_living_hinge_settings_round_trip_and_v1_free_curve_remains_compatible() -> None:
    source = _mesh()
    curve = _living_curve(angle=-75.0, fixed_side=FoldingFixedSide.END.value)
    folded = attach_folding_source(source, source_mesh=source, plane=_plane(), curve=curve)
    restored = restore_folding_source(folded)
    assert restored is not None
    _source, _restored_plane, restored_curve = restored
    assert restored_curve.mode == FoldingMode.LIVING_HINGE.value
    assert restored_curve.fold_angle_deg == pytest.approx(-75.0)
    assert restored_curve.fixed_side == FoldingFixedSide.END.value

    legacy = WorkMesh(name="legacy", vertices=source.vertices, triangles=source.triangles)
    legacy.metadata = {
        "folding_source": {
            "version": 1,
            "source_mesh": folded.metadata["folding_source"]["source_mesh"],
            "plane": folded.metadata["folding_source"]["plane"],
            "curve": {
                "start": (0.0, 0.0, 0.0),
                "end": (10.0, 0.0, 0.0),
                "control_1_offset_mm": 2.0,
                "control_2_offset_mm": -1.0,
            },
        }
    }
    legacy_restored = restore_folding_source(legacy)
    assert legacy_restored is not None
    assert legacy_restored[2].mode == FoldingMode.FREE_CURVE.value


def test_preview_debouncer_restarts_one_timer_and_only_runs_after_idle() -> None:
    calls: list[object] = []

    class FakeTimer:
        def __init__(self) -> None:
            self.starts: list[int] = []
            self.stops = 0

        def stop(self) -> None:
            self.stops += 1

        def start(self, delay: int) -> None:
            self.starts.append(delay)

    scheduler = FoldingPreviewDebouncer(lambda ctx: calls.append(ctx), delay_ms=1350)
    timer = FakeTimer()
    scheduler._timer = timer
    first = object()
    second = object()
    scheduler.schedule(first)
    scheduler.schedule(second)
    assert calls == []
    assert timer.starts == [1350, 1350]
    assert scheduler.pending is True
    assert scheduler.flush() is True
    assert calls == [second]
    assert scheduler.pending is False


def test_curve_changes_do_not_rebuild_the_mesh_until_idle(monkeypatch) -> None:
    mesh = _mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    tool.session.target_object_id = mesh.mesh_id
    tool.session.target_index = 0
    tool.session.target_name = mesh.name
    tool.session.source_mesh = mesh
    tool.session.plane = _plane()
    tool.session.curve = _living_curve(angle=30.0)
    tool.session.phase = FoldingPhase.ADJUST_CURVE

    calls = 0
    real_deform = __import__("laserprog_studio.tooling.folding_tool", fromlist=["deform_mesh"]).deform_mesh

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_deform(*args, **kwargs)

    monkeypatch.setattr("laserprog_studio.tooling.folding_tool.deform_mesh", counted)

    class ManualDebouncer:
        pending = False

        def schedule(self, _ctx):
            self.pending = True

        def cancel(self):
            self.pending = False

        def flush(self, _ctx=None):
            return False

    tool._preview_debouncer = ManualDebouncer()
    tool._on_value_changed(ctx, "folding_angle", 45.0)
    tool._on_value_changed(ctx, "folding_angle", 60.0)
    tool._on_value_changed(ctx, "folding_angle", 75.0)
    assert calls == 0
    assert tool.session.preview_pending is True

    tool._on_preview_idle(ctx)
    assert calls == 1
    assert store.has_preview is True


def test_overlay_is_compact_and_only_exposes_context_actions() -> None:
    mesh = _mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(FOLDING_WORKFLOW_WINDOW_ID)
    assert window is not None
    assert window.width_px <= 330
    assert len(window.fields) <= 3
    assert len(window.buttons) == 1  # Cancel only during mesh selection.

    panel_fields = set(ctx.inspector.describe()["fields"])
    assert {"folding_angle", "folding_fixed_side", "folding_preview_state"}.issubset(panel_fields)
    assert "folding_target" not in panel_fields


def test_live_angle_edits_increment_only_curve_actors_not_target_mesh(monkeypatch) -> None:
    mesh = _mesh()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    tool.session.target_object_id = mesh.mesh_id
    tool.session.target_index = 0
    tool.session.target_name = mesh.name
    tool.session.source_mesh = mesh
    tool.session.selected_face_vertices = ((0.0, -2.0, 0.0), (10.0, -2.0, 0.0), (0.0, 2.0, 0.0))
    tool.session.plane = _plane()
    tool.session.curve = _living_curve(angle=30.0)
    tool.session.phase = FoldingPhase.ADJUST_CURVE
    tool._renderer.sync(ctx)

    replace_calls = 0
    update_calls = 0
    real_replace = ctx.projected_drawing.replace_all
    real_update = ctx.projected_drawing.update_many

    def counted_replace(*args, **kwargs):
        nonlocal replace_calls
        replace_calls += 1
        return real_replace(*args, **kwargs)

    def counted_update(*args, **kwargs):
        nonlocal update_calls
        update_calls += 1
        return real_update(*args, **kwargs)

    monkeypatch.setattr(ctx.projected_drawing, "replace_all", counted_replace)
    monkeypatch.setattr(ctx.projected_drawing, "update_many", counted_update)

    class ManualDebouncer:
        pending = False

        def schedule(self, _ctx):
            self.pending = True

        def cancel(self):
            self.pending = False

        def flush(self, _ctx=None):
            return False

    tool._preview_debouncer = ManualDebouncer()
    tool._on_value_changed(ctx, "folding_angle", 40.0)
    tool._on_value_changed(ctx, "folding_angle", 50.0)
    tool._on_value_changed(ctx, "folding_angle", 60.0)

    assert replace_calls == 0
    assert update_calls == 3
    snapshot = ctx.projected_drawing.snapshot("folding")
    assert any(primitive.id == "folding:target" for primitive in snapshot.primitives)


def test_inspector_stays_empty_until_curve_adjustment() -> None:
    ctx = ToolContext()
    tool = FoldingCreatorTool()
    tool.open(ctx)
    initial = ctx.inspector.describe()["field_states"]
    assert all(not state["visible"] for state in initial.values())

    tool.session.phase = FoldingPhase.ADJUST_CURVE
    tool.session.plane = _plane()
    tool.session.curve = _living_curve(angle=90.0)
    tool._sync(ctx, "Set the angle.", render=False)
    states = ctx.inspector.describe()["field_states"]
    assert states["folding_angle"]["visible"] is True
    assert states["folding_fixed_side"]["visible"] is True
    assert states["folding_length"]["visible"] is True
    assert states["folding_preview_state"]["visible"] is True
    assert states["folding_control_1"]["visible"] is False
