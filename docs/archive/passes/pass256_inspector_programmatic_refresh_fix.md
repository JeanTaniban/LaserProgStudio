# Pass 256 — Programmatic inspector refresh

## Diagnostic conclusion

The Plan Tracer selected-length diagnostics proved that edge selection and path
measurement were correct. The headless `InspectorManager` stored values such as
`694.3 mm · contiguous` and `780.4 mm · closed`, but the Qt label stayed at its
initial em dash because programmatic read-only updates had no presentation
notification path.

## Repair

- `InspectorManager` now exposes weak presentation change subscriptions.
- Layout, value and field-state changes notify presentation listeners.
- Business `on_change` callbacks remain separate and are not invoked for
  computed read-only display fields.
- `LiveDeclarativeToolPanelWidget` subscribes to its current manager and queues a
  coalesced zero-delay Qt refresh only while visible.
- No permanent polling timer was added.
- Identical values do not emit redundant refreshes.

This repairs Plan Tracer's `Selected length` field and all other declarative
read-only reports that are updated programmatically.
