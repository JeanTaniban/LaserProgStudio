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
import io
import json
from pathlib import Path
import tempfile
import time
import zipfile

import numpy as np

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.io.project_file import save_project_atomic
import laserprog_studio.io.project_file as project_file_module
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


def _atomic_failure_probe(root: Path) -> dict[str, object]:
    project = ProjectStore.new_empty(scene_name="main")
    project.active_model_store.set_meshes([_heavy_mesh("atomic_failure", seed=777, vertex_count=2000, triangle_count=4000)])
    original_path = root / "original.lpsproj"
    target_path = root / "target.lpsproj"
    project.project_path = original_path
    project.mark_dirty()

    original_replace = project_file_module.os.replace

    def _fail_replace(_src, _dst):
        raise OSError("synthetic replace failure")

    project_file_module.os.replace = _fail_replace
    error = None
    try:
        save_project_atomic(project, target_path, mark_clean=True)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    finally:
        project_file_module.os.replace = original_replace

    return {
        "error": error,
        "project_dirty_after_failure": bool(project.dirty),
        "project_path_after_failure": str(project.project_path) if project.project_path is not None else None,
        "expected_original_path": str(original_path),
        "target_exists": bool(target_path.exists()),
    }


def _compression_strategy_probe(root: Path) -> dict[str, object]:
    mesh = _heavy_mesh("compression_probe", seed=999, vertex_count=36000, triangle_count=72000)
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    triangles = np.asarray(mesh.triangles, dtype=np.int64)

    def encode_npz(*, compressed: bool) -> tuple[bytes, float]:
        buffer = io.BytesIO()
        started = time.perf_counter()
        if compressed:
            np.savez_compressed(buffer, vertices=vertices, triangles=triangles)
        else:
            np.savez(buffer, vertices=vertices, triangles=triangles)
        elapsed = (time.perf_counter() - started) * 1000.0
        return buffer.getvalue(), float(elapsed)

    def write_outer(name: str, payload: bytes, *, compress_type: int, level: int | None = None) -> tuple[int, float]:
        path = root / name
        started = time.perf_counter()
        kwargs: dict[str, object] = {"compression": compress_type}
        if level is not None and compress_type == zipfile.ZIP_DEFLATED:
            kwargs["compresslevel"] = int(level)
        with zipfile.ZipFile(path, "w", **kwargs) as zf:
            zf.writestr("mesh.npz", payload, compress_type=compress_type)
        elapsed = (time.perf_counter() - started) * 1000.0
        return int(path.stat().st_size), float(elapsed)

    compressed_payload, compressed_encode_ms = encode_npz(compressed=True)
    raw_payload, raw_encode_ms = encode_npz(compressed=False)

    current_size, current_outer_ms = write_outer(
        "compression_current_double.zip",
        compressed_payload,
        compress_type=zipfile.ZIP_DEFLATED,
        level=6,
    )
    inner_only_size, inner_only_outer_ms = write_outer(
        "compression_inner_only.zip",
        compressed_payload,
        compress_type=zipfile.ZIP_STORED,
    )
    outer_only_size, outer_only_outer_ms = write_outer(
        "compression_outer_only.zip",
        raw_payload,
        compress_type=zipfile.ZIP_DEFLATED,
        level=6,
    )

    zstd_result: dict[str, object]
    try:
        import zstandard as zstd

        # Zstd is tested on one canonical uncompressed NPZ payload. This is a
        # persistence-format experiment only; production format is decided by CDC.
        zstd_rows: dict[str, object] = {}
        for level in (1, 3, 6):
            compressor = zstd.ZstdCompressor(level=level)
            started = time.perf_counter()
            payload = compressor.compress(raw_payload)
            elapsed = (time.perf_counter() - started) * 1000.0
            zstd_rows[str(level)] = {
                "compress_ms": float(elapsed),
                "bytes": int(len(payload)),
            }
        zstd_result = zstd_rows
    except Exception as exc:
        zstd_result = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "payload": {
            "vertices": int(len(vertices)),
            "triangles": int(len(triangles)),
            "compressed_npz_bytes": int(len(compressed_payload)),
            "raw_npz_bytes": int(len(raw_payload)),
        },
        "zstandard_raw_npz": zstd_result,
        "current_double_compression": {
            "npz_encode_ms": compressed_encode_ms,
            "outer_write_ms": current_outer_ms,
            "total_encode_write_ms": compressed_encode_ms + current_outer_ms,
            "archive_bytes": current_size,
        },
        "single_inner_npz_outer_stored": {
            "npz_encode_ms": compressed_encode_ms,
            "outer_write_ms": inner_only_outer_ms,
            "total_encode_write_ms": compressed_encode_ms + inner_only_outer_ms,
            "archive_bytes": inner_only_size,
        },
        "single_outer_zip": {
            "npz_encode_ms": raw_encode_ms,
            "outer_write_ms": outer_only_outer_ms,
            "total_encode_write_ms": raw_encode_ms + outer_only_outer_ms,
            "archive_bytes": outer_only_size,
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        result = {
            "deleted_without_semantic_history": _scenario_deleted_without_semantic_history(root),
            "deleted_with_semantic_history": _scenario_deleted_with_semantic_history(root),
            "history_pruned": _scenario_history_pruned(root),
            "removed_scene": _scenario_removed_scene(root),
            "undo_only": _scenario_undo_only(root),
            "compression_strategies": _compression_strategy_probe(root),
            "atomic_failure": _atomic_failure_probe(root),
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
