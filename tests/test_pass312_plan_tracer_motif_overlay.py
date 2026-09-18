"""Pattern overlay refonte v2: live preview + Modify-mode selection.

Contract under test:

* Clicking the toolbox **Pattern** button only opens the overlay when a Plan
  Tracer face is currently selected through Modify mode.  Without a selection
  the button stays inert.
* Once open the overlay shows a live preview of the perforation.  Every
  parameter change (typed value, motif cycle, offset gizmo drag, inspector
  edit) restores the snapshot baseline taken at open time and re-runs the
  motif so the viewport always matches the visible state.
* **Apply** records the preview as a real, undoable command and closes the
  overlay; **Back** restores the baseline and closes without committing.
* The Apply button id contains the ``apply`` token so the generic Qt overlay
  layer flushes pending QLineEdit text before delivering the click — without
  it the user's last edits would be silently dropped.
* Field visibility is dynamic: the ``Seed`` field only appears for the
  stochastic motif, ``Ratio`` only for motifs where it has an effect.
"""
from __future__ import annotations

import pytest

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api.core import ToolEvent, ToolEventType
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tool_core.projected_drawing import ProjectedHandle
from laserprog_studio.tool_core.overlay.qt_commit import button_should_flush_overlay_edits
from laserprog_studio.tooling.plan_trace_2d.constants import (
    _MOTIF_BUTTON_APPLY,
    _MOTIF_BUTTON_CLOSE,
    _MOTIF_BUTTON_KEEP_FORM,
    _MOTIF_BUTTON_NEXT,
    _MOTIF_BUTTON_PREV,
    _MOTIF_BUTTON_PRESET_DELETE,
    _MOTIF_BUTTON_PRESET_SAVE,
    _MOTIF_FIELD_ASPECT,
    _MOTIF_FIELD_CELL_SIZE,
    _MOTIF_FIELD_KIND,
    _MOTIF_FIELD_OFFSET_X,
    _MOTIF_FIELD_PRESET,
    _MOTIF_FIELD_PRESET_NAME,
    _MOTIF_FIELD_SEED,
    _MOTIF_FIELD_WALL,
    _MOTIF_OVERLAY_ID,
    _PATTERN_FACE_BUTTON_ID,
)
from laserprog_studio.tooling.plan_trace_2d.patterns import PATTERN_KIND_CHOICES
from laserprog_studio.tooling.plan_trace_2d.motif_presets import MotifPreset
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )


