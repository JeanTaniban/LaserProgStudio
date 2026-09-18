# Pass48 — Translation drag performance when overlapping objects in Light UI

## Problem
In Light UI, translating a selected object became very slow when the object approached or crossed other objects. Pass47 throttled renders and inspector updates, but the drag path still did two expensive things exactly during contact/snap zones:

- it rewrote the selected mesh polydata points on every mouse event;
- it scanned many target edge/feature snap coordinates on every mouse event;
- the snap status label could be repainted repeatedly with the same text.

## Fix

### Actor-position preview during live translation
During a translation drag, selected actors are now moved with `actor.SetPosition(...)` for the live preview. The real mesh vertices and PyVista polydata are updated only once on mouse release.

This avoids continuous VTK geometry/bounds invalidation while the object overlaps other actors.

### Indexed smart snap cache
The translation smart snap cache now builds sorted per-axis indices. Live dragging uses binary search to inspect only snap candidates inside the active tolerance instead of comparing every moving feature to every target feature.

### Snap label repaint guard
The snap status UI now ignores repeated identical labels, avoiding status-bar repaint spam while the same snap candidate remains active.

## Validation

- `279 passed, 3 skipped`
- Added regression tests in `tests/test_transform_translation_overlap_perf_pass48.py`.
