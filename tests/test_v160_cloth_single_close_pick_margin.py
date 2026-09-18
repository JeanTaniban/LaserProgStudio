from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.join_faces import analyze_textile_close_groups, commit_join_proposal
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.workspace import ClothOverlayMode
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square_mesh(z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        "support",
        [(0, 0, z), (20, 0, z), (20, 20, z), (0, 20, z)],
        [(0, 1, 2), (0, 2, 3)],
    )


def _bind_scene(ctx: ToolContext, *, z: float = 0.0):
    ctx.document.bind(SceneDocument.from_meshes("main", [_square_mesh(z)]))
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            x, y = screen_pos
            if not (0 <= x <= 20 and 0 <= y <= 20):
                return None
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": 0,
                "element_index": 0,
                "world_pos": (float(x), float(y), float(z)),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    ctx.viewport.screen_to_ray = lambda screen_pos: {
        "kind": "ray",
        "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 10.0),
        "metadata": {"direction": (0.0, 0.0, -1.0)},
    }
    return obj


def _ring_document() -> ClothDocument:
    document = ClothDocument()
    points = {
        "a": (0, 0, 0), "b": (20, 0, 0), "c": (20, 20, 0), "d": (0, 20, 0),
        "e": (5, 5, 0), "f": (15, 5, 0), "g": (15, 15, 0), "h": (5, 15, 0),
    }
    for point_id, position in points.items():
        document.add_point(position, point_id=point_id)
    for curve_id, first, second in (
        ("ab", "a", "b"), ("bc", "b", "c"), ("cd", "c", "d"), ("da", "d", "a"),
        ("ef", "e", "f"), ("fg", "f", "g"), ("gh", "g", "h"), ("he", "h", "e"),
    ):
        document.add_line(first, second, curve_id=curve_id)
    document.add_patch(
        ("ab", "bc", "cd", "da"),
        hole_curve_loops=(("ef", "fg", "gh", "he"),),
        patch_id="ring",
    )
    return document


def test_close_button_is_enabled_for_one_textile_group() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(((0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)))
    assert created.committed
    tool._set_selected_textile_groups(((created.created_patch_id,),))
    tool._sync_workspace_selection()
    assert tool._workspace.can_close


def test_close_one_annular_face_proposes_and_commits_hole_cap() -> None:
    document = _ring_document()
    proposals = analyze_textile_close_groups(document, (("ring",),))
    assert len(proposals) == 1
    assert len(proposals[0].caps) == 1
    assert proposals[0].pairs == ()
    assert proposals[0].triangle_preview

    outcome = commit_join_proposal(document, proposals[0])
    assert outcome.committed
    assert len(document.patches) == 2
    created = next(patch for patch_id, patch in document.patches.items() if patch_id != "ring")
    assert created.metadata.get("cloth_creation_kind") == "close_cap"


def test_tool_close_with_one_annular_group_stays_in_orange_submenu() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    tool._session.document = _ring_document()
    tool._drawing.document = tool._session.document
    tool._set_selected_textile_groups((("ring",),))
    tool._sync_workspace_selection()

    tool._enter_close(ctx)
    assert tool._workspace.overlay_mode is ClothOverlayMode.CLOSE
    assert tool._workspace.close_proposal_count == 1
    assert tool.interaction.join_proposals[0].caps


def test_linked_take_face_textile_wins_inside_thickness_margin() -> None:
    ctx = ToolContext()
    obj = _bind_scene(ctx, z=0.0)
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(
        ((0, 0, -0.20), (20, 0, -0.20), (20, 20, -0.20), (0, 20, -0.20)),
        metadata={"cloth_source_object_id": obj.id, "cloth_source_faces": (0, 1)},
    )
    assert created.committed

    tool._select_main(ctx, (10, 10), additive=False)
    assert created.created_patch_id in tool.session.selected_patch_ids
    assert tool.geometry_trace.smart_session.selected_region_count == 0


def test_unrelated_textile_behind_mesh_does_not_use_priority_margin() -> None:
    ctx = ToolContext()
    _bind_scene(ctx, z=0.0)
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(
        ((0, 0, -0.20), (20, 0, -0.20), (20, 20, -0.20), (0, 20, -0.20)),
    )
    assert created.committed

    tool._select_main(ctx, (10, 10), additive=False)
    assert not tool.session.selected_patch_ids
    assert tool.geometry_trace.smart_session.selected_region_count == 1


def test_close_detects_inner_loop_in_take_face_style_technical_group() -> None:
    document = ClothDocument()
    from laserprog_studio.tooling.cloth.drawing import ClothDrawingController

    drawing = ClothDrawingController(document)
    a, b, c, d = (0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)
    e, f, g, h = (5, 5, 0), (15, 5, 0), (15, 15, 0), (5, 15, 0)
    triangles = (
        (a, b, f), (a, f, e),
        (b, c, g), (b, g, f),
        (c, d, h), (c, h, g),
        (d, a, e), (d, e, h),
    )
    patch_ids = []
    for triangle in triangles:
        outcome = drawing.create_surface_from_positions(triangle)
        assert outcome.committed
        patch_ids.append(outcome.created_patch_id)

    proposals = analyze_textile_close_groups(document, (tuple(patch_ids),))
    assert proposals
    assert len(proposals[0].caps) == 1
