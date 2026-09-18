from __future__ import annotations

from laserprog_studio.tool_core.overlay.qt_layout import (
    _SECTIONED_TOOLBAR_BUTTON_HEIGHT,
    _SECTIONED_TOOLBAR_MARGIN_Y,
    _SECTIONED_TOOLBAR_PILL_HEIGHT,
    _SECTIONED_TOOLBAR_SECTION_PAD_Y,
    _SECTIONED_TOOLBAR_SECTION_TITLE_GAP,
    _SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT,
    sectioned_toolbar_shell_height_px,
)


def test_sectioned_toolbar_shell_height_is_derived_from_real_row_geometry() -> None:
    section_content = (
        _SECTIONED_TOOLBAR_SECTION_PAD_Y * 2
        + _SECTIONED_TOOLBAR_SECTION_TITLE_HEIGHT
        + _SECTIONED_TOOLBAR_SECTION_TITLE_GAP
        + _SECTIONED_TOOLBAR_BUTTON_HEIGHT
    )

    assert sectioned_toolbar_shell_height_px() == _SECTIONED_TOOLBAR_MARGIN_Y * 2 + max(
        _SECTIONED_TOOLBAR_PILL_HEIGHT,
        section_content,
    )
    assert sectioned_toolbar_shell_height_px() >= section_content + _SECTIONED_TOOLBAR_MARGIN_Y * 2
