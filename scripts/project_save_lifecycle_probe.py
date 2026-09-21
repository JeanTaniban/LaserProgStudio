# -*- coding: utf-8 -*-
"""Measure project-save retention after geometry is deleted.

The probe distinguishes:
1. current scene state;
2. persistent semantic scene snapshots;
3. transient ModelStore undo/redo state;
4. complete scene removal.

It is diagnostic and intentionally does not modify production behavior.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import time
import zipfile

import numpy as np

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.io.project_file import save_project_atomic
from laserprog_studio.project import ProjectStore


def _heavy_mesh(name: str, *, seed: int, vertex_count: int = 24000, triangle_count: int = 48000) -> WorkMesh:
    rng = np.random.default_rng(int(seed))
    # Irregular deterministic values avoid unrealistically high compression.
    vertices = rng.normal(0.0, 50.0, size=(vertex_count, 3)).astype(np.float64)
    triangles = rng.integers(0, vertex_count, size=(triangle_count, 3), dtype=np.int64)
    # Ensure three distinct indices per triangle so the payload resembles a normal mesh.
    for row in triangles:
        if row[1] == row[0]:
            row[1] = (int(row[1]) + 1) % vertex_count
        if row[2] in (row[0], row[1]):
            row[2] = (int(row[2]) + 2) % vertex_count
    return WorkMesh(
        name=name,
        vertices=[tuple(map(float, row)) for row in vertices],
        triangles=[tuple(map(int, row)) for row in triangles],
    )


def _archive_stats(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path, "r") as zf:
        names = [info.filename for info in zf.infolist()]
        infos = list(zf.infolist())
    return {
        "size_bytes": int(path.stat().st_size),
        "entry_count": len(names),
        "mesh_npz_count": sum(1 for name in names if name.endswith(".npz")),
        "snapshot_npz_count": sum(1 for name in names if "/snapshots/" in name and name.endswith(".npz")),
        "compressed_payload_bytes": int(sum(int(info.compress_size) for info in infos)),
        "uncompressed_payload_bytes": int(sum(int(info.file_size) for info in infos)),
        "entries": names,
    }


def _save(project: ProjectStore, path: Path) -> dict[str, object]:
    started = time.perf_counter()
    save_project_atomic(project, path)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    out = _archive_stats(path)
    out["save_ms"] = float(elapsed_ms)
    return out


def _deepcopy_ms(project: ProjectStore) -> float:
    started = time.perf_counter()
    copy.deepcopy(project)
    return float((time.perf_counter() - started) * 1000.0)


def _scenario_deleted_without_semantic_history(root: Path) -> dict[str, object]:
    project = ProjectStore.new_empty(scene_name="main")
    store = project.active_model_store
    heavy = _heavy_mesh("heavy_deleted", seed=1)
    store.set_meshes([heavy], push_undo=False)
    store.set_meshes([], push_undo=False)
    return {
        "undo_states": len(getattr(store, "_history", []) or []),
        "semantic_snapshots": len(project.active_scene.snapshots),
        "save": _save(project, root / "deleted_no_history.lpsproj"),
    }


def _scenario_deleted_with_semantic_history(root: Path) -> dict[str, object]:
    project = ProjectStore.new_empty(scene_name="main")
    scene = project.active_scene
    store = scene.model_store
    heavy = _heavy_mesh("heavy_in_restore_history", seed=2)

    store.set_meshes([heavy], push_undo=False)
    scene.record_modification("Imported heavy mesh", "import", capture_snapshot=True)

    # This matches push_meshes semantics: mutate committed scene first, then capture
    # a semantic restore point of the post-operation state.
    store.set_meshes([], push_undo=True)
    scene.record_modification("Deleted heavy mesh", "delete", capture_snapshot=True)

    return {
        "undo_states": len(getattr(store, "_history", []) or []),
        "history_entries": len(scene.history),
        "semantic_snapshots": len(scene.snapshots),
        "save": _save(project, root / "deleted_with_history.lpsproj"),
        "deepcopy_ms": _deepcopy_ms(project),
    }


def _scenario_history_pruned(root: Path) -> dict[str, object]:
    project = ProjectStore.new_empty(scene_name="main")
    scene = project.active_scene
    store = scene.model_store
    heavy = _heavy_mesh("heavy_pruned", seed=3)

    store.set_meshes([heavy], push_undo=False)
    scene.record_modification("Imported heavy mesh", "import", capture_snapshot=True)
    store.set_meshes([], push_undo=True)
    scene.record_modification("Deleted heavy mesh", "delete", capture_snapshot=True)

    # Keep only the post-delete semantic restore point.
    scene.history_limit = 1
    scene.prune_history()

    return {
        "undo_states": len(getattr(store, "_history", []) or []),
        "history_entries": len(scene.history),
        "semantic_snapshots": len(scene.snapshots),
        "save": _save(project, root / "history_pruned.lpsproj"),
        "deepcopy_ms": _deepcopy_ms(project),
    }


def _scenario_removed_scene(root: Path) -> dict[str, object]:
    project = ProjectStore.new_empty(scene_name="main")
    heavy = _heavy_mesh("heavy_removed_scene", seed=4)
    heavy_scene = project.create_scene("heavy", meshes=[heavy], make_active=True)
    heavy_scene.record_modification("Generated heavy scene", "scene_generated", capture_snapshot=True)
    heavy_scene_id = heavy_scene.scene_id

    project.switch_scene(next(sid for sid in project.scenes if sid != heavy_scene_id))
    project.remove_scene(heavy_scene_id)

    return {
        "scene_count": len(project.scenes),
        "removed_scene_present": heavy_scene_id in project.scenes,
        "save": _save(project, root / "removed_scene.lpsproj"),
        "deepcopy_ms": _deepcopy_ms(project),
    }


def _scenario_undo_only(root: Path) -> dict[str, object]:
    project = ProjectStore.new_empty(scene_name="main")
    store = project.active_model_store
    # Create several distinct heavyweight undo states, then delete everything.
    for i in range(5):
        store.set_meshes([_heavy_mesh(f"undo_{i}", seed=100 + i)], push_undo=True, max_undo=10)
    store.set_meshes([], push_undo=True, max_undo=10)

    before = {
        "undo_states": len(getattr(store, "_history", []) or []),
        "redo_states": len(getattr(store, "_redo_history", []) or []),
        "deepcopy_ms": _deepcopy_ms(project),
        "save": _save(project, root / "undo_only.lpsproj"),
    }

    # This emulates a persistence-specific snapshot that excludes technical undo.
    saved_history = store._history
    saved_redo = store._redo_history
    try:
        store._history = []
        store._redo_history = []
        after = {
            "deepcopy_ms": _deepcopy_ms(project),
            "save": _save(project, root / "undo_cleared_for_persistence.lpsproj"),
        }
    finally:
        store._history = saved_history
        store._redo_history = saved_redo

    return {"with_undo": before, "without_undo": after}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        result = {
            "deleted_without_semantic_history": _scenario_deleted_without_semantic_history(root),
            "deleted_with_semantic_history": _scenario_deleted_with_semantic_history(root),
            "history_pruned": _scenario_history_pruned(root),
            "removed_scene": _scenario_removed_scene(root),
            "undo_only": _scenario_undo_only(root),
        }

    # Derived ratios make CI evidence easier to read.
    no_hist = float(result["deleted_without_semantic_history"]["save"]["size_bytes"])
    with_hist = float(result["deleted_with_semantic_history"]["save"]["size_bytes"])
    pruned = float(result["history_pruned"]["save"]["size_bytes"])
    result["derived"] = {
        "persistent_history_size_ratio_vs_deleted": with_hist / max(no_hist, 1.0),
        "pruned_size_ratio_vs_persistent_history": pruned / max(with_hist, 1.0),
        "undo_deepcopy_ratio": float(result["undo_only"]["with_undo"]["deepcopy_ms"]) / max(float(result["undo_only"]["without_undo"]["deepcopy_ms"]), 1.0e-9),
    }

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
