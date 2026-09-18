# -*- coding: utf-8 -*-
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable
import itertools
import time
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None

from ..studio_log import log_exception


WorkerFn = Callable[[], Any]
Callback = Callable[[Any], None]
ErrorCallback = Callable[[BaseException], None]
FinallyCallback = Callable[[], None]


@dataclass(slots=True)
class _TaskRecord:
    token: int
    key: str
    future: Future
    timer: Any | None


class BackgroundTaskManager:
    """Small Qt-friendly worker runner for expensive geometry tasks.

    Worker functions run in a single background thread and must not touch Qt
    widgets, VTK actors or the window.  The callbacks are polled back on the Qt
    main thread through a QTimer, which keeps the app responsive while avoiding
    cross-thread UI access.
    """

    def __init__(self, owner: Any, *, max_workers: int = 1, poll_ms: int = 35) -> None:
        self.owner = owner
        self.poll_ms = int(max(10, poll_ms))
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers)), thread_name_prefix="LaserProgWorker")
        self._counter = itertools.count(1)
        self._latest_token_by_key: dict[str, int] = {}
        self._records: dict[tuple[str, int], _TaskRecord] = {}

    def latest_token(self, key: str) -> int | None:
        return self._latest_token_by_key.get(str(key))

    def is_current(self, key: str, token: int) -> bool:
        return self._latest_token_by_key.get(str(key)) == int(token)

    def run(
        self,
        key: str,
        worker: WorkerFn,
        *,
        on_success: Callback | None = None,
        on_error: ErrorCallback | None = None,
        on_finished: FinallyCallback | None = None,
        description: str = "Background task",
    ) -> int:
        """Submit *worker* and return its freshness token.

        Submitting a new task with the same key marks older callbacks stale.
        Already-running work is allowed to finish, but its result is ignored.
        """
        key = str(key)
        token = int(next(self._counter))
        self._latest_token_by_key[key] = token
        if _APP_AUDIT is not None:
            _APP_AUDIT.increment(f"background.submit.{key}")
            _APP_AUDIT.increment("background.submit.total")

        def _measured_worker():
            start = time.perf_counter()
            try:
                return worker()
            finally:
                if _APP_AUDIT is not None:
                    _APP_AUDIT.record_timing(f"background.worker.{key}", (time.perf_counter() - start) * 1000.0, details={"description": description})

        future = self._executor.submit(_measured_worker)
        record = _TaskRecord(token=token, key=key, future=future, timer=None)
        self._records[(key, token)] = record

        try:
            from PySide6.QtCore import QTimer
            timer = QTimer(self.owner)
            timer.setInterval(self.poll_ms)
            timer.timeout.connect(lambda k=key, t=token: self._poll(k, t, on_success, on_error, on_finished, description))
            record.timer = timer
            timer.start()
        except Exception:
            # Headless/unit-test fallback.  This path is synchronous by design:
            # it preserves behavior when no Qt event loop exists.
            try:
                result = future.result()
                if self.is_current(key, token) and on_success is not None:
                    on_success(result)
            except BaseException as exc:  # noqa: BLE001 - deliberate callback boundary
                if self.is_current(key, token) and on_error is not None:
                    on_error(exc)
                else:
                    log_exception(f"background_task:{description}")
            finally:
                if on_finished is not None:
                    on_finished()
                self._records.pop((key, token), None)
        return token

    def _poll(
        self,
        key: str,
        token: int,
        on_success: Callback | None,
        on_error: ErrorCallback | None,
        on_finished: FinallyCallback | None,
        description: str,
    ) -> None:
        record = self._records.get((key, token))
        if record is None:
            return
        if not record.future.done():
            return
        timer = record.timer
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass
        self._records.pop((key, token), None)
        current = self.is_current(key, token)
        try:
            result = record.future.result()
            if current and on_success is not None:
                start = time.perf_counter()
                try:
                    on_success(result)
                finally:
                    if _APP_AUDIT is not None:
                        _APP_AUDIT.record_timing(f"background.success_callback.{key}", (time.perf_counter() - start) * 1000.0, details={"description": description})
        except BaseException as exc:  # noqa: BLE001 - deliberate callback boundary
            if current and on_error is not None:
                on_error(exc)
            else:
                log_exception(f"background_task:{description}")
        finally:
            if current and on_finished is not None:
                start = time.perf_counter()
                try:
                    on_finished()
                finally:
                    if _APP_AUDIT is not None:
                        _APP_AUDIT.record_timing(f"background.finished_callback.{key}", (time.perf_counter() - start) * 1000.0, details={"description": description})

    def shutdown(self) -> None:
        try:
            for record in list(self._records.values()):
                try:
                    if record.timer is not None:
                        record.timer.stop()
                        record.timer.deleteLater()
                except Exception:
                    pass
            self._records.clear()
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


def task_manager_for(owner: Any) -> BackgroundTaskManager:
    manager = getattr(owner, "background_task_manager", None)
    if manager is None:
        manager = BackgroundTaskManager(owner)
        try:
            setattr(owner, "background_task_manager", manager)
        except Exception:
            pass
    return manager


__all__ = ["BackgroundTaskManager", "task_manager_for"]
