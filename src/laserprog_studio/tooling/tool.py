# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .base import ToolSpec


@runtime_checkable
class StudioTool(Protocol):
    """Runtime contract for Studio tools/modifiers.

    ``ToolSpec`` is the static metadata used to build buttons and menus.
    ``StudioTool`` is the object-level extension point new tools should target:
    it can validate/open/close itself through a small AppContext instead of
    depending on the full Qt main window. Existing hand-written tools are
    exposed through explicit runtime classes; external hook-based extensions
    can use ``HookToolAdapter`` through the registry fallback.
    """

    spec: ToolSpec

    def can_open(self, context: Any, selected_count: int) -> bool:
        ...

    def selection_error_message(self, context: Any) -> str:
        ...

    def on_open(self, context: Any) -> None:
        ...

    def on_close(self, context: Any, *, render: bool = False) -> None:
        ...

    def default_parameters(self) -> dict[str, Any]:
        ...

    def validate_parameters(self, values: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True, slots=True)
class HookToolAdapter:
    """Adapter that turns a hook-based extension spec into a StudioTool.

    Built-in tools are expected to provide dedicated runtime classes. This small
    adapter remains for third-party extensions and tests that deliberately route
    open/close through owner/controller methods.
    """

    spec: ToolSpec

    def can_open(self, context: Any, selected_count: int) -> bool:
        if not self.spec.requires_selection:
            return True
        if selected_count <= 0 and bool(getattr(self.spec, "open_without_initial_selection", False)) and context is not None:
            return True
        if self.spec.selection_policy == "multi":
            return selected_count >= 1
        return selected_count >= 1

    def selection_error_message(self, context: Any) -> str:
        if self.spec.selection_policy == "multi":
            return f"Select at least one target part before opening {self.spec.label}."
        if self.spec.selection_policy == "single":
            return f"Select a target part before opening {self.spec.label}."
        return ""

    def default_parameters(self) -> dict[str, Any]:
        return self.spec.default_parameters()

    def validate_parameters(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.spec.validate_parameters(values)

    def on_open(self, context: Any) -> None:
        self._call_hook(context, self.spec.open_hook)

    def on_close(self, context: Any, *, render: bool = False) -> None:
        self._call_hook(context, self.spec.close_hook, render=render)

    @staticmethod
    def _call_hook(context: Any, hook_name: str | None, **kwargs: Any) -> None:
        if not hook_name:
            return
        call_owner_method = getattr(context, "call_owner_method", None)
        if callable(call_owner_method):
            call_owner_method(hook_name, **kwargs)
            return
        owner = getattr(context, "owner", None)
        hook = getattr(owner, hook_name, None)
        if not callable(hook):
            logger = getattr(context, "ui_log", None)
            if callable(logger):
                logger(f"[TOOL] Missing lifecycle hook: {hook_name}")
            return
        try:
            hook(**kwargs)
        except TypeError:
            hook()

__all__ = ["StudioTool", "HookToolAdapter"]
