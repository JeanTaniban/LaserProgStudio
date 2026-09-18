# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.application.tool_lifecycle_controller import ToolLifecycleController

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


class _FakeButton:
    def __init__(self, group=None, checked: bool = False):
        self.group = group
        self.checked = checked
        self._blocked = False

    def blockSignals(self, value: bool) -> bool:
        previous = self._blocked
        self._blocked = bool(value)
        return previous

    def setChecked(self, value: bool) -> None:
        # Simulate Qt exclusive groups: the currently checked button refuses a
        # plain uncheck while the group remains exclusive.
        if not value and self.group is not None and self.group.exclusive():
            return
        self.checked = bool(value)

    def isChecked(self) -> bool:
        return self.checked


class _FakeButtonGroup:
    def __init__(self, exclusive: bool = True):
        self._exclusive = bool(exclusive)
        self._buttons: list[_FakeButton] = []

    def exclusive(self) -> bool:
        return self._exclusive

    def setExclusive(self, value: bool) -> None:
        self._exclusive = bool(value)

    def buttons(self):
        return list(self._buttons)

    def addButton(self, button: _FakeButton) -> None:
        button.group = self
        self._buttons.append(button)


def test_tool_close_can_clear_exclusive_qt_button_group() -> None:
    group = _FakeButtonGroup(exclusive=True)
    button = _FakeButton(checked=True)
    group.addButton(button)

    # A direct uncheck is ignored by the fake exclusive group, matching the Qt
    # bug seen in the toolbox after closing a tool.
    button.setChecked(False)
    assert button.isChecked()

    controller = ToolLifecycleController(SimpleNamespace(owner=SimpleNamespace()))
    controller._clear_button_group_checks(group)

    assert not button.isChecked()
    assert group.exclusive()


def test_texture_projection_controller_is_composed_and_facaded() -> None:
    controller_source = (STUDIO / "application" / "texture_projection_controller.py").read_text(encoding="utf-8")
    mixin_source = (STUDIO / "controllers" / "texture_projection_tool.py").read_text(encoding="utf-8")
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")

    assert "class TextureProjectionController" in controller_source
    assert "def generate_texture_projection_preview" in controller_source
    assert "def clear_texture_projection_selected" in controller_source
    assert "def _qfiledialog" in controller_source
    assert "from .._window_deps import *" not in controller_source
    assert "self.texture_projection_controller = TextureProjectionController.create(self.app_context)" in runtime_source

    # The legacy mixin still owns gizmo interactions for now, but the selected
    # texture preview workflow must be delegated to the composed controller.
    assert "return self._texture_projection_controller().generate_texture_projection_preview" in mixin_source
    assert len(mixin_source.splitlines()) < 1550


def test_pass9_documentation_exists() -> None:
    assert (ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_9.md").exists()
