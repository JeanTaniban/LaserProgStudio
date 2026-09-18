from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.join_faces import (
    _translated_vertex_correspondence_strategies,
    _vertex_anchored_rails,
    _vertex_complete_boundary_strategy,
)
from laserprog_studio.tooling.cloth.picking import ClothSurfaceRaycastCache
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _bind_square_scene(ctx: ToolContext):
    mesh = WorkMesh(
        "support",
        [(0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)],
        [(0, 1, 2), (0, 2, 3)],
    )
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
    return obj


def test_projected_take_face_textile_wins_when_triangle_raycast_misses(monkeypatch) -> None:
    ctx = ToolContext()
    obj = _bind_square_scene(ctx)
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(
        ((0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)),
        metadata={"cloth_source_object_id": obj.id, "cloth_source_faces": (0,)},
    )
    assert created.committed
    monkeypatch.setattr(ClothSurfaceRaycastCache, "hit", lambda *_args, **_kwargs: None)

    tool._select_main(ctx, (10.0, 10.0), additive=False)

    assert tool.session.selected_patch_ids == (created.created_patch_id,)
    assert tool.geometry_trace.smart_session.selected_region_count == 0


def test_projected_textile_from_another_triangle_does_not_steal_mesh_click(monkeypatch) -> None:
    ctx = ToolContext()
    obj = _bind_square_scene(ctx)
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(
        ((0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)),
        metadata={"cloth_source_object_id": obj.id, "cloth_source_faces": (1,)},
    )
    assert created.committed
    monkeypatch.setattr(ClothSurfaceRaycastCache, "hit", lambda *_args, **_kwargs: None)

    tool._select_main(ctx, (10.0, 10.0), additive=False)

    assert not tool.session.selected_patch_ids
    assert tool.geometry_trace.smart_session.selected_region_count == 1


def test_vertex_anchored_rails_preserve_authored_endpoints_and_corners() -> None:
    first = ((0.0, 0.0, 0.0), (0.0, 30.0, 0.0), (10.0, 30.0, 0.0), (10.0, 100.0, 0.0))
    second = ((30.0, 0.0, 0.0), (30.0, 55.0, 0.0), (42.0, 55.0, 0.0), (42.0, 100.0, 0.0))

    aligned = _vertex_anchored_rails(first, second, 8, 72)

    assert aligned is not None
    rail_a, rail_b = aligned
    assert rail_a[0] == first[0] and rail_a[-1] == first[-1]
    assert rail_b[0] == second[0] and rail_b[-1] == second[-1]
    assert all(vertex in rail_a for vertex in first)
    assert all(vertex in rail_b for vertex in second)


def _u_boundary(z: float, scale: float = 1.0):
    return tuple(
        (x * scale, y, z)
        for x, y in (
            (0, 100), (0, 20), (2, 10), (8, 2), (20, 0), (32, 2),
            (38, 10), (40, 20), (40, 100), (34, 100), (34, 22),
            (32, 14), (27, 8), (20, 6), (13, 8), (8, 14), (6, 22), (6, 100),
        )
    )


def test_vertex_correspondence_generates_long_homologous_u_paths() -> None:
    first = _u_boundary(0.0)
    second = _u_boundary(25.0, 1.02)

    strategies = _translated_vertex_correspondence_strategies(
        "first",
        first,
        "second",
        second,
        8,
        72,
    )

    assert strategies
    assert strategies[0].coverage >= 0.90
    pair = strategies[0].pairs[0]
    assert pair.strategy.startswith("vertex_correspondence")
    assert pair.first_rail[0] in first and pair.first_rail[-1] in first
    assert pair.second_rail[0] in second and pair.second_rail[-1] in second


def test_vertex_complete_boundary_uses_authored_u_vertices() -> None:
    first = _u_boundary(0.0)
    second = _u_boundary(25.0)

    strategy = _vertex_complete_boundary_strategy(
        "first",
        first,
        "second",
        second,
        8,
        72,
    )

    assert strategy is not None
    pair = strategy.pairs[0]
    assert pair.strategy == "complete_boundary_vertex"
    assert pair.coverage_first == 1.0 and pair.coverage_second == 1.0
    assert all(vertex in pair.first_rail for vertex in first)
    assert all(vertex in pair.second_rail for vertex in second)
