"""Status and progress reporting service independent from Qt widgets."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class StatusMessage:
    level: Literal["info", "warning", "error", "progress"]
    message: str
    progress: float | None = None
    timestamp: float = field(default_factory=time.time)


class StatusManager:
    """Tool status/reporting API independent from Qt widgets."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._messages: list[StatusMessage] = []

    def bind_context(self, ctx: Any) -> "StatusManager":
        self._ctx = ctx
        return self

    def info(self, message: str) -> StatusMessage:
        return self._add("info", message)

    def warning(self, message: str) -> StatusMessage:
        return self._add("warning", message)

    def error(self, message: str) -> StatusMessage:
        return self._add("error", message)

    def progress(self, message: str, value: float) -> StatusMessage:
        return self._add("progress", message, progress=max(0.0, min(1.0, float(value))))

    def clear(self) -> None:
        self._messages.clear()

    def messages(self, *, level: str | None = None) -> tuple[StatusMessage, ...]:
        if level is None:
            return tuple(self._messages)
        return tuple(message for message in self._messages if message.level == level)

    def latest(self, *, level: str | None = None) -> StatusMessage | None:
        messages = self.messages(level=level)
        return messages[-1] if messages else None

    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self._messages),
            "latest": self._messages[-1].message if self._messages else None,
            "errors": [message.message for message in self._messages if message.level == "error"],
            "warnings": [message.message for message in self._messages if message.level == "warning"],
        }

    def _add(self, level: Literal["info", "warning", "error", "progress"], message: str, *, progress: float | None = None) -> StatusMessage:
        item = StatusMessage(level=level, message=str(message), progress=progress)
        self._messages.append(item)
        ctx = self._ctx
        logger = getattr(getattr(ctx, "scene", None), "ui_log", None) if ctx is not None else None
        if not callable(logger):
            logger = getattr(ctx, "ui_log", None) if ctx is not None else None
        if callable(logger):
            try:
                logger(f"[{level.upper()}] {message}")
            except Exception:
                pass
        return item
