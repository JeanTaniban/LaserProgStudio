# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from _path_setup import ROOT  # noqa: F401
from laserprog_studio.application.splitter_layout_policy import SplitterLayoutPolicy

STUDIO = ROOT / "src" / "laserprog_studio"


def test_splitter_policy_does_not_resize_when_tool_opens_in_normal_ui() -> None:
    policy = SplitterLayoutPolicy(threshold=12, left_min=160, right_min=200, tool_right_min=240, center_auto_min=360)
    plan = policy.plan_open_inspector([260, 820, 280], preferred_left=220, preferred_right=260, from_tool=True)
    assert plan.should_resize is False
    assert plan.target_sizes == [260, 820, 280]
    assert plan.left_collapsible is False
    assert plan.right_collapsible is False
    assert plan.reason == "already-visible"


def test_splitter_policy_opens_only_the_right_pane_from_light_ui() -> None:
    policy = SplitterLayoutPolicy(threshold=12, left_min=160, right_min=200, tool_right_min=240, center_auto_min=360)
    plan = policy.plan_open_inspector([0, 1100, 0], preferred_left=220, preferred_right=260, from_tool=True)
    assert plan.should_resize is True
    assert plan.target_sizes[0] == 0
    assert plan.target_sizes[2] >= 260
    assert plan.left_collapsible is True
    assert plan.right_collapsible is False


def test_splitter_policy_preserves_open_left_when_only_right_is_collapsed() -> None:
    policy = SplitterLayoutPolicy(threshold=12, left_min=160, right_min=200, tool_right_min=240, center_auto_min=360)
    plan = policy.plan_open_inspector([230, 870, 0], preferred_left=220, preferred_right=260, from_tool=True)
    assert plan.should_resize is True
    assert plan.target_sizes[0] == 230
    assert plan.target_sizes[2] >= 260
    assert plan.left_collapsible is False


def test_center_toolbar_is_scrollable_and_does_not_force_viewport_minimum_width() -> None:
    source = (STUDIO / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    assert "self.top_toolbar_scroll = QScrollArea(panel)" in source
    assert "setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)" in source
    assert "minimum width of the whole 3D viewport" in source
    assert "self.center_stack.setMinimumWidth(0)" in source
    assert "self.plotter_area.setMinimumWidth(0)" in source
    assert "root.setStretchFactor(1, 1)" in source


def test_layout_controller_declares_non_light_tool_open_contract() -> None:
    source = (STUDIO / "application" / "layout_controller.py").read_text(encoding="utf-8")
    assert "Non-Light UI contract" in source
    assert "do not touch splitter sizes" in source
    assert "plan_open_inspector" in source
    assert "snapshot.full_splitter_sizes = None" in source
