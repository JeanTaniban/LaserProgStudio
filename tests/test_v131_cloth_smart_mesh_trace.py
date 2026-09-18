# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.geometry_overlay import CLOTH_GEOMETRY_ACTION_PREFIX, CLOTH_GEOMETRY_WINDOW_ID
from laserprog_studio.tooling.cloth.geometry_trace import (
    ClothGeometryTraceController,
    SourceEdgeSelection,
    SourceMeshSnapshot,
    directional_edge_continuation,
)
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _context(mesh: WorkMesh | None = None) -> ToolContext:
    ctx = ToolContext()
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    if mesh is not None:
        ctx.document.bind(SceneDocument.from_meshes("main", [mesh]))
    return ctx


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float) -> bool:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT)
    assert tool.on_event(press, ctx) is False
    return bool(tool.on_event(release, ctx))


def test_clicking_transient_first_polyline_node_closes_and_creates_face() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    drawing.begin("polyline")
    assert drawing.add_position((0.0, 0.0, 0.0)).accepted
    assert drawing.add_position((20.0, 0.0, 0.0)).accepted
    assert drawing.add_position((20.0, 10.0, 0.0)).accepted

    outcome = drawing.add_position((0.0, 0.0, 0.0), closure_tolerance=1.0e-4)

    assert outcome.committed
    assert outcome.created_patch_id is not None
    assert len(document.patches) == 1
    assert len(document.curves) == 3
    assert not drawing.pending_world_points


def test_double_click_closes_existing_polyline_without_duplicate_endpoint() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    assert _click(tool, ctx, 0.0, 0.0)
    assert _click(tool, ctx, 20.0, 0.0)
    assert _click(tool, ctx, 20.0, 10.0)

    double = ToolEvent(
        ToolEventType.MOUSE_DOUBLE_CLICK,
        screen_pos=(20.0, 10.0),
        world_pos=(20.0, 10.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert tool.on_event(double, ctx)
    assert len(tool.session.document.patches) == 1
    assert len(tool.session.document.curves) == 3
    assert not tool._drawing.pending_world_points


def test_clicking_first_visible_node_through_tool_closes_polyline() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    assert _click(tool, ctx, 0.0, 0.0)
    assert _click(tool, ctx, 20.0, 0.0)
    assert _click(tool, ctx, 20.0, 10.0)

    assert _click(tool, ctx, 0.0, 0.0)

    assert len(tool.session.document.patches) == 1
    assert len(tool.session.document.curves) == 3
    assert not tool._drawing.pending_world_points


def _square_mesh() -> WorkMesh:
    return WorkMesh(
        name="Square source",
        vertices=[(0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
    )


def test_mesh_trace_overlay_starts_disabled_then_enables_reliable_face_help() -> None:
    mesh = _square_mesh()
    ctx = _context(mesh)
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": 0,
                "element_index": 0,
                "world_pos": (5.0, 2.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_mesh_trace", ctx)

    initial = {button.id: button for button in ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID).buttons}
    assert not initial[f"{CLOTH_GEOMETRY_ACTION_PREFIX}grow_coplanar"].enabled
    assert not initial[f"{CLOTH_GEOMETRY_ACTION_PREFIX}use_boundary"].enabled
    assert not initial[f"{CLOTH_GEOMETRY_ACTION_PREFIX}trace_selection"].enabled

    assert _click(tool, ctx, 5.0, 2.0)
    selected = {button.id: button for button in ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID).buttons}
    assert selected[f"{CLOTH_GEOMETRY_ACTION_PREFIX}grow_coplanar"].enabled
    assert selected[f"{CLOTH_GEOMETRY_ACTION_PREFIX}use_boundary"].enabled
    assert selected[f"{CLOTH_GEOMETRY_ACTION_PREFIX}trace_selection"].enabled


def test_coplanar_face_growth_traces_one_clean_quad_without_internal_diagonal() -> None:
    mesh = _square_mesh()
    ctx = _context(mesh)
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, _screen_pos, **_filters):
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": 0,
                "element_index": 0,
                "world_pos": (5.0, 2.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_mesh_trace", ctx)
    assert _click(tool, ctx, 5.0, 2.0)
    tool.on_overlay_button_clicked(f"{CLOTH_GEOMETRY_ACTION_PREFIX}grow_coplanar", ctx)
    assert len(tool.geometry_trace.selected_faces) == 2

    tool.on_overlay_button_clicked(f"{CLOTH_GEOMETRY_ACTION_PREFIX}trace_selection", ctx)

    assert len(tool.session.document.patches) == 1
    patch = next(iter(tool.session.document.patches.values()))
    assert len(patch.outer_curve_ids) == 4
    assert len(tool.session.document.curves) == 4
    assert len(tool.session.document.points) == 4
    assert tool.session.edit_mode.value == "modify"
    assert tool._interaction.stage.value == "draw"
    assert tool.geometry_trace.selection_count == 0


def test_directional_edge_prediction_follows_collinear_conjoint_edges() -> None:
    snapshot = SourceMeshSnapshot(
        "strip",
        0,
        "Strip",
        ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0), (0.0, 5.0, 0.0), (10.0, 5.0, 0.0), (20.0, 5.0, 0.0)),
        ((0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4)),
    )
    predicted = directional_edge_continuation(snapshot, ((0, 1),))
    assert (1, 2) in predicted


def test_boundary_prediction_can_be_promoted_to_edge_selection() -> None:
    controller = ClothGeometryTraceController()
    snapshot = SourceMeshSnapshot(
        "square",
        0,
        "Square",
        tuple(_square_mesh().vertices),
        tuple(_square_mesh().triangles),
    )
    controller.snapshots["square"] = snapshot
    controller.selected_faces = (
        __import__("laserprog_studio.tooling.cloth.geometry_trace", fromlist=["SourceFaceSelection"]).SourceFaceSelection("square", 0),
        __import__("laserprog_studio.tooling.cloth.geometry_trace", fromlist=["SourceFaceSelection"]).SourceFaceSelection("square", 1),
    )
    assert len(controller.predictions().boundary_edges) == 4
    assert controller.apply_prediction("boundary") == 4
    assert len(controller.selected_edges) == 4
    assert all(isinstance(item, SourceEdgeSelection) for item in controller.selected_edges)


def test_face_pick_maps_display_actor_cell_back_to_source_triangle() -> None:
    mesh = _square_mesh()
    ctx = _context(mesh)
    obj = ctx.document.objects()[0]
    controller = ClothGeometryTraceController()

    # Actor cell id is deliberately unrelated to source triangle order, while
    # its displayed vertices identify source triangle 1.
    pick = type(
        "Pick",
        (),
        {
            "object_id": obj.id,
            "object_index": 0,
            "element_index": 99,
            "world_pos": (6.0, 7.0, 0.0),
            "normal": (0.0, 0.0, 1.0),
            "metadata": {
                "face_vertices": ((0.0, 0.0, 0.0), (20.0, 10.0, 0.0), (0.0, 10.0, 0.0))
            },
        },
    )()

    face = controller._face_from_pick(ctx, pick)

    assert face is not None
    assert face.face_index == 1
