# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable


class FoldingPreviewDebouncer:
    """Single-shot idle scheduler used by Folding.

    Curve actors stay live during interaction, while the expensive mesh rebuild
    is performed once after the pointer/slider has been idle for ``delay_ms``.
    The class remains usable in headless tests where Qt has no running event
    loop: tests or Apply can call :meth:`flush` explicitly.
    """

    def __init__(self, callback: Callable[[Any], None], *, delay_ms: int = 1200) -> None:
        self.callback = callback
        self.delay_ms = max(0, int(delay_ms))
        self._timer: Any | None = None
        self._ctx: Any | None = None
        self._pending = False

    @property
    def pending(self) -> bool:
        return bool(self._pending)

    def _ensure_timer(self) -> Any | None:
        if self._timer is not None:
            return self._timer
        try:
            from PySide6.QtCore import QCoreApplication, QTimer

            if QCoreApplication.instance() is None:
                return None
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(self._fire)
            self._timer = timer
        except Exception:
            self._timer = None
        return self._timer

    def schedule(self, ctx: Any) -> None:
        self._ctx = ctx
        self._pending = True
        timer = self._ensure_timer()
        if timer is None:
            # Headless/tests have no Qt event loop to deliver a delayed tick.
            self._fire()
            return
        try:
            timer.stop()
            timer.start(self.delay_ms)
        except Exception:
            # Do not leave the UI indefinitely in a pending state if the Qt
            # timer cannot be started (for example during teardown).
            self._fire()

    def _fire(self) -> None:
        if not self._pending:
            return
        ctx = self._ctx
        self._pending = False
        if ctx is not None:
            self.callback(ctx)

    def flush(self, ctx: Any | None = None) -> bool:
        if ctx is not None:
            self._ctx = ctx
        if not self._pending:
            return False
        timer = self._timer
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass
        self._fire()
        return True

    def cancel(self) -> None:
        self._pending = False
        self._ctx = None
        timer = self._timer
        if timer is not None:
            try:
                timer.stop()
            except Exception:
                pass


__all__ = ["FoldingPreviewDebouncer"]
