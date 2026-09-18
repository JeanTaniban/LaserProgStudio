"""Common tool and mode contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .events import ToolEvent

if TYPE_CHECKING:  # pragma: no cover
    from .context import ToolContext


class ToolModeBase:
    id = "mode"
    label = "Mode"

    def enter(self, ctx: "ToolContext") -> None:  # noqa: ARG002
        return None

    def exit(self, ctx: "ToolContext") -> None:  # noqa: ARG002
        return None

    def on_event(self, event: ToolEvent, ctx: "ToolContext") -> bool:  # noqa: ARG002
        return False

    def on_escape(self, ctx: "ToolContext") -> bool:  # noqa: ARG002
        return False


class ToolBase:
    id = "tool"
    label = "Tool"
    default_mode_id = "modify"

    def __init__(self) -> None:
        self.modes: dict[str, ToolModeBase] = {}
        self.active_mode_id: str | None = None

    def register_mode(self, mode: ToolModeBase) -> None:
        self.modes[mode.id] = mode

    @property
    def active_mode(self) -> ToolModeBase | None:
        if self.active_mode_id is None:
            return None
        return self.modes.get(self.active_mode_id)

    def activate(self, ctx: "ToolContext") -> None:
        target = self.default_mode_id if self.default_mode_id in self.modes else self.active_mode_id
        if target is not None:
            self.set_mode(target, ctx)

    def deactivate(self, ctx: "ToolContext") -> None:
        if self.active_mode is not None:
            self.active_mode.exit(ctx)
        ctx.preview.clear_tool(self.id)
        ctx.gizmos.clear_tool(self.id)
        ctx.selection.clear()
        self.active_mode_id = None

    def set_mode(self, mode_id: str, ctx: "ToolContext") -> bool:
        if mode_id not in self.modes:
            return False
        if self.active_mode_id == mode_id:
            return True
        if self.active_mode is not None:
            self.active_mode.exit(ctx)
        self.active_mode_id = mode_id
        self.modes[mode_id].enter(ctx)
        ctx.overlay.set_group_active(f"{self.id}.modes", mode_id)
        return True

    def cancel_to_default(self, ctx: "ToolContext") -> None:
        if self.default_mode_id in self.modes:
            self.set_mode(self.default_mode_id, ctx)

    def on_event(self, event: ToolEvent, ctx: "ToolContext") -> bool:
        if event.is_escape:
            mode = self.active_mode
            handled = bool(mode and mode.on_escape(ctx))
            if not handled:
                self.cancel_to_default(ctx)
            return True
        mode = self.active_mode
        return bool(mode and mode.on_event(event, ctx))


@dataclass(slots=True)
class ToolRegistry:
    _factories: dict[str, Callable[[], ToolBase]] = field(default_factory=dict)
    active_tool: ToolBase | None = None

    def register(self, tool_id: str, factory: Callable[[], ToolBase]) -> None:
        self._factories[tool_id] = factory

    def create(self, tool_id: str) -> ToolBase:
        if tool_id not in self._factories:
            raise KeyError(f"Unknown tool: {tool_id}")
        return self._factories[tool_id]()

    def activate(self, tool_id: str, ctx: "ToolContext") -> ToolBase:
        if self.active_tool is not None:
            self.active_tool.deactivate(ctx)
        self.active_tool = self.create(tool_id)
        self.active_tool.activate(ctx)
        return self.active_tool

    def deactivate_current(self, ctx: "ToolContext") -> None:
        if self.active_tool is not None:
            self.active_tool.deactivate(ctx)
        self.active_tool = None
