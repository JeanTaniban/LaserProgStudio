from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.planar_tools import FixedPlanarView, make_locked_plane
from laserprog_studio.tooling.cloth.geometry_trace import (
    SourceEdgeSelection,
    SourceFaceSelection,
    SourceMeshSnapshot,
)
from laserprog_studio.tooling.plan_trace_2d.constants import _MODE_MESH_TRACE
from laserprog_studio.tooling.plan_trace_2d.mesh_trace import build_projected_trace_plan
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _tilted_square() -> SourceMeshSnapshot:
    return SourceMeshSnapshot(
        "source",
        0,
        "Tilted square",
        (
            (0.0, 0.0, 5.0),
            (10.0, 0.0, 5.0),
            (10.0, 10.0, 10.0),
            (0.0, 10.0, 10.0),
        ),
        ((0, 1, 2), (0, 2, 3)),
    )


def test_face_trace_projects_to_active_plane_and_removes_triangle_diagonal() -> None:
    tool = PlanTrace2DCreatorTool()
    controller = tool._services.mesh_trace.controller
    snapshot = _tilted_square()
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_faces = (
        SourceFaceSelection(snapshot.object_id, 0),
        SourceFaceSelection(snapshot.object_id, 1),
    )

    plan = build_projected_trace_plan(controller, make_locked_plane(FixedPlanarView.TOP, depth=0.0))

    assert len(plan.segments) == 4
    assert plan.duplicate_edge_count == 0
    assert plan.collapsed_edge_count == 0
    assert plan.maximum_projection_distance == 10.0
    assert ((0.0, 0.0), (10.0, 10.0)) not in plan.segments


def test_projection_merges_near_coincident_vertices_from_different_parts() -> None:
    tool = PlanTrace2DCreatorTool()
    controller = tool._services.mesh_trace.controller
    first = SourceMeshSnapshot("a", 0, "A", ((0.0, 0.0, 2.0), (10.0, 0.0, 2.0), (0.0, 1.0, 2.0)), ((0, 1, 2),))
    second = SourceMeshSnapshot("b", 1, "B", ((10.0 + 1.0e-7, 0.0, -4.0), (20.0, 0.0, -4.0), (20.0, 1.0, -4.0)), ((0, 1, 2),))
    controller.snapshots.update({"a": first, "b": second})
    controller.selected_edges = (
        SourceEdgeSelection("a", (0, 1)),
        SourceEdgeSelection("b", (0, 1)),
    )

    plan = build_projected_trace_plan(controller, make_locked_plane(FixedPlanarView.TOP, depth=0.0))

    assert len(plan.segments) == 2
    assert plan.segments[0][1] == plan.segments[1][0]


def test_edges_normal_to_active_plane_are_ignored_as_collapsed() -> None:
    tool = PlanTrace2DCreatorTool()
    controller = tool._services.mesh_trace.controller
    source = SourceMeshSnapshot(
        "vertical",
        0,
        "Vertical",
        ((3.0, 4.0, 0.0), (3.0, 4.0, 10.0), (4.0, 4.0, 0.0)),
        ((0, 1, 2),),
    )
    controller.snapshots["vertical"] = source
    controller.selected_edges = (SourceEdgeSelection("vertical", (0, 1)),)

    plan = build_projected_trace_plan(controller, make_locked_plane(FixedPlanarView.TOP, depth=0.0))

    assert not plan.segments
    assert plan.collapsed_edge_count == 1


def test_trace_creation_builds_a_real_plan_tracer_face_and_is_undoable() -> None:
    tool = PlanTrace2DCreatorTool()
    plane = make_locked_plane(FixedPlanarView.TOP, depth=0.0)
    tool._state.plane = plane
    tool._state.display_plane = plane
    controller = tool._services.mesh_trace.controller
    source = _tilted_square()
    controller.snapshots[source.object_id] = source
    controller.selected_faces = (
        SourceFaceSelection(source.object_id, 0),
        SourceFaceSelection(source.object_id, 1),
    )

    recorded: list[str] = []
    tool._services.sketch_sync._compile_and_sync_sketch = lambda ctx, render=False: tool._state.sketch.compile()
    tool._services.history._record_snapshot_command = lambda ctx, label, before: recorded.append(label)

    outcome = tool._services.mesh_trace.create(SimpleNamespace())

    assert outcome.committed
    assert len(outcome.created_line_ids) == 4
    assert len(tool._state.sketch.lines) == 4
    assert len(tool._state.sketch.faces) == 1
    assert recorded == ["Trace mesh into Plan Tracer"]
    assert all(line.metadata.get("generated_by") == "mesh_trace" for line in tool._state.sketch.lines.values())


