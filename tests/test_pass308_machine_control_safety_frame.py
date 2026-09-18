# -*- coding: utf-8 -*-
from __future__ import annotations

from shapely.geometry import Polygon

from laserprog_studio.engraving.export_2d import Instance2D, RenderConfig
from laserprog_studio.machine.gcode import GCodeJobSettings, generate_frame_gcode, generate_gcode
from laserprog_studio.machine.safety import MachineEnvelope, validate_gcode
from laserprog_studio.machine.transport.serial_grbl import GrblSerialTransport
from pathlib import Path


def _outline_with_hole():
    poly = Polygon(
        [(0, 0), (40, 0), (40, 20), (0, 20)],
        holes=[[(10, 5), (30, 5), (30, 15), (10, 15)]],
    )
    return [Instance2D("cut", "#00C853", poly, 3.0)]


def test_machine_dialog_has_frame_mode_and_explicit_state_machine():
    source = Path("src/laserprog_studio/machine/ui/machine_dialog.py").read_text(encoding="utf-8")
    assert "def _frame_job(" in source
    assert "def _emergency_stop(" in source
    assert 'FRAMING = "framing"' in source
    assert 'EMERGENCY = "emergency"' in source
    assert 'QShortcut(QKeySequence("F12")' in source


def test_safety_blocks_xy_outside_machine_envelope():
    report = validate_gcode(
        ["G21", "G90", "M5", "G0 X10 Y10 F1000", "G1 X401 Y10 F1000", "M5"],
        MachineEnvelope(381.0, 305.0),
        allow_laser=False,
    )
    assert not report.safe
    assert any("outside the permitted range" in issue.message for issue in report.violations)


def test_safety_blocks_laser_commands_in_frame_mode():
    report = validate_gcode(
        ["G21", "G90", "M5", "G0 X1 Y1 F1000", "M4 S10", "G1 X5 Y5 F1000", "M5"],
        MachineEnvelope(381.0, 305.0),
        allow_laser=False,
    )
    assert not report.safe
    assert any("Laser-on commands are forbidden" in issue.message for issue in report.violations)



def test_safety_blocks_rapid_move_while_laser_is_enabled():
    report = validate_gcode(
        ["G21", "G90", "M4 S50", "G0 X10 Y10 F1000", "M5"],
        MachineEnvelope(381.0, 305.0),
        allow_laser=True,
    )
    assert not report.safe
    assert any("Rapid G0 movement" in issue.message for issue in report.violations)


def test_safety_rejects_absolute_z_and_unretracted_relative_z():
    absolute = validate_gcode(
        ["G21", "G90", "M5", "G0 Z-1 F1000", "M5"],
        MachineEnvelope(381.0, 305.0),
        allow_laser=False,
        allow_relative_z=True,
        max_relative_z_depth_mm=2.0,
    )
    assert not absolute.safe
    assert any("Absolute Z" in issue.message for issue in absolute.violations)

    relative = validate_gcode(
        ["G21", "G91", "M5", "G0 Z-1 F1000", "G90", "M5"],
        MachineEnvelope(381.0, 305.0),
        allow_laser=False,
        allow_relative_z=True,
        max_relative_z_depth_mm=2.0,
        z_down_sign=-1,
    )
    assert not relative.safe
    assert any("does not retract Z" in issue.message for issue in relative.violations)


def test_frame_program_uses_only_outer_contours_and_never_enables_laser():
    cfg = RenderConfig()
    cfg.page_margin_ratio = 0.0
    job = generate_gcode(
        _outline_with_hole(),
        cfg,
        GCodeJobSettings(include_fill_engraving=False),
    )
    assert job.frame_paths
    assert all(path.note == "outer" for path in job.frame_paths)
    frame = generate_frame_gcode(job, feed_mm_min=2000.0)
    assert not any(line.strip().startswith(("M3", "M4")) for line in frame)
    assert sum(1 for line in frame if line.startswith("; Exterior frame contour")) == 1
    report = validate_gcode(frame, MachineEnvelope(381.0, 305.0), allow_laser=False)
    assert report.safe, report.blocking_text()


class _FakeSerial:
    def __init__(self):
        self.is_open = True
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, payload: bytes):
        self.writes.append(bytes(payload))
        return len(payload)

    def flush(self):
        return None

    def close(self):
        self.closed = True
        self.is_open = False


def test_transport_emergency_stop_uses_realtime_hold_and_reset_then_closes():
    transport = GrblSerialTransport("COM_TEST")
    fake = _FakeSerial()
    transport._serial = fake  # type: ignore[attr-defined]
    transport.emergency_stop(close_port=True)
    assert fake.writes == [b"!", bytes((0x18,))]
    assert fake.closed
    assert not transport.is_open
