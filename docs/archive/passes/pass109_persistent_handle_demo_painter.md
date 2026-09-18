# Pass109 — Persistent Handle Demo Painter

## Problem

The focused handle demo still felt visually unstable: when a grabbable point entered hover/grab state, the viewport overlay disappeared and reappeared for a frame.

Root cause: the live diagnostic painter called `clear_tool_core_diag_scene()` at the start of every `render_context()` call. Hover/grab state changes therefore removed all diagnostic actors before rebuilding them.

## Fix

The painter is now persistent:

- actors are created once and stored in `_tool_core_diag_scene_state`;
- hover/grab updates mutate existing `PolyData` objects;
- stale groups are hidden with actor visibility instead of removed;
- guide rings, crosses and line batches are updated in place;
- text labels are static and are recreated only when their label signature changes;
- the diagnostic text report is no longer rewritten on every pointer move.

## Rules for production tools

- Do not clear an overlay scene during hover or drag.
- Do not remove/recreate actors to show a new handle state.
- Update point arrays/cell arrays in place when possible.
- Toggle visibility for temporary groups.
- Keep report/log UI updates out of high-frequency mouse move paths.
