from pathlib import Path

from _light_transform_source import read_light_transform_source

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py"
LIGHT = ROOT / "src" / "laserprog_studio" / "ui" / "light_transform_overlay.py"


def test_history_buttons_live_in_left_project_panel_only():
    text = LAYOUT.read_text(encoding="utf-8")
    left_panel_start = text.index("def _make_left_panel")
    center_start = text.index("def _make_center_panel")
    left_block = text[left_panel_start:center_start]
    assert 'history_label = QLabel("History")' in left_block
    assert "self.btn_undo = self.btn_project_undo" in left_block
    assert "self.btn_redo = self.btn_project_redo" in left_block

    workspace_start = text.index("def _make_3d_workspace")
    engrave_start = text.index("def _make_engrave_workspace")
    workspace_block = text[workspace_start:engrave_start]
    assert 'QLabel("History")' not in workspace_block
    assert "self._history_button(" not in workspace_block


def test_center_toolbar_contains_only_toolbox_controls():
    text = LAYOUT.read_text(encoding="utf-8")
    workspace_start = text.index("def _make_3d_workspace")
    engrave_start = text.index("def _make_engrave_workspace")
    workspace_block = text[workspace_start:engrave_start]
    assert "self._setup_configurable_toolbar(top_l)" in workspace_block
    assert "self.btn_toolbar_remove = QToolButton()" in workspace_block
    assert "self.btn_tf_none" not in workspace_block
    assert "self.btn_floor_grid" not in workspace_block
    assert "self.btn_light_ui_toggle" not in workspace_block
    assert "self.btn_apply_preview" not in workspace_block
    assert "self.btn_cancel_preview" not in workspace_block


def test_transform_modes_and_tool_actions_live_in_right_panel():
    text = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    right_start = text.index("def _make_right_panel")
    helper_start = text.index("def _triple_row")
    right_block = text[right_start:helper_start]
    assert "self.transform_group = QButtonGroup(self)" in right_block
    assert 'self.btn_tf_none = self._transform_button("N"' in right_block
    assert 'self.tool_box = QGroupBox("Tool")' in right_block
    assert 'self.preview_label = QLabel("")' in right_block
    assert 'self.btn_apply_preview = QPushButton("Apply")' in right_block
    assert 'self.btn_cancel_preview = QPushButton("Cancel")' in right_block


def test_grid_and_light_ui_controls_live_in_left_view_panel():
    text = LAYOUT.read_text(encoding="utf-8")
    left_start = text.index("def _make_left_panel")
    center_start = text.index("def _make_center_panel")
    left_block = text[left_start:center_start]
    assert 'workspace_title = QLabel("Workspace")' in left_block
    assert "self.btn_floor_grid = QToolButton()" in left_block
    assert "self.btn_light_ui_toggle = QToolButton()" in left_block


def test_light_ui_exit_restores_both_side_panels():
    text = read_light_transform_source(ROOT)
    assert "def _restore_full_ui_side_panels" in text
    assert "Full Light UI collapses left and right together" in text
    assert "self._restore_full_ui_side_panels(reason or \"normal UI\")" in text
    assert "target[0] = max(int(target[0]), left_min)" in text
    assert "target[2] = max(int(target[2]), right_min)" in text
