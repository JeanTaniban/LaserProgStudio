# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import zipfile
import time
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from laserprog_studio.domain.work_model import ModelStore, WorkMesh, ensure_mesh_ids

from ..domain.material import EngravingSettings, MeshMaterial, TextureProjection
from ..project import ProjectStore, SceneDocument, SceneModificationHistoryEntry, safe_slug

PROJECT_FORMAT = "laserprog-studio-project"
PROJECT_FORMAT_VERSION = 1
PROJECT_EXTENSION = ".lpsproj"


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _read_json(zf: zipfile.ZipFile, name: str) -> Any:
    return json.loads(zf.read(name).decode("utf-8"))


def _metadata_to_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if is_dataclass(value):
        return asdict(value)
    out: dict[str, Any] = {}
    for key in dir(value):
        if key.startswith("_"):
            continue
        try:
            item = getattr(value, key)
        except Exception:
            continue
        if callable(item):
            continue
        if isinstance(item, (str, int, float, bool, type(None), list, tuple, dict)):
            out[key] = copy.deepcopy(item)
    return out or None


def _mesh_meta(mesh: WorkMesh, npz_name: str) -> dict[str, Any]:
    return {
        "mesh_id": str(getattr(mesh, "mesh_id", "") or ""),
        "name": str(getattr(mesh, "name", "part") or "part"),
        "color": str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
        "npz": npz_name,
        "material": _metadata_to_dict(getattr(mesh, "material", None)),
        "engraving": _metadata_to_dict(getattr(mesh, "engraving", None)),
        "texture_projections": [_metadata_to_dict(item) for item in (getattr(mesh, "texture_projections", []) or [])],
        "metadata": _metadata_to_dict(getattr(mesh, "metadata", None)),
        "box_generator_meta": _metadata_to_dict(getattr(mesh, "box_generator_meta", None)),
    }


def _write_mesh_npz(zf: zipfile.ZipFile, arcname: str, mesh: WorkMesh, *, compressed_arrays: bool = True) -> None:
    vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float64)
    triangles = np.asarray(getattr(mesh, "triangles", []) or [], dtype=np.int64)
    uvs_value = getattr(mesh, "uvs", None)
    arrays: dict[str, Any] = {"vertices": vertices, "triangles": triangles}
    if uvs_value is not None:
        arrays["uvs"] = np.asarray(uvs_value, dtype=np.float64)
    with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as buffer:
        if compressed_arrays:
            np.savez_compressed(buffer, **arrays)
        else:
            np.savez(buffer, **arrays)
        buffer.seek(0)
        zf.writestr(arcname, buffer.read())


def _read_mesh_npz(zf: zipfile.ZipFile, arcname: str, meta: dict[str, Any]) -> WorkMesh:
    data_bytes = zf.read(arcname)
    with np.load(io.BytesIO(data_bytes), allow_pickle=False) as data:
        vertices = [tuple(float(x) for x in row) for row in data["vertices"].tolist()]
        triangles = [tuple(int(x) for x in row) for row in data["triangles"].tolist()]
        uvs = None
        if "uvs" in data.files:
            uvs = [tuple(float(x) for x in row) for row in data["uvs"].tolist()]
    mesh = WorkMesh(
        name=str(meta.get("name") or "part"),
        vertices=vertices,
        triangles=triangles,
        color=str(meta.get("color") or "#B8B8B8"),
        mesh_id=str(meta.get("mesh_id") or ""),
    )
    if uvs is not None:
        mesh.uvs = uvs
    material = meta.get("material")
    if isinstance(material, dict):
        try:
            mesh.material = MeshMaterial(**{k: v for k, v in material.items() if k in MeshMaterial.__dataclass_fields__})
        except Exception:
            mesh.material = material
    engraving = meta.get("engraving")
    if isinstance(engraving, dict):
        try:
            mesh.engraving = EngravingSettings(**{k: v for k, v in engraving.items() if k in EngravingSettings.__dataclass_fields__})
        except Exception:
            mesh.engraving = engraving
    projections = []
    for item in meta.get("texture_projections") or []:
        if isinstance(item, dict):
            try:
                projections.append(TextureProjection(**{k: v for k, v in item.items() if k in TextureProjection.__dataclass_fields__}))
            except Exception:
                projections.append(item)
    mesh.texture_projections = projections
    generic_metadata = meta.get("metadata")
    if isinstance(generic_metadata, dict):
        try:
            mesh.metadata = copy.deepcopy(generic_metadata)
        except Exception:
            pass
    box_generator_meta = meta.get("box_generator_meta")
    if isinstance(box_generator_meta, dict):
        try:
            setattr(mesh, "box_generator_meta", copy.deepcopy(box_generator_meta))
        except Exception:
            pass
    return mesh


