"""Thin viewport adapter and render scheduler.

This isolates tools from direct PyVista/VTK calls. Tests can use the memory backend,
while the application can adapt this class to the real plotter later.
"""
from __future__ import annotations

import time

try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover - diagnostics must never break rendering
    _APP_AUDIT = None
from dataclasses import dataclass
from typing import Any, Callable

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


@dataclass(slots=True)
class RenderStats:
    light_requests: int = 0
    full_requests: int = 0
    renders_performed: int = 0
    throttled_requests: int = 0


class RenderScheduler:
    def __init__(self, render_func: Callable[[], None] | None = None, *, min_interval_ms: float = 16.0) -> None:
        self.render_func = render_func
        self.min_interval_ms = float(min_interval_ms)
        self.stats = RenderStats()
        self._last_render_at = 0.0

    def request_light_render(self, *, force: bool = False) -> bool:
        self.stats.light_requests += 1
        if _APP_AUDIT is not None:
            _APP_AUDIT.increment("render.light_request")
        now = time.perf_counter() * 1000.0
        if not force and now - self._last_render_at < self.min_interval_ms:
            self.stats.throttled_requests += 1
            if _APP_AUDIT is not None:
                _APP_AUDIT.increment("render.throttled_request")
            return False
        self._perform_render(now, reason="light")
        return True

    def request_full_render(self) -> None:
        self.stats.full_requests += 1
        if _APP_AUDIT is not None:
            _APP_AUDIT.increment("render.full_request")
        self._perform_render(time.perf_counter() * 1000.0, reason="full")

    def _perform_render(self, now_ms: float, *, reason: str = "unknown") -> None:
        self._last_render_at = now_ms
        self.stats.renders_performed += 1
        if _APP_AUDIT is not None:
            _APP_AUDIT.increment("render.performed")
        if self.render_func is not None:
            start = time.perf_counter()
            try:
                self.render_func()
            finally:
                if _APP_AUDIT is not None:
                    _APP_AUDIT.record_timing(f"render.perform.{reason}", (time.perf_counter() - start) * 1000.0)


class ViewportAdapter:
    def __init__(self, *, render_func: Callable[[], None] | None = None) -> None:
        self.actors: dict[str, Any] = {}
        self.scheduler = RenderScheduler(render_func)

    def add_actor(self, actor_id: str, actor: Any) -> None:
        self.actors[actor_id] = actor

    def remove_actor(self, actor_id: str) -> None:
        self.actors.pop(actor_id, None)

    def get_actor(self, actor_id: str) -> Any | None:
        return self.actors.get(actor_id)

    def request_light_render(self, *, force: bool = False) -> bool:
        return self.scheduler.request_light_render(force=force)

    def request_full_render(self) -> None:
        self.scheduler.request_full_render()

    def screen_to_world_on_plane(self, screen_pos: Point2, plane_z: float = 0.0) -> Point3:
        # Real application code can replace this adapter with camera-aware picking.
        return (float(screen_pos[0]), float(screen_pos[1]), float(plane_z))

    def world_to_screen(self, world_pos: Point3) -> Point2:
        # Tests and 2D sketch tools can use this deterministic default.
        return (float(world_pos[0]), float(world_pos[1]))
