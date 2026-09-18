# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application.tool_lifecycle_controller import ToolLifecycleController


class ToolLifecycleLayer:
    """Window-facing facade for the composed ToolLifecycleController.

    The operational tool lifecycle lives in
    ``application.tool_lifecycle_controller``.  This mixin keeps historical
    method names available for Qt signal callbacks and existing controller code
    while the application moves from inherited behaviours to composition.
    """

    def _tool_lifecycle(self) -> ToolLifecycleController:
        controller = getattr(self, "tool_lifecycle_controller", None)
        if controller is None:
            controller = ToolLifecycleController.create(self.app_context)
            self.tool_lifecycle_controller = controller
        return controller

    def _tool_display_name(self, tool_id: str | None = None) -> str:
        return self._tool_lifecycle()._tool_display_name(tool_id)

    def _button_for_tool_spec(self, spec):
        return self._tool_lifecycle()._button_for_tool_spec(spec)

    def _sync_tool_buttons(self) -> None:
        self._tool_lifecycle()._sync_tool_buttons()

    def _sync_modifier_buttons(self) -> None:
        self._tool_lifecycle()._sync_modifier_buttons()

    def confirm_preview_before_tool_change(self, context: str) -> bool:
        return self._tool_lifecycle().confirm_preview_before_tool_change(context)

    def _invoke_tool_hook(self, hook_name: str | None, *, render: bool | None = None) -> None:
        self._tool_lifecycle()._invoke_tool_hook(hook_name, render=render)


    def notify_active_creator_selection_changed(self) -> None:
        self._tool_lifecycle().notify_active_creator_selection_changed()

    def _close_previous_tool_resources(self, tool_id: str) -> None:
        self._tool_lifecycle()._close_previous_tool_resources(tool_id)

    def open_tool(self, tool_id: str) -> None:
        self._tool_lifecycle().open_tool(tool_id)

    def close_active_tool(self, log_it: bool = True, ask_preview: bool = True) -> None:
        self._tool_lifecycle().close_active_tool(log_it=log_it, ask_preview=ask_preview)

    def apply_preview_and_close_tool(self) -> None:
        self._tool_lifecycle().apply_preview_and_close_tool()

    def discard_preview_and_close_tool(self) -> None:
        self._tool_lifecycle().discard_preview_and_close_tool()
