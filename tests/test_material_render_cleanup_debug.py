from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_material_scene_side_effects_are_centralized_and_logged() -> None:
    module = ROOT / "src" / "laserprog_studio" / "rendering" / "material_scene.py"
    text = module.read_text(encoding="utf-8")
    assert "MaterialRenderSettings" in text
    assert "disable_shadows" in text
    assert "disable_vtk_shadows" in text
    assert "material_floor_spec" in text
    assert "enable_vtk_shadows" in text
    assert "prime_vtk_shadow_maps" in text
    assert "shadow_pass_signature" in text
    assert "renderer_actor_count" in text

    controller = (ROOT / "src" / "laserprog_studio" / "controllers" / "material_tool.py").read_text(encoding="utf-8")
    assert "[MATERIAL_RENDER] sync begin" in controller
    assert "[MATERIAL_RENDER] floor cleanup" in controller
    assert "piece-only shadows: floor disabled" in controller
    assert "[MATERIAL_RENDER] real shadows disabled" in controller
    assert "[MATERIAL_RENDER] real shadows enabled" in controller
    assert "[MATERIAL_RENDER] sync end non-material" in controller
    assert "[MATERIAL_RENDER] sync end material" in controller


def test_non_material_modes_cleanup_material_floor_and_shadows() -> None:
    controller = (ROOT / "src" / "laserprog_studio" / "controllers" / "material_tool.py").read_text(encoding="utf-8")
    non_material_block = controller.split('if not settings.material_mode:', 1)[1].split('# Material mode:', 1)[0]
    assert '_remove_material_shadow_actors(reason=f"leave {settings.mode}")' in non_material_block
    assert '_remove_material_floor_actor(reason=f"leave {settings.mode}")' in non_material_block
    assert '_disable_material_shadow_pass(reason=f"leave {settings.mode}")' in non_material_block
    assert 'renderer.AutomaticLightCreationOn()' in non_material_block


def test_interaction_event_filter_is_safe_before_plotter_exists() -> None:
    interaction = (ROOT / "src" / "laserprog_studio" / "controllers" / "interaction.py").read_text(encoding="utf-8")
    assert 'plotter = getattr(self, "plotter", None)' in interaction
    assert 'if plotter is not None and obj is plotter:' in interaction
