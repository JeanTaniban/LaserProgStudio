# Source cleanup pass 12 — Creator context activation fix

This pass fixes the first runtime issue found after migrating Primitives and Box
Generator to the Creator API.

## Problem

The declarative Creator panel could display:

```text
No creator tool context is active.
```

The migrated tool did open, but the right-side panel could not see the active
`ToolContext`.

Root cause: `AppContext` is a slotted dataclass. `CreatorStudioToolAdapter` tried
to attach `tool_context` dynamically, but that assignment was rejected silently.
The panel host then looked for `context.tool_context` / `owner.tool_context` and
received `None`.

## Fix

- Added an explicit `tool_context` slot to `AppContext`.
- Made `CreatorStudioToolAdapter.tool_context(...)` always publish the active
  context to both:
  - `context.tool_context`
  - `context.owner.tool_context`
- Hardened `ToolLifecycleController.open_tool(...)` so re-opening an already
  active Creator tool can rebuild a missing inspector context.

## Tests

Added `tests/test_pass152_creator_panel_context_activation.py` to lock the
regression:

- `AppContext` exposes a real `tool_context` field.
- Creator runtime publishes the same `ToolContext` to app context and owner.
- Opening a Creator tool populates `ctx.inspector.panel`, so the declarative
  panel has something to render.

No public API version bump was needed: this is a runtime wiring bugfix for the
existing `0.13.0` API surface.
