# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any
import time

from ..app_context import AppContext
from ..studio_log import log_exception
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None
from ..tooling.registry import get_studio_tool, get_tool_spec, iter_studio_tools, tool_label
from ..ui.top_level_window_guard import schedule_tool_top_level_guard
from .owner_delegating_controller import OwnerDelegatingController


def _qmessagebox() -> Any:
    from PySide6.QtWidgets import QMessageBox

    return QMessageBox


class ToolLifecycleController(OwnerDelegatingController):
    """Own tool open/close/apply/cancel orchestration outside MainWindow.

    This controller is the application-level coordinator between toolbar clicks,
    selection-policy checks, preview confirmation, layout restoration,
    tool hooks and runtime ``StudioTool`` objects.  It still talks to the Qt
    window through ``OwnerDelegatingController`` while controller extraction continues, but the
    workflow is no longer implemented in the mixin inheritance chain.
    """

    @classmethod
    def create(cls, context: AppContext) -> "ToolLifecycleController":
        return cls(context)

    def _tool_display_name(self, tool_id: str | None = None) -> str:
        return tool_label(self.active_tool if tool_id is None else tool_id)

    def _button_for_tool_spec(self, spec: Any) -> Any:
        if spec is None or not spec.button_attr:
            return None
        return getattr(self.owner, spec.button_attr, None)


    def _clear_button_group_checks(self, group: Any) -> None:
        """Clear checked buttons even when Qt keeps the group exclusive.

        ``QButtonGroup.setExclusive(True)`` can prevent the currently checked
        button from being unchecked by a plain ``button.setChecked(False)``.
        Tool close / cancel / apply must leave no tool selected in the toolbox,
        so temporarily disable exclusivity while clearing the group.
        """
        if group is None:
            return
        try:
            was_exclusive = bool(group.exclusive())
        except Exception:
            was_exclusive = False
        try:
            if was_exclusive:
                group.setExclusive(False)
            for button in list(group.buttons()):
                if button is None or not hasattr(button, "setChecked"):
                    continue
                try:
                    previous_blocked = bool(button.blockSignals(True))
                    button.setChecked(False)
                    button.blockSignals(previous_blocked)
                except Exception:
                    try:
                        button.blockSignals(False)
                    except Exception:
                        pass
        finally:
            try:
                if was_exclusive:
                    group.setExclusive(True)
            except Exception:
                pass

    def _clear_all_tool_button_checks(self) -> None:
        """Clear tool/modifier button checks in every known toolbar group."""
        self._clear_button_group_checks(getattr(self.owner, "tool_group", None))
        self._clear_button_group_checks(getattr(self.owner, "modifier_group", None))
        try:
            for button in list(getattr(self.owner, "toolbar_dynamic_buttons", {}).values()):
                if button is not None and hasattr(button, "setChecked"):
                    previous_blocked = bool(button.blockSignals(True))
                    button.setChecked(False)
                    button.blockSignals(previous_blocked)
        except Exception:
            pass

    def _sync_tool_buttons(self) -> None:
        try:
            remove_mode = bool(getattr(self.owner, "toolbar_remove_mode", False))
            if remove_mode or self.active_tool == self.TOOL_NONE:
                self._clear_button_group_checks(getattr(self.owner, "tool_group", None))
            for tool in iter_studio_tools(category="tool"):
                spec = tool.spec
                button = self._button_for_tool_spec(spec)
                if button is None:
                    continue
                button.blockSignals(True)
                # Trash mode is a toolbar-editing workflow, not a tool selection
                # workflow. Clearing checked states makes every visible item look
                # consistently removable instead of mixing active-tool styling
                # with remove styling.
                button.setChecked(False if remove_mode else self.active_tool == spec.id)
                button.setProperty("toolbarActionAvailable", True)
                button.setEnabled(True)
                try:
                    from .toolbar_controller import TOOLBAR_REMOVABLE_ITEM_STYLE
                    button.setStyleSheet(TOOLBAR_REMOVABLE_ITEM_STYLE if remove_mode else "")
                except Exception:
                    pass
                button.blockSignals(False)
        except Exception:
            log_exception("sync_tool_buttons")
        self._sync_boolean_buttons()
        self._sync_modifier_buttons()

    def _sync_modifier_buttons(self) -> None:
        try:
            selected_count = len(self._selected_transform_indices())
            preview_active = bool(self.has_preview())
            remove_mode = bool(getattr(self.owner, "toolbar_remove_mode", False))
            if remove_mode or self.active_tool == self.TOOL_NONE:
                self._clear_button_group_checks(getattr(self.owner, "modifier_group", None))
            for tool in iter_studio_tools(category="modifier"):
                spec = tool.spec
                button = self._button_for_tool_spec(spec)
                if button is None:
                    continue
                button.blockSignals(True)
                button.setChecked(False if remove_mode else self.active_tool == spec.id)
                can_open = (
                    self.active_tool == self.TOOL_NONE
                    and not preview_active
                    and self._tool_meets_selection_policy(spec, selected_count)
                )
                available = bool(self.active_tool == spec.id or can_open)
                # Toolbar buttons must keep receiving mouse events so users can
                # drag/reorder unavailable modifiers.  Availability is stored as
                # a property and enforced by ConfigurableToolbarController.
                button.setProperty("toolbarActionAvailable", True if remove_mode else available)
                button.setEnabled(True)
                try:
                    from .toolbar_controller import TOOLBAR_REMOVABLE_ITEM_STYLE, TOOLBAR_UNAVAILABLE_ITEM_STYLE
                    button.setStyleSheet(TOOLBAR_REMOVABLE_ITEM_STYLE if remove_mode else ("" if available else TOOLBAR_UNAVAILABLE_ITEM_STYLE))
                except Exception:
                    pass
                button.blockSignals(False)
            if remove_mode:
                self._apply_toolbar_remove_mode_visuals()
        except Exception:
            log_exception("sync_modifier_buttons")

    def confirm_preview_before_tool_change(self, context: str) -> bool:
        """Ask what to do when a tool has unapplied changes.

        Returns False if the action must be aborted.
        """
        if not self.has_preview():
            return True
        try:
            QMessageBox = _qmessagebox()
            box = QMessageBox(self.owner)
            box.setWindowTitle("Unapplied changes")
            box.setIcon(QMessageBox.Question)
            box.setText(f"{self._tool_display_name()} has unapplied changes.\nDo you want to apply them?")
            b_apply = box.addButton("Apply", QMessageBox.AcceptRole)
            b_cancel_changes = box.addButton("Discard changes", QMessageBox.DestructiveRole)
            box.addButton("Stay in tool", QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is b_apply:
                self.commit_preview_to_model(f"Applied before {context}", rebuild=True, operation_type="tool_apply")
                return True
            if clicked is b_cancel_changes:
                self.discard_preview_only(context)
                return True
            return False
        except Exception:
            log_exception("confirm_preview_before_tool_change")
            return False

    def _invoke_tool_hook(self, hook_name: str | None, *, render: bool | None = None) -> None:
        if not hook_name:
            return
        hook = getattr(self.owner, hook_name, None)
        if hook is None:
            # New controller-based tools should not add MainWindow forwarding methods
            # just to satisfy retired hook strings.  Let controllers claim
            # hooks first, then log a real missing hook.
            planar = getattr(self.owner, "planar_tool_controller", None)
            if planar is not None and callable(getattr(planar, "handle_lifecycle_hook", None)):
                try:
                    if planar.handle_lifecycle_hook(str(hook_name), render=render):
                        return
                except Exception:
                    log_exception("invoke_planar_lifecycle_hook")
            self.ui_log(f"[TOOL] Missing lifecycle hook: {hook_name}")
            return
        try:
            if render is None:
                hook()
            else:
                hook(render=render)
        except TypeError:
            hook()


    def notify_active_creator_selection_changed(self) -> None:
        """Notify the active Creator API tool that the host selection changed."""
        try:
            tool = get_studio_tool(self.active_tool)
            if tool is None:
                return
            callback = getattr(tool, "on_scene_selection_changed", None)
            if callable(callback):
                callback(self.context)
        except Exception:
            log_exception("notify_active_creator_selection_changed")

    def _close_previous_tool_resources(self, tool_id: str) -> None:
        tool = get_studio_tool(tool_id)
        if tool is not None:
            tool.on_close(self.context, render=False)
            return
        # Owner-method fallback while unknown historical tools are migrated to specs.
        if tool_id == self.TOOL_JOINT:
            self._clear_joint_selection_state()
        if tool_id == self.TOOL_MOD_SPLIT:
            self._clear_split_plane_actor(render=False)

    def open_tool(self, tool_id: str) -> None:
        try:
            orchestrator = getattr(self.owner, "ui_orchestration", None)
            if orchestrator is not None:
                orchestrator.publish("tool.open.requested", source_id=str(tool_id), payload={"value": str(tool_id), "active_tool": str(self.active_tool)})
        except Exception:
            pass
        if _APP_AUDIT is not None:
            _APP_AUDIT.increment("tool.open.request")
        start = time.perf_counter()
        try:
            return self._open_tool_measured(tool_id)
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("tool.open.total", (time.perf_counter() - start) * 1000.0, details={"tool_id": tool_id})

    def _open_tool_measured(self, tool_id: str) -> None:
        tool = get_studio_tool(tool_id)
        spec = tool.spec if tool is not None else get_tool_spec(tool_id)
        if tool_id == self.TOOL_JOINT:
            try:
                from .boolean_backend_warmup import start_boolean_backend_warmup

                start_boolean_backend_warmup(self.owner)
            except Exception:
                pass
        selected_count = len(self._selected_transform_indices())
        if tool is not None and not tool.can_open(self.context, selected_count):
            message = tool.selection_error_message(self.context)
            self.ui_log(f"[TOOL] {message}")
            try:
                _qmessagebox().information(self.owner, spec.label, message)
            except Exception:
                pass
            try:
                orchestrator = getattr(self.owner, "ui_orchestration", None)
                if orchestrator is not None:
                    orchestrator.publish("tool.open.blocked", source_id=str(tool_id), payload={"value": str(tool_id), "reason": "selection_policy", "message": message})
                    orchestrator.show_contextual_error(
                        scene_id="tool.selection_requirement",
                        anchor_id=orchestrator.toolbar_anchor_for_tool(tool_id),
                        title="Sélection requise",
                        body=message,
                    )
            except Exception:
                pass
            self._sync_modifier_buttons()
            return
        if tool is None and spec is not None and not self._tool_meets_selection_policy(spec, selected_count):
            message = self._tool_selection_error_message(spec)
            self.ui_log(f"[TOOL] {message}")
            try:
                _qmessagebox().information(self.owner, spec.label, message)
            except Exception:
                pass
            try:
                orchestrator = getattr(self.owner, "ui_orchestration", None)
                if orchestrator is not None:
                    orchestrator.publish("tool.open.blocked", source_id=str(tool_id), payload={"value": str(tool_id), "reason": "selection_policy", "message": message})
                    orchestrator.show_contextual_error(
                        scene_id="tool.selection_requirement",
                        anchor_id=orchestrator.toolbar_anchor_for_tool(tool_id),
                        title="Sélection requise",
                        body=message,
                    )
            except Exception:
                pass
            self._sync_modifier_buttons()
            return
        if self.active_tool == tool_id:
            # Re-opening an already active Creator tool should also repair its
            # declarative context. This protects the UI from stale panels created
            # before the tool had a chance to populate ctx.inspector.
            if tool is not None:
                try:
                    ctx = tool.tool_context(self.context)
                    if getattr(getattr(ctx, "inspector", None), "panel", None) is None:
                        tool.on_open(self.context)
                    try:
                        from .creator_viewport_ui import sync_creator_overlay_windows

                        sync_creator_overlay_windows(self.owner, ctx)
                    except Exception:
                        pass
                    if spec is not None:
                        self.tool_panel_stack.setCurrentIndex(spec.panel_index)
                except Exception:
                    log_exception("reopen_creator_tool_context")
            self._ensure_inspector_open(f"tool {tool_id} already active")
            self._sync_tool_buttons()
            try:
                orchestrator = getattr(self.owner, "ui_orchestration", None)
                if orchestrator is not None:
                    orchestrator.publish("tool.reopened", source_id=str(tool_id), payload={"value": str(tool_id)})
            except Exception:
                pass
            return
        old_tool = self.active_tool
        if old_tool == self.TOOL_NONE:
            self._remember_inspector_mode_before_tool_open()
        if not self.confirm_preview_before_tool_change("tool change"):
            if old_tool == self.TOOL_NONE:
                controller = getattr(self.owner, "layout_controller", None)
                if controller is not None:
                    controller.snapshot.reset()
                else:
                    try:
                        self.ui_layout_state.inspector.reset()
                    except Exception:
                        pass
            self._sync_tool_buttons()
            try:
                orchestrator = getattr(self.owner, "ui_orchestration", None)
                if orchestrator is not None:
                    orchestrator.publish("tool.open.blocked_by_active_tool", source_id=str(tool_id), payload={"value": str(tool_id), "active_tool": str(old_tool)})
                    orchestrator.show_active_tool_conflict(requested_tool_id=str(tool_id))
            except Exception:
                pass
            return
        self._close_previous_tool_resources(old_tool)
        self._ensure_inspector_open(f"open tool {tool_id}")
        # Any opened tool owns the scene/preview workflow. Keep the persistent
        # transform mode selected in memory, but remove the overlay immediately.
        self._clear_gizmo_interaction(clear_highlight=True)
        self._clear_gizmo_actors()
        self.active_tool = tool_id
        try:
            self.tool_state.active_tool = tool_id
        except Exception:
            pass
        self.transform_box.setVisible(False)
        self._schedule_light_transform_overlay_sync("tool/preview state")
        if spec is not None:
            self._apply_tool_selection_policy(spec)
            # Creator API tools create their declarative inspector panel during
            # on_open(). Open them before switching the stacked widget so the
            # live declarative panel can render the freshly-created ctx.inspector.
            if tool is not None:
                tool.on_open(self.context)
                try:
                    from .creator_viewport_ui import sync_creator_overlay_windows

                    sync_creator_overlay_windows(self.owner, tool.tool_context(self.context))
                except Exception:
                    pass
            else:
                self._invoke_tool_hook(spec.open_hook)
            self.tool_panel_stack.setCurrentIndex(spec.panel_index)
        else:
            self.ui_log(f"[TOOL] Unknown tool id: {tool_id}")
        self._sync_tool_buttons()
        self.update_preview_state()
        self.refresh_actor_styles(render=False)
        self.update_gizmo(render=False)
        self.update_inspector()
        self.update_joint_info()
        self.plotter.render()
        schedule_tool_top_level_guard(self.owner, reason=f"open tool {tool_id}")
        self.ui_log(f"[TOOL] Open: {tool_id}")
        try:
            orchestrator = getattr(self.owner, "ui_orchestration", None)
            if orchestrator is not None:
                orchestrator.register_standard_anchors()
                orchestrator.publish("tool.opened", source_id=str(tool_id), payload={"value": str(tool_id)})
        except Exception:
            pass

    def close_active_tool(self, log_it: bool = True, ask_preview: bool = True) -> None:
        start = time.perf_counter()
        old_tool_for_audit = getattr(self, "active_tool", "")
        try:
            return self._close_active_tool_measured(log_it=log_it, ask_preview=ask_preview)
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("tool.close.total", (time.perf_counter() - start) * 1000.0, details={"tool_id": old_tool_for_audit})

    def _close_active_tool_measured(self, log_it: bool = True, ask_preview: bool = True) -> None:
        if ask_preview and not self.confirm_preview_before_tool_change("close tool"):
            return
        elif not ask_preview and self.has_preview():
            self.discard_preview_only("close tool")
        old_tool = self.active_tool
        self._close_previous_tool_resources(old_tool)
        self.active_tool = self.TOOL_NONE
        try:
            self.tool_state.active_tool = self.TOOL_NONE
        except Exception:
            pass
        self.tool_panel_stack.setCurrentIndex(0)
        try:
            self.transform_box.setVisible(True)
        except Exception:
            pass
        self._restore_inspector_mode_after_tool_close("close tool")
        self._clear_all_tool_button_checks()
        self.active_index = self.selected_indices[-1] if self.selected_indices else None
        self._sync_tool_buttons()
        self.update_preview_state()
        self.update_gizmo(render=False)
        try:
            self.plotter.render()
        except Exception:
            pass
        if log_it:
            self.ui_log("[TOOL] Closed, preview disabled")
        try:
            orchestrator = getattr(self.owner, "ui_orchestration", None)
            if orchestrator is not None:
                orchestrator.publish("tool.closed", source_id=str(old_tool), payload={"value": str(old_tool)})
        except Exception:
            pass

    def apply_preview_and_close_tool(self) -> None:
        start = time.perf_counter()
        active_tool_for_audit = getattr(self, "active_tool", "")
        try:
            return self._apply_preview_and_close_tool_measured()
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("tool.apply_and_close.total", (time.perf_counter() - start) * 1000.0, details={"tool_id": active_tool_for_audit})

    def _apply_preview_and_close_tool_measured(self) -> None:
        if not self.has_preview():
            planar = getattr(self.owner, "planar_tool_controller", None)
            if planar is not None and callable(getattr(planar, "ensure_preview_before_apply", None)):
                try:
                    planar.ensure_preview_before_apply()
                except Exception:
                    log_exception("planar_preview_before_apply")
        if self.mesh_store is None or not self.has_preview():
            try:
                active_tool_before_apply = self.active_tool
                tool = get_studio_tool(active_tool_before_apply)
                can_apply = getattr(tool, "can_apply", None)
                apply = getattr(tool, "apply", None)
                if tool is None or not callable(can_apply) or not bool(can_apply(self.context)) or not callable(apply):
                    return
                if not bool(apply(self.context)):
                    return
                self._close_previous_tool_resources(active_tool_before_apply)
                self.active_tool = self.TOOL_NONE
                try:
                    self.tool_state.active_tool = self.TOOL_NONE
                except Exception:
                    pass
                self.tool_panel_stack.setCurrentIndex(0)
                try:
                    self.transform_box.setVisible(True)
                except Exception:
                    pass
                self._restore_inspector_mode_after_tool_close("apply creator tool")
                self._clear_all_tool_button_checks()
                self._sync_tool_buttons()
                self.selected_indices = []
                self.active_index = None
                self.rebuild_scene(keep_camera=True)
                self.update_preview_state()
                self._sync_history_buttons()
                try:
                    orchestrator = getattr(self.owner, "ui_orchestration", None)
                    if orchestrator is not None:
                        orchestrator.publish("tool.applied", source_id=str(active_tool_before_apply), payload={"value": str(active_tool_before_apply)})
                except Exception:
                    pass
            except Exception:
                log_exception("apply_creator_tool_without_preview")
            return
        try:
            active_tool_before_apply = self.active_tool
            if active_tool_before_apply == getattr(self, "TOOL_LAYFLAT", "layflat"):
                ok = self.owner.preview_controller.commit_preview_to_new_scene(
                    "Lay flat applied",
                    scene_name=None,
                    operation_type="layflat",
                )
                if not ok:
                    return
            else:
                self.commit_preview_to_model(f"{self._tool_display_name()} applied", rebuild=False, operation_type="tool_apply")
            self._close_previous_tool_resources(active_tool_before_apply)
            self.active_tool = self.TOOL_NONE
            try:
                self.tool_state.active_tool = self.TOOL_NONE
            except Exception:
                pass
            self.tool_panel_stack.setCurrentIndex(0)
            try:
                self.transform_box.setVisible(True)
            except Exception:
                pass
            self._restore_inspector_mode_after_tool_close("apply preview")
            self._clear_all_tool_button_checks()
            self._sync_tool_buttons()
            try:
                self.ui_log(
                    f"[SELECTION_DIAG] clear_selection begin reason=apply_preview "
                    f"selected_before={list(getattr(self.owner, 'selected_indices', []))} "
                    f"active_before={getattr(self.owner, 'active_index', None)} "
                    f"mode={getattr(self.owner, 'transform_mode', None)}"
                )
            except Exception:
                pass
            self.selected_indices = []
            self.active_index = None
            self.rebuild_scene(keep_camera=True)
            # Do not refocus the editor camera when leaving/applying a tool.
            # The user's current view must stay exactly where it is.
            self.update_preview_state()
            self._sync_history_buttons()
            try:
                orchestrator = getattr(self.owner, "ui_orchestration", None)
                if orchestrator is not None:
                    orchestrator.publish("tool.applied", source_id=str(active_tool_before_apply), payload={"value": str(active_tool_before_apply)})
            except Exception:
                pass
        except Exception:
            log_exception("apply_preview_and_close_tool")

    def discard_preview_and_close_tool(self) -> None:
        start = time.perf_counter()
        cancelled_tool = str(getattr(self, "active_tool", ""))
        try:
            self.discard_preview_only("cancel button")
            self.close_active_tool(log_it=True)
            try:
                orchestrator = getattr(self.owner, "ui_orchestration", None)
                if orchestrator is not None:
                    orchestrator.publish("tool.cancelled", source_id=cancelled_tool, payload={"value": cancelled_tool})
            except Exception:
                pass
        finally:
            if _APP_AUDIT is not None:
                _APP_AUDIT.record_timing("tool.cancel_and_close.total", (time.perf_counter() - start) * 1000.0)