def _rectangle_sketch(width: float = 200.0, height: float = 120.0) -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((width, 0.0)).id
    p3 = sketch.add_point((width, height)).id
    p4 = sketch.add_point((0.0, height)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    return sketch


def _select_face_in_modify(ctx: ToolContext, face_id: str) -> None:
    """Stub only the lookup methods the Pattern overlay uses.

    The real ``SelectionManager`` exposes ``actors(owner_tool=...)`` as a
    method called by the sketch sync service; replacing it would break the
    preview pipeline.  We only override the two read paths the Pattern
    eligibility check relies on.
    """

    fake_actor = type(
        "_FaceActor",
        (),
        {
            "metadata": {
                "plan_trace_role": "face",
                "plan_trace_sketch_face_id": face_id,
            },
            "owner_tool": "plan_trace_2d",
        },
    )()
    stash: dict[str, object] = {"face_actor": fake_actor}
    ctx.selection.ids = lambda: tuple(stash.keys())
    original_actor_lookup = ctx.selection.actor
    ctx.selection.actor = lambda actor_id, _stash=stash, _orig=original_actor_lookup: (
        _stash.get(str(actor_id)) or _orig(str(actor_id))
    )


def _tool_ready_to_open() -> tuple[PlanTrace2DCreatorTool, ToolContext, str]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _rectangle_sketch()
    face_id = next(iter(tool._state.sketch.faces.keys()))
    _select_face_in_modify(ctx, face_id)
    tool._services.overlay._last_ctx = ctx
    return tool, ctx, face_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pass312_motif_button_requires_modify_face_selection_to_open() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _rectangle_sketch()
    # No Modify selection — clicking Pattern must NOT open the overlay.
    tool._services.overlay._last_ctx = ctx

    tool.on_overlay_button_clicked(_PATTERN_FACE_BUTTON_ID, ctx)
    assert tool._services.motif_overlay.is_open() is False
    assert _MOTIF_OVERLAY_ID not in ctx.overlay.windows


def test_pass312_motif_button_opens_overlay_when_face_selected_via_modify() -> None:
    tool, ctx, face_id = _tool_ready_to_open()

    tool.on_overlay_button_clicked(_PATTERN_FACE_BUTTON_ID, ctx)
    assert tool._services.motif_overlay.is_open() is True
    assert tool._state.pattern_face_id == face_id
    assert _MOTIF_OVERLAY_ID in ctx.overlay.windows


def test_pass312_has_eligible_face_drives_toolbar_motif_button_enabled() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    assert tool._services.motif_overlay.has_eligible_face(ctx) is True

    ctx.selection.ids = lambda: []
    assert tool._services.motif_overlay.has_eligible_face(ctx) is False


def test_pass312_toolbar_motif_button_is_disabled_without_selected_face() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _rectangle_sketch()
    ctx.selection.ids = lambda: []

    action = next(
        action
        for action in tool._services.overlay._toolbar_actions(ctx)
        if action.id == _PATTERN_FACE_BUTTON_ID
    )
    assert action.enabled is False

    face_id = next(iter(tool._state.sketch.faces.keys()))
    _select_face_in_modify(ctx, face_id)
    action = next(
        action
        for action in tool._services.overlay._toolbar_actions(ctx)
        if action.id == _PATTERN_FACE_BUTTON_ID
    )
    assert action.enabled is True


def test_pass312_apply_button_id_includes_apply_token_for_qt_flush() -> None:
    """Without ``apply`` in the id, Qt would drop pending QLineEdit values
    before the click reaches the tool — exactly the bug reported."""

    assert button_should_flush_overlay_edits(_MOTIF_BUTTON_APPLY) is True



def test_pass312_return_button_id_does_not_trigger_generic_qt_close() -> None:
    """Qt reserves button ids containing ``close`` for a raw window hide.

    The Pattern return action must pass through the tool service so the baseline
    snapshot is restored and preview linework is cleaned before the overlay
    disappears.
    """

    assert "close" not in _MOTIF_BUTTON_CLOSE.lower()


def test_pass312_number_fields_accept_decimal_comma_and_units() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    handled = tool.on_overlay_field_changed(
        _MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "9,25 mm", ctx
    )

    assert handled is True
    assert tool._state.motif_cell_size == pytest.approx(9.25)


def test_pass312_motif_number_fields_opt_into_live_edit_dispatch() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    cell_field = next(
        field
        for field in ctx.overlay.windows[_MOTIF_OVERLAY_ID].fields
        if field.id == _MOTIF_FIELD_CELL_SIZE
    )
    assert cell_field.live is True

def test_pass312_field_edit_is_taken_into_account_for_apply() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    handled = tool.on_overlay_field_changed(
        _MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "9.25", ctx
    )
    assert handled is True
    assert tool._state.motif_cell_size == pytest.approx(9.25)
    # Apply must reuse the freshly-typed value, not the default.
    tool.on_overlay_button_clicked(_MOTIF_BUTTON_APPLY, ctx)
    assert tool._state.motif_cell_size == pytest.approx(9.25)


def test_pass312_opening_overlay_runs_live_preview_immediately() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    points_before = len(tool._state.sketch.points)

    tool._services.motif_overlay.open(ctx)
    face = tool._state.sketch.faces[face_id]

    assert len(face.hole_polygons) > 0
    # Preview must no longer explode the sketch into hundreds of point/line actors.
    assert len(tool._state.sketch.points) == points_before


def test_pass312_close_without_apply_restores_baseline_face() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    holes_before = len(tool._state.sketch.faces[face_id].hole_polygons)

    tool._services.motif_overlay.open(ctx)
    assert len(tool._state.sketch.faces[face_id].hole_polygons) > holes_before

    tool._services.motif_overlay.close(ctx, restore=True)
    restored_face = next(iter(tool._state.sketch.faces.values()))
    assert len(restored_face.hole_polygons) == holes_before


def test_pass312_apply_button_commits_preview_and_closes_overlay() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    preview_holes = len(tool._state.sketch.faces[face_id].hole_polygons)

    tool.on_overlay_button_clicked(_MOTIF_BUTTON_APPLY, ctx)
    assert tool._services.motif_overlay.is_open() is False
    committed_face = next(iter(tool._state.sketch.faces.values()))
    assert len(committed_face.hole_polygons) == preview_holes
    assert committed_face.metadata.get("plan_trace_2d.pattern.direct_holes") is True
    # Apply must materialise a perforated face actor directly; no deselect/click
    # with Modify should be needed for the holes to appear.
    face_actors = [
        actor for actor in ctx.selection.actors(owner_tool=tool.id)
        if str(getattr(actor, "id", "")).startswith("plan_trace:face:")
    ]
    assert face_actors
    assert any(getattr(actor, "metadata", {}).get("filled_polygon_holes") for actor in face_actors)




def test_pass312_committed_direct_motif_holes_survive_compile_sync() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    tool.on_overlay_button_clicked(_MOTIF_BUTTON_APPLY, ctx)
    face = next(iter(tool._state.sketch.faces.values()))
    committed_holes = len(face.hole_polygons)
    assert committed_holes > 0

    # Global Apply/can_apply compiles the sketch. Direct motif holes must be
    # restored after topology regeneration instead of disappearing until the
    # user clicks the face again with Modify.
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    face_after_compile = next(iter(tool._state.sketch.faces.values()))
    assert len(face_after_compile.hole_polygons) == committed_holes
    assert face_after_compile.metadata.get("plan_trace_2d.pattern.direct_holes") is True


def test_pass312_changing_parameter_debounces_preview_from_baseline() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    initial_holes = len(tool._state.sketch.faces[face_id].hole_polygons)

    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "6.0", ctx)
    # Text edit is accepted immediately but the expensive preview is delayed.
    assert tool._state.motif_cell_size == pytest.approx(6.0)
    assert tool._state.motif_preview_pending is True
    assert len(tool._state.sketch.faces[face_id].hole_polygons) == initial_holes

    tool._services.motif_overlay._run_scheduled_preview(ctx, tool._state.motif_preview_generation)
    smaller_holes = len(tool._state.sketch.faces[face_id].hole_polygons)
    assert smaller_holes > initial_holes


