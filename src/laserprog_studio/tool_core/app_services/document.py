"""Document and mesh-object facades exposed through ToolContext."""
from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Callable, Iterable

from .common import ToolServiceError


@dataclass(frozen=True, slots=True)
class DocumentObject:
    """Stable creator-facing view of one scene object/mesh."""

    id: str
    index: int
    name: str
    mesh: Any


class DocumentFacade:
    """Creator-facing document API.

    ``ToolContext.document`` is a facade, not the raw historical object.  Bind a
    real scene/project with ``ctx.document.bind(scene_or_project)``.  The facade
    currently targets the mesh/document operations required by existing tools:
    listing meshes, adding/replacing/removing objects and managing previews.
    """

    def __init__(self, target: Any | None = None) -> None:
        self._target = target
        self._ctx: Any | None = None

    def bind_context(self, ctx: Any) -> "DocumentFacade":
        self._ctx = ctx
        return self

    def bind(self, target: Any | None) -> "DocumentFacade":
        """Bind the facade to a scene/project without invalidating on no-op rebinding.

        CreatorStudioToolAdapter.tool_context() is intentionally called for every
        viewport event so tools always see the current host owner/scene.  The old
        implementation invalidated ctx.scene_cache on every call even when the
        target object was unchanged.  In Plan Tracer this turned plain mouse
        movement into a global cache-invalidating operation and made downstream
        snap code much harder to cache correctly.
        """

        if target is self._target:
            _increment_perf(self._ctx, "document.bind.same_target")
            return self
        self._target = target
        _increment_perf(self._ctx, "document.bind.changed_target")
        self._invalidate_cache()
        return self


    def ensure(self) -> bool:
        """Ensure a usable document/model store is bound.

        Creator tools call this instead of reaching into the historical Qt
        window.  In the current application it delegates to the owner/preview
        controller if needed, then binds the active scene, project store or
        owner as the best available document target.
        """

        if self.available:
            return True
        ctx = self._ctx
        if ctx is None:
            return False
        owner = getattr(ctx, "owner", None)
        project = getattr(owner, "project_store", None) if owner is not None else None
        scene = getattr(project, "active_scene", None) if project is not None else None
        if scene is None:
            scene = getattr(ctx, "scene", None)
        candidates = [scene, project, owner]
        for candidate in candidates:
            if candidate is not None:
                self.bind(candidate)
                if self.available:
                    return True

        if owner is not None:
            ensure = getattr(owner, "_ensure_model_store", None)
            if callable(ensure):
                try:
                    ensure()
                except Exception:
                    pass
            else:
                preview_controller = getattr(owner, "preview_controller", None)
                ensure = getattr(preview_controller, "ensure_model_store", None)
                if callable(ensure):
                    try:
                        ensure()
                    except Exception:
                        pass
            project = getattr(owner, "project_store", None)
            scene = getattr(project, "active_scene", None) if project is not None else None
            for candidate in (scene, project, owner):
                if candidate is not None:
                    self.bind(candidate)
                    if self.available:
                        return True
        return self.available

    @property
    def raw(self) -> Any | None:
        return self._target

    @property
    def available(self) -> bool:
        return self._model_store(required=False) is not None or self._mesh_list(required=False) is not None

    def objects(self, *, include_preview: bool = True) -> tuple[DocumentObject, ...]:
        meshes = self.meshes(include_preview=include_preview)
        return tuple(_object_from_mesh(mesh, index) for index, mesh in enumerate(meshes))

    def meshes(self, *, include_preview: bool = True) -> tuple[Any, ...]:
        store = self._model_store(required=False)
        if store is not None:
            if include_preview and getattr(store, "preview_meshes", None) is not None:
                return tuple(getattr(store, "preview_meshes") or ())
            return tuple(getattr(store, "committed_meshes", getattr(store, "meshes", ())) or ())
        mesh_list = self._mesh_list(required=True)
        return tuple(mesh_list or ())

    def get(self, object_id: str | int) -> DocumentObject:
        index = self.index_for(object_id)
        return self.objects()[index]

    def index_for(self, object_id: str | int) -> int:
        if isinstance(object_id, int):
            index = int(object_id)
            if 0 <= index < len(self.objects()):
                return index
            raise KeyError(f"Scene object index out of range: {index}")
        wanted = str(object_id)
        for obj in self.objects():
            if obj.id == wanted or obj.name == wanted:
                return obj.index
        raise KeyError(f"Unknown scene object: {wanted!r}")

    def add_mesh(self, mesh: Any, *, label: str = "Add mesh", push_undo: bool = True) -> DocumentObject:
        meshes = [*self.meshes(include_preview=False), copy.deepcopy(mesh)]
        self.set_meshes(meshes, label=label, push_undo=push_undo)
        return self.objects(include_preview=False)[-1]

    def replace_mesh(self, object_id: str | int, mesh: Any, *, label: str = "Replace mesh", push_undo: bool = True) -> DocumentObject:
        index = self.index_for(object_id)
        meshes = list(self.meshes(include_preview=False))
        replacement = copy.deepcopy(mesh)
        if hasattr(meshes[index], "mesh_id") and not getattr(replacement, "mesh_id", None):
            try:
                setattr(replacement, "mesh_id", getattr(meshes[index], "mesh_id"))
            except Exception:
                pass
        meshes[index] = replacement
        self.set_meshes(meshes, label=label, push_undo=push_undo)
        return self.objects(include_preview=False)[index]

    def update_mesh(self, object_id: str | int, updater: Callable[[Any], Any], *, label: str = "Update mesh", push_undo: bool = True) -> DocumentObject:
        current = copy.deepcopy(self.get(object_id).mesh)
        updated = updater(current)
        if updated is None:
            updated = current
        return self.replace_mesh(object_id, updated, label=label, push_undo=push_undo)

    def remove_object(self, object_id: str | int, *, label: str = "Remove object", push_undo: bool = True) -> DocumentObject:
        index = self.index_for(object_id)
        meshes = list(self.meshes(include_preview=False))
        removed = _object_from_mesh(meshes.pop(index), index)
        self.set_meshes(meshes, label=label, push_undo=push_undo)
        return removed

    def set_meshes(self, meshes: Iterable[Any], *, label: str = "Set meshes", push_undo: bool = True, source_path: Any | None = None) -> None:
        mesh_list = list(copy.deepcopy(list(meshes)))
        store = self._model_store(required=False)
        if store is not None and callable(getattr(store, "set_meshes", None)):
            kwargs: dict[str, Any] = {"push_undo": bool(push_undo)}
            if source_path is not None:
                kwargs["source_path"] = source_path
            store.set_meshes(mesh_list, **kwargs)
        else:
            raw_list = self._mesh_list(required=True)
            raw_list[:] = mesh_list
        self._record_modification(label)
        self._invalidate_cache()

    def snapshot(self) -> tuple[list[Any], Any | None]:
        store = self._model_store(required=False)
        if store is not None and callable(getattr(store, "snapshot", None)):
            return store.snapshot()
        return copy.deepcopy(list(self.meshes(include_preview=False))), None

    def restore_snapshot(self, snapshot: tuple[Iterable[Any], Any | None], *, label: str = "Restore snapshot", push_undo: bool = True) -> None:
        meshes, source_path = snapshot
        self.set_meshes(meshes, label=label, push_undo=push_undo, source_path=source_path)

    @property
    def has_preview(self) -> bool:
        store = self._model_store(required=False)
        return bool(getattr(store, "has_preview", False)) if store is not None else False

    def set_preview_meshes(self, meshes: Iterable[Any], *, source_path: Any | None = None) -> None:
        store = self._model_store(required=True)
        setter = getattr(store, "set_preview_meshes", None)
        if not callable(setter):
            raise ToolServiceError("Bound document does not support preview meshes.")
        kwargs = {"source_path": source_path} if source_path is not None else {}
        setter(list(meshes), **kwargs)
        self._invalidate_cache()

    def commit_preview(self, *, label: str = "Apply preview", operation_type: str = "tool_apply") -> bool:
        store = self._model_store(required=True)
        committer = getattr(store, "commit_preview", None)
        if not callable(committer):
            raise ToolServiceError("Bound document does not support preview commit.")
        changed = bool(committer())
        if changed:
            self._record_modification(label, operation_type=operation_type)
            self._invalidate_cache()
        return changed

    def discard_preview(self) -> bool:
        store = self._model_store(required=True)
        discard = getattr(store, "discard_preview", None)
        if not callable(discard):
            raise ToolServiceError("Bound document does not support preview discard.")
        changed = bool(discard())
        if changed:
            self._invalidate_cache()
        return changed

    def set_material(self, object_id: str | int, material: Any, *, label: str = "Assign material") -> DocumentObject:
        def _assign(mesh: Any) -> Any:
            setattr(mesh, "material", material)
            return mesh

        return self.update_mesh(object_id, _assign, label=label)

    def set_metadata(self, object_id: str | int, key: str, value: Any, *, label: str = "Update metadata") -> DocumentObject:
        def _assign(mesh: Any) -> Any:
            metadata = getattr(mesh, "metadata", None)
            if metadata is None:
                metadata = {}
                setattr(mesh, "metadata", metadata)
            metadata[str(key)] = value
            return mesh

        return self.update_mesh(object_id, _assign, label=label)

    def _model_store(self, *, required: bool) -> Any | None:
        target = self._resolve_target()
        candidates = [target]
        if target is not None:
            candidates.extend(
                getattr(target, attr, None)
                for attr in ("model_store", "active_model_store", "mesh_store")
            )
            active_scene = getattr(target, "active_scene", None)
            if active_scene is not None:
                candidates.extend([active_scene, getattr(active_scene, "model_store", None)])
        for candidate in candidates:
            if candidate is not None and (hasattr(candidate, "set_meshes") or hasattr(candidate, "committed_meshes")):
                return candidate
        if required:
            raise ToolServiceError("No model store is bound to ctx.document. Call ctx.document.bind(scene_or_project) first.")
        return None

    def _mesh_list(self, *, required: bool) -> list[Any] | None:
        target = self._resolve_target()
        meshes = getattr(target, "meshes", None)
        if isinstance(meshes, list):
            return meshes
        if required:
            raise ToolServiceError("No mesh list is bound to ctx.document. Call ctx.document.bind(scene_or_project) first.")
        return None

    def _resolve_target(self) -> Any | None:
        if self._target is not None:
            return self._target
        ctx = self._ctx
        if ctx is None:
            return None
        scene = getattr(ctx, "scene", None)
        if scene is not None and (hasattr(scene, "model_store") or hasattr(scene, "meshes") or hasattr(scene, "active_scene")):
            return scene
        return None

    def _record_modification(self, label: str, *, operation_type: str = "tool_api") -> None:
        target = self._resolve_target()
        if target is None:
            return
        recorder = getattr(target, "record_modification", None)
        if callable(recorder):
            try:
                recorder(label, operation_type, capture_snapshot=False)
            except TypeError:
                try:
                    recorder(label, operation_type)
                except Exception:
                    pass

    def _invalidate_cache(self) -> None:
        ctx = self._ctx
        if ctx is not None:
            scene_cache = getattr(ctx, "scene_cache", None)
            invalidate = getattr(scene_cache, "invalidate", None)
            if callable(invalidate):
                invalidate()


def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if not callable(increment):
        return
    try:
        increment(str(name), int(value))
    except Exception:
        pass


def _object_from_mesh(mesh: Any, index: int) -> DocumentObject:
    mesh_id = str(getattr(mesh, "mesh_id", "") or f"index:{index}")
    name = str(getattr(mesh, "name", "") or f"Object {index + 1}")
    return DocumentObject(mesh_id, int(index), name, mesh)
