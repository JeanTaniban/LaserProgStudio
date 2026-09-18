# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class SplitterSideState:
    """Read-only interpretation of the main left/viewport/right splitter."""

    left: int
    center: int
    right: int
    threshold: int

    @property
    def total(self) -> int:
        return max(int(self.left) + int(self.center) + int(self.right), 1)

    @property
    def left_collapsed(self) -> bool:
        return int(self.left) <= int(self.threshold)

    @property
    def right_collapsed(self) -> bool:
        return int(self.right) <= int(self.threshold)

    @property
    def full_light(self) -> bool:
        return self.left_collapsed and self.right_collapsed

    @property
    def inspector_visible(self) -> bool:
        return not self.right_collapsed


@dataclass(frozen=True, slots=True)
class InspectorOpenPlan:
    """A deterministic splitter plan for opening an inspector/tool pane."""

    should_resize: bool
    target_sizes: list[int]
    left_collapsible: bool
    right_collapsible: bool
    reason: str


@dataclass(frozen=True, slots=True)
class SplitterLayoutPolicy:
    """Policy object for the main app splitter.

    The central VTK viewport must be flexible: normal side panes are allowed to
    resize without fighting each other.  Tool opening is therefore conservative:
    if the right inspector is already visible in normal UI, opening an inspector
    tool must not rewrite the user's splitter sizes.
    """

    threshold: int = 12
    left_min: int = 160
    right_min: int = 200
    tool_right_min: int = 240
    center_auto_min: int = 360

    def side_state(self, sizes: Sequence[int]) -> SplitterSideState:
        left = int(sizes[0]) if len(sizes) > 0 else 0
        center = int(sizes[1]) if len(sizes) > 1 else 0
        right = int(sizes[2]) if len(sizes) > 2 else 0
        return SplitterSideState(left=left, center=center, right=right, threshold=int(self.threshold))

    def minimums_for_current_state(self, sizes: Sequence[int]) -> tuple[bool, bool]:
        """Return left/right collapsibility for the current visual mode."""
        state = self.side_state(sizes)
        # If a side pane was collapsed by Light UI, keep it collapsible.  In
        # normal UI, keep visible panes protected by their readable minimums.
        return bool(state.left_collapsed), bool(state.right_collapsed)

    def plan_open_inspector(
        self,
        sizes: Sequence[int],
        *,
        preferred_left: int,
        preferred_right: int,
        from_tool: bool,
    ) -> InspectorOpenPlan:
        state = self.side_state(sizes)
        left_collapsible, _right_collapsible = self.minimums_for_current_state(sizes)

        if from_tool and state.inspector_visible:
            # Normal UI already exposes the right inspector.  Do not resize or
            # persist anything; just let the tool panel switch inside the pane.
            return InspectorOpenPlan(
                should_resize=False,
                target_sizes=[state.left, state.center, state.right],
                left_collapsible=left_collapsible,
                right_collapsible=False,
                reason="already-visible",
            )

        required_right = max(int(preferred_right), int(self.right_min), int(self.tool_right_min) if from_tool else int(self.right_min))
        keep_left_collapsed = bool(state.left_collapsed)
        left = 0 if keep_left_collapsed else max(int(state.left), int(self.left_min))
        right = int(required_right)
        total = state.total

        # Automatic opening should prefer shrinking the center before stealing
        # width from the opposite side pane.  Side panes are reduced only when
        # the window is genuinely too narrow for a usable viewport.
        center_min = int(self.center_auto_min)
        if left + right + center_min > total:
            overflow = left + right + center_min - total
            if not keep_left_collapsed:
                shrink_left = min(max(left - int(self.left_min), 0), overflow)
                left -= shrink_left
                overflow -= shrink_left
            shrink_right = min(max(right - int(self.right_min), 0), overflow)
            right -= shrink_right
            overflow -= shrink_right
        center = max(total - left - right, center_min)
        if left + center + right > total:
            center = max(total - left - right, 0)
        return InspectorOpenPlan(
            should_resize=True,
            target_sizes=[int(left), int(center), int(right)],
            left_collapsible=keep_left_collapsed,
            right_collapsible=False,
            reason="open-collapsed-inspector" if state.right_collapsed else "open-inspector",
        )