def test_pass312_debounce_ignores_stale_intermediate_preview() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    initial_holes = len(tool._state.sketch.faces[face_id].hole_polygons)

    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "1", ctx)
    old_generation = tool._state.motif_preview_generation
    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "10", ctx)

    assert tool._services.motif_overlay._run_scheduled_preview(ctx, old_generation) is False
    assert len(tool._state.sketch.faces[face_id].hole_polygons) == initial_holes
    assert tool._services.motif_overlay._run_scheduled_preview(ctx, tool._state.motif_preview_generation) is True
    assert tool._state.motif_cell_size == pytest.approx(10.0)


def test_pass312_cycle_motif_rebuilds_overlay_with_new_visible_fields() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._state.motif_kind = "square"
    tool._services.motif_overlay.open(ctx)

    field_ids = {field.id for field in ctx.overlay.windows[_MOTIF_OVERLAY_ID].fields}
    assert _MOTIF_FIELD_SEED not in field_ids  # square is not stochastic
    assert _MOTIF_FIELD_ASPECT not in field_ids  # square has no aspect

    # Cycle until we hit "organic", which exposes BOTH aspect and seed.
    for _ in range(len(PATTERN_KIND_CHOICES) + 1):
        if tool._state.motif_kind == "organic":
            break
        tool.on_overlay_button_clicked(_MOTIF_BUTTON_NEXT, ctx)

    field_ids = {field.id for field in ctx.overlay.windows[_MOTIF_OVERLAY_ID].fields}
    assert _MOTIF_FIELD_SEED in field_ids
    assert _MOTIF_FIELD_ASPECT in field_ids


def test_pass312_inspector_change_mirrors_into_overlay_state_and_preview() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    tool._services.overlay._on_panel_settings_changed(
        "plan_trace_2d.pattern_cell_size", 8.0
    )
    assert tool._state.motif_cell_size == pytest.approx(8.0)


def test_pass312_offset_field_edit_updates_state_and_gizmo_position() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    registry = ctx.projected_drawing.for_tool(tool.id)
    initial = registry.get("plan_trace_2d.motif.offset_handle:center")
    assert isinstance(initial, ProjectedHandle)
    initial_center = initial.position
    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_OFFSET_X, "12.0", ctx)
    updated = registry.get("plan_trace_2d.motif.offset_handle:center")
    assert isinstance(updated, ProjectedHandle)
    assert updated.position != initial_center
    assert not ctx.gizmos.handles(owner_tool=tool.id)


