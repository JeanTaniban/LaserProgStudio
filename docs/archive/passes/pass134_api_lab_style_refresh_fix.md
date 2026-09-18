# Pass134 — API Lab style and camera-refresh correction

This pass fixes the Creator API Lab interaction polish after the native style reintegration.

## Changes

- Restored the Pass120 point-style renderer contract for API Lab handles.
- Normalized the selected point color across all native point styles to the minimal dot yellow/orange highlight.
- Normalized selected line feedback to the same yellow/orange highlight through `tool_api.styles.SELECTED_HIGHLIGHT_COLOR`.
- Removed the midpoint gizmo shown on line/arc/polyline hover, selection and grab. Lines are selected and moved through their linework, not through a point-like grab handle.
- Empty API Lab presses no longer clear selection or rebuild visual geometry. This prevents camera drag refresh from happening at camera-drag start.
- Camera-sized guide refresh now recognizes API Lab handles and remains on the end-of-camera-move path.

## Validation

- Full test suite: 546 passed, 3 skipped.
- New tests cover selected highlight colors, selected line payloads, absence of line midpoint gizmos, empty-press no-refresh behavior and API Lab camera-guide refresh detection.
