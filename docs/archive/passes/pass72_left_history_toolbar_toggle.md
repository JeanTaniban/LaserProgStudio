# Pass 72 — Left panel parts list, default history and toolbar toggle

Changes:
- The left Parts list reserves enough vertical space for roughly ten visible rows before the left pane scrolls.
- The default transform mode is now Translate (`T`) at startup.
- The right Tool space no longer appears empty when no tool is active: it shows the current scene history summary and technical undo/redo counts.
- The `+ Tools` button is now a real non-modal toggle. Clicking it again closes the palette without the close/reopen race caused by `Qt.Popup`.
- The toolbar palette hint now follows the configured toolbar limit of 18 functions.

Validation:
- Added regression coverage in `tests/test_pass72_left_history_toolbar_toggle.py`.
- Full test suite: 342 passed, 3 skipped.
