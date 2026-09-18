from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.picking import ClothSurfaceRaycastCache
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth.workspace import ClothOverlayMode
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _simple_document() -> ClothDocument:
    document = ClothDocument()
    for point_id, position in {
        "a": (0.0, 0.0, 0.0),
        "b": (20.0, 0.0, 0.0),
        "c": (20.0, 20.0, 0.0),
        "d": (0.0, 20.0, 0.0),
    }.items():
        document.add_point(position, point_id=point_id)
    for curve_id, start, end in (("ab", "a", "b"), ("bc", "b", "c"), ("cd", "c", "d"), ("da", "d", "a")):
        document.add_line(start, end, curve_id=curve_id)
    document.add_patch(("ab", "bc", "cd", "da"), patch_id="panel")
    return document


def test_cloth_overlay_action_ids_never_trigger_generic_window_close() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = tool._drawing.create_surface_from_positions(((20, 0, 0), (30, 0, 0), (30, 10, 0), (20, 10, 0)))
    tool._set_selected_textile_groups(((first.created_patch_id,), (second.created_patch_id,)))
    tool._sync_workspace_selection()
    tool._sync_overlay(ctx)

    main = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert main is not None
    close_button = next(button for button in main.buttons if button.display_label == "Close")
    assert "close" not in close_button.id.lower()

    tool.on_overlay_button_clicked(close_button.id, ctx)
    assert tool._workspace.overlay_mode is ClothOverlayMode.CLOSE
    submenu = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert submenu is not None
    assert all("close" not in button.id.lower() for button in submenu.buttons)


def test_textile_raycast_falls_back_to_per_patch_geometry_when_canonical_build_has_issues(monkeypatch) -> None:
    import laserprog_studio.tooling.cloth.mesh_builder as mesh_builder

    document = _simple_document()

    @dataclass
    class FailedBuild:
        mesh: object | None = None
        issues: tuple[str, ...] = ("synthetic canonical build issue",)
        patch_triangle_ranges: dict[str, tuple[int, int]] = None  # type: ignore[assignment]

        def __post_init__(self) -> None:
            if self.patch_triangle_ranges is None:
                self.patch_triangle_ranges = {}

    monkeypatch.setattr(mesh_builder, "build_cloth_surface_mesh", lambda *_args, **_kwargs: FailedBuild())

    ctx = ToolContext()
    ctx.viewport.screen_to_ray = lambda screen_pos: {
        "kind": "ray",
        "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 10.0),
        "metadata": {"direction": (0.0, 0.0, -1.0)},
    }
    cache = ClothSurfaceRaycastCache()
    hit = cache.hit(ctx, document, (10.0, 10.0))

    assert hit is not None
    assert hit.patch_id == "panel"
    assert cache.build_mode == "per_patch_fallback"
    assert cache.triangles
    assert "synthetic canonical build issue" in cache.build_issues


def test_main_selection_prefers_fallback_textile_hit_over_coincident_source_mesh(monkeypatch) -> None:
    import laserprog_studio.tooling.cloth.mesh_builder as mesh_builder
    from laserprog_studio.domain.work_model import WorkMesh
    from laserprog_studio.project.scene_document import SceneDocument

    @dataclass
    class FailedBuild:
        mesh: object | None = None
        issues: tuple[str, ...] = ("synthetic canonical build issue",)
        patch_triangle_ranges: dict[str, tuple[int, int]] = None  # type: ignore[assignment]

        def __post_init__(self) -> None:
            if self.patch_triangle_ranges is None:
                self.patch_triangle_ranges = {}

    monkeypatch.setattr(mesh_builder, "build_cloth_surface_mesh", lambda *_args, **_kwargs: FailedBuild())

    mesh = WorkMesh("support", [(0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)], [(0, 1, 2), (0, 2, 3)])
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [mesh]))
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
                "world_pos": (float(x), float(y), 0.0),
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

    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(
        ((0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)),
        metadata={"cloth_source_object_id": obj.id, "cloth_source_faces": (0, 1)},
    )
    assert created.committed

    tool._select_main(ctx, (10.0, 10.0), additive=False)
    assert tool.session.selected_patch_ids == (created.created_patch_id,)
    assert tool.geometry_trace.smart_session.selected_region_count == 0
