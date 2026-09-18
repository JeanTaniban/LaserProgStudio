# -*- coding: utf-8 -*-
"""Shared work model (3MF).

Goal: a single global state (list of meshed objects) that can be loaded, modified by tools,
displayed in a viewer, then exported via a global button.

Relies on the 3MF reader in `laserprog_studio.fabrication.layflat_arranger`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, List, Tuple
import copy
import uuid


def make_mesh_id() -> str:
    """Return a stable application-side identifier for one work mesh.

    The id is intentionally independent from names and list indices: names can
    duplicate, and indices change whenever pieces are inserted, deleted, or when
    future scene tabs are switched.  A short prefix makes project files easier
    to inspect by hand.
    """

    return f"mesh_{uuid.uuid4().hex}"


@dataclass
class WorkMesh:
    name: str
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]
    color: str = "#B8B8B8"
    # Forward-compatible V2 metadata. These optional fields are intentionally
    # typed as Any so older serialized projects and loose helper code do not
    # need to import the full domain metadata stack at module load.
    material: Any | None = None
    engraving: Any | None = None
    uvs: list[tuple[float, float]] | None = None
    texture_projections: list[Any] = field(default_factory=list)
    # Generic creator/tool metadata. Tool-specific source payloads live here so
    # generated geometry can be reopened by the tool that created it.
    metadata: dict[str, Any] = field(default_factory=dict)
    # Stable identity used by the future project/scene layer.  It is excluded
    # from dataclass equality so existing geometry comparisons and undo change
    # detection remain based on visible/content changes, not identity churn.
    mesh_id: str = field(default_factory=make_mesh_id, compare=False)


def ensure_mesh_id(mesh: Any) -> str:
    """Ensure *mesh* has a non-empty stable id and return it."""

    value = str(getattr(mesh, "mesh_id", "") or "").strip()
    if not value:
        value = make_mesh_id()
        try:
            setattr(mesh, "mesh_id", value)
        except Exception:
            pass
    return value


def reset_mesh_id(mesh: Any) -> str:
    """Assign a fresh identity to a copied/duplicated mesh and return it."""

    value = make_mesh_id()
    try:
        setattr(mesh, "mesh_id", value)
    except Exception:
        pass
    return value


def ensure_mesh_ids(meshes: Iterable[Any]) -> None:
    """Ensure every mesh in an iterable has a stable id in-place."""

    for mesh in meshes:
        ensure_mesh_id(mesh)


def reset_mesh_ids(meshes: Iterable[Any]) -> None:
    """Assign fresh identities to every mesh in an iterable in-place."""

    for mesh in meshes:
        reset_mesh_id(mesh)


def _mesh_display_color(mesh: Any) -> str:
    material = getattr(mesh, "material", None)
    try:
        if material is not None and not isinstance(material, dict):
            value = str(getattr(material, "base_color", "") or "")
            if value:
                return value
        if isinstance(material, dict):
            value = str(material.get("base_color") or "")
            if value:
                return value
    except Exception:
        pass
    return str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8")


def _parse_hex_color(value: str) -> tuple[float, float, float]:
    v = (value or "").strip()
    if v.startswith("#"):
        v = v[1:]
    if len(v) == 8:
        v = v[:6]
    if len(v) != 6:
        return (0.72, 0.72, 0.72)
    try:
        r = int(v[0:2], 16) / 255.0
        g = int(v[2:4], 16) / 255.0
        b = int(v[4:6], 16) / 255.0
        return (r, g, b)
    except Exception:
        return (0.72, 0.72, 0.72)


class ModelStore:
    def __init__(self) -> None:
        self._committed_meshes: list[WorkMesh] = []
        self._preview_meshes: list[WorkMesh] | None = None
        self._source_path: Path | None = None
        self._history: list[tuple[list[WorkMesh], Path | None]] = []
        self._redo_history: list[tuple[list[WorkMesh], Path | None]] = []
        self._selected_mesh_indices: list[int] = []
        self._listeners: list[Callable[[], None]] = []

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    @property
    def meshes(self) -> list[WorkMesh]:
        return self._preview_meshes if self._preview_meshes is not None else self._committed_meshes

    @property
    def committed_meshes(self) -> list[WorkMesh]:
        return self._committed_meshes

    @property
    def preview_meshes(self) -> list[WorkMesh] | None:
        return self._preview_meshes

    @property
    def has_preview(self) -> bool:
        return self._preview_meshes is not None

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_history)

    @property
    def selected_mesh_indices(self) -> list[int]:
        return list(self._selected_mesh_indices)

    @property
    def selected_pair(self) -> tuple[int | None, int | None]:
        a = self._selected_mesh_indices[0] if len(self._selected_mesh_indices) >= 1 else None
        b = self._selected_mesh_indices[1] if len(self._selected_mesh_indices) >= 2 else None
        return a, b

    def set_meshes(
        self,
        meshes: Iterable[WorkMesh],
        *,
        source_path: Path | None = None,
        push_undo: bool = False,
        max_undo: int = 10,
    ) -> None:
        """Replace current model.

        When push_undo is True, the previous committed scene is stored in the
        undo stack and the redo stack is cleared. This is used by immediate
        UI actions such as transforms, duplicate, delete, and booleans.
        """
        new_meshes = copy.deepcopy(list(meshes))
        ensure_mesh_ids(new_meshes)
        if push_undo and (not self._meshes_equal(new_meshes, self._committed_meshes) or source_path != self._source_path):
            self._history.append((copy.deepcopy(self._committed_meshes), self._source_path))
            if len(self._history) > max_undo:
                self._history = self._history[-max_undo:]
            self._redo_history.clear()
        self._committed_meshes = new_meshes
        self._preview_meshes = None
        self._source_path = source_path
        self._selected_mesh_indices = [i for i in self._selected_mesh_indices if i < len(self._committed_meshes)]
        self._notify()

    def set_preview_meshes(self, meshes: Iterable[WorkMesh], *, source_path: Path | None = None) -> None:
        """Update the displayed preview without changing the committed model until applied."""
        self._preview_meshes = copy.deepcopy(list(meshes))
        ensure_mesh_ids(self._preview_meshes)
        if source_path is not None:
            self._source_path = source_path
        self._selected_mesh_indices = [i for i in self._selected_mesh_indices if i < len(self._preview_meshes)]
        self._notify()

    def clear(self) -> None:
        self._committed_meshes = []
        self._preview_meshes = None
        self._source_path = None
        self._history.clear()
        self._redo_history.clear()
        self._selected_mesh_indices.clear()
        self._notify()

    def commit_preview(self, *, max_undo: int = 10) -> bool:
        """Apply preview to committed model and store the previous state for undo."""
        if self._preview_meshes is None:
            return False
        new_meshes = copy.deepcopy(self._preview_meshes)
        ensure_mesh_ids(new_meshes)
        if not self._meshes_equal(new_meshes, self._committed_meshes):
            self._history.append((copy.deepcopy(self._committed_meshes), self._source_path))
            if len(self._history) > max_undo:
                self._history = self._history[-max_undo:]
            self._redo_history.clear()
        self._committed_meshes = new_meshes
        self._preview_meshes = None
        self._selected_mesh_indices.clear()
        self._notify()
        return True

    def discard_preview(self) -> bool:
        if self._preview_meshes is None:
            return False
        self._preview_meshes = None
        self._selected_mesh_indices.clear()
        self._notify()
        return True

    def snapshot(self) -> tuple[list[WorkMesh], Path | None]:
        """Return a deep-copy snapshot of the committed scene."""
        ensure_mesh_ids(self._committed_meshes)
        return copy.deepcopy(self._committed_meshes), self._source_path

    @staticmethod
    def _meshes_equal(a: list[WorkMesh], b: list[WorkMesh]) -> bool:
        return a == b

    def push_undo_snapshot(self, meshes: Iterable[WorkMesh], source_path: Path | None, *, max_undo: int = 10) -> bool:
        """Push an explicit pre-action snapshot into the undo stack.

        Returns False when the snapshot matches the current committed state, which
        avoids creating useless undo steps for clicks/drags that did not change geometry.
        """
        snapshot_meshes = copy.deepcopy(list(meshes))
        ensure_mesh_ids(snapshot_meshes)
        if self._meshes_equal(snapshot_meshes, self._committed_meshes) and source_path == self._source_path:
            return False
        self._history.append((snapshot_meshes, source_path))
        if len(self._history) > max_undo:
            self._history = self._history[-max_undo:]
        self._redo_history.clear()
        return True

    def undo(self, *, max_redo: int = 10) -> bool:
        if not self._history:
            return False
        self._redo_history.append((copy.deepcopy(self._committed_meshes), self._source_path))
        if len(self._redo_history) > max_redo:
            self._redo_history = self._redo_history[-max_redo:]
        prev_meshes, prev_source = self._history.pop()
        self._committed_meshes = copy.deepcopy(prev_meshes)
        self._preview_meshes = None
        self._source_path = prev_source
        self._selected_mesh_indices.clear()
        self._notify()
        return True

    def redo(self, *, max_undo: int = 10) -> bool:
        if not self._redo_history:
            return False
        self._history.append((copy.deepcopy(self._committed_meshes), self._source_path))
        if len(self._history) > max_undo:
            self._history = self._history[-max_undo:]
        next_meshes, next_source = self._redo_history.pop()
        self._committed_meshes = copy.deepcopy(next_meshes)
        self._preview_meshes = None
        self._source_path = next_source
        self._selected_mesh_indices.clear()
        self._notify()
        return True

    def toggle_selected_mesh_index(self, index: int) -> None:
        meshes = self.meshes
        if not (0 <= index < len(meshes)):
            return

        if index in self._selected_mesh_indices:
            self._selected_mesh_indices = [i for i in self._selected_mesh_indices if i != index]
            self._notify()
            return

        self._selected_mesh_indices.append(index)
        if len(self._selected_mesh_indices) > 2:
            self._selected_mesh_indices.pop(0)
        self._notify()

    def subscribe(self, listener: Callable[[], None]) -> None:
        self._listeners.append(listener)

    def _notify(self) -> None:
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    def load_3mf(self, path: Path) -> None:
        from laserprog_studio.fabrication.layflat_arranger import read_3mf_meshes  # local import, avoids boot-time cycles

        meshes: list[WorkMesh] = []
        for obj in read_3mf_meshes(path):
            meshes.append(WorkMesh(name=obj.name or "object", vertices=obj.vertices, triangles=obj.triangles, color=obj.color))
        self._history.clear()
        self._redo_history.clear()
        self.set_meshes(meshes, source_path=path)

    def export_3mf(self, path: Path, *, application_name: str = "Laser Toolbox - Work Model", use_preview: bool = True) -> None:
        meshes = self.meshes if use_preview else self._committed_meshes
        xml = build_3mf_model_xml(meshes, application_name=application_name)
        write_3mf_container(path, xml)


def _fmt(v: float) -> str:
    if abs(v) < 1e-9:
        v = 0.0
    return f"{v:.6f}".rstrip("0").rstrip(".")


def build_3mf_model_xml(meshes: List[WorkMesh], *, application_name: str) -> str:
    import uuid
    from xml.sax.saxutils import escape

    core_ns = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
    material_ns = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
    production_ns = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<model unit="millimeter" xml:lang="en-US" xmlns="{core_ns}" xmlns:m="{material_ns}" xmlns:p="{production_ns}">')
    lines.append(f'  <metadata name="Application">{escape(application_name)}</metadata>')
    lines.append("  <resources>")
    material_id = 1
    lines.append(f'    <m:basematerials id="{material_id}">')
    for m in meshes:
        lines.append(f'      <m:base name="{escape(m.name)}" displaycolor="{_mesh_display_color(m)}"/>')
    lines.append("    </m:basematerials>")

    for index, m in enumerate(meshes, start=1):
        material_index = index - 1
        lines.append(f'    <object id="{index}" name="{escape(m.name)}" type="model" p:UUID="{uuid.uuid4()}">')
        lines.append("      <mesh>")
        lines.append("        <vertices>")
        for x, y, z in m.vertices:
            lines.append(f'          <vertex x="{_fmt(x)}" y="{_fmt(y)}" z="{_fmt(z)}"/>')
        lines.append("        </vertices>")
        lines.append("        <triangles>")
        for a, b, c in m.triangles:
            lines.append(
                f'          <triangle v1="{a}" v2="{b}" v3="{c}" pid="{material_id}" '
                f'p1="{material_index}" p2="{material_index}" p3="{material_index}"/>'
            )
        lines.append("        </triangles>")
        lines.append("      </mesh>")
        lines.append("    </object>")

    lines.append("  </resources>")
    lines.append(f'  <build p:UUID="{uuid.uuid4()}">')
    for index, m in enumerate(meshes, start=1):
        lines.append(f'    <item objectid="{index}" partnumber="{escape(m.name)}" p:UUID="{uuid.uuid4()}"/>')
    lines.append("  </build>")
    lines.append("</model>")
    return "\n".join(lines)


def write_3mf_container(path: Path, model_xml: str) -> None:
    import zipfile

    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=5) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)


__all__ = ["WorkMesh", "ModelStore", "make_mesh_id", "ensure_mesh_id", "ensure_mesh_ids", "reset_mesh_id", "reset_mesh_ids", "_parse_hex_color"]
