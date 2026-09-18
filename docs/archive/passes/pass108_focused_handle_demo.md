# Pass108 - Focused handle/gizmo diagnostic demo

The Tool Core Diagnostic panel is now focused on the primitives needed before migrating production tools to `tool_core`.

## Demo contents

The viewport demo contains five size rows, from XS to XL. Each row draws:

- one fixed point;
- one grabbable point;
- one standalone line;
- one line between two fixed points;
- one line between two grabbable points;
- one circle with a fixed center and a grabbable radius point.

## Handle states

Grabbable handles are intentionally different from fixed points:

- fixed points use neutral grey handles;
- grabbable points use blue handles;
- hover uses a brighter cyan state;
- grabbed uses an orange state;
- grabbable handles also receive guide rings and cross marks, so they are distinguishable by shape as well as color.

## Interaction

When the Tool Core Diagnostic tool is active, the Qt viewport event filter forwards pointer events to the diagnostic controller:

- mouse move updates hover state;
- left press on a grabbable handle enters grabbed state;
- mouse drag updates only the active handle position and dependent previews;
- release exits grabbed state and returns to hover if the cursor is still close.

## Performance rules preserved

The focused demo still goes through the shared managers:

- `GizmoManager` for handle state;
- `PreviewManager` for lines and circles;
- `OverlayManager` for the demo control panel;
- batched viewport rendering by kind/state/size;
- no production tool is migrated yet.

The diagnostic panel intentionally removes broad showcase buttons from the main UI. Older deterministic scenarios still exist in code for tests and comparison, but the visible tool is now the focused handle lab.