def test_mesh_trace_is_exposed_as_a_real_plan_tracer_mode() -> None:
    tool = PlanTrace2DCreatorTool()
    sections = tool._services.overlay._toolbar_sections(None)
    modes = [mode for section in sections for mode in section.modes]

    assert _MODE_MESH_TRACE in tuple(tool._services.mode_state._normalize_tool_mode(mode.id.rsplit(".", 1)[-1]) for mode in modes)
    mesh_mode = next(mode for mode in modes if mode.id.endswith(".mesh_trace"))
    assert mesh_mode.enabled
    assert mesh_mode.display_label == "Mesh trace"


def test_real_mesh_trace_workflow_projects_grows_traces_and_returns_to_modify() -> None:
    from laserprog_studio.domain.work_model import WorkMesh
    from laserprog_studio.project.scene_document import SceneDocument
    from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
    from laserprog_studio.tool_core.app_services import PickResult
    from laserprog_studio.tooling.plan_trace_2d.mesh_trace import (
        PLAN_TRACE_MESH_TRACE_ACTION_PREFIX,
        PLAN_TRACE_MESH_TRACE_WINDOW_ID,
    )

    mesh = WorkMesh(
        name="Tilted source",
        vertices=list(_tilted_square().vertices),
        triangles=list(_tilted_square().triangles),
    )
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [mesh]))
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            return PickResult(
                "face",
                screen_pos=screen_pos,
                world_pos=(5.0, 2.0, 7.0),
                object_id=obj.id,
                object_index=0,
                element_index=0,
                normal=(0.0, -0.4472135955, 0.894427191),
            )

    ctx.scene = Scene()
    ctx.pick.bind_context(ctx)
    tool = PlanTrace2DCreatorTool()
    plane = make_locked_plane(FixedPlanarView.TOP, depth=0.0)
    tool._state.plane = plane
    tool._state.display_plane = plane
    tool._state.phase = "draw"

    tool._set_active_tool(ctx, _MODE_MESH_TRACE, reason="test", render=False)
    assert ctx.overlay.window(PLAN_TRACE_MESH_TRACE_WINDOW_ID) is not None
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(5.0, 2.0), button=MouseButton.LEFT),
        ctx,
    )
    tool.on_overlay_button_clicked(f"{PLAN_TRACE_MESH_TRACE_ACTION_PREFIX}grow_coplanar", ctx)
    assert len(tool._services.mesh_trace.controller.selected_faces) == 2

    tool.on_overlay_button_clicked(f"{PLAN_TRACE_MESH_TRACE_ACTION_PREFIX}trace_selection", ctx)

    assert tool._state.active_tool == "modify"
    assert len(tool._state.sketch.lines) == 4
    assert len(tool._state.sketch.faces) == 1
    assert tool._services.mesh_trace.controller.selection_count == 0
    assert not ctx.overlay.window(PLAN_TRACE_MESH_TRACE_WINDOW_ID).visible


def test_projection_uses_the_active_front_plane_axes_not_global_xy() -> None:
    tool = PlanTrace2DCreatorTool()
    controller = tool._services.mesh_trace.controller
    source = SourceMeshSnapshot(
        "front-source",
        0,
        "Front source",
        (
            (2.0, 9.0, 3.0),
            (12.0, -4.0, 3.0),
            (12.0, 7.0, 13.0),
        ),
        ((0, 1, 2),),
    )
    controller.snapshots[source.object_id] = source
    controller.selected_edges = (
        SourceEdgeSelection(source.object_id, (0, 1)),
        SourceEdgeSelection(source.object_id, (1, 2)),
    )

    plan = build_projected_trace_plan(controller, make_locked_plane(FixedPlanarView.FRONT, depth=-2.0))

    # FRONT uses world X as sketch U and world Z as sketch V. World Y is only
    # the projection depth and must not leak into the resulting 2D geometry.
    assert plan.segments == (
        ((2.0, 3.0), (12.0, 3.0)),
        ((12.0, 3.0), (12.0, 13.0)),
    )
    assert plan.maximum_projection_distance == 7.0


def test_projection_uses_the_active_right_plane_axes_and_orientation() -> None:
    tool = PlanTrace2DCreatorTool()
    controller = tool._services.mesh_trace.controller
    source = SourceMeshSnapshot(
        "right-source",
        0,
        "Right source",
        (
            (8.0, 2.0, 4.0),
            (-3.0, 12.0, 4.0),
        ),
        ((0, 1, 1),),
    )
    controller.snapshots[source.object_id] = source
    controller.selected_edges = (SourceEdgeSelection(source.object_id, (0, 1)),)

    plan = build_projected_trace_plan(controller, make_locked_plane(FixedPlanarView.RIGHT, depth=1.0))

    # RIGHT looks along +X and defines U along -Y, V along +Z.
    assert plan.segments == (((-2.0, 4.0), (-12.0, 4.0)),)
    assert plan.maximum_projection_distance == 7.0
