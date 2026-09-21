# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtGui import QImage, QPixmap

from .._window_deps import *
from ..application.background_tasks import BackgroundTaskManager


class ImageMaskImportLayer:
    """File > Import 2D mask workflow."""

    def import_2d_mask_dialog(self) -> None:
        try:
            if not self.confirm_preview_before_tool_change("import 2D mask"):
                return
            dialog = QDialog(self)
            dialog.setWindowTitle("Import 2D mask")
            dialog.setMinimumWidth(430)
            layout = QVBoxLayout(dialog)
            layout.setSpacing(10)

            intro = QLabel(
                "Create a clean binary 3D object from a 2D image.\n"
                "Background = empty. Material = 10 mm high."
            )
            intro.setWordWrap(True)
            intro.setObjectName("SubTitle")
            layout.addWidget(intro)

            form = QGridLayout()
            form.setHorizontalSpacing(8)
            form.setVerticalSpacing(8)
            file_edit = QLineEdit()
            file_edit.setPlaceholderText("Select a PNG or JPG…")
            browse = QPushButton("Browse…")
            form.addWidget(QLabel("Mask image"), 0, 0)
            form.addWidget(file_edit, 0, 1)
            form.addWidget(browse, 0, 2)

            def add_slider(row: int, title: str, value: int, tooltip: str) -> QSlider:
                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 100)
                slider.setSingleStep(1)
                slider.setPageStep(5)
                slider.setValue(int(value))
                slider.setToolTip(tooltip)
                value_label = QLabel(str(int(value)))
                value_label.setMinimumWidth(28)
                value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                slider.valueChanged.connect(lambda v, label=value_label: label.setText(str(int(v))))
                form.addWidget(QLabel(title), row, 0)
                form.addWidget(slider, row, 1)
                form.addWidget(value_label, row, 2)
                return slider

            levels_slider = add_slider(
                1,
                "Levels",
                50,
                "Lower = stricter selection. Higher = keep more faint material. 50 uses automatic levels.",
            )
            smooth_slider = add_slider(
                2,
                "Smooth",
                35,
                "Smooth the vector outline after thresholding. Preserves thin details; no image blur is applied.",
            )
            invert_check = QCheckBox("Invert")
            invert_check.setToolTip("Use bright areas as material instead of dark areas.")
            form.addWidget(invert_check, 3, 1, 1, 2)
            layout.addLayout(form)

            preview_title = QLabel("Preview — black = 10 mm material, white = empty")
            preview_title.setObjectName("SubTitle")
            layout.addWidget(preview_title)

            preview_label = QLabel("Select an image to preview the binary mask.")
            preview_label.setAlignment(Qt.AlignCenter)
            preview_label.setMinimumSize(360, 220)
            preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            preview_label.setStyleSheet(
                "QLabel { background: #f8fafc; color: #334155; border: 1px solid #94a3b8; border-radius: 10px; padding: 8px; }"
            )
            layout.addWidget(preview_label)

            preview_status = QLabel("Adjust Levels, Smooth, or Invert to update the preview.")
            preview_status.setObjectName("SubTitle")
            preview_status.setWordWrap(True)
            layout.addWidget(preview_status)

            preview_timer = QTimer(dialog)
            preview_timer.setSingleShot(True)
            preview_tasks = BackgroundTaskManager(dialog, max_workers=1, poll_ms=25)
            dialog.destroyed.connect(lambda *_args: preview_tasks.shutdown())

            def _pil_to_pixmap(image) -> QPixmap:
                rgba = image.convert("RGBA")
                qimage = QImage(
                    rgba.tobytes("raw", "RGBA"),
                    int(rgba.width),
                    int(rgba.height),
                    int(rgba.width) * 4,
                    QImage.Format_RGBA8888,
                )
                return QPixmap.fromImage(qimage.copy())

            def refresh_preview() -> None:
                raw_path = file_edit.text().strip()
                if not raw_path:
                    preview_label.setPixmap(QPixmap())
                    preview_label.setText("Select an image to preview the binary mask.")
                    preview_status.setText("Black = final 10 mm material. White = empty.")
                    return
                path = Path(raw_path).expanduser()
                if not path.exists():
                    preview_label.setPixmap(QPixmap())
                    preview_label.setText("Image not found.")
                    preview_status.setText("Choose a valid PNG, JPG, JPEG, or BMP image.")
                    return

                request_path = Path(path)
                request_invert = bool(invert_check.isChecked())
                request_levels = int(levels_slider.value())
                request_smooth = float(smooth_slider.value())
                max_w = max(320, int(preview_label.width()) - 20)
                max_h = max(180, int(preview_label.height()) - 20)
                preview_status.setText("Computing preview…")

                def _worker():
                    from laserprog_studio.geometry_ops.image_mask_relief import build_mask_preview

                    image, footprint = build_mask_preview(
                        request_path,
                        invert=request_invert,
                        levels=request_levels,
                        smooth=request_smooth,
                        max_grid_size=512,
                        max_preview_size=(max_w, max_h),
                        legacy_size_cap_px=512,
                    )
                    smoothing = footprint.smoothing_report
                    return (
                        image,
                        float(smoothing.accepted_level),
                        bool(smoothing.fallback_used),
                    )

                def _success(payload) -> None:
                    image, accepted_smooth, smooth_limited = payload
                    preview_label.setText("")
                    preview_label.setPixmap(_pil_to_pixmap(image))
                    smooth_text = f"Smooth {int(request_smooth)}"
                    if smooth_limited:
                        smooth_text += f" → {accepted_smooth:g} (topology protected)"
                    preview_status.setText(
                        f"Levels {request_levels} · {smooth_text} · "
                        f"Invert {'on' if request_invert else 'off'}"
                    )

                def _error(exc: BaseException) -> None:
                    preview_label.setPixmap(QPixmap())
                    preview_label.setText("Preview unavailable.")
                    preview_status.setText(str(exc))

                preview_tasks.run(
                    "mask-2d-preview",
                    _worker,
                    on_success=_success,
                    on_error=_error,
                    description="2D mask preview",
                    coalesce_pending=True,
                )

            def schedule_preview() -> None:
                preview_timer.start(120)

            preview_timer.timeout.connect(refresh_preview)
            levels_slider.valueChanged.connect(lambda _value: schedule_preview())
            smooth_slider.valueChanged.connect(lambda _value: schedule_preview())
            invert_check.toggled.connect(lambda _checked: schedule_preview())
            file_edit.textChanged.connect(lambda _text: schedule_preview())

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            layout.addWidget(buttons)

            def choose_file() -> None:
                path, _ = QFileDialog.getOpenFileName(
                    dialog,
                    "Select 2D mask image",
                    str(ROOT),
                    "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)",
                )
                if path:
                    file_edit.setText(path)

            browse.clicked.connect(choose_file)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            if dialog.exec() != QDialog.Accepted:
                return
            path = Path(file_edit.text()).expanduser()
            if not path.exists():
                QMessageBox.warning(self, "Import 2D mask", "Select a valid PNG/JPG image.")
                return
            self.import_2d_mask(
                path,
                invert=bool(invert_check.isChecked()),
                levels=int(levels_slider.value()),
                smooth=float(smooth_slider.value()),
            )
        except Exception:
            log_exception("import_2d_mask_dialog")
            QMessageBox.warning(self, "Import 2D mask", "Error while importing the 2D mask. See logs.")

    def import_2d_mask(
        self,
        path: str | Path,
        *,
        max_height_mm: float = 10.0,
        pixel_size_mm: float = 1.0,
        invert: bool = False,
        binary: bool = True,
        binary_threshold: float = 0.5,
        max_grid_size: int = 512,
        legacy_size_cap_px: int | None = 512,
        levels: float | None = None,
        smooth: float = 35.0,
    ) -> None:
        try:
            from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh

            result = build_mask_relief_mesh(
                path,
                max_height_mm=float(max_height_mm),
                pixel_size_mm=float(pixel_size_mm),
                invert=bool(invert),
                binary=bool(binary),
                binary_threshold=float(binary_threshold),
                max_grid_size=int(max_grid_size),
                legacy_size_cap_px=legacy_size_cap_px,
                levels=levels,
                smooth=float(smooth),
            )
            base = [copy.deepcopy(m) for m in self.committed_meshes()]
            base.append(result.mesh)
            new_index = len(base) - 1
            self.push_meshes(base, f"Import 2D mask {Path(path).name}", semantic_operation_type="import")
            self.selected_indices = [new_index]
            self.active_index = new_index
            self.refresh_actor_styles(render=False)
            self.update_inspector()
            self.update_gizmo(render=False)
            self.focus_camera_on_bounds(scene_bounds(self.current_meshes()), "import 2D mask")
            try:
                self.plotter.render()
            except Exception:
                pass
            stats = result.stats
            accepted_smooth = float((result.mesh.metadata or {}).get("mask_smooth_accepted", float(smooth)))
            msg = (
                f"[MASK] Imported {Path(path).name} | binary=1 grid={stats.width}x{stats.height} "
                f"active={stats.active_pixels} vertices={stats.vertices} triangles={stats.triangles} "
                f"height={stats.max_height_mm:g}mm levels={levels if levels is not None else 'threshold'} "
                f"smooth={float(smooth):g}"
            )
            if accepted_smooth + 1.0e-9 < float(smooth):
                msg += f"→{accepted_smooth:g}"
            msg += f" threshold={stats.binary_threshold:.3f}"
            if stats.downsampled:
                msg += f" | downsampled from {stats.source_width}x{stats.source_height}"
            self.ui_log(msg)
        except Exception as exc:
            log_exception("import_2d_mask")
            QMessageBox.warning(self, "Import 2D mask", str(exc))
