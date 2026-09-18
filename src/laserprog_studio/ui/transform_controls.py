# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from .transform_icons import transform_icon


class UITransformControlsLayer:
    def _transform_button(self, icon_text: str, tooltip: str, mode: str) -> QToolButton:
        b = QToolButton()
        b.setText(icon_text)
        b.setToolTip(tooltip)
        b.setCheckable(True)
        b.setToolButtonStyle(Qt.ToolButtonIconOnly)
        icon_name = {
            self.TRANSFORM_NONE: "none",
            self.TRANSFORM_TRANSLATE: "translate",
            self.TRANSFORM_ROTATE: "rotate",
            self.TRANSFORM_SCALE: "scale",
        }.get(mode)
        icon = transform_icon(icon_name)
        if icon is not None and not icon.isNull():
            b.setIcon(icon)
            b.setIconSize(QSize(32, 32))
        b.setMinimumSize(48, 44)
        b.setMaximumSize(56, 50)
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        b.setFont(font)
        b.clicked.connect(lambda checked=False, m=mode: self.set_transform_mode(m))
        self.transform_group.addButton(b)
        return b

    def set_transform_mode(self, mode: str) -> None:
        requested_mode = mode
        if mode not in {self.TRANSFORM_NONE, self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}:
            mode = self.TRANSFORM_NONE
        try:
            self.ui_log(
                f"[TRANSFORM_DIAG] set_transform_mode requested={requested_mode} resolved={mode} "
                f"previous={getattr(self, 'transform_mode', None)} selected={list(getattr(self, 'selected_indices', []))} "
                f"active={getattr(self, 'active_index', None)} available={self._transform_tools_available()} "
                f"active_tool={getattr(self, 'active_tool', None)} preview={self.has_preview()}"
            )
        except Exception:
            pass
        self.transform_mode = mode
        self._gizmo_delta_display_signature = None
        if mode == self.TRANSFORM_NONE:
            self._clear_gizmo_interaction(clear_highlight=True)
        self._sync_transform_buttons()
        self._sync_light_transform_mode_from_transform_mode()
        label = {
            self.TRANSFORM_NONE: "None",
            self.TRANSFORM_TRANSLATE: "Translate",
            self.TRANSFORM_ROTATE: "Rotate",
            self.TRANSFORM_SCALE: "Scale",
        }[mode]
        try:
            self.statusBar().showMessage(f"Transform: {label}", 2200)
        except Exception:
            pass
        self.ui_log(f"[TRANSFORM] Mode: {label}")
        try:
            self.ui_log(f"[TRANSFORM_DIAG] set_transform_mode calling update_gizmo mode={self.transform_mode}")
            self.update_gizmo(render=False)
            self.ui_log(f"[TRANSFORM_DIAG] set_transform_mode render after update mode={self.transform_mode} gizmo_actors={len(getattr(self, 'gizmo_actors', {}))}")
            self.plotter.render()
        except Exception:
            log_exception("set_transform_mode update_gizmo/render")

    def _history_tools_available(self) -> bool:
        try:
            return self.active_tool == self.TOOL_NONE and not self.has_preview()
        except Exception:
            return False

    def _sync_history_buttons(self) -> None:
        try:
            base_enabled = self._history_tools_available()
            can_undo = bool(base_enabled and self.mesh_store is not None and getattr(self.mesh_store, "can_undo", False))
            can_redo = bool(base_enabled and self.mesh_store is not None and getattr(self.mesh_store, "can_redo", False))
            creator_tool_active = False
            try:
                active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none"))
                if active != getattr(self, "TOOL_NONE", "none"):
                    from ..tooling.registry import get_studio_tool

                    tool = get_studio_tool(active)
                    creator_tool_active = bool(callable(getattr(tool, "on_event", None)) and callable(getattr(tool, "tool_context", None)))
            except Exception:
                creator_tool_active = False
            # Keep the global QAction shortcuts enabled while a Creator tool owns
            # the viewport.  The action handler routes Ctrl+Z/Ctrl+Y into the
            # tool first; disabling the QAction here prevents Qt from delivering
            # the shortcut at all.  Scene-history buttons remain disabled during
            # tools because they still call the scene history directly.
            action_undo = bool(can_undo or creator_tool_active)
            action_redo = bool(can_redo or creator_tool_active)
            for obj, enabled in [
                (getattr(self, "act_undo", None), action_undo),
                (getattr(self, "act_redo", None), action_redo),
                (getattr(self, "btn_undo", None), can_undo),
                (getattr(self, "btn_redo", None), can_redo),
                (getattr(self, "btn_project_undo", None), can_undo),
                (getattr(self, "btn_project_redo", None), can_redo),
            ]:
                if obj is not None:
                    obj.setEnabled(enabled)
        except Exception:
            pass

    def _transform_tools_available(self) -> bool:
        """Return True only when the persistent transform mode can be used now.

        Opening a tool gives ownership of the scene to that tool/preview workflow.
        The selected transform mode is kept, but N/T/R/S are disabled visually and
        the overlay is hidden until the tool is closed.
        """
        try:
            return self.active_tool == self.TOOL_NONE and not self.has_preview()
        except Exception:
            return False

    def _sync_transform_buttons(self) -> None:
        try:
            mapping = {
                self.TRANSFORM_NONE: self.btn_tf_none,
                self.TRANSFORM_TRANSLATE: self.btn_tf_translate,
                self.TRANSFORM_ROTATE: self.btn_tf_rotate,
                self.TRANSFORM_SCALE: self.btn_tf_scale,
            }
            enabled = self._transform_tools_available()
            for mode, button in mapping.items():
                button.blockSignals(True)
                button.setChecked(self.transform_mode == mode)
                button.setEnabled(enabled)
                button.blockSignals(False)
        except Exception:
            pass

    def _boolean_tools_available(self) -> bool:
        try:
            return self.active_tool == self.TOOL_NONE and not self.has_preview()
        except Exception:
            return False

    def _sync_boolean_buttons(self) -> None:
        try:
            remove_mode = bool(getattr(self, "toolbar_remove_mode", False))
            enabled = self._boolean_tools_available() and not bool(getattr(self, "_boolean_job_active", False))
            selected_count = len(self._selected_transform_indices())
            rules = [
                (getattr(self, "btn_bool_subtract", None), selected_count >= 1),
                (getattr(self, "btn_bool_union", None), selected_count >= 2),
                (getattr(self, "btn_bool_separate", None), selected_count >= 1),
            ]
            for button, condition in rules:
                if button is not None:
                    available = bool(enabled and condition)
                    # Keep boolean buttons enabled so drag/drop reorder works even
                    # when the action itself cannot run.  The toolbar controller
                    # checks this property before invoking the callback.
                    button.setProperty("toolbarActionAvailable", True if remove_mode else available)
                    button.setEnabled(True)
                    try:
                        from ..application.toolbar_controller import TOOLBAR_REMOVABLE_ITEM_STYLE, TOOLBAR_UNAVAILABLE_ITEM_STYLE
                        button.setStyleSheet(TOOLBAR_REMOVABLE_ITEM_STYLE if remove_mode else ("" if available else TOOLBAR_UNAVAILABLE_ITEM_STYLE))
                    except Exception:
                        pass
            if remove_mode:
                self._apply_toolbar_remove_mode_visuals()
        except Exception:
            pass

    def _on_snap_settings_changed(self, *_args) -> None:
        try:
            self.grid_snap_enabled = bool(self.grid_snap_check.isChecked())
            self.smart_snap_enabled = bool(self.smart_snap_check.isChecked())
            self.rotation_snap_enabled = bool(self.rotation_snap_check.isChecked())
            self.grid_snap_step = max(float(self.grid_snap_step_spin.value()), 0.01)
            self.smart_snap_tolerance = max(float(self.smart_snap_tol_spin.value()), 0.01)
            self.rotation_snap_step_deg = max(float(self.rotation_snap_step_spin.value()), 1.0)
            self.rotation_snap_tolerance_deg = max(float(self.rotation_snap_tol_spin.value()), 0.1)
            text = self._snap_idle_status_text()
            try:
                self.snap_status_label.setText(text)
            except Exception:
                pass
            self.ui_log(f"[SNAP] {text}")
        except Exception:
            log_exception("snap_settings_changed")

    def _snap_settings(self) -> SnapSettings:
        try:
            # Read widgets directly when available; fall back to cached values during startup/tests.
            grid_enabled = bool(self.grid_snap_check.isChecked())
            smart_enabled = bool(self.smart_snap_check.isChecked())
            grid_step = float(self.grid_snap_step_spin.value())
            smart_tolerance = float(self.smart_snap_tol_spin.value())
        except Exception:
            grid_enabled = bool(self.grid_snap_enabled)
            smart_enabled = bool(self.smart_snap_enabled)
            grid_step = float(self.grid_snap_step)
            smart_tolerance = float(self.smart_snap_tolerance)
        return SnapSettings(
            grid_enabled=grid_enabled,
            smart_enabled=smart_enabled,
            grid_step=max(grid_step, 0.01),
            smart_tolerance=max(smart_tolerance, 0.01),
        )

    def _rotation_snap_settings(self) -> tuple[bool, float, float]:
        try:
            enabled = bool(self.rotation_snap_check.isChecked())
            step = float(self.rotation_snap_step_spin.value())
            tolerance = float(self.rotation_snap_tol_spin.value())
        except Exception:
            enabled = bool(self.rotation_snap_enabled)
            step = float(self.rotation_snap_step_deg)
            tolerance = float(self.rotation_snap_tolerance_deg)
        return enabled, max(step, 1.0), max(tolerance, 0.1)

    def _snap_idle_status_text(self) -> str:
        settings = self._snap_settings()
        rot_enabled, rot_step, rot_tol = self._rotation_snap_settings()
        parts = []
        if settings.grid_enabled:
            parts.append(f"grid {settings.grid_step:g} mm")
        if settings.smart_enabled:
            parts.append(f"smart {settings.smart_tolerance:g} mm")
        if rot_enabled:
            parts.append(f"rot {rot_step:g} deg +/-{rot_tol:g} deg")
        return "Snap: " + (" + ".join(parts) if parts else "off")

    def _set_snap_status(self, text: str | None) -> None:
        try:
            label = str(text) if text else None
            if label == getattr(self, "_last_snap_label", None):
                return
            if label:
                self._last_snap_label = label
                self.snap_status_label.setText(f"Snap: {label}")
                try:
                    self.statusBar().showMessage(f"Snap: {label}", 700)
                except Exception:
                    pass
            else:
                if self._last_snap_label is None:
                    return
                self._last_snap_label = None
                self.snap_status_label.setText(self._snap_idle_status_text())
        except Exception:
            pass
