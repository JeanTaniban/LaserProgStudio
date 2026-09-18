from __future__ import annotations

from pathlib import Path
from types import MethodType, SimpleNamespace

from laserprog_studio.application.projected_drawing_2d import ProjectedDrawingOverlay2D
from laserprog_studio.diagnostics import projected_overlay_debug


class _Props:
    def __init__(self, actors: list[object]) -> None:
        self.actors = actors

    def IsItemPresent(self, actor: object) -> int:  # noqa: N802
        return int(actor in self.actors)


class _Renderer:
    def __init__(self) -> None:
        self.actors: list[object] = []

    def GetViewProps(self) -> _Props:  # noqa: N802
        return _Props(self.actors)

    def AddActor2D(self, actor: object) -> None:  # noqa: N802
        if actor not in self.actors:
            self.actors.append(actor)


class _Manager:
    def state_token(self, _owner_tool: str) -> tuple[int, bool]:
        return (4, True)

    def snapshot(self, _owner_tool: str):
        raise AssertionError("global actor recovery must stay on the no-op sync path")


def test_runtime_diagnostics_package_is_part_of_the_application_source() -> None:
    package_dir = Path(projected_overlay_debug.__file__).resolve().parent
    assert (package_dir / "__init__.py").is_file()
    assert (package_dir / "projected_overlay_debug.py").is_file()
    assert callable(projected_overlay_debug.record_projected_overlay_event)


def test_projected_drawing_recovers_globally_removed_cached_actors() -> None:
    actor = object()
    visual = SimpleNamespace(actor=actor, dirty_all=False, dirty_indices=set())
    live_renderer = _Renderer()
    requested: list[str] = []

    overlay = ProjectedDrawingOverlay2D.__new__(ProjectedDrawingOverlay2D)
    overlay.owner = SimpleNamespace(_scene_rebuild_generation=0)
    overlay.manager = _Manager()
    overlay.owner_tool = "cloth"
    overlay.renderer = live_renderer
    overlay._observer_id = None
    overlay._visuals = {"batch": visual}
    overlay._handle_visuals = {}
    overlay._text_visuals = {}
    overlay._compiled = ()
    overlay._revision = 4
    overlay._visible = True
    overlay._last_projection_signature = ("camera", 1)
    overlay._last_projection_viewport = None
    overlay._last_camera_state = None
    overlay._last_sync_camera_mode = "static"
    overlay._attached_scene_generation = 0
    overlay._diagnostic_metrics = {
        "sync_count": 0,
        "compile_count": 0,
        "projection_count": 0,
        "cache_hit_count": 0,
    }
    overlay._ensure_renderer = MethodType(lambda self: live_renderer, overlay)
    overlay._projection_signature = MethodType(lambda self: ("camera", 1), overlay)
    overlay._request_render = MethodType(lambda self, reason: requested.append(str(reason)), overlay)
    overlay._record_sync_audit = MethodType(
        lambda self, *, compile_ms, rebuild_ms, projection_ms, path="full": None,
        overlay,
    )
    overlay._live_actor_presence_snapshot = MethodType(lambda self, renderer=None: {}, overlay)
    overlay._main_renderer = MethodType(lambda self: None, overlay)
    overlay._apply_parallel_camera_affine = MethodType(lambda self, before, after: False, overlay)
    overlay._update_projection = MethodType(lambda self, *, force_all: True, overlay)

    changed = overlay.sync_from_manager(force=False, render=False)

    assert changed is True
    assert live_renderer.actors == [actor]
    assert visual.dirty_all is True
    assert requested == ["projected_drawing_2d.reattach"]
