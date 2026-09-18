"""Preview session helpers for generated tools and modifiers."""
from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Iterable, Mapping

from .common import ToolServiceError


@dataclass(slots=True)
class PreviewSession:
    ctx: Any
    owner_tool: str
    label: str = "Preview session"
    snapshot: tuple[list[Any], Any | None] | None = None
    active: bool = True
    applied: bool = False

    def show_meshes(self, meshes: Iterable[Any]) -> None:
        self._ensure_active()
        self.ctx.document.set_preview_meshes(list(meshes))
        self._sync_owner_preview_state()
        self.ctx.status.info(f"{self.label}: preview updated")

    def show_mesh(self, mesh: Any, *, append: bool = True) -> None:
        base = list(self.ctx.document.meshes(include_preview=False)) if append else []
        base.append(mesh)
        self.show_meshes(base)

    def replace_object_preview(self, object_id: str | int, mesh: Any) -> None:
        self._ensure_active()
        index = self.ctx.document.index_for(object_id)
        meshes = list(self.ctx.document.meshes(include_preview=False))
        meshes[index] = copy.deepcopy(mesh)
        self.show_meshes(meshes)

    def replace_objects_preview(self, replacements: Mapping[str | int, Any] | Iterable[tuple[str | int, Any]]) -> None:
        """Stage several object replacements in one atomic preview update.

        Calling ``replace_object_preview`` repeatedly would rebuild every
        replacement from the committed document and therefore discard earlier
        replacements.  Group modifiers such as Folding need one shared preview
        transaction while preserving every source object as a distinct mesh.
        """

        self._ensure_active()
        items = replacements.items() if isinstance(replacements, Mapping) else tuple(replacements)
        meshes = list(self.ctx.document.meshes(include_preview=False))
        seen: set[int] = set()
        for object_id, mesh in items:
            index = int(self.ctx.document.index_for(object_id))
            if index in seen:
                raise ToolServiceError(f"Duplicate preview replacement for object index {index}.")
            seen.add(index)
            meshes[index] = copy.deepcopy(mesh)
        self.show_meshes(meshes)

    def apply(self, *, label: str | None = None, operation_type: str = "tool_apply") -> bool:
        self._ensure_active()
        changed = self.ctx.document.commit_preview(label=label or self.label, operation_type=operation_type)
        self.active = False
        self.applied = changed
        self.ctx.status.info(f"{label or self.label}: applied" if changed else f"{label or self.label}: no changes")
        return changed

    def cancel(self) -> bool:
        if not self.active:
            return False
        changed = self.ctx.document.discard_preview() if self.ctx.document.has_preview else False
        self.active = False
        self.ctx.status.info(f"{self.label}: cancelled")
        return changed

    def _sync_owner_preview_state(self) -> None:
        owner = getattr(self.ctx, "owner", None)
        if owner is None:
            return
        rebuild = getattr(owner, "rebuild_scene", None)
        if callable(rebuild):
            try:
                rebuild(keep_camera=True)
            except TypeError:
                rebuild()
        update_preview_state = getattr(owner, "update_preview_state", None)
        if callable(update_preview_state):
            try:
                update_preview_state()
            except Exception:
                pass
        sync_history = getattr(owner, "_sync_history_buttons", None)
        if callable(sync_history):
            try:
                sync_history()
            except Exception:
                pass

    def _ensure_active(self) -> None:
        if not self.active:
            raise ToolServiceError(f"Preview session {self.label!r} is closed.")

    def __enter__(self) -> "PreviewSession":
        return self

    def __exit__(self, exc_type: Any, exc: BaseException | None, tb: Any) -> None:
        if exc_type is not None and self.active:
            self.cancel()


class PreviewSessionManager:
    def __init__(self) -> None:
        self._ctx: Any | None = None
        self.current: PreviewSession | None = None

    def bind_context(self, ctx: Any) -> "PreviewSessionManager":
        self._ctx = ctx
        return self

    def start(self, *, owner_tool: str = "tool", label: str = "Preview session", cancel_existing: bool = True) -> PreviewSession:
        ctx = self._require_ctx()
        if cancel_existing and self.current is not None and self.current.active:
            self.current.cancel()
        session = PreviewSession(ctx=ctx, owner_tool=str(owner_tool), label=str(label), snapshot=ctx.document.snapshot())
        self.current = session
        return session

    def cancel(self) -> bool:
        return bool(self.current and self.current.cancel())

    def apply(self, *, label: str | None = None, operation_type: str = "tool_apply") -> bool:
        if self.current is None or not bool(getattr(self.current, "active", False)):
            return False
        return self.current.apply(label=label, operation_type=operation_type)

    def _require_ctx(self) -> Any:
        if self._ctx is None:
            raise ToolServiceError("PreviewSessionManager is not bound to a ToolContext.")
        return self._ctx
