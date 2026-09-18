from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_material_ui_has_no_render_floor_toggle() -> None:
    layout = (ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    assert "Sol de rendu" not in layout
    assert "material_render_floor" not in layout


def test_material_shadows_prime_vtk_without_floor_dependency() -> None:
    scene = (ROOT / "src" / "laserprog_studio" / "rendering" / "material_scene.py").read_text(encoding="utf-8")
    tool = (ROOT / "src" / "laserprog_studio" / "controllers" / "material_tool.py").read_text(encoding="utf-8")
    assert "vtk_shadow_maps_piece_only_v5_floor_pulse" in scene
    assert "prime_vtk_shadow_maps" in scene
    assert "vtk shadow maps floor-pulse piece-only" in scene
    assert "floor_signature" not in scene
    assert "def _sync_material_floor_actor" not in tool
    assert "receiver floor created" not in tool
    assert "piece-only shadows: floor disabled" in tool
    assert "shadow_pass_signature(settings=settings, bounds=b, mesh_count=len(meshes))" in tool
