from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _RecordingScene:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.logs: list[str] = []

    def pick_face_at(self, screen_pos, **filters):
        self.calls.append(("face", dict(filters)))
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(screen_pos[0]), float(screen_pos[1]), 9.0),
            object_id="all_parts_face",
            object_index=7,
        )

    def pick_object_at(self, screen_pos, **filters):
        self.calls.append(("object", dict(filters)))
        return PickResult.none(screen_pos)

    def ui_log(self, message: str) -> None:
        self.logs.append(str(message))


def _ctx(scene=None) -> ToolContext:
    ctx = ToolContext()
    ctx.scene = scene if scene is not None else _RecordingScene()
    ctx.pick.bind_context(ctx)
    return ctx


def test_plan_anchor_raycast_requests_all_scene_parts_and_records_diagnostics() -> None:
    scene = _RecordingScene()
    ctx = _ctx(scene)

    picked = plan2d.pick_plan_anchor_by_raycast(ctx, (10.0, 20.0), view="top", log_diagnostics=True, diagnostics_label="test")

    assert picked.hit is True
    assert picked.plane.depth == 9.0
    assert scene.calls[0] == ("face", {"all_parts": True, "only_selected": False})
    assert picked.diagnostics["backend"] == "ctx.pick.face_at"
    assert picked.diagnostics["result"] == "hit"
    assert any("[PLAN_TRACE_RAYCAST] test" in line for line in scene.logs)


def test_overlay_manager_updates_window_button_specs_immediately_for_exclusive_groups() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)

    assert ctx.overlay.toggle_button("plan_trace_2d.tool.line") is True
    toolbox = ctx.overlay.window("plan_trace_2d.toolbox")
    assert toolbox is not None
    checked = [button.id for button in toolbox.buttons if button.checked]
    assert checked == ["plan_trace_2d.tool.line"]


def test_plan_tool_overlay_click_updates_mode_and_highlight_without_waiting_for_hover() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)

    ctx.overlay.toggle_button("plan_trace_2d.tool.rectangle")
    tool.on_overlay_button_clicked("plan_trace_2d.tool.rectangle", ctx)

    assert tool._state.active_tool == "rectangle"
    toolbox = ctx.overlay.window("plan_trace_2d.toolbox")
    assert toolbox is not None
    assert toolbox.overlay_kind == "command_deck"
    assert [field.id for field in toolbox.fields] == ["plan_trace_2d.mode_badge", "plan_trace_2d.command_status"]
    assert toolbox.fields[0].value == "Rectangle"
    assert [button.id for button in toolbox.buttons if button.checked] == ["plan_trace_2d.tool.rectangle"]
    mode_buttons = [button for button in toolbox.buttons if button.group == "plan_trace_2d.tool"]
    assert mode_buttons and all(button.style == "mode" for button in mode_buttons)
    delete_button = next(button for button in toolbox.buttons if button.id == "plan_trace_2d.action.delete")
    assert delete_button.style == "ghost"
    assert toolbox.buttons[-1].id == "plan_trace_2d.validation.subtract"


def test_scene_cache_discovers_document_mesh_targets_for_plan_smart_snap() -> None:
    from laserprog_studio.domain.work_model import WorkMesh
    from laserprog_studio.planar_tools import make_locked_plane
    from laserprog_studio.tool_core.snap.types import SnapSource

    ctx = ToolContext()
    mesh = WorkMesh(
        "snap_part",
        [(10.0, 20.0, 9.0), (40.0, 20.0, 9.0), (10.0, 50.0, 9.0)],
        [(0, 1, 2)],
    )
    ctx.document.bind(type("Doc", (), {"meshes": [mesh]})())
    ctx.scene_cache.rebuild(ctx, scope="snap")

    targets = tuple(ctx.scene_cache.snap_targets())
    assert any(target.source == SnapSource.MESH_VERTEX for target in targets)
    assert any(target.source == SnapSource.MESH_EDGE for target in targets)

    plane = make_locked_plane("top", depth=9.75)
    snap = plan2d.smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace_2d",
        plane=plane,
        candidate_world=(10.2, 20.2, 9.75),
        screen_pos=(10.2, 20.2),
        rebuild_cache=False,
    )

    assert snap.snapped is True
    assert snap.source == SnapSource.MESH_VERTEX.value
    assert snap.world_pos == (10.0, 20.0, 9.75)


def test_qt_overlay_adapter_uses_exclusive_button_groups_and_transform_style() -> None:
    from pathlib import Path

    source = read_qt_overlay_runtime_source()

    assert "QButtonGroup" in source
    assert "group.setExclusive(True)" in source
    assert "_tool_core_overlay_button_groups" in source
    assert "ToolCoreOverlayButton" in source
    assert "_paint_overlay_frame" in source
