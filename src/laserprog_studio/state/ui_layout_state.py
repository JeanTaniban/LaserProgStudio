# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

LayoutMode = Literal["full", "light"]


@dataclass(slots=True)
class InspectorLayoutState:
    """Splitter snapshot owned by tool inspector workflows."""

    restore_light_ui: bool = False
    light_ui_sizes: list[int] | None = None
    full_splitter_sizes: list[int] | None = None
    user_dragged_during_tool: bool = False
    left_was_collapsed: bool = False
    right_was_collapsed: bool = False

    def reset(self) -> None:
        self.restore_light_ui = False
        self.light_ui_sizes = None
        self.full_splitter_sizes = None
        self.user_dragged_during_tool = False
        self.left_was_collapsed = False
        self.right_was_collapsed = False


@dataclass
class UiLayoutState:
    """Remember splitter intent separately from current Qt widget sizes.

    Future Light UI fixes should update this state when both left and right
    panes are collapsed, instead of inferring the whole layout from the right
    inspector only.
    """

    mode: LayoutMode = "full"
    last_full_splitter_sizes: list[int] = field(default_factory=list)
    last_left_width: int = 220
    last_center_width: int = 1120
    last_right_width: int = 260
    left_collapsed: bool = False
    right_collapsed: bool = False
    inspector: InspectorLayoutState = field(default_factory=InspectorLayoutState)
    toolbar_item_ids: list[str] = field(default_factory=list)
    toolbar_registry_version: int = 3

    def update_from_splitter_sizes(self, sizes: list[int], threshold: int = 12) -> None:
        left = int(sizes[0]) if len(sizes) > 0 else 0
        right = int(sizes[2]) if len(sizes) > 2 else 0
        self.left_collapsed = left <= threshold
        self.right_collapsed = right <= threshold
        self.mode = "light" if self.left_collapsed and self.right_collapsed else "full"
        if len(sizes) >= 3:
            center = max(int(sizes[1]), 0)
            if left > threshold:
                self.last_left_width = left
            if center > 100:
                self.last_center_width = center
            if right > threshold:
                self.last_right_width = right
        if self.mode == "full" and len(sizes) >= 3:
            self.last_full_splitter_sizes = [int(v) for v in sizes[:3]]

    def apply_preferences(self, payload: dict) -> None:
        """Load persisted JSON values while tolerating older files."""
        if not isinstance(payload, dict):
            return
        for attr in ("mode", "last_left_width", "last_center_width", "last_right_width", "left_collapsed", "right_collapsed"):
            if attr in payload:
                try:
                    setattr(self, attr, payload[attr])
                except Exception:
                    pass
        toolbar_ids = payload.get("toolbar_item_ids")
        if isinstance(toolbar_ids, list):
            try:
                self.toolbar_item_ids = [str(v) for v in toolbar_ids]
            except Exception:
                self.toolbar_item_ids = []
        try:
            self.toolbar_registry_version = int(payload.get("toolbar_registry_version", self.toolbar_registry_version))
        except Exception:
            self.toolbar_registry_version = 3
        sizes = payload.get("last_full_splitter_sizes")
        if isinstance(sizes, list) and len(sizes) >= 3:
            try:
                self.last_full_splitter_sizes = [int(v) for v in sizes[:3]]
            except Exception:
                pass
        # Coerce to sane minimums; collapsed panes are handled by QSplitter, not stored widths.
        try:
            self.last_left_width = max(int(self.last_left_width), 160)
            self.last_center_width = max(int(self.last_center_width), 420)
            self.last_right_width = max(int(self.last_right_width), 200)
        except Exception:
            self.last_left_width, self.last_center_width, self.last_right_width = 220, 1120, 260

    def preferred_full_sizes(self, total: int | None = None) -> list[int]:
        left = max(int(self.last_left_width), 160)
        right = max(int(self.last_right_width), 200)
        center = max(int(self.last_center_width), 420)
        if total is not None and total > 0:
            total = int(total)
            if left + right + 420 > total:
                overflow = left + right + 420 - total
                # Reduce side panes proportionally but do not make them unusably small.
                shrink_left = min(max(left - 160, 0), overflow // 2)
                left -= shrink_left
                overflow -= shrink_left
                shrink_right = min(max(right - 200, 0), overflow)
                right -= shrink_right
                overflow -= shrink_right
            center = max(total - left - right, 420)
        return [left, center, right]
