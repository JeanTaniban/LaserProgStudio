# Pass 179 - External Creator API authoring clarity

Goal: make the native Creator UI behaviour understandable for an external tool author and prevent the optimized interaction/rendering path from becoming an optional convention.

## Decisions

- Normal external tools subclass `CreatorTool` and are registered with `register_tool(..., runtime=create_tool(), ...)`.
- `register_tool(...)` wraps `CreatorTool` runtimes in `CreatorStudioToolAdapter`.
- `CreatorStudioToolAdapter` runs the native Creator UI runtime before `on_event`.
- Tool authors declare semantic actors, styles, previews and official gizmos.
- Tool authors do not implement hover/select/grab, empty-click selection clearing, drag fast-path rendering, camera-axis orientation or field-of-view scaling.
- Low-level functions such as `hover_select_grab_actors(...)`, `handle_native_creator_ui_event(...)`, `refresh_creator_ui_drag(...)` and `refresh_creator_ui_camera(...)` remain available for diagnostics/tests/adapters, not for normal production tools.

## Documentation updates

- Added `docs/tool_creator/00_external_tool_quickstart.md` as the starting point for external tool authors.
- Rewrote `docs/tool_creator/01_create_a_tool.md` around `CreatorTool` + `register_tool`.
- Rewrote `docs/tool_creator/03_actors_selection_grab.md` so actor interaction is described as native and automatic.
- Clarified `docs/tool_creator/06_overlay_preview_gizmos.md`, `09_creator_api_checklist.md`, `12_native_interaction_styles.md` and `16_gizmo_catalog_tool.md`.
- Updated `docs/tool_creator/README.md` so the minimal example no longer teaches manual interaction calls.

## Example update

`examples/tool_creator/minimal_point_line_tool.py` now subclasses `CreatorTool`, requests official point/line styles and contains no manual interaction runtime calls.

## Regression guard

Added `tests/test_pass179_external_creator_api_clarity.py` to verify:

- the quickstart teaches `CreatorTool` + `register_tool`;
- the README minimal shape does not teach manual interaction/refresh helpers;
- the minimal example is a `CreatorTool` and does not call the low-level runtime;
- `CreatorStudioToolAdapter` invokes native interaction before tool `on_event`;
- generated direction markdown preserves the authoring boundary.
