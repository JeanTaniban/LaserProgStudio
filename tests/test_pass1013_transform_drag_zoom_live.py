from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from laserprog_studio.application.transform_gizmo_api import (
    MANIPULATOR_ID,
    OWNER_TOOL,
    pick_native_transform_gizmo,
    resize_native_transform_gizmo_live,
    sync_native_translate_gizmo,
)
from laserprog_studio.rendering.render_scheduler import CentralRenderScheduler
from laserprog_studio.snapping import (
    SnapSettings,
    build_translation_moving_profile,
    build_translation_snap_cache,
    compute_translation_snap_cached,
    compute_translation_snap_offset_cached,
)


@dataclass
class _Mesh:
    vertices: list[tuple[float, float, float]]


class _FakePlotter:
    def __init__(self) -> None:
        self.calls = 0

    def height(self) -> int:
        return 400

    def width(self) -> int:
        return 600

    def render(self) -> None:
        self.calls += 1


class _FakeOwner:
    _native_transform_gizmo_enabled = True

    def __init__(self) -> None:
        self.plotter = _FakePlotter()
        self.gizmo_actors = {}
        self._native_transform_gizmo_active = False

    def _world_to_display(self, point):
        x, y, z = point
        return (300.0 + float(x) * 10.0, 200.0 + float(y) * 10.0, float(z))


def _axes():
    return {
        "x": ((1.0, 0.0, 0.0), "#ff0000"),
        "y": ((0.0, 1.0, 0.0), "#00ff00"),
        "z": ((0.0, 0.0, 1.0), "#0000ff"),
    }


def test_pass1013_scalar_translation_snap_matches_vertex_path() -> None:
    moving = _Mesh([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 5.0, 0.0), (0.0, 5.0, 0.0)])
    target = _Mesh([(20.0, 0.0, 0.0), (30.0, 0.0, 0.0), (30.0, 5.0, 0.0), (20.0, 5.0, 0.0), (24.9, 2.0, 0.0)])
    cache = build_translation_snap_cache(meshes=[moving, target], moving_index=0, moving_indices={0})
    profile = build_translation_moving_profile(moving.vertices)
    settings = SnapSettings(grid_enabled=False, smart_enabled=True, smart_tolerance=0.25)
    offset = 14.8
    proposed = [(x + offset, y, z) for x, y, z in moving.vertices]

    old = compute_translation_snap_cached(
        cache=cache,
        start_vertices=moving.vertices,
        proposed_vertices=proposed,
        axis="x",
        settings=settings,
    )
    fast = compute_translation_snap_offset_cached(
        cache=cache,
        moving_profile=profile,
        axis="x",
        offset=offset,
        settings=settings,
    )

    assert fast.mode == old.mode == "smart"
    assert fast.candidate is not None and old.candidate is not None
    assert fast.candidate.kind == old.candidate.kind
    assert abs(fast.correction - old.correction) < 1e-9


def test_pass1013_native_translate_gizmo_resizes_live_without_redeclaration() -> None:
    owner = _FakeOwner()
    assert sync_native_translate_gizmo(owner, center=(0.0, 0.0, 0.0), length=10.0, axes=_axes(), render=False)
    ctx = owner._native_transform_gizmo_ctx
    handle_before = ctx.transform_gizmos.handle(f"{MANIPULATOR_ID}:x", owner_tool=OWNER_TOOL)

    assert resize_native_transform_gizmo_live(owner, length=5.0, render=False)

    handle_after = ctx.transform_gizmos.handle(f"{MANIPULATOR_ID}:x", owner_tool=OWNER_TOOL)
    assert handle_before is not None and handle_after is not None
    assert handle_after.id == handle_before.id
    assert len(ctx.transform_gizmos.handles(owner_tool=OWNER_TOOL)) == 4
    assert owner._native_transform_gizmo_snapshot.length == 5.0
    assert handle_after.position == (5.0, 0.0, 0.0)
    line = next(item for item in ctx.preview.items(owner_tool=OWNER_TOOL) if item.id == f"{MANIPULATOR_ID}:axis:x")
    assert line.points == ((0.0, 0.0, 0.0), (4.3, 0.0, 0.0))
    assert pick_native_transform_gizmo(owner, 349.0, 200.0) == ("gizmo", "x")


def test_pass1013_translation_actor_path_does_not_allocate_vertices_per_mouse_move() -> None:
    source = Path("src/laserprog_studio/controllers/transform_drag.py").read_text(encoding="utf-8")
    body = source.split("def _update_gizmo_translate_drag", 1)[1].split("def _update_gizmo_rotate_drag", 1)[0]
    actor_prefix = body.split("if self._drag_actor_preview_enabled():", 1)[0]
    assert "compute_translation_snap_offset_cached" in body
    assert "_drag_live_translation_offset" in body
    assert "proposed_by_index" not in actor_prefix
    assert "transform.drag.translate.actor_offset_fast_path" in body


def test_pass1013_wheel_refreshes_gizmo_live_and_keeps_final_burst_refresh() -> None:
    interaction = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    refresh = Path("src/laserprog_studio/controllers/interaction_gizmo_refresh.py").read_text(encoding="utf-8")
    camera = Path("src/laserprog_studio/controllers/camera.py").read_text(encoding="utf-8")
    assert "_request_zoom_gizmo_refresh(after_camera_event=True)" in interaction
    assert "resize_native_transform_gizmo_live" in refresh
    assert "_gizmo_live_refresh_interval_ms" in refresh
    assert "_refresh_camera_scaled_overlays(render=False)" in camera


def test_pass1013_camera_zoom_burst_uses_interactive_render_budget(monkeypatch) -> None:
    import laserprog_studio.rendering.render_scheduler as module

    monkeypatch.setattr(module, "_qt_event_loop_available", lambda: True)
    monkeypatch.setattr(module, "_qt_mouse_buttons_down", lambda: False)
    monkeypatch.setattr(module, "_now_ms", lambda: 100.0)
    monkeypatch.setattr(module.time, "monotonic", lambda: 5.0)

    owner = type("Owner", (), {"_camera_zoom_burst_until": 6.0})()
    plotter = _FakePlotter()
    scheduler = CentralRenderScheduler(owner, plotter, min_interval_ms=33.0, interactive_min_interval_ms=16.0)

    class _Timer:
        def __init__(self) -> None:
            self.active = False
            self.starts: list[int] = []

        def isActive(self) -> bool:
            return self.active

        def start(self, delay: int) -> None:
            self.active = True
            self.starts.append(int(delay))

    timer = _Timer()
    scheduler._timer = timer  # type: ignore[attr-defined]
    scheduler._last_render_at_ms = 90.0
    scheduler.request(reason="plotter.render")
    assert timer.starts[-1] == 6
