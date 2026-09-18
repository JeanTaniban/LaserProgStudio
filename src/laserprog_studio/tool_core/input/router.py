"""Small event router shared by migrated viewport tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..context import ToolContext
from ..events import ToolEvent, ToolEventType
from ..tools import ToolBase


class EventSink(Protocol):
    def on_event(self, event: ToolEvent, ctx: ToolContext) -> bool: ...


@dataclass(slots=True)
class EventRouter:
    """Dispatch normalized events to a tool and keep drag lifecycle centralized."""

    ctx: ToolContext
    active_tool: ToolBase | EventSink | None = None
    event_count: int = 0
    handled_count: int = 0
    drag_active: bool = False
    _history: list[ToolEventType] = field(default_factory=list)

    def set_tool(self, tool: ToolBase | EventSink | None) -> None:
        self.active_tool = tool

    def route(self, event: ToolEvent) -> bool:
        self.event_count += 1
        self._history.append(event.type)
        if len(self._history) > 32:
            self._history.pop(0)
        if event.type == ToolEventType.MOUSE_PRESS and event.is_left_click and not self.drag_active:
            self.drag_active = True
            self.ctx.begin_drag()
        try:
            handled = bool(self.active_tool and self.active_tool.on_event(event, self.ctx))
            if handled:
                self.handled_count += 1
            return handled
        finally:
            if event.type in {ToolEventType.MOUSE_RELEASE, ToolEventType.CANCEL} and self.drag_active:
                self.drag_active = False
                self.ctx.end_drag()

    def recent_types(self) -> tuple[ToolEventType, ...]:
        return tuple(self._history)
