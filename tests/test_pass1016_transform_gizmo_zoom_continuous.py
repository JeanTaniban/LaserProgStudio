from pathlib import Path


def test_pass1016_wheel_zoom_runs_a_continuous_camera_scale_pulse() -> None:
    source = Path("src/laserprog_studio/controllers/interaction_gizmo_refresh.py").read_text(encoding="utf-8")
    request = source.split("def _request_zoom_gizmo_refresh", 1)[1].split("def _request_live_gizmo_refresh", 1)[0]
    pulse = source.split("def _run_zoom_live_pulse", 1)[1].split("def _request_zoom_gizmo_refresh", 1)[0]

    assert "_schedule_zoom_live_pulse" in request
    assert "_request_live_gizmo_refresh(render=True, fast_transform_resize=True)" in pulse
    assert "_camera_zoom_burst_until" in pulse
    assert "QTimer.singleShot(interval_ms" in pulse


def test_pass1016_runtime_initializes_zoom_pulse_state() -> None:
    source = Path("src/laserprog_studio/runtime_state.py").read_text(encoding="utf-8")
    assert "self._gizmo_zoom_live_pulse_pending = False" in source
    assert "self._gizmo_zoom_live_serial = 0" in source
