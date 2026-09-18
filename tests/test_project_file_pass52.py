# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.domain.material import EngravingSettings, MeshMaterial
from laserprog_studio.io import load_project, save_project_atomic
from laserprog_studio.project import ProjectStore


def make_mesh() -> WorkMesh:
    mesh = WorkMesh("part", [(0, 0, 0), (2, 0, 0), (0, 2, 0)], [(0, 1, 2)], color="#00C853")
    mesh.material = MeshMaterial(name="Green", base_color="#00C853")
    mesh.engraving = EngravingSettings(role="outline", layer="engrave", enabled=True)
    return mesh


def test_lpsproj_roundtrip_preserves_scenes_mesh_ids_and_history(tmp_path: Path) -> None:
    project = ProjectStore.new_empty()
    main = project.active_scene
    mesh = make_mesh()
    main.model_store.set_meshes([mesh])
    entry = main.record_modification("Import part", "import")
    assert entry is not None

    second = project.create_scene("second", meshes=[make_mesh()], make_active=True)
    second.record_modification("Generated scene", "scene_generated")

    path = tmp_path / "example.lpsproj"
    save_project_atomic(project, path)
    assert path.exists()
    assert project.dirty is False

    loaded = load_project(path)
    assert loaded.dirty is False
    assert len(loaded.scenes) == 2
    assert loaded.active_scene.name == "second"
    loaded_main = next(scene for scene in loaded.scenes.values() if scene.name == "main")
    assert loaded_main.meshes[0].mesh_id == mesh.mesh_id
    assert loaded_main.history[0].description == "Import part"
    assert loaded_main.history[0].snapshot_id in loaded_main.snapshots
    assert loaded_main.meshes[0].material.base_color == "#00C853"
    assert loaded_main.meshes[0].engraving.role == "outline"
