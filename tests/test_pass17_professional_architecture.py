from __future__ import annotations

from pathlib import Path
import unittest

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.assets import RecentTextureStore
from laserprog_studio.domain import EngravingSettings, MeshDomainData, MeshMaterial, TextureProjection
from laserprog_studio.engraving import EngravingExportPlan, get_engraving_layer, iter_export_layers
from laserprog_studio.io.three_mf import MaterialExportRecord, TextureExportRecord, ThreeMfExportPlan
from laserprog_studio.primitives import build_primitive_mesh, get_primitive_spec, iter_primitive_specs
from laserprog_studio.rendering.display_modes import get_display_mode
from laserprog_studio.rendering.materials import actor_style_for_mesh
from laserprog_studio.tooling.ids import TOOL_PRIMITIVE
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec


class Pass17ProfessionalArchitectureTest(unittest.TestCase):
    def test_work_mesh_accepts_forward_compatible_domain_metadata(self):
        material = MeshMaterial(name="Oak", base_color="#AA7744", texture_id="tex_demo")
        engraving = EngravingSettings(role="fill", layer="engrave", texture_usage="engrave")
        projection = TextureProjection(texture_id="tex_demo", target_mesh_name="part", repeat=True)
        mesh = WorkMesh(
            name="part",
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            triangles=[(0, 1, 2)],
            material=material,
            engraving=engraving,
            uvs=[(0, 0), (1, 0), (0, 1)],
            texture_projections=[projection],
        )
        self.assertEqual(mesh.material.base_color, "#AA7744")
        self.assertEqual(mesh.engraving.layer, "engrave")
        self.assertTrue(mesh.texture_projections[0].repeat)
        self.assertEqual(MeshDomainData().material.base_color, "#B8B8B8")

    def test_primitive_registry_builds_predictable_meshes_without_pyvista(self):
        ids = [spec.id for spec in iter_primitive_specs()]
        self.assertTrue({"box", "cylinder", "sphere", "cone", "hex_prism"}.issubset(ids))
        box = build_primitive_mesh({"primitive_id": "box", "size_x": 10, "size_y": 20, "size_z": 30}, name_index=3)
        self.assertEqual(box.name, "box_03")
        self.assertEqual(len(box.vertices), 8)
        self.assertEqual(len(box.triangles), 12)
        hex_mesh = build_primitive_mesh({"primitive_id": "cylinder", "segments": 6}, name_index=1)
        self.assertEqual(len(hex_mesh.vertices), 14)  # 2 rings + 2 centers
        self.assertEqual(len(hex_mesh.triangles), 24)
        sphere = build_primitive_mesh({"primitive_id": "sphere", "theta_resolution": 8, "phi_resolution": 4}, name_index=1)
        self.assertEqual(len(sphere.vertices), 26)
        self.assertEqual(get_primitive_spec("unknown").id, "box")

    def test_primitive_tool_is_first_non_legacy_runtime_tool_with_parameters(self):
        spec = get_tool_spec(TOOL_PRIMITIVE)
        tool = get_studio_tool(TOOL_PRIMITIVE)
        self.assertIsNotNone(spec)
        self.assertTrue(spec.parameters)
        self.assertIsNotNone(tool)
        self.assertEqual(tool.__class__.__name__, "PrimitiveTool")
        defaults = tool.default_parameters()
        self.assertEqual(defaults["primitive_id"], "box")
        self.assertIn("segments", defaults)

    def test_rendering_material_style_contract(self):
        mesh = WorkMesh(
            name="styled",
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            triangles=[(0, 1, 2)],
            material=MeshMaterial(base_color="#336699", opacity=0.75),
        )
        solid = actor_style_for_mesh(mesh, get_display_mode("solid"))
        self.assertEqual(solid.representation, "surface")
        self.assertTrue(solid.lighting)
        self.assertFalse(solid.show_edges)
        self.assertEqual(solid.opacity, 1.0)
        self.assertEqual(solid.color, (0xB8 / 255.0, 0xB8 / 255.0, 0xB8 / 255.0))
        material = actor_style_for_mesh(mesh, get_display_mode("material"))
        self.assertEqual(material.color, (0x33 / 255.0, 0x66 / 255.0, 0x99 / 255.0))
        self.assertEqual(material.opacity, 0.75)
        wire = actor_style_for_mesh(mesh, "wireframe")
        self.assertEqual(wire.representation, "surface")
        self.assertTrue(wire.show_edges)

    def test_texture_and_export_planning_contracts(self):
        store = RecentTextureStore(limit=5)
        for i in range(7):
            store.add(Path(f"texture_{i}.png"))
        recent = store.recent_paths()
        self.assertEqual(len(recent), 5)
        self.assertEqual(recent[0].name, "texture_6.png")
        self.assertEqual(recent[-1].name, "texture_2.png")

        layers = iter_export_layers()
        self.assertEqual([layer.id for layer in layers], ["cut", "engrave"])
        self.assertEqual(get_engraving_layer("missing").id, "engrave")
        plan = EngravingExportPlan(output_dir=Path("exports"), basename="job")
        self.assertEqual(plan.output_path_for(get_engraving_layer("cut")).name, "job_cut.png")

        export_plan = ThreeMfExportPlan(
            materials=[MaterialExportRecord("mat_1", "#FFFFFF", texture_id="tex_1")],
            textures=[TextureExportRecord("tex_1", Path("a.png"), "3D/Textures/a.png")],
        )
        self.assertTrue(export_plan.has_textures)


if __name__ == "__main__":
    unittest.main()
