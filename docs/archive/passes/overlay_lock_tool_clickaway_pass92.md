# Pass 92 — Light UI scale lock and +Tools click-away

## Light UI overlay

- Put the scale ratio lock button inside a permanently reserved fixed-width slot.
- Replaced the text lock button with a drawn vector lock/unlock icon so rendering does not depend on emoji fonts.
- Kept the lock visible only in Scale mode while preserving the row geometry in Position/Rotation/Scale.
- Added dedicated styles for the lock slot, hover state, checked state, and disabled state.

## +Tools palette

- Added a Qt application event filter dedicated to the toolbar palette.
- Clicking outside the palette now closes it.
- Clicking the `+ Tools` button itself is excluded from the click-away path so the existing toggle behaviour remains stable.
- The event filter is removed when the palette closes or is destroyed.

## Validation

- `python -m pytest -q`
- Result: 381 passed, 3 skipped.
