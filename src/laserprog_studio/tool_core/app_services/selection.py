"""Selection facade for scene/document objects."""
from __future__ import annotations

from typing import Any, Iterable

from .common import ToolServiceError
from .document import DocumentFacade, DocumentObject


class SceneSelectionFacade:
    """Selection API for real scene objects, distinct from tool actors."""

    def __init__(self) -> None:
        self._ctx: Any | None = None

    def bind_context(self, ctx: Any) -> "SceneSelectionFacade":
        self._ctx = ctx
        return self

    def selected_indices(self) -> tuple[int, ...]:
        """Return the current *host* scene selection.

        During the Creator API migration there are two selection stores in play:
        the historical Qt window/SelectionState used by picking and the
        ModelStore.selected_mesh_indices used by some headless tests.  The Qt
        selection is authoritative whenever a real window is bound; otherwise
        Creator tools opened after a user click see an empty ModelStore
        selection and modifiers such as Simplify/Hollow never stage previews.
        """

        owner_indices = self._owner_selected_indices()
        if owner_indices is not None:
            cleaned = self._clean_indices(owner_indices)
            self._sync_store_selection(cleaned)
            return tuple(cleaned)

        state = getattr(self._ctx, "selection_state", None)
        if state is not None:
            cleaned = self._clean_indices(getattr(state, "selected_indices", []) or [])
            self._sync_store_selection(cleaned)
            return tuple(cleaned)

        store = self._store(required=False)
        if store is not None:
            return tuple(self._clean_indices(getattr(store, "selected_mesh_indices", []) or []))
        return ()

    def active_index(self) -> int | None:
        indices = self.selected_indices()
        state = getattr(self._ctx, "selection_state", None)
        raw = getattr(state, "active_index", None)
        if raw is not None:
            return int(raw)
        return indices[-1] if indices else None

    def selected_objects(self) -> tuple[DocumentObject, ...]:
        objects = self._document().objects()
        return tuple(objects[index] for index in self.selected_indices() if 0 <= index < len(objects))

    def selected_meshes(self) -> tuple[Any, ...]:
        return tuple(obj.mesh for obj in self.selected_objects())

    def active_object(self) -> DocumentObject | None:
        index = self.active_index()
        if index is None:
            return None
        try:
            return self._document().objects()[index]
        except Exception:
            return None

    def select_indices(self, indices: Iterable[int], *, active_index: int | None = None) -> tuple[int, ...]:
        """Select scene objects by index and sync the host UI when present."""

        return self.set_selected(indices, active_index=active_index)

    def select_range(self, start: int, stop: int) -> tuple[int, ...]:
        """Select a contiguous inclusive/exclusive index range like ``range``."""

        return self.set_selected(range(int(start), int(stop)))

    def select_last(self, count: int = 1) -> tuple[int, ...]:
        """Select the last ``count`` document objects."""

        total = len(self._document().objects())
        amount = max(0, int(count))
        return self.set_selected(range(max(0, total - amount), total))

    def set_selected(self, indices: Iterable[int], *, active_index: int | None = None) -> tuple[int, ...]:
        objects = self._document().objects()
        cleaned: list[int] = []
        for raw in indices:
            index = int(raw)
            if 0 <= index < len(objects) and index not in cleaned:
                cleaned.append(index)
        store = self._store(required=False)
        if store is not None and hasattr(store, "_selected_mesh_indices"):
            setattr(store, "_selected_mesh_indices", list(cleaned))
            notify = getattr(store, "_notify", None)
            if callable(notify):
                notify()
        state = getattr(self._ctx, "selection_state", None)
        if state is not None:
            try:
                state.selected_indices = list(cleaned)
                state.active_index = active_index if active_index is not None else (cleaned[-1] if cleaned else None)
            except Exception:
                pass
        owner = getattr(self._ctx, "owner", None)
        active = active_index if active_index is not None else (cleaned[-1] if cleaned else None)
        if owner is not None:
            try:
                owner.selected_indices = list(cleaned)
                owner.active_index = active
            except Exception:
                pass
            self._sync_owner_mesh_list(owner, cleaned)
        return tuple(cleaned)

    def _sync_owner_mesh_list(self, owner: Any, selected: list[int]) -> None:
        mesh_list = getattr(owner, "mesh_list", None)
        if mesh_list is None:
            return
        try:
            mesh_list.clearSelection()
            for index in selected:
                item = mesh_list.item(int(index))
                if item is not None:
                    item.setSelected(True)
        except Exception:
            pass

    def _owner_selected_indices(self) -> list[int] | None:
        ctx = self._ctx
        owner = getattr(ctx, "owner", None) if ctx is not None else None
        if owner is None:
            return None
        try:
            return [int(i) for i in (getattr(owner, "selected_indices", []) or [])]
        except Exception:
            return []

    def _clean_indices(self, indices: Iterable[int]) -> list[int]:
        try:
            total = len(self._document().objects(include_preview=True))
        except Exception:
            total = 0
        cleaned: list[int] = []
        for raw in indices or []:
            try:
                index = int(raw)
            except Exception:
                continue
            if (total <= 0 or 0 <= index < total) and index not in cleaned:
                cleaned.append(index)
        return cleaned

    def _sync_store_selection(self, selected: list[int]) -> None:
        store = self._store(required=False)
        if store is None or not hasattr(store, "_selected_mesh_indices"):
            return
        try:
            current = list(getattr(store, "_selected_mesh_indices", []) or [])
            if current == list(selected):
                return
            setattr(store, "_selected_mesh_indices", list(selected))
            notify = getattr(store, "_notify", None)
            if callable(notify):
                notify()
        except Exception:
            pass

    def clear(self) -> None:
        self.set_selected(())

    def require_single(self, message: str = "Select exactly one scene object.") -> DocumentObject:
        selected = self.selected_objects()
        if len(selected) != 1:
            raise ToolServiceError(message)
        return selected[0]

    def require_multi(self, min_count: int = 1, message: str | None = None) -> tuple[DocumentObject, ...]:
        selected = self.selected_objects()
        if len(selected) < int(min_count):
            raise ToolServiceError(message or f"Select at least {int(min_count)} scene object(s).")
        return selected

    def _document(self) -> DocumentFacade:
        ctx = self._ctx
        if ctx is None:
            raise ToolServiceError("Scene selection is not bound to a ToolContext.")
        document = getattr(ctx, "document", None)
        if not isinstance(document, DocumentFacade):
            raise ToolServiceError("ctx.document is not a DocumentFacade.")
        return document

    def _store(self, *, required: bool) -> Any | None:
        return self._document()._model_store(required=required)