def test_pass312_close_removes_offset_gizmo_from_scene() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    registry = ctx.projected_drawing.for_tool(tool.id)
    assert isinstance(registry.get("plan_trace_2d.motif.offset_handle:center"), ProjectedHandle)
    assert not ctx.gizmos.handles(owner_tool=tool.id)

    tool._services.motif_overlay.close(ctx, restore=True)
    assert registry.get("plan_trace_2d.motif.offset_handle:center") is None



def test_pass312_offset_drag_is_resolved_through_native_actor_api() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    handle_id = "plan_trace_2d.motif.offset_handle:x"
    ctx.selection.state.grabbed_ids = (handle_id,)
    ctx.selection.state.grab_active = True

    assert tool._services.motif_overlay.begin_offset_drag_from_native(
        ctx, ToolEvent(ToolEventType.MOUSE_PRESS, world_pos=(100.0, 60.0, 0.0)), (handle_id,)
    )
    resolved = tool.resolve_drag_positions(
        ToolEvent(ToolEventType.MOUSE_MOVE, world_pos=(112.0, 65.0, 0.0)), ctx
    )

    assert resolved is not None
    assert handle_id in resolved
    assert tool._state.motif_offset_x == pytest.approx(12.0)
    assert tool._state.motif_offset_y == pytest.approx(0.0)

def test_pass312_overlay_uses_preset_actions_instead_of_pattern_arrows() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    window = ctx.overlay.windows[_MOTIF_OVERLAY_ID]
    button_ids = {button.id for button in window.buttons}
    assert _MOTIF_BUTTON_PREV not in button_ids
    assert _MOTIF_BUTTON_NEXT not in button_ids
    assert button_ids == {
        _MOTIF_BUTTON_PRESET_SAVE,
        _MOTIF_BUTTON_PRESET_DELETE,
        _MOTIF_BUTTON_APPLY,
        _MOTIF_BUTTON_KEEP_FORM,
        _MOTIF_BUTTON_CLOSE,
    }


def test_pass312_kind_is_a_direct_select_enum() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._state.motif_kind = "hinge_straight"
    tool._services.motif_overlay.open(ctx)
    kind_field = next(
        field
        for field in ctx.overlay.windows[_MOTIF_OVERLAY_ID].fields
        if field.id == _MOTIF_FIELD_KIND
    )
    assert kind_field.kind == "select"
    assert kind_field.value == "hinge_straight"
    assert tuple(kind_field.options) == tuple(PATTERN_KIND_CHOICES)


def test_pass312_apply_collects_window_values_even_without_live_callback() -> None:
    """Regression: Apply must not depend on a fragile Qt text callback only.

    The overlay manager is the API source of truth, exactly like the metric
    validation overlay.  If a renderer updates the declarative field value but a
    live callback is missed, Apply still reads and uses that value.
    """

    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    ctx.overlay.update_field(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "9.25")
    tool.on_overlay_button_clicked(_MOTIF_BUTTON_APPLY, ctx)

    assert tool._state.motif_cell_size == pytest.approx(9.25)


def test_pass312_motif_field_ids_tolerate_overlay_renderer_prefixes() -> None:
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    handled = tool.on_overlay_field_changed(
        _MOTIF_OVERLAY_ID,
        f"{_MOTIF_OVERLAY_ID}.field.{_MOTIF_FIELD_CELL_SIZE}",
        "8.5",
        ctx,
    )

    assert handled is True
    assert tool._state.motif_cell_size == pytest.approx(8.5)


def test_pass312_apply_reads_actual_qt_widget_text_when_callbacks_are_broken() -> None:
    """Pattern Apply has a final safety net: live QLineEdit text.

    This models the real bug report where the field visibly contains the edited
    text but the tool callback/manager layer can still be stale.
    """

    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)

    class _FakeEdit:
        def __init__(self, text: str) -> None:
            self._text = text

        def text(self) -> str:
            return self._text

        def hasFocus(self) -> bool:
            return True

    fake_widget = type(
        "_FakePatternWidget",
        (),
        {
            "_tool_core_overlay_field_edits": {
                _MOTIF_FIELD_CELL_SIZE: _FakeEdit("7.5"),
                _MOTIF_FIELD_WALL: _FakeEdit("1.5"),
            }
        },
    )()
    ctx.owner = type("_FakeOwner", (), {"active_tool": tool.id, "_tool_core_overlay_widgets": {_MOTIF_OVERLAY_ID: fake_widget}})()

    tool.on_overlay_button_clicked(_MOTIF_BUTTON_APPLY, ctx)

    assert tool._state.motif_cell_size == pytest.approx(7.5)
    assert tool._state.motif_wall == pytest.approx(1.5)


