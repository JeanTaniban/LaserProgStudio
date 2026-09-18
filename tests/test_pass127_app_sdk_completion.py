# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh

from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_api import OperationResult, ToolContext


def _mesh(name: str = "mesh") -> WorkMesh:
    return WorkMesh(name=name, vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], triangles=[(0, 1, 2)])


def test_pass127_material_assets_and_engraving_are_creator_services() -> None:
    scene = SceneDocument.from_meshes("main", [_mesh("panel")])
    ctx = ToolContext(document=scene)

    material = ctx.materials.create("Birch plywood", base_color="#D8B16A", opacity=0.8)
    assigned = ctx.materials.assign(0, material)
    assert assigned.mesh.material.name == "Birch plywood"
    assert ctx.materials.get(0).base_color == "#D8B16A"

    texture = ctx.assets.import_image("/tmp/wood.png", usage="engrave", asset_id="wood")
    ctx.assets.attach_to_material(0, texture.id)
    assert ctx.materials.get(0).texture_id == "wood"
    assert ctx.assets.get_texture("wood").filename == "wood.png"

    ctx.engraving.assign_role(0, "outline")
    assert ctx.engraving.role_for(0) == "outline"
    assert getattr(ctx.document.get(0).mesh, "color") == "#00C853"


def test_pass127_planar_sdk_solves_regions_and_generates_mesh() -> None:
    ctx = ToolContext()
    ctx.planar.set_plane(origin=(10, 0, 0), normal=(0, 0, 1))
    p1 = ctx.planar.add_point(plane_pos=(0, 0), point_id="p1")
    p2 = ctx.planar.add_point(plane_pos=(4, 0), point_id="p2")
    p3 = ctx.planar.add_point(plane_pos=(4, 3), point_id="p3")
    p4 = ctx.planar.add_point(plane_pos=(0, 3), point_id="p4")
    ctx.planar.add_line(p1.id, p2.id)
    ctx.planar.add_line(p2.id, p3.id)
    ctx.planar.add_line(p3.id, p4.id)
    ctx.planar.add_line(p4.id, p1.id)

    regions = ctx.planar.solve_regions()
    assert len(regions) == 1
    assert regions[0].area == 12.0
    mesh = ctx.planar.generate_mesh(regions[0], name="plate")
    assert mesh.name == "plate"
    assert len(mesh.vertices) == 4
    assert mesh.vertices[0] == (10.0, 0.0, 0.0)


def test_pass127_high_level_gizmos_create_persistent_handles() -> None:
    ctx = ToolContext()
    plane = ctx.gizmos.plane(id="split", owner_tool="tool.split", origin=(1, 2, 3), normal=(0, 0, 2))
    assert plane.kind == "plane"
    assert set(plane.handle_ids) == {"split:origin", "split:normal"}

    triad = ctx.gizmos.triad(id="move", owner_tool="tool.move")
    assert triad.kind == "translate"
    assert len(ctx.gizmos.handles(owner_tool="tool.move")) == 4

    box = ctx.gizmos.box_bounds(id="bbox", owner_tool="tool.box", bounds=(0, 2, 0, 4, 0, 6))
    assert box.origin == (1.0, 2.0, 3.0)
    assert len(box.handle_ids) == 8


def test_pass127_standard_operations_can_delegate_to_backend_and_preview() -> None:
    class Backend(SceneDocument):
        def operation_simplify(self, inputs, params, ctx):
            factor = params.get("factor", 1)
            return OperationResult.success([*inputs, _mesh(f"simplified-{factor}")], report="simplified")

    scene = Backend.from_meshes("main", [_mesh("source")])
    ctx = ToolContext(document=scene)
    ctx.scene_selection.set_selected([0])

    result = ctx.operations.simplify(params={"factor": 2}, preview=True, owner_tool="tool.simplify")
    assert result.ok
    assert ctx.status.latest().message == "simplified"
    assert scene.model_store.has_preview
    assert [obj.name for obj in ctx.document.objects()] == ["source", "simplified-2"]

    assert ctx.preview_session.apply(label="Apply simplify")
    assert [obj.name for obj in ctx.document.objects()] == ["source", "simplified-2"]
