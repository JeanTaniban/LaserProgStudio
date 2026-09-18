# Pass 13 — Inspector Resize Performance

The right inspector felt much slower than the left panel while dragging its
splitter handle.

Root cause: `QSplitter.splitterMoved` fires continuously during dragging. The
right panel path was calling the full compact transform overlay sync on every
pixel, including spinbox refreshes and overlay geometry work. The left panel did
not pay that cost.

Fixes:

- `splitterMoved` now schedules a debounced overlay/layout sync instead of doing
  all work immediately.
- compact transform spinboxes are refreshed only when the overlay is visible or
  its visibility changes, not for every right-panel resize while the inspector is
  open.
- overlay positioning caches its geometry signature and no longer calls
  `adjustSize()` during resize churn.
- static tests and the refactor verifier guard this path so the heavy per-pixel
  refresh does not come back.
