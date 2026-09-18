# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tool_api import styles
from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab, LabActorKind, LabInteraction
from laserprog_studio.tool_core import ToolContext


def test_pass134_selected_points_use_minimal_yellow_orange_highlight() -> None:
    expected = (0.94, 0.66, 0.02, 1.0)
    for point_style in styles.list_point_styles():
        assert point_style.color_for("selected") == expected


def test_pass134_selected_lines_use_shared_yellow_orange_payload_without_midpoint_gizmo() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diag")
    lab.setup()
    lab.set_options(actor_kind=LabActorKind.LINE.value, interaction=LabInteraction.GRABBABLE.value, line_style="grabbable")
    before = {actor.id for actor in ctx.selection.actors(owner_tool="tool_core_diag")}
    lab.add_from_options()
    actor = next(actor for actor in ctx.selection.actors(owner_tool="tool_core_diag") if actor.id not in before)

    ctx.selection.select(actor.id, replace=True)
    lab.render_visuals()

    preview = next(item for item in ctx.preview.items(owner_tool="tool_core_diag") if item.id == actor.id)
    assert preview.payload["color"] == styles.SELECTED_HIGHLIGHT_COLOR
    assert preview.payload["style_id"] == "selected"
    assert all(":mid" not in handle.id for handle in ctx.gizmos.handles(owner_tool="tool_core_diag"))


def test_pass134_empty_api_lab_press_does_not_trigger_selection_refresh_at_camera_drag_start() -> None:
    class _Owner:
        pass

    from laserprog_studio.application.tool_core_diag_controller import ToolCoreDiagController

    controller = ToolCoreDiagController.create(type("Ctx", (), {"owner": _Owner()})())
    controller.runner.run_api_lab_setup()
    controller._api_lab_active = True
    controller._last_scene_stats = {"before": 1}

    handled = controller._handle_api_lab_pointer_press(9999.0, 9999.0, shift_down=False)

    assert handled is False
    assert controller._last_scene_stats == {"before": 1}


def test_pass134_camera_size_refresh_knows_api_lab_guides_are_camera_sized() -> None:
    class _Owner:
        def __init__(self) -> None:
            self.plotter = type("Plotter", (), {"actors": {}, "height": lambda self: 800, "render": lambda self: None})()

        def _world_to_display(self, pos):
            return (float(pos[0]), float(pos[1]), 0.5)

    from laserprog_studio.application.tool_core_diag_controller import ToolCoreDiagController

    owner = _Owner()
    controller = ToolCoreDiagController.create(type("Ctx", (), {"owner": owner})())
    controller.runner.run_api_lab_setup()
    assert controller._has_camera_sized_guides() is True
