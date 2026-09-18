from __future__ import annotations

from pathlib import Path

SRC = Path("src/laserprog_studio/controllers/transform_drag.py").read_text(encoding="utf-8")


def _body(name: str, next_name: str) -> str:
    return SRC.split(f"def {name}", 1)[1].split(f"def {next_name}", 1)[0]


def test_pass1008_translate_drag_uses_cached_snap_and_actor_preview_commit() -> None:
    body = _body("_update_gizmo_translate_drag", "_update_gizmo_rotate_drag")
    finish = SRC.split("def _finish_gizmo_drag", 1)[1]
    assert "compute_translation_snap_cached" in body
    assert "self._set_drag_actor_offset" in body
    assert "meshes[i].vertices = proposed_by_index[i]" in body  # fallback path remains available
    assert "_commit_live_transform_preview()" in finish


def test_pass1008_rotate_and_scale_drag_do_not_write_polydata_on_default_live_path() -> None:
    rotate = _body("_update_gizmo_rotate_drag", "_update_gizmo_scale_drag")
    scale = _body("_update_gizmo_scale_drag", "_finish_gizmo_drag")
    assert "self._apply_drag_actor_matrix" in rotate
    assert "transform.drag.rotate.actor_preview" in rotate
    assert "self._apply_drag_actor_matrix" in scale
    assert "transform.drag.scale.actor_preview" in scale
    assert "self._request_drag_render(" in rotate
    assert "self._request_drag_render(" in scale


def test_pass1008_drag_loop_throttles_readout_render_and_subpixel_motion() -> None:
    assert "def _drag_qpos_changed_enough" in SRC
    assert "transform.drag.skipped_subpixel" in SRC
    assert "def _request_drag_render" in SRC
    assert "transform.drag.render_throttled" in SRC
    assert "def _live_drag_readout" in SRC
    assert "transform.drag.readout_throttled" in SRC
