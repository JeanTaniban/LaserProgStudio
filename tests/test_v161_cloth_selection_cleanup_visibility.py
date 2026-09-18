from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.geometry_trace import (
    ClothGeometryTraceController,
    SourceFaceSelection,
    SourceMeshSnapshot,
)
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _strip_mesh() -> WorkMesh:
    vertices = []
    for index in range(4):
        angle = math.radians(-24.0 + index * 16.0)
        vertices.extend(((8.0 * math.sin(angle), 0.0, 8.0 * math.cos(angle)), (8.0 * math.sin(angle), 2.0, 8.0 * math.cos(angle))))
    triangles = []
    for index in range(3):
        a = 2 * index
        triangles.extend(((a, a + 2, a + 3), (a, a + 3, a + 1)))
    return WorkMesh("curved", vertices, triangles)


def test_shift_regions_that_overlap_or_touch_are_one_clean_logical_region() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_strip_mesh(), object_id="strip")
    first = surface_selection.surface_region_from_faces(snapshot, (0, 1, 2, 3), seed_face=0)
    second = surface_selection.surface_region_from_faces(snapshot, (2, 3, 4, 5), seed_face=4)
    session = surface_selection.SurfaceSelectionSession()

    session.adopt(snapshot, first)
    combined = session.add_region(snapshot, second)

    assert set(combined.face_indices) == set(range(6))
    assert session.selected_region_count == 1
    assert session.selection_mode == "exact"


def test_take_face_removes_geometrically_duplicate_triangles() -> None:
    mesh = WorkMesh(
        "duplicates",
        [(0, 0, 0), (10, 0, 0), (0, 10, 0), (0, 0, 0), (10, 0, 0), (0, 10, 0)],
        [(0, 1, 2), (3, 4, 5)],
    )
    obj = SimpleNamespace(id="mesh", name="duplicates", mesh=mesh)
    snapshot = SourceMeshSnapshot.from_object(obj, object_id=obj.id, object_index=0)
    assert snapshot is not None
    controller = ClothGeometryTraceController()
    controller.snapshots[obj.id] = snapshot
    controller.selected_faces = (SourceFaceSelection(obj.id, 0), SourceFaceSelection(obj.id, 1))
    document = ClothDocument()

    outcome = controller.create(document, ClothDrawingController(document))

    assert outcome.committed
    assert len(document.patches) == 1
    assert len(outcome.created_patch_groups) == 1


def test_take_face_welds_touching_faces_with_duplicate_vertex_ids_into_one_group() -> None:
    mesh = WorkMesh(
        "split ids",
        [
            (0, 0, 0), (10, 0, 0), (0, 10, 0),
            (10, 0, 0), (10, 10, 0), (0, 10, 0),
        ],
        [(0, 1, 2), (3, 4, 5)],
    )
    obj = SimpleNamespace(id="mesh", name="split ids", mesh=mesh)
    snapshot = SourceMeshSnapshot.from_object(obj, object_id=obj.id, object_index=0)
    assert snapshot is not None
    controller = ClothGeometryTraceController()
    controller.snapshots[obj.id] = snapshot
    controller.selected_faces = (SourceFaceSelection(obj.id, 0), SourceFaceSelection(obj.id, 1))
    document = ClothDocument()

    outcome = controller.create(document, ClothDrawingController(document))

    assert outcome.committed
    assert len(outcome.created_patch_groups) == 1
    assert len(document.patches) == 1


def test_linked_textile_priority_uses_normal_gap_at_oblique_view() -> None:
    mesh = WorkMesh(
        "support",
        [(0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0)],
        [(0, 1, 2), (0, 2, 3)],
    )
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [mesh]))
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, _screen_pos, **_filters):
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": 0,
                "element_index": 0,
                "world_pos": (10.0, 10.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    direction = (1.0, 0.0, -0.2)
    length = math.sqrt(sum(value * value for value in direction))
    direction = tuple(value / length for value in direction)
    ctx.viewport.screen_to_ray = lambda _screen_pos: {
        "kind": "ray",
        "world_pos": (0.0, 10.0, 2.0),
        "metadata": {"direction": direction},
    }

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


def test_cloth_rendering_is_more_visible_and_internal_edges_are_discreet() -> None:
    source = Path("src/laserprog_studio/tooling/cloth/rendering.py").read_text(encoding="utf-8")
    assert 'fill_opacity=0.30' in source
    assert 'internal_same_group and not detailed_edges' in source
    assert 'width = 0.55' in source
    assert 'opacity = 0.16' in source
