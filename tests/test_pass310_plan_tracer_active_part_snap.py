from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.planar_tools import FixedPlanarView, make_locked_plane
from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.snap.types import SnapSource, SnapTarget
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tooling.plan_trace_2d.panel import build_plan_trace_2d_panel


class _IdentityViewport:
    @staticmethod
    def world_to_screen(pos):
        return (float(pos[0]), float(pos[1]))

    @staticmethod
    def request_full_render():
        return True

    @staticmethod
    def request_light_render():
        return True


class _PickFacade:
    def __init__(self, object_id: str = "active", object_index: int = 0):
        self.object_id = object_id
        self.object_index = object_index

    def face_at(self, screen_pos, all_parts=True, only_selected=False):  # noqa: ARG002
        return SimpleNamespace(
            hit=True,
            kind="face",
            screen_pos=screen_pos,
            world_pos=(0.0, 0.0, 0.0),
            object_id=self.object_id,
            object_index=self.object_index,
            normal=(0.0, 0.0, 1.0),
        )


class _Document:
    def __init__(self):
        active_mesh = SimpleNamespace(mesh_id="active_mesh", name="ActiveMesh", vertices=((0, 0, 0),), triangles=())
        other_mesh = SimpleNamespace(mesh_id="other_mesh", name="OtherMesh", vertices=((100, 0, 0),), triangles=())
        self._objects = (
            SimpleNamespace(id="active", name="Active part", mesh=active_mesh),
            SimpleNamespace(id="other", name="Other part", mesh=other_mesh),
        )

    def ensure(self):
        return None

    def objects(self, include_preview=False):  # noqa: ARG002
        return self._objects

    def get(self, key):
        if isinstance(key, int):
            return self._objects[key]
        for obj in self._objects:
            if obj.id == key or obj.name == key:
                return obj
        raise KeyError(key)


def test_plan_tracer_panel_exposes_active_part_snap_toggle() -> None:
    panel = build_plan_trace_2d_panel(
        on_mode_changed=lambda _field, _value: None,
        on_settings_changed=lambda _field, _value: None,
        on_action=lambda _event: None,
    )
    field = next(field for field in panel.fields() if field.id == "plan_trace_2d.active_part_snap")
    assert field.default is False

    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool.on_open(ctx)
    ctx.inspector.update_value("plan_trace_2d.active_part_snap", True)
    tool._services.overlay._apply_panel_settings(ctx)
    assert tool._state.snap_active_object_only is True


def test_snap_manager_can_filter_scene_targets_to_active_object() -> None:
    ctx = ToolContext()
    ctx.viewport = _IdentityViewport()
    ctx.scene_cache.set_snap_targets(
        (
            SnapTarget.point("active_vertex", (0.0, 0.0, 0.0), source=SnapSource.MESH_VERTEX, radius_px=12.0, priority=10, metadata={"object_id": "active", "object_index": 0}),
            SnapTarget.point("other_vertex", (100.0, 0.0, 0.0), source=SnapSource.MESH_VERTEX, radius_px=12.0, priority=10, metadata={"object_id": "other", "object_index": 1}),
        )
    )

    blocked = ctx.snap.smart(
        (100.0, 0.0, 0.0),
        (100.0, 0.0),
        ctx,
        allowed_object_ids=("active",),
        allowed_object_indices=(0,),
        rebuild_cache=False,
    )
    assert not blocked.snapped

    allowed = ctx.snap.smart(
        (0.0, 0.0, 0.0),
        (0.0, 0.0),
        ctx,
        allowed_object_ids=("active",),
        allowed_object_indices=(0,),
        rebuild_cache=False,
    )
    assert allowed.snapped
    assert allowed.source_id == "active_vertex"


def test_plan_tracer_records_clicked_face_as_active_snap_object() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext(document=_Document())
    ctx.viewport = _IdentityViewport()
    ctx.pick = _PickFacade(object_id="mesh:0", object_index=0)
    ctx.owner = SimpleNamespace(_qt_click_pos=None, _qt_click_time=0.0)
    tool.on_open(ctx)

    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 10.0), button="left"), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(10.0, 10.0), button="left"), ctx)

    assert "mesh:0" in tool._state.active_snap_object_ids
    assert 0 in tool._state.active_snap_object_indices


def test_plan2d_alignment_guides_respect_active_object_scope() -> None:
    ctx = ToolContext()
    ctx.viewport = _IdentityViewport()
    ctx.scene_cache.set_snap_targets(
        (
            SnapTarget.point(
                "inactive_guide",
                (100.0, 50.0, 0.0),
                source=SnapSource.MESH_VERTEX,
                radius_px=12.0,
                priority=10,
                metadata={"object_id": "other", "object_index": 1},
            ),
        )
    )
    plane = make_locked_plane(FixedPlanarView.TOP, depth=0.0)

    scene_wide = plan2d.smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace",
        plane=plane,
        candidate_world=(100.0, 0.0, 0.0),
        screen_pos=(100.0, 0.0),
        rebuild_cache=False,
    )
    assert scene_wide.snapped

    active_only = plan2d.smart_snap_on_plan(
        ctx,
        owner_tool="plan_trace",
        plane=plane,
        candidate_world=(100.0, 0.0, 0.0),
        screen_pos=(100.0, 0.0),
        allowed_object_ids=("active",),
        allowed_object_indices=(0,),
        rebuild_cache=False,
    )
    assert not active_only.snapped