def test_pass312_motif_diagnostics_log_collected_value_sources(tmp_path, monkeypatch) -> None:
    """The Pattern editor writes a JSONL trace usable on Matthis' machine."""

    monkeypatch.chdir(tmp_path)
    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "8.0", ctx)
    tool.on_overlay_button_clicked(_MOTIF_BUTTON_APPLY, ctx)

    log_path = tmp_path / "diagnostics" / "plan_trace_2d_motif_overlay_debug.jsonl"
    assert log_path.exists()
    text = log_path.read_text(encoding="utf-8")
    assert "apply.collect_values" in text
    assert _MOTIF_FIELD_CELL_SIZE in text


def test_pass312_runtime_adapter_forwards_motif_field_changes_to_creator_tool() -> None:
    """Regression from the real Qt diagnostics: ``adapter.notify_field.no_callback``.

    The Plan Tracer registry exposes a ``CreatorStudioToolAdapter`` runtime
    object, not the raw ``PlanTrace2DCreatorTool``.  If the runtime adapter does
    not forward ``on_overlay_field_changed``, Qt text edits update only the
    generic overlay manager; the Pattern state stays stale and the next refresh
    rewrites the field with the old value.
    """

    from types import SimpleNamespace

    from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DTool
    from laserprog_studio.tooling.registry import get_tool_spec

    spec = get_tool_spec("plan_trace")
    assert spec is not None
    runtime = PlanTrace2DTool(spec)
    creator = runtime.creator
    ctx = ToolContext()
    creator._state.plane = _plane()
    creator._state.sketch = _rectangle_sketch()
    face_id = next(iter(creator._state.sketch.faces.keys()))
    _select_face_in_modify(ctx, face_id)
    creator._services.overlay._last_ctx = ctx
    creator._services.motif_overlay.open(ctx)

    handled = runtime.on_overlay_field_changed(
        _MOTIF_OVERLAY_ID,
        _MOTIF_FIELD_CELL_SIZE,
        "9.25 mm",
        SimpleNamespace(tool_context=ctx),
    )

    assert handled is True
    assert creator._state.motif_cell_size == pytest.approx(9.25)
    assert creator._state.motif_pending_field_values[_MOTIF_FIELD_CELL_SIZE] == "9.25 mm"


def test_pass312_loading_named_preset_restores_kind_and_all_parameters(monkeypatch) -> None:
    from laserprog_studio.tooling.plan_trace_2d import motif_overlay as overlay_module

    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    preset = MotifPreset(
        id="user:flex",
        name="Flexible plywood",
        kind="hinge_wave",
        parameters={
            "cell_size": 6.5,
            "wall": 0.8,
            "margin": 3.0,
            "keep_form": False,
            "angle": 22.0,
            "aspect": 1.7,
            "seed": 19,
            "offset_x": 4.0,
            "offset_y": -5.0,
        },
    )
    monkeypatch.setattr(overlay_module, "load_motif_presets", lambda: (preset,))

    handled = tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_PRESET, preset.id, ctx)

    assert handled is True
    assert tool._state.motif_preset_id == preset.id
    assert tool._state.motif_preset_name == preset.name
    assert tool._state.motif_kind == "hinge_wave"
    assert tool._state.motif_cell_size == pytest.approx(6.5)
    assert tool._state.motif_wall == pytest.approx(0.8)
    assert tool._state.motif_margin == pytest.approx(3.0)
    assert tool._state.motif_keep_form is False
    assert tool._state.motif_angle == pytest.approx(22.0)
    assert tool._state.motif_aspect == pytest.approx(1.7)
    assert tool._state.motif_seed == 19
    assert tool._state.motif_offset_x == pytest.approx(4.0)
    assert tool._state.motif_offset_y == pytest.approx(-5.0)


