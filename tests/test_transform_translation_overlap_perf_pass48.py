from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.snapping import SnapSettings, build_translation_snap_cache, compute_translation_snap_cached


@dataclass
class Mesh:
    vertices: list[tuple[float, float, float]]


def test_pass48_cached_snap_uses_sorted_axis_index_and_still_finds_feature_snap() -> None:
    moving = Mesh([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 5.0, 0.0), (0.0, 5.0, 0.0)])
    targets = []
    for i in range(80):
        x = 40.0 + i * 17.0
        targets.append(Mesh([(x, 0.0, 0.0), (x + 8.0, 0.0, 0.0), (x + 8.0, 5.0, 0.0), (x, 5.0, 0.0), (x + 3.25, 2.0, 0.0)]))
    # Feature at 43.25 should capture moving max at 43.20 with +0.05 correction.
    proposed = [(x + 33.2, y, z) for x, y, z in moving.vertices]
    cache = build_translation_snap_cache(meshes=[moving, *targets], moving_index=0, moving_indices={0})
    assert cache.axis_index is not None
    assert cache.axis_index["x"].features

    snap = compute_translation_snap_cached(
        cache=cache,
        start_vertices=moving.vertices,
        proposed_vertices=proposed,
        axis="x",
        settings=SnapSettings(grid_enabled=False, smart_enabled=True, smart_tolerance=0.10),
    )

    assert snap.mode == "smart"
    assert snap.candidate is not None
    assert snap.candidate.kind == "feature"
    assert abs(snap.correction - 0.05) < 1e-9


def test_pass51_translation_drag_uses_actor_preview_but_commits_once() -> None:
    source = open("src/laserprog_studio/controllers/transform_drag.py", encoding="utf-8").read()
    translate_body = source.split("def _update_gizmo_translate_drag", 1)[1].split("def _update_gizmo_rotate_drag", 1)[0]
    finish_body = source.split("def _finish_gizmo_drag", 1)[1]
    assert "_set_drag_actor_offset" in translate_body
    assert "_commit_live_transform_preview()" in finish_body
    assert "_commit_live_translation_preview()" not in finish_body


def test_pass48_snap_status_does_not_repaint_same_label_each_mouse_tick() -> None:
    source = open("src/laserprog_studio/ui/transform_controls.py", encoding="utf-8").read()
    body = source.split("def _set_snap_status", 1)[1].split("def ", 1)[0]
    assert "label == getattr(self, \"_last_snap_label\"" in body
    assert "return" in body
