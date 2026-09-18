"""Creator-facing multi-scene output service.

Tools use this facade instead of importing the Qt window, project store or scene
controllers.  The service deliberately exposes a narrow transaction needed by
surface generators such as Cloth: commit one mesh in the active scene and one
linked mesh in a secondary scene while preserving the active tab.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Iterable

from .common import ToolServiceError


@dataclass(frozen=True, slots=True)
class LinkedSceneOutputResult:
    active_scene_id: str
    folded_object_id: str
    flat_scene_id: str
    flat_scene_name: str
    flat_object_id: str
    created_flat_scene: bool


class ProjectScenesFacade:
    def __init__(self) -> None:
        self._ctx: Any | None = None

    def bind_context(self, ctx: Any) -> "ProjectScenesFacade":
        self._ctx = ctx
        return self

    @property
    def available(self) -> bool:
        return self._project(required=False) is not None

    def create_scene(
        self,
        name: str,
        meshes: Iterable[Any],
        *,
        make_active: bool = False,
        operation_label: str = "Generated scene",
        operation_type: str = "scene_generated",
        metadata: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        project = self._project(required=True)
        scene = project.create_scene(
            str(name or "Generated scene"),
            meshes=copy.deepcopy(list(meshes)),
            make_active=bool(make_active),
            mark_dirty=True,
            fresh_mesh_ids=False,
        )
        try:
            scene.record_modification(
                str(operation_label),
                str(operation_type),
                capture_snapshot=True,
                metadata=dict(metadata or {}),
            )
        except Exception:
            pass
        self._sync_host(active_changed=bool(make_active))
        return str(scene.scene_id), str(scene.name)

    def replace_scene_meshes(
        self,
        scene_id: str,
        meshes: Iterable[Any],
        *,
        label: str = "Update generated scene",
        operation_type: str = "tool_apply",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        project = self._project(required=True)
        scene = project.scenes.get(str(scene_id))
        if scene is None:
            raise ToolServiceError(f"Unknown project scene: {scene_id!r}")
        scene.model_store.set_meshes(copy.deepcopy(list(meshes)), push_undo=True)
        project.mark_dirty(scene.scene_id)
        try:
            scene.record_modification(label, operation_type, capture_snapshot=True, metadata=dict(metadata or {}))
        except Exception:
            pass
        self._sync_host(active_changed=False)

    def apply_linked_surface_outputs(
        self,
        folded_mesh: Any,
        flat_mesh: Any,
        *,
        source_object_id: str | int | None = None,
        flat_scene_name: str = "Cloth · Flat pattern",
        existing_flat_scene_id: str | None = None,
        label: str = "Apply Cloth surface",
        operation_type: str = "cloth_apply",
    ) -> LinkedSceneOutputResult:
        """Commit linked folded/flat outputs with rollback on failure.

        The current scene is updated through ``DocumentFacade`` so it receives
        the normal ModelStore undo snapshot.  The secondary scene is created or
        updated while the current scene stays active.  A tool-level command is
        also recorded when available, allowing Creator workflows and tests to
        undo the pair as one semantic action.
        """

        ctx = self._require_ctx()
        project = self._project(required=True)
        active_scene = project.active_scene
        active_scene_id = str(active_scene.scene_id)
        project_active_before = str(project.active_scene_id or active_scene_id)
        active_snapshot = active_scene.snapshot()
        flat_scene = project.scenes.get(str(existing_flat_scene_id or "")) if existing_flat_scene_id else None
        flat_snapshot = flat_scene.snapshot() if flat_scene is not None else None
        created_flat_scene = flat_scene is None

        folded = copy.deepcopy(folded_mesh)
        flat = copy.deepcopy(flat_mesh)
        try:
            if flat_scene is None:
                flat_scene = project.create_scene(
                    str(flat_scene_name or "Cloth · Flat pattern"),
                    meshes=[],
                    make_active=False,
                    mark_dirty=False,
                    fresh_mesh_ids=False,
                )
            flat_scene_id = str(flat_scene.scene_id)
            pair_metadata = {
                "cloth_linked_active_scene_id": active_scene_id,
                "cloth_linked_flat_scene_id": flat_scene_id,
            }
            for mesh, output_kind in ((folded, "folded"), (flat, "flat")):
                metadata = dict(getattr(mesh, "metadata", {}) or {})
                metadata.update(pair_metadata)
                metadata["cloth_output_kind"] = output_kind
                mesh.metadata = metadata

            # Replace/add the active-scene output in one ModelStore mutation.
            current_meshes = list(ctx.document.meshes(include_preview=False))
            if source_object_id is None:
                current_meshes.append(folded)
                active_index = len(current_meshes) - 1
            else:
                active_index = ctx.document.index_for(source_object_id)
                original = current_meshes[active_index]
                if hasattr(original, "mesh_id"):
                    folded.mesh_id = getattr(original, "mesh_id")
                current_meshes[active_index] = folded
            ctx.document.set_meshes(current_meshes, label=label, push_undo=True)

            flat_scene.model_store.set_meshes((flat,), push_undo=not created_flat_scene)
            project.mark_dirty(active_scene_id)
            project.mark_dirty(flat_scene_id)
            project.active_scene_id = project_active_before
            try:
                active_scene.record_modification(
                    label,
                    operation_type,
                    capture_snapshot=True,
                    metadata={"flat_scene_id": flat_scene_id, "source_object_id": source_object_id},
                )
                flat_scene.record_modification(
                    f"{label} · flat pattern",
                    "scene_generated" if created_flat_scene else operation_type,
                    capture_snapshot=True,
                    metadata={"source_scene_id": active_scene_id},
                )
            except Exception:
                pass

            # Record a paired Creator command after the action has happened.
            command_stack = getattr(ctx, "commands", None)
            recorder = getattr(command_stack, "record_executed", None)
            if callable(recorder):
                after_active = active_scene.snapshot()
                after_flat = flat_scene.snapshot()
                from laserprog_studio.tool_core.commands import FunctionCommand

                def restore(active_data, flat_data, *, include_flat: bool) -> None:
                    active_meshes, active_path = active_data
                    active_scene.model_store.set_meshes(active_meshes, source_path=active_path, push_undo=False)
                    if include_flat:
                        flat_meshes, flat_path = flat_data
                        flat_scene.model_store.set_meshes(flat_meshes, source_path=flat_path, push_undo=False)
                    else:
                        if flat_scene_id in project.scenes and len(project.scenes) > 1:
                            project.remove_scene(flat_scene_id)
                    project.active_scene_id = project_active_before
                    project.dirty = True
                    self._sync_host(active_changed=False)

                recorder(
                    FunctionCommand(
                        str(label),
                        do_func=lambda: restore(after_active, after_flat, include_flat=True),
                        undo_func=lambda: restore(active_snapshot, flat_snapshot or ([], None), include_flat=not created_flat_scene),
                    )
                )

            self._sync_host(active_changed=False)
            folded_id = str(getattr(folded, "mesh_id", "") or f"index:{active_index}")
            flat_id = str(getattr(flat, "mesh_id", "") or "index:0")
            return LinkedSceneOutputResult(
                active_scene_id=active_scene_id,
                folded_object_id=folded_id,
                flat_scene_id=flat_scene_id,
                flat_scene_name=str(flat_scene.name),
                flat_object_id=flat_id,
                created_flat_scene=created_flat_scene,
            )
        except Exception:
            # Roll back both sides.  Keep the source scene active.
            active_meshes, active_path = active_snapshot
            active_scene.model_store.set_meshes(active_meshes, source_path=active_path, push_undo=False)
            if created_flat_scene:
                if flat_scene is not None and str(flat_scene.scene_id) in project.scenes and len(project.scenes) > 1:
                    project.remove_scene(str(flat_scene.scene_id))
            elif flat_scene is not None and flat_snapshot is not None:
                flat_meshes, flat_path = flat_snapshot
                flat_scene.model_store.set_meshes(flat_meshes, source_path=flat_path, push_undo=False)
            project.active_scene_id = project_active_before
            self._sync_host(active_changed=False)
            raise

    def _project(self, *, required: bool) -> Any | None:
        ctx = self._require_ctx()
        owner = getattr(ctx, "owner", None)
        project = getattr(owner, "project_store", None) if owner is not None else None
        if project is None:
            raw = getattr(ctx.document, "raw", None)
            project = raw if hasattr(raw, "create_scene") and hasattr(raw, "active_scene") else None
        if required and project is None:
            raise ToolServiceError("This tool needs a project with scene support.")
        return project

    def _sync_host(self, *, active_changed: bool) -> None:
        ctx = self._require_ctx()
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        if active_changed:
            try:
                from laserprog_studio.project import sync_window_to_active_scene

                sync_window_to_active_scene(owner)
            except Exception:
                pass
        for name in ("rebuild_scene", "update_preview_state", "_sync_history_buttons", "sync_scene_tabs", "update_project_title", "update_inspector"):
            callback = getattr(owner, name, None)
            if not callable(callback):
                continue
            try:
                if name == "rebuild_scene":
                    callback(keep_camera=True)
                else:
                    callback()
            except TypeError:
                try:
                    callback()
                except Exception:
                    pass
            except Exception:
                pass

    def _require_ctx(self) -> Any:
        if self._ctx is None:
            raise ToolServiceError("ProjectScenesFacade is not bound to a ToolContext.")
        return self._ctx


__all__ = ["LinkedSceneOutputResult", "ProjectScenesFacade"]
