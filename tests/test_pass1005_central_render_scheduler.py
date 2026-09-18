# -*- coding: utf-8 -*-
from __future__ import annotations

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.rendering.render_scheduler import CentralRenderScheduler, install_central_render_scheduler


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
    _performance_mode = "optimized"


def test_pass1005_plotter_render_is_patched_and_coalesced(monkeypatch) -> None:
    import laserprog_studio.rendering.render_scheduler as module

    monkeypatch.setattr(module, "_qt_event_loop_available", lambda: True)
    owner = _Owner()
    plotter = _FakePlotter()
    scheduler = CentralRenderScheduler(owner, plotter, min_interval_ms=33.0)
    fake_timer = _FakeTimer()
    scheduler._timer = fake_timer  # type: ignore[attr-defined]
    scheduler.install_plotter_patch()

    assert getattr(plotter, "_lps_original_render") is not plotter.render
    assert plotter.calls == 0

    plotter.render()
    plotter.render()

    assert plotter.calls == 0
    assert fake_timer.active is True
    assert scheduler.stats.requests == 2
    assert scheduler.stats.coalesced == 1

    fake_timer.active = False
    assert scheduler.flush() is True
    assert plotter.calls == 1
    assert scheduler.stats.performed == 1


def test_pass1005_immediate_render_uses_original_renderer(monkeypatch) -> None:
    import laserprog_studio.rendering.render_scheduler as module

    monkeypatch.setattr(module, "_qt_event_loop_available", lambda: True)
    owner = _Owner()
    plotter = _FakePlotter()
    scheduler = install_central_render_scheduler(owner, plotter, min_interval_ms=33.0)
    assert scheduler is not None

    assert owner.request_render(reason="unit.immediate", immediate=True) is True
    assert plotter.calls == 1
    assert scheduler.stats.immediate_requests == 1
    assert scheduler.stats.performed == 1


def test_pass1005_headless_requests_stay_synchronous(monkeypatch) -> None:
    import laserprog_studio.rendering.render_scheduler as module

    monkeypatch.setattr(module, "_qt_event_loop_available", lambda: False)
    owner = _Owner()
    plotter = _FakePlotter()
    scheduler = install_central_render_scheduler(owner, plotter, min_interval_ms=33.0)
    assert scheduler is not None

    assert plotter.render() is True
    assert plotter.calls == 1
    assert scheduler.stats.performed == 1
