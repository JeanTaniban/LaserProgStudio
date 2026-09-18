# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from laserprog_studio.engraving.export_2d import export_falcon_svg
from laserprog_studio.machine.gcode import GCodeJob, GCodeJobSettings, ManualFocusSettings, generate_frame_gcode, generate_gcode
from laserprog_studio.machine.profiles import FALCON_A1_PRO_PROFILE, MachineProfile
from laserprog_studio.machine.safety import MachineEnvelope, validate_gcode
from laserprog_studio.machine.transport import GrblSerialTransport, MachineTransportError, list_serial_ports


class MachineRunState(str, Enum):
    DISCONNECTED = "disconnected"
    IDLE = "idle"
    STREAMING = "streaming"
    FRAMING = "framing"
    STOPPING = "stopping"
    EMERGENCY = "emergency"


class _MachineStreamWorker(QObject):
    progress = Signal(int, str, int)
    completed = Signal(str, int)
    failed = Signal(str)

    def __init__(self, transport: GrblSerialTransport, lines: tuple[str, ...], *, loop: bool, operation: str):
        super().__init__()
        self._transport = transport
        self._lines = tuple(lines)
        self._loop = bool(loop)
        self._operation = str(operation)
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        cycles = 0
        sent_total = 0
        try:
            self._transport.command("M5", wait_ok=True)
            while not self._cancel.is_set():
                cycles += 1

                def on_progress(count: int, line: str) -> None:
                    self.progress.emit(count, line, cycles)

                sent_total += self._transport.stream_gcode(
                    self._lines,
                    progress=on_progress,
                    should_cancel=self._cancel.is_set,
                )
                if not self._loop:
                    break
            if self._transport.is_open:
                try:
                    self._transport.command("M5", wait_ok=True)
                except Exception:
                    pass
            self.completed.emit(self._operation, sent_total)
        except Exception as exc:
            self.failed.emit(str(exc))


