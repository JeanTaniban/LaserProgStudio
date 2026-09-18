# -*- coding: utf-8 -*-
from __future__ import annotations

from ..app_context import AppContext
from ..state.ui_layout_state import InspectorLayoutState
from ..studio_log import log_exception
from .action_controller import WindowController
from .splitter_layout_policy import SplitterLayoutPolicy


InspectorRestoreSnapshot = InspectorLayoutState


class LayoutController(WindowController):
    """Own inspector/light-UI restoration outside the MainWindow mixin chain.

    Tools often need the full right inspector while the user may currently be in
    compact Light UI. This controller centralises that workflow so tool classes
    can ask for an inspector without knowing splitter thresholds or restoration
    details.
    """

    @classmethod
    def create(cls, context: AppContext) -> "LayoutController":
        return cls(context)

    def __init__(self, context: AppContext):
        super().__init__(context)
        self.snapshot = context.layout.inspector

    def note_user_splitter_drag(self, sizes: list[int] | None = None) -> None:
        """Remember that the user overrode an automatic tool inspector resize."""
        self.snapshot.user_dragged_during_tool = True
        if isinstance(sizes, list) and len(sizes) >= 3:
            try:
                self.snapshot.full_splitter_sizes = [int(v) for v in sizes[:3]]
            except Exception:
                pass

    def prepare_interactive_tool_resize(self) -> None:
        """Make tool splitter drags normal, without collapsing visible panes."""
        w = self.owner
        try:
            sizes = [int(v) for v in w.main_splitter.sizes()] if getattr(w, "main_splitter", None) is not None else []
            left_collapsible, _right_collapsible = self._layout_policy().minimums_for_current_state(sizes)
            # During a tool the right inspector must stay usable. The left pane
            # is collapsible only when it was already collapsed/Light UI, not just
            # because a tool is active.
            w._set_side_panel_minimums(left_collapsible=bool(left_collapsible), right_collapsible=False)
        except Exception:
            pass

    def remember_before_tool_open(self) -> None:
        """Remember whether compact/light UI must be restored after tool close."""
        w = self.owner
        try:
            if getattr(w, "active_tool", w.TOOL_NONE) != w.TOOL_NONE:
                return
            sizes = [int(v) for v in w.main_splitter.sizes()] if getattr(w, "main_splitter", None) is not None else []
            side_state = self._layout_policy().side_state(sizes) if len(sizes) >= 3 else None
            compact = bool(w._is_transform_overlay_mode())
            full_light = bool(w._is_full_light_ui_mode())
            self.snapshot.restore_light_ui = compact
            self.snapshot.light_ui_sizes = None
            self.snapshot.left_was_collapsed = bool(side_state.left_collapsed) if side_state is not None else False
            self.snapshot.right_was_collapsed = bool(side_state.right_collapsed) if side_state is not None else compact
            if compact and getattr(w, "main_splitter", None) is not None:
                try:
                    self.snapshot.light_ui_sizes = [int(v) for v in w.main_splitter.sizes()]
                except Exception:
                    self.snapshot.light_ui_sizes = None
            self.snapshot.user_dragged_during_tool = False
            self.snapshot.full_splitter_sizes = None
            w.ui_log(
                "[INSPECTOR] remember before tool: "
                f"compact_overlay={compact} full_light={full_light} sizes={self.snapshot.light_ui_sizes}"
            )
        except Exception:
            log_exception("remember_inspector_mode_before_tool_open")

    def restore_after_tool_close(self, reason: str = "") -> None:
        """Restore compact/light UI when a tool had opened the inspector for it."""
        try:
            if not bool(self.snapshot.restore_light_ui):
                self._restore_saved_full_splitter(reason)
                return
            self._restore_compact_transform_ui(reason)
        except Exception:
            log_exception("restore_inspector_mode_after_tool_close")
        finally:
            self.snapshot.restore_light_ui = False
            self.snapshot.light_ui_sizes = None

    def ensure_inspector_open(self, reason: str = "") -> None:
        """Open the right inspector only when it is actually collapsed.

        In normal/non-Light UI the inspector is already visible, so opening a
        tool must not push the left pane or rewrite splitter sizes. Automatic
        resizing is reserved for Light UI / right-collapsed layouts.
        """
        w = self.owner
        try:
            if getattr(w, "main_splitter", None) is None:
                return
            sizes = [int(v) for v in w.main_splitter.sizes()]
            if len(sizes) < 3:
                return

            total = max(sum(sizes), 1)
            pref_left, pref_right = self._preferred_side_widths(total)
            open_from_tool = "open tool" in str(reason or "") or "tool " in str(reason or "")
            policy = self._layout_policy()
            plan = policy.plan_open_inspector(
                sizes,
                preferred_left=int(pref_left),
                preferred_right=int(pref_right),
                from_tool=bool(open_from_tool),
            )
            try:
                w._set_side_panel_minimums(
                    left_collapsible=bool(plan.left_collapsible),
                    right_collapsible=bool(plan.right_collapsible),
                )
            except Exception:
                try:
                    w._set_side_panel_compact_minimums(False)
                except Exception:
                    pass

            if not plan.should_resize:
                # Non-Light UI contract: do not touch splitter sizes when the
                # user already has a visible right inspector.
                self.snapshot.full_splitter_sizes = None
                self.snapshot.user_dragged_during_tool = False
                w.ui_log(
                    f"[INSPECTOR] kept user splitter for {reason or 'tool'} "
                    f"-> sizes={sizes} mode={plan.reason}"
                )
                w._log_inspector_state_if_changed(reason or "inspector already open", force=True)
                return

            self.snapshot.full_splitter_sizes = [int(v) for v in sizes[:3]]
            self.snapshot.user_dragged_during_tool = False

            target = [int(v) for v in plan.target_sizes[:3]]
            w._set_main_splitter_sizes_coalesced(target, reason=f"open inspector {reason or 'tool'}", save_full=False)
            w.ui_log(
                f"[INSPECTOR] opened for {reason or 'tool'} -> sizes={target} "
                f"from={sizes} mode={plan.reason} user_saved={self.snapshot.full_splitter_sizes}"
            )
            w._log_inspector_state_if_changed(reason or "forced open", force=True)
        except Exception:
            log_exception("ensure_inspector_open")

    def _layout_policy(self) -> SplitterLayoutPolicy:
        w = self.owner
        return SplitterLayoutPolicy(
            threshold=int(getattr(w, "_layout_light_collapse_threshold", getattr(w, "_right_panel_light_threshold", 12))),
            left_min=int(getattr(w, "_left_panel_min_visible_width", 160)),
            right_min=int(getattr(w, "_right_panel_min_visible_width", 200)),
            tool_right_min=int(getattr(w, "_right_panel_tool_min_width", 240)),
            center_auto_min=int(getattr(w, "_center_panel_auto_min_width", 360)),
        )

    def _preferred_side_widths(self, total: int) -> tuple[int, int]:
        w = self.owner
        state = getattr(w, "ui_layout_state", None)
        if state is not None and hasattr(state, "preferred_full_sizes"):
            pref_left, _pref_center, pref_right = state.preferred_full_sizes(total)
            return int(pref_left), int(pref_right)
        return 220, 260

    def _restore_saved_full_splitter(self, reason: str) -> None:
        w = self.owner
        saved_full = self.snapshot.full_splitter_sizes
        user_dragged = bool(self.snapshot.user_dragged_during_tool)
        if isinstance(saved_full, list) and len(saved_full) >= 3 and not user_dragged and getattr(w, "main_splitter", None) is not None:
            try:
                w._set_side_panel_compact_minimums(False)
                target = [int(saved_full[0]), max(int(saved_full[1]), 420), int(saved_full[2])]
                w._set_main_splitter_sizes_coalesced(target, reason=f"restore user splitter {reason or 'tool close'}", save_full=False)
                w.ui_log(f"[INSPECTOR] restored user splitter after {reason or 'tool close'} -> sizes={saved_full}")
            except Exception:
                log_exception("restore_user_splitter_after_tool_close")
        self.snapshot.full_splitter_sizes = None
        self.snapshot.user_dragged_during_tool = False
        w._log_inspector_state_if_changed(reason or "tool closed", force=True)
        w._schedule_light_transform_overlay_sync(reason or "tool closed")

    def _restore_compact_transform_ui(self, reason: str) -> None:
        w = self.owner
        if getattr(w, "main_splitter", None) is None:
            return
        current = [int(v) for v in w.main_splitter.sizes()]
        if len(current) < 3:
            return
        saved = self.snapshot.light_ui_sizes
        try:
            w._set_side_panel_compact_minimums(True)
        except Exception:
            pass
        if isinstance(saved, list) and len(saved) >= 3:
            target = [int(saved[0]), max(int(saved[1]), 420), int(saved[2])]
        else:
            total = max(sum(int(v) for v in current[:3]), 1)
            left = max(int(current[0]), int(getattr(w, "_left_panel_min_visible_width", 160)))
            center = max(int(total) - left, 420)
            target = [left, center, 0]
        w._set_main_splitter_sizes_coalesced(target, reason=f"restore compact {reason or 'tool close'}", save_full=False)
        w.ui_log(f"[INSPECTOR] restored compact transform UI after {reason or 'tool close'} -> sizes={target}")
        w._log_inspector_state_if_changed(reason or "restore compact", force=True)