def _path_to_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _str_to_path(value: str | None) -> Path | None:
    return Path(value) if value else None


def _write_mesh_collection(zf: zipfile.ZipFile, base: str, meshes: list[WorkMesh], *, compressed_arrays: bool = True) -> list[dict[str, Any]]:
    ensure_mesh_ids(meshes)
    metas: list[dict[str, Any]] = []
    for index, mesh in enumerate(meshes):
        mesh_id = str(getattr(mesh, "mesh_id", "") or f"mesh_{index}")
        npz_name = f"{base}/meshes/{index:04d}_{safe_slug(mesh_id)}.npz"
        _write_mesh_npz(zf, npz_name, mesh, compressed_arrays=compressed_arrays)
        metas.append(_mesh_meta(mesh, npz_name))
    return metas


def _read_mesh_collection(zf: zipfile.ZipFile, metas: list[dict[str, Any]]) -> list[WorkMesh]:
    meshes: list[WorkMesh] = []
    for meta in metas:
        meshes.append(_read_mesh_npz(zf, str(meta["npz"]), meta))
    ensure_mesh_ids(meshes)
    return meshes


def save_project(project: ProjectStore, path: str | Path, *, mark_clean: bool = True, autosave_fast: bool = False) -> Path:
    start = time.perf_counter()
    try:
        return _save_project_measured(project, path, mark_clean=mark_clean, autosave_fast=autosave_fast)
    finally:
        if _APP_AUDIT is not None:
            try:
                out_path = Path(path)
                size = int(out_path.stat().st_size) if out_path.exists() else 0
                _APP_AUDIT.record_timing("io.project.save", (time.perf_counter() - start) * 1000.0, details={"path": str(path), "size_bytes": size, "autosave_fast": autosave_fast})
            except Exception:
                pass


def _save_project_measured(project: ProjectStore, path: str | Path, *, mark_clean: bool = True, autosave_fast: bool = False) -> Path:
    """Write a complete `.lpsproj` project file.

    Autosave/recovery files pass ``mark_clean=False`` so they do not silently
    become the user's canonical project path and do not clear the dirty flag.
    """

    out_path = Path(path)
    old_project_path = project.project_path
    old_dirty = bool(getattr(project, "dirty", False))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Manual saves keep the compact historical format.  Autosave is a recovery
    # path and must prioritise responsiveness over maximum compression: heavy
    # DEFLATE + np.savez_compressed on large meshes can freeze the Qt thread for
    # several seconds when run synchronously.
    zip_compression = zipfile.ZIP_DEFLATED
    zip_level = 1 if autosave_fast else 6
    compressed_arrays = not bool(autosave_fast)
    with zipfile.ZipFile(out_path, "w", compression=zip_compression, compresslevel=zip_level) as zf:
        zf.writestr(
            "manifest.json",
            _json_bytes({"format": PROJECT_FORMAT, "version": PROJECT_FORMAT_VERSION}),
        )
        scene_entries: list[dict[str, Any]] = []
        for order, scene in enumerate(project.scenes.values()):
            scene_slug = f"{order:03d}_{safe_slug(scene.scene_id, fallback='scene')}"
            base = f"scenes/{scene_slug}"
            meshes, source_path = scene.snapshot()
            mesh_metas = _write_mesh_collection(zf, base, meshes, compressed_arrays=compressed_arrays)
            snapshot_entries: list[dict[str, Any]] = []
            for snapshot_id, snapshot in scene.snapshots.items():
                snapshot_meshes, snapshot_source = snapshot
                snap_base = f"{base}/snapshots/{safe_slug(snapshot_id, fallback='snapshot')}"
                snapshot_entries.append(
                    {
                        "snapshot_id": snapshot_id,
                        "source_path": _path_to_str(snapshot_source),
                        "meshes": _write_mesh_collection(zf, snap_base, copy.deepcopy(snapshot_meshes), compressed_arrays=compressed_arrays),
                    }
                )
            scene_json = {
                "scene_id": scene.scene_id,
                "name": scene.name,
                "source_path": _path_to_str(source_path),
                "meshes": mesh_metas,
                "history": [entry.to_dict() for entry in scene.history],
                "snapshots": snapshot_entries,
            }
            zf.writestr(f"{base}/scene.json", _json_bytes(scene_json))
            scene_entries.append({"scene_id": scene.scene_id, "scene_path": f"{base}/scene.json", "name": scene.name})
        zf.writestr(
            "project.json",
            _json_bytes(
                {
                    "project_id": project.project_id,
                    "active_scene_id": project.active_scene_id,
                    "scenes": scene_entries,
                }
            ),
        )
    if mark_clean:
        project.project_path = out_path
        project.mark_clean()
    else:
        project.project_path = old_project_path
        project.dirty = old_dirty
    return out_path


