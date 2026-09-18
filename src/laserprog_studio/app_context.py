# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState


@dataclass(slots=True)
class AppContext:
    """Small contract object passed to future tools/controllers.

    The historical code still uses the Qt main window as a large shared object.
    This context is the migration bridge: it exposes the stable state objects and
    forwards dynamic services such as ``mesh_store`` to the owning window so the
    reference never goes stale when a scene is loaded or cleared.
    """

    owner: Any
    selection: SelectionState
    transform: TransformState
    tool: ToolState
    preview: PreviewState
    layout: UiLayoutState
    render: RenderState
    clipboard: ClipboardState
    # Runtime Creator API context currently active for declarative tools.
    # AppContext uses slots, so CreatorStudioToolAdapter cannot attach this
    # dynamically unless the field exists explicitly.
    tool_context: Any | None = None

    @classmethod
    def from_window(cls, window: Any) -> "AppContext":
        return cls(
            owner=window,
            selection=window.selection_state,
            transform=window.transform_state,
            tool=window.tool_state,
            preview=window.preview_state,
            layout=window.ui_layout_state,
            render=window.render_state,
            clipboard=window.clipboard_state,
        )


    @property
    def ui_orchestration(self) -> Any:
        """Public UI guidance/layout/event API exposed to tools without coupling them to QMainWindow."""
        return getattr(self.owner, "ui_orchestration", None)

    @property
    def renderer(self) -> Any:
        return getattr(self.owner, "scene_renderer", None)

    @property
    def planar(self) -> Any:
        return getattr(self.owner, "planar_tool_state", None)

    @property
    def mesh_store(self) -> Any:
        return getattr(self.owner, "mesh_store", None)

    @property
    def project_store(self) -> Any:
        return getattr(self.owner, "project_store", None)

    @property
    def active_scene(self) -> Any:
        project = self.project_store
        return getattr(project, "active_scene", None) if project is not None else None

    def call_owner_method(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a owner method with a safe log when it is missing.

        New tool objects should depend on AppContext, not on the concrete
        QMainWindow. This helper is the controlled bridge used by tools
        while their hooks are migrated into proper StudioTool classes.
        """
        method = getattr(self.owner, name, None)
        if not callable(method):
            planar = getattr(self.owner, "planar_tool_controller", None)
            if planar is not None and callable(getattr(planar, "handle_lifecycle_hook", None)):
                try:
                    if planar.handle_lifecycle_hook(str(name), render=kwargs.get("render")):
                        return None
                except Exception:
                    pass
            self.ui_log(f"[TOOL] Missing lifecycle hook: {name}")
            return None
        try:
            return method(*args, **kwargs)
        except TypeError:
            if kwargs:
                return method(*args)
            raise

    def ui_log(self, message: str) -> None:
        logger = getattr(self.owner, "ui_log", None)
        if callable(logger):
            logger(message)
