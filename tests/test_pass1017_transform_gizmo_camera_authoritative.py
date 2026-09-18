from pathlib import Path


def test_overlay_rebuilds_ephemeral_geometry_from_current_camera() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_overlay_2d.py").read_text(encoding="utf-8")
    assert "def _camera_scaled_snapshot" in source
    assert "self.owner._gizmo_length_at(center, self.owner.current_meshes())" in source
    body = source.split("def update_before_render", 1)[1].split("def _before_render", 1)[0]
    assert "snapshot = self._camera_scaled_snapshot(source_snapshot)" in body


def test_transform_2d_wheel_uses_native_render_as_single_clock() -> None:
    source = Path("src/laserprog_studio/controllers/interaction_gizmo_refresh.py").read_text(encoding="utf-8")
    body = source.split("def _request_zoom_gizmo_refresh", 1)[1].split("def _request_live_gizmo_refresh", 1)[0]
    assert "transform_is_2d" in body
    assert "if needs_auxiliary_pulse:" in body
    assert "self._schedule_zoom_live_pulse" in body
