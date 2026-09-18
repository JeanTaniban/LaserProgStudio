# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class ToolSelectionPolicyLayer:
    """Selection rules for tool/modifier opening.

    The registry declares the policy; this mixin enforces it in one place.
    Keeping this logic out of ToolLifecycleLayer prevents future tools from
    adding ad-hoc selection checks in open_tool().
    """


    def _active_tool_allows_scene_multi_selection(self) -> bool:
        """Return True when the current tool should keep normal multi-selection."""
        try:
            active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none"))
            if active in {getattr(self, "TOOL_NONE", "none"), getattr(self, "TOOL_MOD_SPLIT", "split"), getattr(self, "TOOL_JOINT", "joint")}:
                return True
            from ..tooling.registry import get_tool_spec

            spec = get_tool_spec(str(active))
            return bool(spec is not None and getattr(spec, "allows_multi_selection", False))
        except Exception:
            return False

    def _tool_meets_selection_policy(self, spec, selected_count: int) -> bool:
        if spec is None or not getattr(spec, "requires_selection", False):
            return True
        if getattr(spec, "selection_policy", "none") == "multi":
            return selected_count >= 1
        return selected_count >= 1

    def _tool_selection_error_message(self, spec) -> str:
        label = getattr(spec, "label", "Tool")
        policy = getattr(spec, "selection_policy", "none")
        if policy == "multi":
            return f"Select at least one target part before opening {label}."
        if policy == "single":
            return f"Select a target part before opening {label}."
        return ""

    def _apply_tool_selection_policy(self, spec) -> None:
        if spec is None:
            return
        if spec.clear_selection_on_open:
            try:
                self.ui_log(
                    f"[SELECTION_DIAG] clear_selection begin reason=open_tool_{spec.id} "
                    f"selected_before={list(getattr(self, 'selected_indices', []))} "
                    f"active_before={getattr(self, 'active_index', None)} mode={getattr(self, 'transform_mode', None)}"
                )
            except Exception:
                pass
            self.selected_indices = []
            self.active_index = None
            return
        if not spec.allows_multi_selection and len(self.selected_indices) > 1:
            self.selected_indices = self.selected_indices[-1:]
        if spec.active_index_from_selection:
            self.active_index = self.selected_indices[-1] if self.selected_indices else None