class MachineEngravingDialog(QDialog):
    """Safe GRBL engraving sender with bounded motion and laser-off framing."""

    def __init__(self, parent, *, instances, cfg, default_dir: Path | str, profile: MachineProfile = FALCON_A1_PRO_PROFILE):
        super().__init__(parent)
        self._instances = instances
        self._cfg = cfg
        self._default_dir = Path(default_dir)
        self._profile = profile
        self._job: GCodeJob | None = None
        self._gcode_text = ""
        self._transport: GrblSerialTransport | None = None
        self._state = MachineRunState.DISCONNECTED
        self._thread: QThread | None = None
        self._worker: _MachineStreamWorker | None = None
        self._abort_expected = False
        self.setWindowTitle("Machine / Engraving — Safe G-code + USB")
        self.resize(1080, 760)
        self._build_ui()
        self._refresh_ports()
        self._set_state(MachineRunState.DISCONNECTED)
        self._append_log(profile.notes)
        self._append_log(
            f"Safety envelope: X 0…{profile.work_area_x_mm:.3f} mm, "
            f"Y 0…{profile.work_area_y_mm:.3f} mm. F12 = emergency stop."
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        title = QLabel(f"{self._profile.label} — guarded machine control")
        title.setStyleSheet("font-weight: 900; font-size: 13pt;")
        root.addWidget(title)
        subtitle = QLabel(
            "Every program is validated against the configured machine dimensions before USB transmission. "
            "Frame mode follows exterior contours repeatedly with M5 enforced. Keep the physical machine stop accessible."
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.state_label = QLabel()
        self.state_label.setStyleSheet("font-weight: 900; padding: 5px;")
        root.addWidget(self.state_label)

        grid = QHBoxLayout()
        grid.addWidget(self._build_focus_box(), 1)
        grid.addWidget(self._build_job_box(), 1)
        grid.addWidget(self._build_usb_box(), 1)
        root.addLayout(grid)

        buttons = QHBoxLayout()
        self.btn_svg = QPushButton("Export Falcon SVG")
        self.btn_svg.clicked.connect(self._export_svg)
        buttons.addWidget(self.btn_svg)
        self.btn_generate = QPushButton("Generate + validate G-code")
        self.btn_generate.clicked.connect(self._generate_gcode)
        buttons.addWidget(self.btn_generate)
        self.btn_save = QPushButton("Save G-code")
        self.btn_save.clicked.connect(self._save_gcode)
        buttons.addWidget(self.btn_save)
        buttons.addStretch(1)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(False)
        self.preview.setPlaceholderText(
            "Generated G-code appears here. Manual edits are allowed, but unsupported or out-of-envelope commands are blocked before sending."
        )
        root.addWidget(self.preview, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(175)
        root.addWidget(self.log)

        self._emergency_shortcut = QShortcut(QKeySequence("F12"), self)
        self._emergency_shortcut.activated.connect(self._emergency_stop)

    def _build_focus_box(self) -> QGroupBox:
        box = QGroupBox("Manual focus / Z safety")
        layout = QGridLayout(box)
        self.support_h = self._double(0.0, 200.0, 0.0, 0.1)
        self.material_h = self._double(0.1, 80.0, 3.0, 0.1)
        self.focus_dist = self._double(0.1, 50.0, self._profile.default_focus_distance_mm, 0.1)
        self.safety_margin = self._double(0.0, 10.0, 0.5, 0.1)
        self.max_focus_depth = self._double(0.0, 80.0, 1.0, 0.1)
        self.z_steps_enabled = QCheckBox("Move Z between cut passes")
        self.z_step = self._double(0.0, 20.0, 0.0, 0.1)
        self.z_direction = QComboBox()
        self.z_direction.addItem("GRBL conventional: Z negative goes down", -1)
        self.z_direction.addItem("Machine-specific: Z positive goes down", 1)
        rows = [
            ("Support/honeycomb height", self.support_h, "mm"),
            ("Material thickness", self.material_h, "mm"),
            ("Focus distance", self.focus_dist, "mm"),
            ("Safety margin", self.safety_margin, "mm"),
            ("Max focus depth", self.max_focus_depth, "mm"),
        ]
        for row, (label, widget, unit) in enumerate(rows):
            layout.addWidget(QLabel(label), row, 0)
            layout.addWidget(widget, row, 1)
            layout.addWidget(QLabel(unit), row, 2)
        row = len(rows)
        layout.addWidget(self.z_steps_enabled, row, 0, 1, 3)
        row += 1
        layout.addWidget(QLabel("Z step per pass"), row, 0)
        layout.addWidget(self.z_step, row, 1)
        layout.addWidget(QLabel("mm"), row, 2)
        row += 1
        layout.addWidget(QLabel("Z direction"), row, 0)
        layout.addWidget(self.z_direction, row, 1, 1, 2)
        note = QLabel("Absolute Z commands are always blocked. Z movement is emitted as bounded relative steps and retracted at job end.")
        note.setWordWrap(True)
        layout.addWidget(note, row + 1, 0, 1, 3)
        return box

    def _build_job_box(self) -> QGroupBox:
        box = QGroupBox("G-code job")
        layout = QGridLayout(box)
        self.include_fill = QCheckBox("Engrave red fill as hatch")
        self.include_fill.setChecked(True)
        self.include_cut = QCheckBox("Cut green outlines")
        self.include_cut.setChecked(True)
        self.dynamic_power = QCheckBox("Use M4 dynamic laser power")
        self.dynamic_power.setChecked(True)
        self.cut_power = self._double(0.0, 100.0, 80.0, 1.0)
        self.cut_speed = self._double(1.0, min(20_000.0, self._profile.max_feed_mm_min), 180.0, 10.0)
        self.cut_passes = QSpinBox(); self.cut_passes.setRange(1, 50); self.cut_passes.setValue(1)
        self.engrave_power = self._double(0.0, 100.0, 18.0, 1.0)
        self.engrave_speed = self._double(1.0, self._profile.max_feed_mm_min, 1200.0, 10.0)
        self.hatch_spacing = self._double(0.02, 5.0, 0.25, 0.01)
        self.travel_speed = self._double(1.0, self._profile.max_feed_mm_min, 3000.0, 10.0)
        layout.addWidget(self.include_fill, 0, 0, 1, 3)
        layout.addWidget(self.include_cut, 1, 0, 1, 3)
        layout.addWidget(self.dynamic_power, 2, 0, 1, 3)
        rows = [
            ("Cut power", self.cut_power, "%"),
            ("Cut speed", self.cut_speed, "mm/min"),
            ("Cut passes", self.cut_passes, ""),
            ("Engrave power", self.engrave_power, "%"),
            ("Engrave speed", self.engrave_speed, "mm/min"),
            ("Hatch spacing", self.hatch_spacing, "mm"),
            ("Travel speed", self.travel_speed, "mm/min"),
        ]
        for i, (label, widget, unit) in enumerate(rows, start=3):
            layout.addWidget(QLabel(label), i, 0)
            layout.addWidget(widget, i, 1)
            layout.addWidget(QLabel(unit), i, 2)
        return box

    def _build_usb_box(self) -> QGroupBox:
        box = QGroupBox("USB GRBL — guarded sender")
        layout = QGridLayout(box)
        self.port_combo = QComboBox()
        self.btn_refresh_ports = QPushButton("Refresh")
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self._toggle_connect)
        self.btn_status = QPushButton("Status ?")
        self.btn_status.clicked.connect(lambda: self._send_command("?", wait_ok=False))
        self.btn_firmware = QPushButton("Firmware $I")
        self.btn_firmware.clicked.connect(lambda: self._send_command("$I"))
        self.btn_unlock = QPushButton("Unlock $X")
        self.btn_unlock.clicked.connect(self._unlock_machine)
        self.btn_laser_off = QPushButton("Laser off M5")
        self.btn_laser_off.clicked.connect(lambda: self._send_command("M5"))
        self.frame_speed = self._double(1.0, self._profile.max_frame_feed_mm_min, 2500.0, 50.0)
        self.xy_inset = self._double(0.0, min(self._profile.work_area_x_mm, self._profile.work_area_y_mm) * 0.25, 0.0, 0.5)
        self.btn_frame = QPushButton("Start FRAME loop (M5)")
        self.btn_frame.clicked.connect(self._frame_job)
        self.btn_send = QPushButton("Send current G-code")
        self.btn_send.setStyleSheet("font-weight: 900;")
        self.btn_send.clicked.connect(self._send_gcode)
        self.btn_emergency = QPushButton("EMERGENCY STOP — F12")
        self.btn_emergency.setStyleSheet("font-weight: 1000; background: #b00020; color: white; padding: 8px;")
        self.btn_emergency.clicked.connect(self._emergency_stop)

        layout.addWidget(QLabel("Port"), 0, 0)
        layout.addWidget(self.port_combo, 0, 1)
        layout.addWidget(self.btn_refresh_ports, 0, 2)
        layout.addWidget(self.btn_connect, 1, 0, 1, 3)
        layout.addWidget(QLabel(f"Machine X/Y: {self._profile.work_area_x_mm:.1f} × {self._profile.work_area_y_mm:.1f} mm"), 2, 0, 1, 3)
        layout.addWidget(QLabel("XY safety inset"), 3, 0)
        layout.addWidget(self.xy_inset, 3, 1)
        layout.addWidget(QLabel("mm"), 3, 2)
        layout.addWidget(QLabel("Frame speed"), 4, 0)
        layout.addWidget(self.frame_speed, 4, 1)
        layout.addWidget(QLabel("mm/min"), 4, 2)
        layout.addWidget(self.btn_status, 5, 0)
        layout.addWidget(self.btn_firmware, 5, 1)
        layout.addWidget(self.btn_unlock, 5, 2)
        layout.addWidget(self.btn_laser_off, 6, 0)
        layout.addWidget(self.btn_frame, 6, 1, 1, 2)
        layout.addWidget(self.btn_send, 7, 0, 1, 3)
        layout.addWidget(self.btn_emergency, 8, 0, 1, 3)
        note = QLabel(
            "FRAME loops over the actual exterior contours when available, with M5 before every movement sequence. "
            "Stopping FRAME or using emergency stop resets GRBL and requires reconnection."
        )
        note.setWordWrap(True)
        layout.addWidget(note, 9, 0, 1, 3)
        return box

    def _settings(self) -> GCodeJobSettings:
        focus = ManualFocusSettings(
            support_height_mm=float(self.support_h.value()),
            material_thickness_mm=float(self.material_h.value()),
            focus_distance_mm=float(self.focus_dist.value()),
            safety_margin_mm=float(self.safety_margin.value()),
            max_focus_depth_mm=float(self.max_focus_depth.value()),
            enable_z_steps=bool(self.z_steps_enabled.isChecked()),
            z_step_per_pass_mm=float(self.z_step.value()),
            z_down_sign=int(self.z_direction.currentData()),
        )
        return GCodeJobSettings(
            job_name="LaserProg Falcon A1 Pro job",
            cut_power_percent=float(self.cut_power.value()),
            cut_feed_mm_min=float(self.cut_speed.value()),
            cut_passes=int(self.cut_passes.value()),
            engrave_power_percent=float(self.engrave_power.value()),
            engrave_feed_mm_min=float(self.engrave_speed.value()),
            hatch_spacing_mm=float(self.hatch_spacing.value()),
            travel_feed_mm_min=float(self.travel_speed.value()),
            use_dynamic_power_m4=bool(self.dynamic_power.isChecked()),
            include_fill_engraving=bool(self.include_fill.isChecked()),
            include_outline_cut=bool(self.include_cut.isChecked()),
            focus=focus,
        )

    def _envelope(self) -> MachineEnvelope:
        return MachineEnvelope(
            width_mm=float(self._profile.work_area_x_mm),
            height_mm=float(self._profile.work_area_y_mm),
            inset_mm=float(self.xy_inset.value()),
            max_feed_mm_min=float(self._profile.max_feed_mm_min),
            max_power_s=int(self._profile.default_power_max_s),
        )

    def _allowed_z_depth(self, settings: GCodeJobSettings) -> float:
        material_limit = max(0.0, float(settings.focus.material_thickness_mm) - max(0.0, float(settings.focus.safety_margin_mm)))
        return min(max(0.0, float(settings.focus.max_focus_depth_mm)), material_limit)

    def _export_svg(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Falcon SVG", str(self._default_dir / "laserprog_falcon.svg"), "SVG (*.svg)")
        if not path:
            return
        try:
            out = export_falcon_svg(self._instances, self._cfg, Path(path))
            self._append_log(f"SVG exported: {out}")
        except Exception as exc:
            QMessageBox.warning(self, "SVG export", str(exc))

    def _generate_gcode(self) -> bool:
        try:
            settings = self._settings()
            job = generate_gcode(self._instances, self._cfg, settings, self._profile)
            report = validate_gcode(
                job.lines,
                self._envelope(),
                allow_laser=True,
                allow_relative_z=bool(settings.focus.enable_z_steps),
                max_relative_z_depth_mm=self._allowed_z_depth(settings),
                z_down_sign=int(settings.focus.z_down_sign),
            )
            self._job = job
            self._gcode_text = job.text
            self.preview.setPlainText(self._gcode_text)
            summary = (
                f"G-code generated: {job.cut_paths} cut path(s), {job.engrave_paths} hatch segment(s), "
                f"size {job.width_mm:.2f} × {job.height_mm:.2f} mm."
            )
            if job.warnings:
                summary += "\nWarnings:\n- " + "\n- ".join(job.warnings)
            if report.safe:
                summary += (
                    f"\nSafety validation passed: X {report.min_x_mm:.3f}…{report.max_x_mm:.3f} mm, "
                    f"Y {report.min_y_mm:.3f}…{report.max_y_mm:.3f} mm."
                )
            else:
                summary += "\nBLOCKED by safety validation:\n" + report.blocking_text()
            self._append_log(summary)
            if not report.safe:
                QMessageBox.warning(self, "Unsafe G-code", report.blocking_text())
            return report.safe
        except Exception as exc:
            QMessageBox.warning(self, "G-code generation", str(exc))
            return False

    def _save_gcode(self) -> None:
        if not self.preview.toPlainText().strip():
            self._generate_gcode()
        text = self.preview.toPlainText().strip()
        if not text:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save G-code", str(self._default_dir / "laserprog_falcon_a1_pro.gcode"), "G-code (*.gcode *.nc *.txt)")
        if not path:
            return
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        self._append_log(f"G-code saved: {out}")

    def _refresh_ports(self) -> None:
        if self._state in (MachineRunState.STREAMING, MachineRunState.FRAMING, MachineRunState.STOPPING):
            return
        self.port_combo.clear()
        ports = list_serial_ports()
        if not ports:
            self.port_combo.addItem("No serial port detected", "")
            return
        for port in ports:
            self.port_combo.addItem(port.label, port.device)

    def _toggle_connect(self) -> None:
        if self._transport is not None and self._transport.is_open:
            if self._state in (MachineRunState.STREAMING, MachineRunState.FRAMING, MachineRunState.STOPPING):
                QMessageBox.warning(self, "USB", "Stop the active machine operation before disconnecting.")
                return
            self._transport.close()
            self._transport = None
            self._set_state(MachineRunState.DISCONNECTED)
            self._append_log("USB disconnected.")
            return
        port = str(self.port_combo.currentData() or "")
        if not port:
            QMessageBox.warning(self, "USB", "No serial port selected.")
            return
        try:
            self._set_state(MachineRunState.STOPPING, detail="Connecting…")
            transport = GrblSerialTransport(port)
            banner = transport.connect()
            self._transport = transport
            self._set_state(MachineRunState.IDLE)
            self._append_log("USB connected." + (("\n" + "\n".join(banner)) if banner else ""))
        except MachineTransportError as exc:
            self._transport = None
            self._set_state(MachineRunState.DISCONNECTED)
            QMessageBox.warning(self, "USB", str(exc))

    def _unlock_machine(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Unlock GRBL?",
            "$X clears an alarm without homing. Only continue if the cause of the alarm has been physically corrected and the origin is known.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._send_command("$X")

    def _send_command(self, line: str, *, wait_ok: bool = True) -> None:
        if not self._require_idle_connection():
            return
        try:
            responses = self._transport.command(line, wait_ok=wait_ok)  # type: ignore[union-attr]
            self._append_log(f"> {line}" + (("\n" + "\n".join(responses)) if responses else ""))
        except MachineTransportError as exc:
            QMessageBox.warning(self, "USB", str(exc))

    def _frame_job(self) -> None:
        if self._state == MachineRunState.FRAMING:
            self._stop_active_operation("Frame mode stopped by user.")
            return
        if not self._require_idle_connection():
            return
        if not self._generate_gcode() or self._job is None:
            return
        frame_lines = generate_frame_gcode(self._job, feed_mm_min=float(self.frame_speed.value()))
        report = validate_gcode(frame_lines, self._envelope(), allow_laser=False, allow_relative_z=False)
        if not report.safe:
            QMessageBox.warning(self, "Unsafe frame", report.blocking_text())
            return
        answer = QMessageBox.question(
            self,
            "Start continuous FRAME mode?",
            "The machine will repeatedly follow the exterior contours with the laser forced OFF (M5).\n\n"
            "Verify the origin and keep clear of moving axes. Press the FRAME button again to stop. F12 is emergency stop.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_stream(frame_lines, loop=True, operation="frame")

    def _send_gcode(self) -> None:
        if not self._require_idle_connection():
            return
        text = self.preview.toPlainText().strip()
        if not text:
            if not self._generate_gcode():
                return
            text = self.preview.toPlainText().strip()
        if not text:
            return
        settings = self._settings()
        blocking_settings = [w for w in settings.validate() if any(word in w.lower() for word in ("exceed", "must", "cannot"))]
        if blocking_settings:
            QMessageBox.warning(self, "Unsafe Z/job settings", "Fix these settings before sending:\n\n" + "\n".join(blocking_settings))
            return
        lines = tuple(text.splitlines())
        report = validate_gcode(
            lines,
            self._envelope(),
            allow_laser=True,
            allow_relative_z=bool(settings.focus.enable_z_steps),
            max_relative_z_depth_mm=self._allowed_z_depth(settings),
            z_down_sign=int(settings.focus.z_down_sign),
        )
        if not report.safe:
            QMessageBox.warning(self, "Transmission blocked by machine safety", report.blocking_text())
            self._append_log("Transmission blocked:\n" + report.blocking_text())
            return
        answer = QMessageBox.warning(
            self,
            "Send laser job?",
            f"Validated envelope: X {report.min_x_mm:.3f}…{report.max_x_mm:.3f} mm, "
            f"Y {report.min_y_mm:.3f}…{report.max_y_mm:.3f} mm.\n\n"
            "This will stream laser-on G-code. Verify material, focus, origin, frame, air assist, enclosure and supervision.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._start_stream(lines, loop=False, operation="job")

    def _start_stream(self, lines: tuple[str, ...], *, loop: bool, operation: str) -> None:
        transport = self._transport
        if transport is None or not transport.is_open:
            return
        if self._thread is not None:
            QMessageBox.warning(self, "Machine", "A machine operation is already active.")
            return
        self._abort_expected = False
        thread = QThread(self)
        worker = _MachineStreamWorker(transport, lines, loop=loop, operation=operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_stream_progress)
        worker.completed.connect(self._on_stream_completed)
        worker.failed.connect(self._on_stream_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._clear_worker)
        self._thread = thread
        self._worker = worker
        self._set_state(MachineRunState.FRAMING if loop else MachineRunState.STREAMING)
        self._append_log("FRAME mode started; M5 enforced." if loop else "Laser job streaming started.")
        thread.start()

    @Slot(int, str, int)
    def _on_stream_progress(self, count: int, line: str, cycle: int) -> None:
        if count == 1 or count % 25 == 0:
            prefix = f"[frame cycle {cycle}]" if self._state == MachineRunState.FRAMING else "[job]"
            self._append_log(f"{prefix} [{count}] {line}")

    @Slot(str, int)
    def _on_stream_completed(self, operation: str, sent_total: int) -> None:
        if self._state not in (MachineRunState.EMERGENCY, MachineRunState.DISCONNECTED):
            self._set_state(MachineRunState.IDLE if self._transport and self._transport.is_open else MachineRunState.DISCONNECTED)
        if not self._abort_expected:
            self._append_log(f"{operation.title()} operation complete ({sent_total} command(s) sent).")

    @Slot(str)
    def _on_stream_failed(self, message: str) -> None:
        if self._abort_expected:
            self._append_log("Active machine operation aborted safely; reconnect before continuing.")
            return
        self._append_log("Machine operation failed: " + message)
        self._set_state(MachineRunState.IDLE if self._transport and self._transport.is_open else MachineRunState.DISCONNECTED)
        QMessageBox.warning(self, "Machine operation", message)

    @Slot()
    def _clear_worker(self) -> None:
        thread = self._thread
        self._worker = None
        self._thread = None
        if thread is not None:
            thread.deleteLater()

    def _stop_active_operation(self, reason: str) -> None:
        if self._state not in (MachineRunState.FRAMING, MachineRunState.STREAMING):
            return
        self._abort_expected = True
        self._set_state(MachineRunState.STOPPING)
        if self._worker is not None:
            self._worker.request_cancel()
        self._append_log(reason + " Sending GRBL real-time hold/reset; reconnection will be required.")
        transport = self._transport
        self._transport = None
        if transport is not None and transport.is_open:
            try:
                transport.emergency_stop(close_port=True)
            except Exception as exc:
                self._append_log("Stop command warning: " + str(exc))
        self._set_state(MachineRunState.DISCONNECTED)

    def _emergency_stop(self) -> None:
        self._abort_expected = True
        if self._worker is not None:
            self._worker.request_cancel()
        self._set_state(MachineRunState.EMERGENCY)
        self._append_log("EMERGENCY STOP: GRBL feed hold + soft reset requested. Laser output and motion must be verified physically.")
        transport = self._transport
        self._transport = None
        if transport is not None and transport.is_open:
            try:
                transport.emergency_stop(close_port=True)
            except Exception as exc:
                self._append_log("Emergency command warning: " + str(exc))
        QMessageBox.critical(
            self,
            "Emergency stop sent",
            "LaserProg sent GRBL real-time HOLD + RESET and closed the serial connection.\n\n"
            "Use the machine's physical emergency stop or power switch if any motion or laser output continues. Inspect the machine before reconnecting.",
        )

    def _require_idle_connection(self) -> bool:
        if self._state != MachineRunState.IDLE or self._transport is None or not self._transport.is_open:
            QMessageBox.warning(self, "USB", "Connect to the machine and wait for the READY state first.")
            return False
        return True

    def _set_state(self, state: MachineRunState, *, detail: str = "") -> None:
        self._state = state
        labels = {
            MachineRunState.DISCONNECTED: "DISCONNECTED",
            MachineRunState.IDLE: "READY — connected, laser off expected",
            MachineRunState.STREAMING: "RUNNING LASER JOB",
            MachineRunState.FRAMING: "FRAME MODE — LOOPING, LASER OFF",
            MachineRunState.STOPPING: "STOPPING / CONNECTING",
            MachineRunState.EMERGENCY: "EMERGENCY STOP SENT — RECONNECT REQUIRED",
        }
        text = detail or labels[state]
        self.state_label.setText(text)
        active = state in (MachineRunState.STREAMING, MachineRunState.FRAMING, MachineRunState.STOPPING)
        connected = state == MachineRunState.IDLE
        self.btn_connect.setText("Disconnect" if connected else "Connect")
        self.btn_connect.setEnabled(not active)
        self.port_combo.setEnabled(not active and not connected)
        self.btn_refresh_ports.setEnabled(not active and not connected)
        self.btn_status.setEnabled(connected)
        self.btn_firmware.setEnabled(connected)
        self.btn_unlock.setEnabled(connected)
        self.btn_laser_off.setEnabled(connected)
        self.btn_send.setEnabled(connected)
        self.btn_frame.setEnabled(connected or state == MachineRunState.FRAMING)
        self.btn_frame.setText("STOP FRAME — reset GRBL" if state == MachineRunState.FRAMING else "Start FRAME loop (M5)")
        self.btn_generate.setEnabled(not active)
        self.btn_svg.setEnabled(not active)
        self.btn_save.setEnabled(not active)
        self.btn_emergency.setEnabled(state != MachineRunState.DISCONNECTED or self._transport is not None)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._state in (MachineRunState.STREAMING, MachineRunState.FRAMING, MachineRunState.STOPPING):
            answer = QMessageBox.warning(
                self,
                "Machine operation active",
                "Closing now will issue an emergency stop and reset GRBL. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._emergency_stop()
            thread = self._thread
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(1500)
        elif self._transport is not None:
            self._transport.close()
            self._transport = None
        event.accept()

    def _append_log(self, text: str) -> None:
        text = str(text or "").strip()
        if text:
            self.log.appendPlainText(text)

    @staticmethod
    def _double(minimum: float, maximum: float, value: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(float(minimum), float(maximum))
        spin.setValue(float(value))
        spin.setSingleStep(float(step))
        spin.setDecimals(3)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        return spin


__all__ = ["MachineEngravingDialog", "MachineRunState"]
