# -*- coding: utf-8 -*-
from __future__ import annotations

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.rendering.render_scheduler import CentralRenderScheduler


class _FakePlotter:
    def __init__(self) -> None:
        self.calls = 0

    def render(self) -> None:
        self.calls += 1


class _FakeTimer:
    def __init__(self) -> None:
        self.active = False
        self.starts: list[int] = []

    def isActive(self) -> bool:
        return self.active

    def start(self, delay: int) -> None:
        self.active = True
        self.starts.append(int(delay))


class _Owner:
    pass


def test_pass1010_mouse_drag_uses_faster_camera_render_budget(monkeypatch) -> None:
    """Central render throttling must not make camera drags feel like 30 FPS.

    Anonymous plotter.render() calls are what VTK camera interaction emits.  In
    normal UI refreshes they keep the 33 ms budget, but while a mouse button is
    held they are allowed to queue at the interactive 16 ms budget.
    """

    import laserprog_studio.rendering.render_scheduler as module

    monkeypatch.setattr(module, "_qt_event_loop_available", lambda: True)
    monkeypatch.setattr(module, "_qt_mouse_buttons_down", lambda: True)
    monkeypatch.setattr(module, "_now_ms", lambda: 100.0)

    plotter = _FakePlotter()
    scheduler = CentralRenderScheduler(
        _Owner(),
        plotter,
        min_interval_ms=33.0,
        interactive_min_interval_ms=16.0,
    )
    timer = _FakeTimer()
    scheduler._timer = timer  # type: ignore[attr-defined]
    scheduler._last_render_at_ms = 90.0

    scheduler.request(reason="plotter.render")

    assert timer.starts[-1] == 6
    assert scheduler.stats.throttled == 1
