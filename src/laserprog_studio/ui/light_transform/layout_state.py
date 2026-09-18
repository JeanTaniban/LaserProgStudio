# -*- coding: utf-8 -*-
from __future__ import annotations

from ..._window_deps import *



class LightTransformOverlayLayoutStateLayer:
    """Focused Light UI overlay behavior extracted from the original mixin."""

    def _inspector_size_debug(self) -> tuple[list[int], int, int]:
        try:
            sizes = [int(v) for v in self.main_splitter.sizes()]
        except Exception:
            sizes = []
        try:
            width = int(self.right_panel.width())
        except Exception:
            width = -1
        try:
            threshold = int(getattr(self, "_layout_light_collapse_threshold", getattr(self, "_right_panel_light_threshold", 12)))
        except Exception:
            threshold = 12
        return sizes, width, threshold

    def _layout_light_threshold(self) -> int:
        try:
            return int(getattr(self, "_layout_light_collapse_threshold", getattr(self, "_right_panel_light_threshold", 12)))
        except Exception:
            return 12

    def _splitter_sizes(self) -> list[int]:
        try:
            return [int(v) for v in self.main_splitter.sizes()]
        except Exception:
            return []

    def _splitter_side_sizes(self) -> tuple[int, int, int]:
        sizes = self._splitter_sizes()
        left_size = int(sizes[0]) if len(sizes) >= 1 else 999999
        center_size = int(sizes[1]) if len(sizes) >= 2 else 999999
        right_size = int(sizes[2]) if len(sizes) >= 3 else 999999
        return left_size, center_size, right_size

    def _sync_ui_layout_state_from_splitter(self, *, save_full: bool = True) -> bool:
        """Update UiLayoutState from the real splitter sizes.

        Application Light UI is active only when both side panes are collapsed.
        The compact transform overlay is intentionally separate: it appears as
        soon as the right inspector is collapsed, even when the left panel stays
        open.
        """
        sizes = self._splitter_sizes()
        try:
            state = getattr(self, "ui_layout_state", None)
            if state is not None:
                before = list(getattr(state, "last_full_splitter_sizes", []) or [])
                state.update_from_splitter_sizes(sizes, threshold=self._layout_light_threshold())
                if not save_full and before:
                    state.last_full_splitter_sizes = before
                self._schedule_ui_layout_preferences_save()
                return str(getattr(state, "mode", "full")) == "light"
        except Exception:
            log_exception("sync_ui_layout_state_from_splitter")
        try:
            threshold = self._layout_light_threshold()
            left_size = int(sizes[0]) if len(sizes) >= 1 else 999999
            right_size = int(sizes[2]) if len(sizes) >= 3 else 999999
            return left_size <= threshold and right_size <= threshold
        except Exception:
            return False

    def _is_full_light_ui_mode(self) -> bool:
        """True only when both side panes are collapsed.

        This is a read-only query.  Older builds called
        _sync_ui_layout_state_from_splitter() here, which wrote preferences and
        scheduled timers from many display/resize paths.
        """
        try:
            left_size, _center_size, right_size = self._splitter_side_sizes()
            threshold = int(self._layout_light_threshold())
            return int(left_size) <= threshold and int(right_size) <= threshold
        except Exception:
            return False

    def _is_right_inspector_collapsed(self) -> bool:
        """True when the right inspector is collapsed, regardless of the left pane."""
        try:
            _left_size, _center_size, right_size = self._splitter_side_sizes()
            return int(right_size) <= int(self._layout_light_threshold())
        except Exception:
            return False

    def _is_transform_overlay_mode(self) -> bool:
        """The transform overlay replaces only the right inspector.

        This must not be tied to full Light UI. If the user keeps the left
        project/parts panel open but closes the right inspector, the compact
        transform overlay is still the correct replacement UI.
        """
        try:
            if self.center_stack.currentWidget() is not self.page_3d:
                return False
        except Exception:
            pass
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE or self.has_preview():
                return False
        except Exception:
            pass
        return bool(self._is_right_inspector_collapsed())

    def _is_inspector_light_mode(self) -> bool:
        """Stable name for compact transform-overlay mode."""
        return bool(self._is_transform_overlay_mode())

    def _log_inspector_state_if_changed(self, reason: str = "", force: bool = False) -> None:
        try:
            light = bool(self._is_inspector_light_mode())
            previous = getattr(self, "_last_inspector_light_mode", None)
            if force or previous is None or bool(previous) != light:
                self._last_inspector_light_mode = light
                sizes, width, threshold = self._inspector_size_debug()
                app_light = bool(self._is_full_light_ui_mode())
                state = "right-closed/overlay" if light else "right-open/full"
                if app_light:
                    state = "light-ui/both-closed"
                extra = f" reason={reason}" if reason else ""
                self.ui_log(f"[INSPECTOR] state={state} sizes={sizes} right_width={width} threshold={threshold}{extra}")
        except Exception:
            log_exception("log_inspector_state")

    def _on_main_splitter_moved(self, *_args) -> None:
        if bool(getattr(self, "_layout_transition_in_progress", False)):
            return
        # This is the single source of truth for user layout changes.  Controlled
        # programmatic setSizes() calls block the signal, so reaching this method
        # means the user actually dragged the splitter.
        try:
            sizes = self._splitter_sizes()
            tool_active = getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE
            if tool_active:
                controller = getattr(self, "layout_controller", None)
                if controller is not None:
                    controller.note_user_splitter_drag(sizes)
                    controller.prepare_interactive_tool_resize()
                else:
                    try:
                        self.ui_layout_state.inspector.user_dragged_during_tool = True
                    except Exception:
                        pass
                # Do not persist or reinterpret Light UI while an inspector tool is
                # active. The user is just resizing workspace panes, and running
                # the full overlay/layout sync path on every splitter tick caused
                # visible stutter and side panes snapping to their minimums.
                self._log_inspector_state_if_changed("tool splitter moved")
                return
            self._sync_ui_layout_state_from_splitter(save_full=True)
        except Exception:
            log_exception("user_splitter_layout_save")
        # QSplitter emits splitterMoved continuously while the user drags a
        # handle. Coalesce the heavier overlay/inspector refresh.
        self._schedule_light_transform_overlay_sync("splitter moved")

    def _schedule_light_transform_overlay_sync(self, reason: str = "splitter moved") -> None:
        try:
            self._pending_light_overlay_sync_reason = str(reason or "splitter moved")
            if bool(getattr(self, "_light_overlay_sync_pending", False)):
                return
            self._light_overlay_sync_pending = True
        # debounce marker: QTimer.singleShot(45, self._run_scheduled_light_transform_overlay_sync)
            QTimer.singleShot(int(getattr(self, "_layout_overlay_sync_delay_ms", 90)), self._run_scheduled_light_transform_overlay_sync)
        except Exception:
            log_exception("schedule_light_transform_overlay_sync")
            self._run_scheduled_light_transform_overlay_sync()

    def _run_scheduled_light_transform_overlay_sync(self) -> None:
        self._light_overlay_sync_pending = False
        reason = str(getattr(self, "_pending_light_overlay_sync_reason", "splitter moved") or "splitter moved")
        try:
            self._log_inspector_state_if_changed(reason)
            self._sync_light_transform_overlay(reason=reason)
        except Exception:
            log_exception("run_scheduled_light_transform_overlay_sync")

    def _sync_light_transform_overlay(self, *, force: bool = False, sync_fields: bool | None = None, reason: str = "") -> None:
        overlay = getattr(self, "light_transform_overlay", None)
        if overlay is None:
            return
        visible = bool(self._is_transform_overlay_mode())
        previous = getattr(self, "_last_light_overlay_visible", None)
        visibility_changed = previous is None or bool(previous) != visible
        try:
            if visibility_changed or bool(overlay.isVisible()) != visible:
                if visible:
                    self._position_light_transform_overlay(force=True)
                    overlay.show()
                    overlay.raise_()
                    overlay.update()
                else:
                    overlay.hide()
                    self._invalidate_light_overlay_backing()
            if visible:
                self._schedule_light_overlay_position(force=force or visibility_changed)
                overlay.raise_()
                if force or visibility_changed:
                    overlay.update()
        except Exception:
            log_exception("sync_light_transform_overlay")
        if visibility_changed:
            self._last_light_overlay_visible = visible
            sizes, width, threshold = self._inspector_size_debug()
            extra = f" reason={reason}" if reason else ""
            self.ui_log(f"[LIGHT_OVERLAY] visible={visible} sizes={sizes} right_width={width} threshold={threshold}{extra}")
        self._sync_light_ui_toggle_button()
        if sync_fields is None:
            # The spinbox refresh is the heavy part. It is useful when the
            # compact overlay is visible or just became visible, but it must not
            # run for every inspector resize while the right panel is open.
            sync_fields = bool(visible) and (force or visibility_changed)
        if bool(sync_fields):
            self._sync_light_transform_fields()

    def _sync_light_ui_toggle_button(self) -> None:
        try:
            available = bool(getattr(self, "active_tool", self.TOOL_NONE) == self.TOOL_NONE and not self.has_preview())
            full_light = bool(self._is_full_light_ui_mode())
            for button in [getattr(self, "btn_light_ui_toggle", None), getattr(self, "light_btn_exit_ui", None)]:
                if button is None:
                    continue
                button.blockSignals(True)
                try:
                    if button is getattr(self, "btn_light_ui_toggle", None):
                        button.setEnabled(available)
                        button.setChecked(full_light)
                    else:
                        # The left-panel Light UI toggle is hidden when Light UI
                        # collapses the side panes.  Keep a dedicated escape hatch
                        # inside the overlay, but show it only for the full Light UI
                        # state so the right-inspector overlay stays uncluttered.
                        button.setEnabled(available and full_light)
                        button.setVisible(full_light)
                finally:
                    button.blockSignals(False)
        except Exception:
            log_exception("sync_light_ui_toggle_button")

    def _set_main_splitter_sizes_coalesced(self, sizes: list[int], *, reason: str = "layout", save_full: bool = True) -> bool:
        """Apply splitter sizes once and coalesce the expensive overlay refresh.

        Programmatic setSizes() can emit splitterMoved several times. Blocking
        the signal during controlled layout transitions prevents the slow path
        from running repeatedly when tools/light UI are opened/closed many times.
        """
        try:
            splitter = getattr(self, "main_splitter", None)
            if splitter is None or len(sizes) < 3:
                return False
            target = [max(int(v), 0) for v in sizes[:3]]
            current = [int(v) for v in splitter.sizes()[:3]]
            if len(current) >= 3 and all(abs(int(a) - int(b)) <= 1 for a, b in zip(current, target)):
                # No layout change: avoid scheduling another overlay pass.
                return False
            previous_blocked = bool(splitter.signalsBlocked())
            self._layout_transition_in_progress = True
            try:
                splitter.blockSignals(True)
                splitter.setSizes(target)
            finally:
                splitter.blockSignals(previous_blocked)
            try:
                if bool(save_full):
                    self._sync_ui_layout_state_from_splitter(save_full=True)
                else:
                    # Programmatic tool/light transitions should not persist a
                    # temporary splitter layout or schedule preference writes.
                    state = getattr(self, "ui_layout_state", None)
                    if state is not None:
                        state.update_from_splitter_sizes(target, threshold=self._layout_light_threshold())
            except Exception:
                pass
            self._schedule_light_transform_overlay_sync(reason)
            return True
        except Exception:
            log_exception("set_main_splitter_sizes_coalesced")
            return False
        finally:
            def _clear_layout_transition():
                try:
                    self._layout_transition_in_progress = False
                except Exception:
                    pass
            QTimer.singleShot(0, _clear_layout_transition)

    def _schedule_ui_layout_preferences_save(self) -> None:
        try:
            if bool(getattr(self, "_ui_layout_save_pending", False)):
                return
            self._ui_layout_save_pending = True
            QTimer.singleShot(250, self._save_ui_layout_preferences_now)
        except Exception:
            pass

    def _save_ui_layout_preferences_now(self) -> None:
        try:
            self._ui_layout_save_pending = False
            from ..services.ui_preferences import save_ui_layout_preferences
            state = getattr(self, "ui_layout_state", None)
            if state is not None:
                save_ui_layout_preferences(state)
        except Exception:
            pass

    def _set_side_panel_minimums(self, *, left_collapsible: bool, right_collapsible: bool) -> None:
        try:
            left = getattr(self, "left_panel", None)
            right = getattr(self, "right_panel", None)
            left_min = int(getattr(self, "_left_panel_min_visible_width", 160))
            right_min = int(getattr(self, "_right_panel_min_visible_width", 200))
            if left is not None:
                left.setMinimumWidth(0 if left_collapsible else left_min)
                left.setMaximumWidth(16777215)
            if right is not None:
                right.setMinimumWidth(0 if right_collapsible else right_min)
                right.setMaximumWidth(16777215)
        except Exception:
            log_exception("set_side_panel_minimums")

    def _set_side_panel_compact_minimums(self, compact: bool) -> None:
        """Let QSplitter collapse/restore both side panes for full Light UI."""
        self._set_side_panel_minimums(left_collapsible=bool(compact), right_collapsible=bool(compact))

    def _set_inspector_light_mode(self, light: bool, reason: str = "button") -> None:
        try:
            if self.main_splitter is None:
                return
            if bool(light):
                if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE or self.has_preview():
                    self.ui_log("[INSPECTOR] Light UI ignored while a tool or preview is active")
                    self._sync_light_ui_toggle_button()
                    return
                sizes = [int(v) for v in self.main_splitter.sizes()]
                if len(sizes) < 3:
                    return
                try:
                    state = getattr(self, "ui_layout_state", None)
                    if state is not None and not self._sync_ui_layout_state_from_splitter(save_full=True):
                        state.last_full_splitter_sizes = [max(int(sizes[0]), int(getattr(self, "_left_panel_min_visible_width", 160))), max(int(sizes[1]), 420), max(int(sizes[2]), int(getattr(self, "_right_panel_min_visible_width", 200)))]
                except Exception:
                    pass
                total = max(sum(int(v) for v in sizes), 1)
                self._set_side_panel_compact_minimums(True)
                # Collapse both side panes. The compact Light UI overlay now
                # replaces both the project/parts panel and the right inspector.
                target = [0, max(total, 420), 0]
                self._set_main_splitter_sizes_coalesced(target, reason=f"light ui {reason}", save_full=False)
                self.ui_log(f"[INSPECTOR] light UI enabled by {reason} -> sizes={target}")
                self._log_inspector_state_if_changed(reason or "light ui", force=True)
            else:
                self._restore_full_ui_side_panels(reason or "normal UI")
            self._sync_light_ui_toggle_button()
        except Exception:
            log_exception("set_inspector_light_mode")

    def _on_light_ui_button_toggled(self, checked: bool) -> None:
        self._set_inspector_light_mode(bool(checked), "toolbar button")

    def _restore_full_ui_side_panels(self, reason: str = "normal UI") -> None:
        """Leave full Light UI by reopening both side panes.

        Full Light UI collapses left and right together.  Clicking the toolbar
        button off must therefore restore a normal three-pane workspace, not
        only reopen the right inspector.  The target prefers the last explicit
        full layout and falls back to sane readable side widths.
        """
        try:
            splitter = getattr(self, "main_splitter", None)
            if splitter is None:
                return
            current = [int(v) for v in splitter.sizes()[:3]]
            if len(current) < 3:
                return
            threshold = int(self._layout_light_threshold())
            total = max(sum(int(v) for v in current[:3]), 1)
            left_min = int(getattr(self, "_left_panel_min_visible_width", 160))
            right_min = int(getattr(self, "_right_panel_min_visible_width", 200))
            center_min = int(getattr(self, "_center_panel_auto_min_width", 360))

            state = getattr(self, "ui_layout_state", None)
            target = None
            if state is not None:
                saved = getattr(state, "last_full_splitter_sizes", None)
                if isinstance(saved, list) and len(saved) >= 3:
                    try:
                        target = [int(saved[0]), int(saved[1]), int(saved[2])]
                    except Exception:
                        target = None
                if target is None and hasattr(state, "preferred_full_sizes"):
                    try:
                        target = [int(v) for v in state.preferred_full_sizes(total)[:3]]
                    except Exception:
                        target = None

            if target is None:
                target = [220, max(total - 480, center_min), 260]

            # Ensure both side panes are visibly reopened even if the saved
            # layout came from an older preference file or a semi-collapsed UI.
            target[0] = max(int(target[0]), left_min)
            target[2] = max(int(target[2]), right_min)
            if sum(target[:3]) != total:
                target[1] = max(int(total) - int(target[0]) - int(target[2]), center_min)
            if sum(target[:3]) > total:
                overflow = sum(target[:3]) - total
                target[1] = max(int(target[1]) - overflow, 0)
            if target[1] < center_min and total > left_min + right_min:
                # Keep the viewport usable by reducing side panes only when the
                # window is genuinely narrow.
                missing = center_min - target[1]
                shrink_left = min(max(target[0] - left_min, 0), missing // 2)
                target[0] -= shrink_left
                missing -= shrink_left
                shrink_right = min(max(target[2] - right_min, 0), missing)
                target[2] -= shrink_right
                target[1] = max(total - target[0] - target[2], 0)

            self._set_side_panel_compact_minimums(False)
            # If the user exits Light UI, both sides should be protected as
            # visible panes immediately after the split is restored.
            try:
                self.main_splitter.setCollapsible(0, True)
                self.main_splitter.setCollapsible(2, True)
            except Exception:
                pass
            self._set_main_splitter_sizes_coalesced(target, reason=f"normal UI {reason}", save_full=True)
            try:
                self._sync_ui_layout_state_from_splitter(save_full=True)
            except Exception:
                pass
            self.ui_log(f"[INSPECTOR] normal UI enabled by {reason} -> sizes={target}")
            self._log_inspector_state_if_changed(reason or "normal UI", force=True)
            self._schedule_light_transform_overlay_sync(reason or "normal UI")
        except Exception:
            log_exception("restore_full_ui_side_panels")
