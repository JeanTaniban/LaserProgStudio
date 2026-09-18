# Value field click selection update

## Goal

All numeric/value fields are now faster to edit:

- single left click selects the full field text;
- double left click keeps the native text editing behavior.

This applies to the full inspector, tool panels, snapping settings, primitive/box/joint fields, and the light transform overlay.

## Implementation notes

The behavior is installed through the main window event filter on QAbstractSpinBox line edits and QLineEdit value fields.

The mouse press is not consumed. A zero-delay Qt timer runs selectAll() after Qt has handled focus and cursor placement, which avoids fighting the native widget behavior.

Mouse double-click is intentionally left untouched so the user can edit a smaller text fragment when needed.
