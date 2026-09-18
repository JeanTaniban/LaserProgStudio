# Pass123 - Tool Creator API clarity continuation

Pass123 continues the public creator-tool API work started in Pass122.

## Added

- Lower-case inspector DSL helpers: `inspector.panel`, `inspector.section`, `inspector.float_field`, `inspector.button`, etc.
- Inspector contracts now accept lists as well as tuples and reject duplicate field ids early.
- `InspectorManager.update_values(...)` and `InspectorManager.describe(...)` for easier testing and diagnostics.
- `SnapTarget.ui_point(...)` and `tool_api.snap.ui_point(...)` for snap targets coming from GUI/overlay/gizmo elements.
- Smart snap cache-refresh controls: `rebuild_cache=True/False/None`.
- Smart snap exclusions: `exclude_ids=...`, useful while dragging selected actors.
- `SceneCacheSummary`, `SceneCache.summary()`, `set_snap_targets(...)`, `clear_snap_targets(...)` and `add_ui_point(...)`.
- Complete example: `examples/tool_creator/creator_api_demo_tool.py`.
- Tool Core Diagnostic button: **Creator API**.
- Creator API checklist: `docs/tool_creator/09_creator_api_checklist.md`.

## Validation

Full test suite: 505 passed, 3 skipped.