def test_pass312_save_preset_uses_visible_name_and_current_parameters(monkeypatch) -> None:
    from laserprog_studio.tooling.plan_trace_2d import motif_overlay as overlay_module

    tool, ctx, _face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    captured = {}

    def _save(name, *, kind, parameters):
        captured.update(name=name, kind=kind, parameters=dict(parameters))
        return MotifPreset(id="user:fine", name=name, kind=kind, parameters=dict(parameters))

    monkeypatch.setattr(overlay_module, "save_motif_preset", _save)
    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_PRESET_NAME, "Fine grid", ctx)
    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "7.25", ctx)
    tool.on_overlay_button_clicked(_MOTIF_BUTTON_PRESET_SAVE, ctx)

    assert captured["name"] == "Fine grid"
    assert captured["kind"] == tool._state.motif_kind
    assert captured["parameters"]["cell_size"] == pytest.approx(7.25)
    assert set(captured["parameters"]) == {
        "cell_size", "wall", "margin", "keep_form", "angle", "aspect", "seed", "offset_x", "offset_y"
    }
    assert tool._state.motif_preset_id == "user:fine"


def test_v177_back_invalidates_pending_preview_timer_before_restore() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    tool._services.motif_overlay.open(ctx)
    tool.on_overlay_field_changed(_MOTIF_OVERLAY_ID, _MOTIF_FIELD_CELL_SIZE, "5.0", ctx)
    stale_generation = tool._state.motif_preview_generation
    assert tool._state.motif_preview_pending is True

    tool._services.motif_overlay.close(ctx, restore=True)

    assert tool._services.motif_overlay.is_open() is False
    assert tool._state.motif_preview_generation > stale_generation
    assert tool._state.motif_preview_pending is False
    assert tool._services.motif_overlay._run_scheduled_preview(ctx, stale_generation) is False
    restored_face = next(iter(tool._state.sketch.faces.values()))
    assert len(restored_face.hole_polygons) == 0


def test_v177_reapplying_pattern_replaces_unique_face_assignment_without_linework_growth() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    points_before = len(tool._state.sketch.points)
    lines_before = len(tool._state.sketch.lines)

    assert tool._services.patterns.apply_as_union_face_holes(
        ctx,
        (face_id,),
        kind="square",
        cell_size=24.0,
        wall=2.0,
        margin=2.0,
        persistent=True,
        render=False,
    )
    first_assignment = next(iter(tool._state.motif_assignments_by_outer_signature.values()))
    assert first_assignment["kind"] == "square"

    assert tool._services.patterns.apply_as_union_face_holes(
        ctx,
        (face_id,),
        kind="honeycomb",
        cell_size=18.0,
        wall=1.5,
        margin=2.0,
        persistent=True,
        render=False,
    )

    assert len(tool._state.motif_assignments_by_outer_signature) == 1
    assignment = next(iter(tool._state.motif_assignments_by_outer_signature.values()))
    assert assignment["kind"] == "honeycomb"
    assert len(tool._state.sketch.points) == points_before
    assert len(tool._state.sketch.lines) == lines_before
    assert not any(line.metadata.get("plan_trace_2d.pattern") for line in tool._state.sketch.lines.values())


def test_v177_open_existing_pattern_loads_its_parameters_for_edit_instead_of_stacking_defaults() -> None:
    tool, ctx, face_id = _tool_ready_to_open()
    assert tool._services.patterns.apply_as_union_face_holes(
        ctx,
        (face_id,),
        kind="circle",
        cell_size=17.5,
        wall=1.25,
        margin=3.5,
        angle=13.0,
        aspect=1.2,
        seed=11,
        offset_x=2.0,
        offset_y=-1.0,
        persistent=True,
        render=False,
    )
    tool._state.motif_kind = "square"
    tool._state.motif_cell_size = 99.0

    tool._services.motif_overlay.open(ctx)

    assert tool._state.motif_kind == "circle"
    assert tool._state.motif_cell_size == pytest.approx(17.5)
    assert tool._state.motif_wall == pytest.approx(1.25)
    assert tool._state.motif_margin == pytest.approx(3.5)
    assert tool._state.motif_angle == pytest.approx(13.0)
    assert tool._state.motif_offset_x == pytest.approx(2.0)
    assert tool._state.motif_offset_y == pytest.approx(-1.0)
