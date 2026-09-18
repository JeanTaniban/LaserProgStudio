# -*- coding: utf-8 -*-
from __future__ import annotations


class StateBridge:
    """Synchronize window-style attributes with structured state objects.

    Controllers still expose convenient attributes such as ``selected_indices``
    and ``active_tool``.  The dataclass states remain the source of truth when
    present; a small in-object fallback keeps headless tests and partial owners
    usable without constructing the full application context.
    """

    @staticmethod
    def _coerce_indices(value) -> list[int]:
        if value is None:
            return []
        return [int(v) for v in list(value)]

    @property
    def selected_indices(self) -> list[int]:
        state = getattr(self, "selection_state", None)
        if state is not None:
            return state.selected_indices
        return self.__dict__.setdefault("_fallback_selected_indices", [])

    @selected_indices.setter
    def selected_indices(self, value) -> None:
        indices = self._coerce_indices(value)
        state = getattr(self, "selection_state", None)
        if state is not None:
            state.selected_indices = indices
        else:
            self.__dict__["_fallback_selected_indices"] = indices

    @property
    def active_index(self) -> int | None:
        state = getattr(self, "selection_state", None)
        if state is not None:
            return state.active_index
        return self.__dict__.get("_fallback_active_index")

    @active_index.setter
    def active_index(self, value: int | None) -> None:
        index = None if value is None else int(value)
        state = getattr(self, "selection_state", None)
        if state is not None:
            state.active_index = index
        else:
            self.__dict__["_fallback_active_index"] = index

    @property
    def active_tool(self) -> str:
        state = getattr(self, "tool_state", None)
        if state is not None:
            return state.active_tool
        return self.__dict__.get("_fallback_active_tool", "none")

    @active_tool.setter
    def active_tool(self, value: str) -> None:
        tool_id = str(value)
        state = getattr(self, "tool_state", None)
        if state is not None:
            state.active_tool = tool_id
        else:
            self.__dict__["_fallback_active_tool"] = tool_id

    @property
    def transform_mode(self) -> str:
        state = getattr(self, "transform_state", None)
        if state is not None:
            return state.mode
        return self.__dict__.get("_fallback_transform_mode", "none")

    @transform_mode.setter
    def transform_mode(self, value: str) -> None:
        mode = str(value)
        state = getattr(self, "transform_state", None)
        if state is not None:
            state.mode = mode
        else:
            self.__dict__["_fallback_transform_mode"] = mode

    @property
    def scale_ratio_locked(self) -> bool:
        state = getattr(self, "transform_state", None)
        if state is not None:
            return bool(getattr(state, "scale_ratio_locked", False))
        return bool(self.__dict__.get("_fallback_scale_ratio_locked", False))

    @scale_ratio_locked.setter
    def scale_ratio_locked(self, value: bool) -> None:
        locked = bool(value)
        state = getattr(self, "transform_state", None)
        if state is not None:
            state.scale_ratio_locked = locked
        else:
            self.__dict__["_fallback_scale_ratio_locked"] = locked

    @property
    def actors_by_index(self):
        state = getattr(self, "render_state", None)
        if state is not None:
            return state.actors_by_index
        return self.__dict__.setdefault("_fallback_actors_by_index", {})

    @actors_by_index.setter
    def actors_by_index(self, value) -> None:
        state = getattr(self, "render_state", None)
        if state is not None:
            state.actors_by_index = value
        else:
            self.__dict__["_fallback_actors_by_index"] = value

    @property
    def polydata_by_index(self):
        state = getattr(self, "render_state", None)
        if state is not None:
            return state.polydata_by_index
        return self.__dict__.setdefault("_fallback_polydata_by_index", {})

    @polydata_by_index.setter
    def polydata_by_index(self, value) -> None:
        state = getattr(self, "render_state", None)
        if state is not None:
            state.polydata_by_index = value
        else:
            self.__dict__["_fallback_polydata_by_index"] = value

    @property
    def floor_grid_actor(self):
        state = getattr(self, "render_state", None)
        if state is not None:
            return state.floor_grid_actor
        return self.__dict__.get("_fallback_floor_grid_actor")

    @floor_grid_actor.setter
    def floor_grid_actor(self, value) -> None:
        state = getattr(self, "render_state", None)
        if state is not None:
            state.floor_grid_actor = value
        else:
            self.__dict__["_fallback_floor_grid_actor"] = value

    @property
    def _copy_buffer_meshes(self):
        state = getattr(self, "clipboard_state", None)
        if state is not None:
            return state.meshes
        return self.__dict__.setdefault("_fallback_copy_buffer_meshes", [])

    @_copy_buffer_meshes.setter
    def _copy_buffer_meshes(self, value) -> None:
        meshes = [] if value is None else list(value)
        state = getattr(self, "clipboard_state", None)
        if state is not None:
            state.meshes = meshes
        else:
            self.__dict__["_fallback_copy_buffer_meshes"] = meshes


__all__ = ["StateBridge"]
