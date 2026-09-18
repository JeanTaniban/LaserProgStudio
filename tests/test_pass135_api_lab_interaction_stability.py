# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tool_api import styles
from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabInteraction
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.gizmos import GizmoVisualState


def test_pass135_minimal_dot_is_two_px_idle_and_three_px_active_in_api_resolver() -> None:
    idle = styles.resolve_actor_visual(
        interaction="grabbable",
        point_style_id="minimal",
        visual_state="auto",
        hover=False,
        selected=False,
        grabbed=False,
    )
    hover = styles.resolve_actor_visual(
        interaction="grabbable",
        point_style_id="minimal",
        visual_state="auto",
        hover=True,
    )
    selected = styles.resolve_actor_visual(
        interaction="grabbable",
        point_style_id="minimal",
        visual_state="auto",
        selected=True,
    )
    grabbed = styles.resolve_actor_visual(
        interaction="grabbable",
        point_style_id="minimal",
        visual_state="auto",
        grabbed=True,
    )

    assert idle.radius_px == 2
    assert hover.radius_px == 3
    assert selected.radius_px == 3
    assert grabbed.radius_px == 3


def test_pass135_minimal_dot_manager_policy_is_two_px_idle_and_three_px_active() -> None:
    ctx = ToolContext()

    assert ctx.gizmos.radius_for_style("minimal", 99, GizmoVisualState.GRABBABLE) == 2
    assert ctx.gizmos.radius_for_style("minimal", 99, GizmoVisualState.FIXED) == 2
    assert ctx.gizmos.radius_for_style("minimal", 99, GizmoVisualState.HOVER) == 3
    assert ctx.gizmos.radius_for_style("minimal", 99, GizmoVisualState.SELECTED) == 3
    assert ctx.gizmos.radius_for_style("minimal", 99, GizmoVisualState.GRABBED) == 3


def test_pass135_empty_click_clears_selection_semantically_without_immediate_render_refresh() -> None:
    class _Owner:
        pass

    from laserprog_studio.application.tool_core_diag_controller import ToolCoreDiagController

    controller = ToolCoreDiagController.create(type("Ctx", (), {"owner": _Owner()})())
    controller.runner.run_api_lab_setup()
    controller._api_lab_active = True
    actor = next(actor for actor in controller.runner.ctx.selection.actors(owner_tool="tool_core_diag") if actor.selectable)
    controller.runner.ctx.selection.select(actor.id, replace=True)
    controller._last_scene_stats = {"before": 1}

    handled_press = controller._handle_api_lab_pointer_press(9999.0, 9999.0, shift_down=False)

    assert handled_press is False
    assert controller.runner.ctx.selection.ids() == ()
    assert controller._last_scene_stats == {"before": 1}
    assert controller._api_lab_empty_press_cleared is True


def test_pass135_fixed_actor_cannot_be_selected_or_grabbed_or_moved() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="test.pass135.fixed")
    lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.FIXED.value, point_style="minimal")
    fixed_actor = lab.add_from_options()
    actor = next(actor for actor in ctx.selection.actors(owner_tool="test.pass135.fixed") if actor.points[0] == (0.0, 0.0, 0.0))

    assert actor.id.startswith("api_lab:point_")
    assert actor.selectable is False
    assert actor.grabbable is False
    assert lab.select_at((0.0, 0.0), lambda p: (float(p[0]), float(p[1]))) is None
    assert ctx.selection.ids() == ()
    assert lab.begin_grab_if_possible(actor.id, (0.0, 0.0), actor.points[0]) == ()
    assert lab.move_selected((10.0, 0.0, 0.0)) == 0
    assert ctx.selection.actor(actor.id).points[0] == (0.0, 0.0, 0.0)


def test_pass135_reregistering_actor_as_fixed_drops_stale_selection_and_grab_state() -> None:
    from laserprog_studio.tool_api import actors

    ctx = ToolContext()
    registry = ctx.actor_registry("test.pass135.stale")
    actor = registry.add(actors.point("same-id", (0, 0, 0), interaction="grabbable"))
    assert ctx.selection.select(actor.id) is True
    assert ctx.selection.begin_grab(actor.id, (0, 0), actor.points[0]) == (actor.id,)

    registry.add(actors.point("same-id", (0, 0, 0), interaction="fixed"), replace=True)

    assert ctx.selection.ids() == ()
    assert ctx.selection.state.grabbed_ids == ()
    assert ctx.selection.state.grab_active is False
    assert ctx.selection.hit_test((0, 0), lambda p: (float(p[0]), float(p[1])), owner_tool="test.pass135.stale", selectable_only=True) is None


def test_pass135_selecting_line_after_multiple_adds_keeps_all_lab_visuals_declared() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="test.pass135.visuals")
    lab.setup()
    for _ in range(3):
        lab.set_options(actor_kind=LabActorKind.POINT.value, interaction=LabInteraction.GRABBABLE.value, point_style="minimal")
        lab.add_from_options()
    lab.set_options(actor_kind=LabActorKind.LINE.value, interaction=LabInteraction.SELECTABLE.value, line_style="selectable")
    before = {actor.id for actor in ctx.selection.actors(owner_tool="test.pass135.visuals")}
    lab.add_from_options()
    line = next(actor for actor in ctx.selection.actors(owner_tool="test.pass135.visuals") if actor.id not in before)

    assert ctx.selection.select(line.id, replace=True) is True
    snapshot = lab.render_visuals()

    point_count = len([actor for actor in ctx.selection.actors(owner_tool="test.pass135.visuals") if str(actor.kind.value if hasattr(actor.kind, "value") else actor.kind) == "point"])
    line_preview_ids = {item.id for item in ctx.preview.items(owner_tool="test.pass135.visuals")}
    visible_handles = [handle for handle in ctx.gizmos.handles(owner_tool="test.pass135.visuals") if handle.visible]

    assert line.id in line_preview_ids
    assert snapshot.previews >= 1
    assert len(visible_handles) >= point_count
    assert all(":mid" not in handle.id for handle in ctx.gizmos.handles(owner_tool="test.pass135.visuals"))
