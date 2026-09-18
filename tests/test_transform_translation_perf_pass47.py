from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.snapping import (
    SnapSettings,
    build_translation_snap_cache,
    compute_translation_snap,
    compute_translation_snap_cached,
)


@dataclass
class Mesh:
    vertices: list[tuple[float, float, float]]


def test_pass47_cached_translation_snap_matches_uncached_feature_snap() -> None:
    moving = Mesh([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 5.0, 0.0), (0.0, 5.0, 0.0)])
    target = Mesh([(20.0, 0.0, 0.0), (30.0, 0.0, 0.0), (30.0, 5.0, 0.0), (20.0, 5.0, 0.0), (24.9, 2.0, 0.0)])
    meshes = [moving, target]
    proposed = [(x + 14.8, y, z) for x, y, z in moving.vertices]
    settings = SnapSettings(grid_enabled=False, smart_enabled=True, smart_tolerance=0.25)

    uncached = compute_translation_snap(
        meshes=meshes,
        moving_index=0,
        moving_indices={0},
        start_vertices=moving.vertices,
        proposed_vertices=proposed,
        axis="x",
        settings=settings,
    )
    cache = build_translation_snap_cache(meshes=meshes, moving_index=0, moving_indices={0})
    cached = compute_translation_snap_cached(
        cache=cache,
        start_vertices=moving.vertices,
        proposed_vertices=proposed,
        axis="x",
        settings=settings,
    )

    assert cached.mode == uncached.mode == "smart"
    assert cached.candidate is not None and uncached.candidate is not None
    assert cached.candidate.kind == uncached.candidate.kind
    assert abs(cached.correction - uncached.correction) < 1e-9


def test_pass51_translation_drag_loop_uses_actor_preview_with_mesh_fallback() -> None:
    source = open("src/laserprog_studio/controllers/transform_drag.py", encoding="utf-8").read()
    translate_body = source.split("def _update_gizmo_translate_drag", 1)[1].split("def _update_gizmo_rotate_drag", 1)[0]
    assert "compute_translation_snap_cached" in translate_body
    assert "compute_translation_snap(" in translate_body  # fallback when cache is unavailable
    assert "self._set_drag_actor_offset" in translate_body
    assert "meshes[i].vertices = proposed_by_index[i]" in translate_body
    assert "self._live_drag_readout" in translate_body
    assert "self._request_drag_render" in translate_body