def save_project_atomic(project: ProjectStore, path: str | Path, *, mark_clean: bool = True, autosave_fast: bool = False) -> Path:
    start = time.perf_counter()
    try:
        return _save_project_atomic_measured(project, path, mark_clean=mark_clean, autosave_fast=autosave_fast)
    finally:
        if _APP_AUDIT is not None:
            _APP_AUDIT.record_timing("io.project.save_atomic", (time.perf_counter() - start) * 1000.0, details={"path": str(path), "autosave_fast": autosave_fast})


def _save_project_atomic_measured(project: ProjectStore, path: str | Path, *, mark_clean: bool = True, autosave_fast: bool = False) -> Path:
    """Atomically write a project file via a temporary sibling file."""

    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{out_path.name}.", suffix=".tmp", dir=str(out_path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        # Keep project state transactional too: writing the temporary archive
        # must never mark the in-memory document clean or repoint it to the
        # temporary file before the final atomic replace has succeeded.
        save_project(project, tmp_path, mark_clean=False, autosave_fast=autosave_fast)
        os.replace(tmp_path, out_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass
    if mark_clean:
        project.project_path = out_path
        project.mark_clean()
    return out_path


def load_project(path: str | Path) -> ProjectStore:
    start = time.perf_counter()
    try:
        return _load_project_measured(path)
    finally:
        if _APP_AUDIT is not None:
            _APP_AUDIT.record_timing("io.project.load", (time.perf_counter() - start) * 1000.0, details={"path": str(path)})


def _load_project_measured(path: str | Path) -> ProjectStore:
    """Read a `.lpsproj` project file."""

    in_path = Path(path)
    with zipfile.ZipFile(in_path, "r") as zf:
        manifest = _read_json(zf, "manifest.json")
        if manifest.get("format") != PROJECT_FORMAT:
            raise ValueError(f"Unsupported project format: {manifest.get('format')!r}")
        if int(manifest.get("version", 0)) > PROJECT_FORMAT_VERSION:
            raise ValueError(f"Unsupported newer project version: {manifest.get('version')!r}")
        project_json = _read_json(zf, "project.json")
        project = ProjectStore(project_id=str(project_json.get("project_id") or ""))
        project.scenes.clear()
        for scene_ref in project_json.get("scenes") or []:
            scene_data = _read_json(zf, str(scene_ref["scene_path"]))
            store = ModelStore()
            store.set_meshes(_read_mesh_collection(zf, list(scene_data.get("meshes") or [])), source_path=_str_to_path(scene_data.get("source_path")))
            scene = SceneDocument(
                scene_id=str(scene_data.get("scene_id") or scene_ref.get("scene_id")),
                name=str(scene_data.get("name") or scene_ref.get("name") or "Scene"),
                model_store=store,
            )
            scene.history = [SceneModificationHistoryEntry.from_dict(item) for item in (scene_data.get("history") or [])]
            scene.snapshots.clear()
            for snapshot_entry in scene_data.get("snapshots") or []:
                sid = str(snapshot_entry.get("snapshot_id") or "")
                if not sid:
                    continue
                snapshot_meshes = _read_mesh_collection(zf, list(snapshot_entry.get("meshes") or []))
                scene.snapshots[sid] = (snapshot_meshes, _str_to_path(snapshot_entry.get("source_path")))
            project.scenes[scene.scene_id] = scene
        active_scene_id = str(project_json.get("active_scene_id") or "")
        if active_scene_id in project.scenes:
            project.active_scene_id = active_scene_id
        elif project.scenes:
            project.active_scene_id = next(iter(project.scenes.keys()))
        else:
            project = ProjectStore.new_empty(scene_name="main")
        project.project_path = in_path
        project.mark_clean()
        return project


__all__ = [
    "PROJECT_EXTENSION",
    "PROJECT_FORMAT",
    "PROJECT_FORMAT_VERSION",
    "load_project",
    "save_project",
    "save_project_atomic",
]
