"""Normalized input events used by every viewport tool."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


class ToolEventType(str, Enum):
    MOUSE_PRESS = "mouse_press"
    MOUSE_MOVE = "mouse_move"
    MOUSE_RELEASE = "mouse_release"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    CANCEL = "cancel"


class MouseButton(str, Enum):
    LEFT = "left"
    MIDDLE = "middle"
    RIGHT = "right"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class ToolEvent:
    type: ToolEventType
    screen_pos: Point2 | None = None
    world_pos: Point3 | None = None
    button: MouseButton = MouseButton.NONE
    key: str | None = None
    modifiers: frozenset[str] = field(default_factory=frozenset)
    raw: Any | None = None

    @property
    def is_escape(self) -> bool:
        return self.type == ToolEventType.KEY_PRESS and (self.key or "").lower() in {"escape", "esc"}

    @property
    def is_delete(self) -> bool:
        return self.type == ToolEventType.KEY_PRESS and (self.key or "").lower() in {"delete", "del", "backspace"}

    @property
    def is_press(self) -> bool:
        return self.type == ToolEventType.MOUSE_PRESS

    @property
    def is_move(self) -> bool:
        return self.type == ToolEventType.MOUSE_MOVE

    @property
    def is_release(self) -> bool:
        return self.type == ToolEventType.MOUSE_RELEASE

    @property
    def is_double_click(self) -> bool:
        return self.type == ToolEventType.MOUSE_DOUBLE_CLICK

    @property
    def is_left(self) -> bool:
        return self.button == MouseButton.LEFT

    @property
    def is_left_click(self) -> bool:
        return self.is_left

    @property
    def shift(self) -> bool:
        return any(value.lower() == "shift" for value in self.modifiers)

    @property
    def ctrl(self) -> bool:
        return any(value.lower() in {"ctrl", "control"} for value in self.modifiers)

    @property
    def alt(self) -> bool:
        return any(value.lower() == "alt" for value in self.modifiers)

    @property
    def has_world_pos(self) -> bool:
        return self.world_pos is not None

    @property
    def has_screen_pos(self) -> bool:
        return self.screen_pos is not None


@dataclass(slots=True)
class DragState:
    active: bool = False
    handle_id: str | None = None
    start_screen_pos: Point2 | None = None
    current_screen_pos: Point2 | None = None
    start_world_pos: Point3 | None = None
    current_world_pos: Point3 | None = None

    def begin(self, event: ToolEvent, handle_id: str | None = None) -> None:
        self.active = True
        self.handle_id = handle_id
        self.start_screen_pos = event.screen_pos
        self.current_screen_pos = event.screen_pos
        self.start_world_pos = event.world_pos
        self.current_world_pos = event.world_pos

    def update(self, event: ToolEvent) -> None:
        if not self.active:
            return
        self.current_screen_pos = event.screen_pos
        self.current_world_pos = event.world_pos

    @property
    def drag_delta_screen(self) -> Point2 | None:
        if self.start_screen_pos is None or self.current_screen_pos is None:
            return None
        return (float(self.current_screen_pos[0]) - float(self.start_screen_pos[0]), float(self.current_screen_pos[1]) - float(self.start_screen_pos[1]))

    @property
    def drag_delta_world(self) -> Point3 | None:
        if self.start_world_pos is None or self.current_world_pos is None:
            return None
        return (
            float(self.current_world_pos[0]) - float(self.start_world_pos[0]),
            float(self.current_world_pos[1]) - float(self.start_world_pos[1]),
            float(self.current_world_pos[2]) - float(self.start_world_pos[2]),
        )

    def end(self) -> None:
        self.active = False
        self.handle_id = None
        self.start_screen_pos = None
        self.current_screen_pos = None
        self.start_world_pos = None
        self.current_world_pos = None


def screen_distance(a: Point2, b: Point2) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return (dx * dx + dy * dy) ** 0.5
