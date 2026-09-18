# -*- coding: utf-8 -*-
from __future__ import annotations

from ..._window_deps import *



class LightTransformOverlayFieldsLayer:
    """Focused Light UI overlay behavior extracted from the original mixin."""

    def _light_mode_for_transform_mode(self, mode: str | None = None) -> str | None:
        mode = self.transform_mode if mode is None else mode
        return {
            self.TRANSFORM_TRANSLATE: "position",
            self.TRANSFORM_ROTATE: "rotation",
            self.TRANSFORM_SCALE: "scale",
        }.get(mode)

    def _transform_mode_for_light_mode(self, mode: str | None) -> str:
        return {
            "position": self.TRANSFORM_TRANSLATE,
            "rotation": self.TRANSFORM_ROTATE,
            "scale": self.TRANSFORM_SCALE,
        }.get(str(mode), self.TRANSFORM_NONE)

    def _set_light_button_checked(self, mode: str | None) -> None:
        group = getattr(self, "light_transform_group", None)
        if group is None:
            return
        buttons = [
            getattr(self, "light_btn_position", None),
            getattr(self, "light_btn_rotation", None),
            getattr(self, "light_btn_scale", None),
        ]
        previous = bool(getattr(self, "_updating_light_transform_mode", False))
        self._updating_light_transform_mode = True
        try:
            group.setExclusive(False)
            for btn in buttons:
                if btn is None:
                    continue
                btn.blockSignals(True)
                btn.setChecked(str(btn.property("light_mode") or "") == str(mode) if mode is not None else False)
                btn.blockSignals(False)
            group.setExclusive(True)
        except Exception:
            log_exception("set_light_button_checked")
        finally:
            self._updating_light_transform_mode = previous

    def _sync_light_transform_mode_from_transform_mode(self) -> None:
        try:
            mode = self._light_mode_for_transform_mode(self.transform_mode)
            if mode is not None:
                self._light_transform_mode = mode
            self._set_light_button_checked(mode)
            self._sync_scale_ratio_lock_widgets()
            self._sync_light_transform_fields()
        except Exception:
            log_exception("sync_light_transform_mode")

    def _on_light_transform_mode_changed(self, button=None) -> None:
        if bool(getattr(self, "_updating_light_transform_mode", False)):
            return
        try:
            btn = button or self.light_transform_group.checkedButton()
            if btn is None:
                return
            mode = str(btn.property("light_mode") or "position")
            if mode not in {"position", "rotation", "scale"}:
                mode = "position"
            self._light_transform_mode = mode
            target_mode = self._transform_mode_for_light_mode(mode)
            if self.transform_mode != target_mode:
                self.set_transform_mode(target_mode)
            else:
                self._sync_light_transform_fields()
        except Exception:
            log_exception("light_transform_mode_changed")

    def _on_light_overlay_close_clicked(self) -> None:
        """Disable transform tools from the compact overlay and clear selection."""
        try:
            self.set_transform_mode(self.TRANSFORM_NONE)
            self.clear_selection("light overlay close")
            self._sync_light_transform_fields()
            try:
                self.statusBar().showMessage("Transform disabled and selection cleared", 1800)
            except Exception:
                pass
            self.ui_log("[LIGHT_OVERLAY] Close: transform none, selection cleared")
        except Exception:
            log_exception("light_overlay_close")

    def _on_light_overlay_exit_ui_clicked(self) -> None:
        """Restore the full three-pane UI from the compact Light UI overlay."""
        try:
            self._set_inspector_light_mode(False, "overlay Full UI button")
        except Exception:
            log_exception("light_overlay_exit_ui")

    def _sync_light_transform_fields(self) -> None:
        if bool(getattr(self, "_updating_light_transform_fields", False)):
            return
        spins = [getattr(self, "light_x", None), getattr(self, "light_y", None), getattr(self, "light_z", None)]
        if any(sp is None for sp in spins):
            return
        mode = str(getattr(self, "_light_transform_mode", "position"))
        source = {
            "position": [getattr(self, "pos_x", None), getattr(self, "pos_y", None), getattr(self, "pos_z", None)],
            "rotation": [getattr(self, "rot_x", None), getattr(self, "rot_y", None), getattr(self, "rot_z", None)],
            "scale": [getattr(self, "scale_x", None), getattr(self, "scale_y", None), getattr(self, "scale_z", None)],
        }.get(mode)
        if not source or any(w is None for w in source):
            return
        selected = bool(self._selected_transform_indices())
        available = bool(self._transform_tools_available())
        mode_active = self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}
        enabled = selected and available and mode_active
        previous = bool(getattr(self, "_updating_light_transform_fields", False))
        self._updating_light_transform_fields = True
        try:
            if mode == "rotation":
                mn, mx, step, suffix, unit = -360.0, 360.0, 5.0, "", "deg"
            elif mode == "scale":
                mn, mx, step, suffix, unit = 0.0, 100000.0, 1.0, "", "mm"
            else:
                mn, mx, step, suffix, unit = -100000.0, 100000.0, 1.0, "", "mm"
            values = [float(w.value()) for w in source]
            for spin, value in zip(spins, values):
                spin.blockSignals(True)
                spin.setRange(mn, mx)
                spin.setSingleStep(step)
                spin.setSuffix(suffix)
                spin.setValue(float(value))
                spin.setEnabled(enabled)
                spin.blockSignals(False)
            try:
                self.light_unit_label.setText(unit)
                self.light_unit_label.setEnabled(enabled)
            except Exception:
                pass
            for btn in [getattr(self, "light_btn_position", None), getattr(self, "light_btn_rotation", None), getattr(self, "light_btn_scale", None)]:
                if btn is not None:
                    btn.setEnabled(available)
            if getattr(self, "light_btn_close", None) is not None:
                self.light_btn_close.setEnabled(available)
            self._set_light_button_checked(self._light_mode_for_transform_mode(self.transform_mode))
            self._sync_scale_ratio_lock_widgets()
        except Exception:
            log_exception("sync_light_transform_fields")
        finally:
            self._updating_light_transform_fields = previous

    def _on_light_transform_field_changed(self, *_args) -> None:
        if bool(getattr(self, "_updating_light_transform_fields", False)):
            return
        if bool(getattr(self, "_updating_transform_fields", False)):
            return
        if self.active_index is None:
            return
        if not self._transform_tools_available() or self.transform_mode == self.TRANSFORM_NONE:
            self._sync_light_transform_fields()
            return
        mode = self._light_mode_for_transform_mode(self.transform_mode) or str(getattr(self, "_light_transform_mode", "position"))
        target = {
            "position": [getattr(self, "pos_x", None), getattr(self, "pos_y", None), getattr(self, "pos_z", None)],
            "rotation": [getattr(self, "rot_x", None), getattr(self, "rot_y", None), getattr(self, "rot_z", None)],
            "scale": [getattr(self, "scale_x", None), getattr(self, "scale_y", None), getattr(self, "scale_z", None)],
        }.get(mode)
        if not target or any(w is None for w in target):
            return
        try:
            if mode == "scale":
                self._propagate_locked_scale_change_from_widgets([self.light_x, self.light_y, self.light_z])
            values = [float(self.light_x.value()), float(self.light_y.value()), float(self.light_z.value())]
            self._set_spin_values_blocked({target[0]: values[0], target[1]: values[1], target[2]: values[2]})
            self.apply_transform_to_active(live=True)
        except Exception:
            log_exception("light_transform_field_changed")
