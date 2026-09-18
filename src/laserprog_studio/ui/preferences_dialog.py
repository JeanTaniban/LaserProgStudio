# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .._window_deps import *
from ..services.appearance_preferences import (
    AppearancePreferences,
    load_appearance_preferences,
    save_appearance_preferences,
)
from ..services.project_preferences import (
    KeyboardShortcutsPreferences,
    LaserEngravingPreferences,
    ProjectPreferences,
    load_project_preferences,
    save_project_preferences,
)


class ProjectPreferencesDialog(QDialog):
    """Floating project preferences window with section navigation."""

    def __init__(self, owner: Any) -> None:
        super().__init__(owner)
        self.owner = owner
        self.setWindowTitle("Preferences")
        self.setObjectName("ProjectPreferencesDialog")
        self.setModal(False)
        self.resize(720, 470)
        self._prefs = getattr(owner, "project_preferences", None) or load_project_preferences()
        self._appearance_prefs = load_appearance_preferences()
        self._build_ui()
        self._load_values(self._prefs)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        self.sections = QListWidget(self)
        self.sections.setObjectName("PreferencesSections")
        self.sections.setFixedWidth(176)
        for label in ("Project", "Laser engraving", "Modeling", "Shortcuts", "Diagnostics"):
            self.sections.addItem(label)
        body.addWidget(self.sections, 0)

        self.stack = QStackedWidget(self)
        body.addWidget(self.stack, 1)
        self._build_project_page()
        self._build_laser_page()
        self._build_modeling_page()
        self._build_shortcuts_page()
        self._build_diagnostics_page()
        self.sections.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.sections.setCurrentRow(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply, self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        apply_button = buttons.button(QDialogButtonBox.Apply)
        if apply_button is not None:
            apply_button.clicked.connect(self.apply_to_owner)
        root.addWidget(buttons)

    def _page(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        title_label = QLabel(title, page)
        title_label.setObjectName("Title")
        layout.addWidget(title_label)
        subtitle_label = QLabel(subtitle, page)
        subtitle_label.setWordWrap(True)
        subtitle_label.setObjectName("SubTitle")
        layout.addWidget(subtitle_label)
        self.stack.addWidget(page)
        return page, layout

    def _spin_mm(self, minimum: float, maximum: float, decimals: int = 2) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(float(minimum), float(maximum))
        spin.setDecimals(int(decimals))
        spin.setSingleStep(1.0 if decimals <= 1 else 0.5)
        spin.setSuffix(" mm")
        return spin

    def _grid_row(self, grid: QGridLayout, row: int, label: str, widget: QWidget, help_text: str = "") -> None:
        lab = QLabel(label, self)
        lab.setMinimumWidth(190)
        grid.addWidget(lab, row, 0)
        grid.addWidget(widget, row, 1)
        if help_text:
            hint = QLabel(help_text, self)
            hint.setWordWrap(True)
            hint.setObjectName("SubTitle")
            grid.addWidget(hint, row, 2)

    def _build_project_page(self) -> None:
        _page, layout = self._page("Project", "Comfort settings that affect the current scene and new projects.")
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.autosave_enabled = QCheckBox("Enable autosave", self)
        self.autosave_interval = QSpinBox(self)
        self.autosave_interval.setRange(3, 3600)
        self.autosave_interval.setSuffix(" s")
        self.grid_step = self._spin_mm(0.5, 1000.0, 1)
        self.native_file_dialogs = QCheckBox("Use native system file dialogs", self)
        self._grid_row(grid, 0, "Autosave", self.autosave_enabled, "Only disables the automatic timer, not manual saving.")
        self._grid_row(grid, 1, "Autosave interval", self.autosave_interval, "Applied without restarting.")
        self._grid_row(grid, 2, "Grid step", self.grid_step, "Used by the floor grid and fabrication guides.")
        self._grid_row(grid, 3, "File explorer", self.native_file_dialogs, "Uses the full operating-system file explorer for Open, Save and Export dialogs. Restart if the current session was launched with compact Qt dialogs.")
        layout.addStretch(1)

    def _build_laser_page(self) -> None:
        _page, layout = self._page(
            "Laser engraving",
            "Default dimensions in millimetres. The machine area is a visual guide and does not modify meshes.",
        )
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.board_thickness = self._spin_mm(0.05, 2000.0, 2)
        self.machine_x = self._spin_mm(1.0, 100000.0, 1)
        self.machine_y = self._spin_mm(1.0, 100000.0, 1)
        self.show_machine_area = QCheckBox("Show machine area in the scene", self)
        self.primitive_x = self._spin_mm(1.0, 100000.0, 1)
        self.primitive_y = self._spin_mm(1.0, 100000.0, 1)
        self._grid_row(grid, 0, "Board thickness", self.board_thickness, "Used by the primitive board.")
        self._grid_row(grid, 1, "Machine area X max", self.machine_x, "Usable cutting / engraving width.")
        self._grid_row(grid, 2, "Machine area Y max", self.machine_y, "Usable cutting / engraving depth.")
        self._grid_row(grid, 3, "Show area", self.show_machine_area, "Grid-like guide centred on the origin.")
        self._grid_row(grid, 4, "Primitive board X", self.primitive_x, "Default size of the board created from the right-click menu.")
        self.pattern_max_segments = QSpinBox(self)
        self.pattern_max_segments.setRange(1000, 1_000_000)
        self.pattern_max_segments.setSingleStep(5000)
        self.pattern_max_segments.setSuffix(" segments")
        self._grid_row(grid, 5, "Primitive board Y", self.primitive_y, "The board 3D height uses the thickness above.")
        self._grid_row(grid, 6, "Max Pattern segments", self.pattern_max_segments, "Upper budget for dense Plan Tracer 2D Pattern generation and preview.")
        layout.addStretch(1)

    def _build_modeling_page(self) -> None:
        _page, layout = self._page(
            "Modeling",
            "Geometry settings applied to project modeling operations.",
        )
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.boolean_subtract_margin = self._spin_mm(-1000.0, 1000.0, 2)
        self.boolean_subtract_margin.setSingleStep(0.05)
        self._grid_row(
            grid,
            0,
            "Subtract clearance",
            self.boolean_subtract_margin,
            "Uniform clearance applied to Boolean Subtract cutters: positive = larger hole, negative = smaller hole.",
        )
        note = QLabel(
            "The clearance offsets the cutter faces. It does not proportionally scale the cutter bounds.",
            self,
        )
        note.setWordWrap(True)
        note.setObjectName("SubTitle")
        layout.addWidget(note)
        layout.addStretch(1)

    def _combo(self, choices: tuple[tuple[str, str], ...]) -> QComboBox:
        combo = QComboBox(self)
        for value, label in choices:
            combo.addItem(label, value)
        return combo

    def _build_shortcuts_page(self) -> None:
        _page, layout = self._page(
            "Shortcuts",
            "Fast viewport shortcuts. Changes apply to the current project preferences immediately after Apply/OK.",
        )
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.shortcut_toolbar_modifier = self._combo((("shift", "Shift"),))
        self.shortcut_transform_cycle_key = self._combo((("tab", "Tab"), ("space", "Space")))
        self.shortcut_preview_apply_key = self._combo((("left_alt", "Left Alt"), ("space", "Space")))
        self.shortcut_hold_threshold = QDoubleSpinBox(self)
        self.shortcut_hold_threshold.setRange(0.2, 2.0)
        self.shortcut_hold_threshold.setDecimals(2)
        self.shortcut_hold_threshold.setSingleStep(0.05)
        self.shortcut_hold_threshold.setSuffix(" s")
        self.shortcut_multi_press_window = QDoubleSpinBox(self)
        self.shortcut_multi_press_window.setRange(0.1, 2.0)
        self.shortcut_multi_press_window.setDecimals(2)
        self.shortcut_multi_press_window.setSingleStep(0.05)
        self.shortcut_multi_press_window.setSuffix(" s")
        self._grid_row(grid, 0, "Toolbar selection", self.shortcut_toolbar_modifier, "Shift + number selects the visible toolbar item: Shift+1 opens the first item, Shift+0 the tenth. AZERTY keys (&, é, quote, …) are accepted.")
        self._grid_row(grid, 1, "Transform cycle", self.shortcut_transform_cycle_key, "Quick taps: 1 = Translate, 2 = Rotate, 3 = Scale. Holding the key switches to Neutral.")
        self._grid_row(grid, 2, "Preview / Apply", self.shortcut_preview_apply_key, "Quick press generates preview. Holding the key applies/validates the active tool.")
        self._grid_row(grid, 3, "Hold threshold", self.shortcut_hold_threshold, "Default 0.5 s. Used by Transform cycle and Preview / Apply.")
        self._grid_row(grid, 4, "Multi-press window", self.shortcut_multi_press_window, "Time allowed between quick taps for Tab cycling. Minimum 0.10 s for very fast cycling.")
        layout.addStretch(1)

    def _build_diagnostics_page(self) -> None:
        _page, layout = self._page(
            "Diagnostics",
            "Enable this only to reproduce a bug or generate traces. Keep it disabled during normal use.",
        )
        self.debug_mode = QCheckBox("Diagnostics debug mode", self)
        layout.addWidget(self.debug_mode)
        note = QLabel("Changes apply immediately and stay synchronized with View > Performance / Debug.", self)
        note.setWordWrap(True)
        note.setObjectName("SubTitle")
        layout.addWidget(note)
        layout.addStretch(1)

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        try:
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)
        except Exception:
            pass

    def _combo_value(self, combo: QComboBox, default: str) -> str:
        try:
            value = combo.currentData()
            return str(value if value is not None else default)
        except Exception:
            return str(default)

    def _load_values(self, prefs: ProjectPreferences) -> None:
        laser = prefs.laser
        self.autosave_enabled.setChecked(bool(prefs.autosave_enabled))
        self.autosave_interval.setValue(int(prefs.autosave_interval_s))
        self.grid_step.setValue(float(prefs.default_floor_grid_step_mm))
        self.board_thickness.setValue(float(laser.default_board_thickness_mm))
        self.machine_x.setValue(float(laser.machine_area_x_mm))
        self.machine_y.setValue(float(laser.machine_area_y_mm))
        self.show_machine_area.setChecked(bool(laser.show_machine_area))
        self.primitive_x.setValue(float(laser.primitive_board_x_mm))
        self.primitive_y.setValue(float(laser.primitive_board_y_mm))
        self.pattern_max_segments.setValue(int(getattr(laser, "plan_tracer_pattern_max_segments", 120000)))
        self.boolean_subtract_margin.setValue(float(getattr(laser, "boolean_subtract_margin_mm", 0.0)))
        try:
            self.native_file_dialogs.setChecked(bool(getattr(self._appearance_prefs, "use_native_dialogs", True)))
        except Exception:
            self.native_file_dialogs.setChecked(True)
        shortcuts = getattr(prefs, "shortcuts", KeyboardShortcutsPreferences())
        self._set_combo_value(self.shortcut_toolbar_modifier, str(getattr(shortcuts, "toolbar_modifier", "shift")))
        self._set_combo_value(self.shortcut_transform_cycle_key, str(getattr(shortcuts, "transform_cycle_key", "tab")))
        self._set_combo_value(self.shortcut_preview_apply_key, str(getattr(shortcuts, "preview_apply_key", "left_alt")))
        self.shortcut_hold_threshold.setValue(float(getattr(shortcuts, "hold_threshold_s", 0.5)))
        self.shortcut_multi_press_window.setValue(float(getattr(shortcuts, "multi_press_window_s", 0.65)))
        try:
            self.debug_mode.setChecked(str(getattr(self.owner, "_performance_mode", "optimized")) == "debug")
        except Exception:
            self.debug_mode.setChecked(False)

    def preferences_from_fields(self) -> ProjectPreferences:
        return ProjectPreferences(
            schema_version=1,
            laser=LaserEngravingPreferences(
                default_board_thickness_mm=float(self.board_thickness.value()),
                machine_area_x_mm=float(self.machine_x.value()),
                machine_area_y_mm=float(self.machine_y.value()),
                show_machine_area=bool(self.show_machine_area.isChecked()),
                primitive_board_x_mm=float(self.primitive_x.value()),
                primitive_board_y_mm=float(self.primitive_y.value()),
                boolean_subtract_margin_mm=float(self.boolean_subtract_margin.value()),
                plan_tracer_pattern_max_segments=int(self.pattern_max_segments.value()),
            ),
            shortcuts=KeyboardShortcutsPreferences(
                toolbar_modifier=self._combo_value(self.shortcut_toolbar_modifier, "shift"),
                transform_cycle_key=self._combo_value(self.shortcut_transform_cycle_key, "tab"),
                preview_apply_key=self._combo_value(self.shortcut_preview_apply_key, "left_alt"),
                hold_threshold_s=float(self.shortcut_hold_threshold.value()),
                multi_press_window_s=float(self.shortcut_multi_press_window.value()),
            ),
            autosave_enabled=bool(self.autosave_enabled.isChecked()),
            autosave_interval_s=int(self.autosave_interval.value()),
            default_floor_grid_step_mm=float(self.grid_step.value()),
        )

    def apply_to_owner(self) -> bool:
        prefs = self.preferences_from_fields()
        save_project_preferences(prefs)
        self._prefs = prefs
        try:
            current_appearance = getattr(self, "_appearance_prefs", None) or load_appearance_preferences()
            appearance = AppearancePreferences(
                force_dark_mode=bool(getattr(current_appearance, "force_dark_mode", True)),
                use_native_dialogs=bool(self.native_file_dialogs.isChecked()),
            )
            save_appearance_preferences(appearance)
            self._appearance_prefs = appearance
        except Exception:
            pass
        try:
            self.owner.project_preferences = prefs
            self.owner.floor_grid_step = float(prefs.default_floor_grid_step_mm)
        except Exception:
            pass
        try:
            timer = getattr(self.owner, "_autosave_timer", None)
            if timer is not None:
                timer.setInterval(max(int(prefs.autosave_interval_s), 3) * 1000)
                if bool(prefs.autosave_enabled):
                    timer.start()
                else:
                    timer.stop()
        except Exception:
            pass
        try:
            self.owner.set_performance_mode("debug" if self.debug_mode.isChecked() else "optimized")
        except Exception:
            pass
        try:
            self.owner._update_floor_grid_actor(render=True)
        except Exception:
            try:
                self.owner._update_laser_area_actor(render=True)
            except Exception:
                pass
        try:
            self.owner.statusBar().showMessage("Preferences saved", 1800)
        except Exception:
            pass
        return True

    def _accept(self) -> None:
        self.apply_to_owner()
        self.accept()


def open_project_preferences_dialog(owner: Any) -> ProjectPreferencesDialog:
    existing = getattr(owner, "project_preferences_dialog", None)
    try:
        if existing is not None and existing.isVisible():
            existing.raise_()
            existing.activateWindow()
            return existing
    except Exception:
        pass
    dialog = ProjectPreferencesDialog(owner)
    owner.project_preferences_dialog = dialog
    try:
        dialog.finished.connect(lambda *_: setattr(owner, "project_preferences_dialog", None))
    except Exception:
        pass
    dialog.show()
    try:
        dialog.raise_()
        dialog.activateWindow()
    except Exception:
        pass
    return dialog


__all__ = ["ProjectPreferencesDialog", "open_project_preferences_dialog"]
