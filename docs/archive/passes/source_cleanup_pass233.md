# Source cleanup pass 233 — UI/controller legacy reduction

## Scope

- Moved the tool-inspector splitter snapshot out of transient window fields and into `UiLayoutState.inspector`.
- Renamed the application controller base from `LegacyWindowController` to `WindowController`.
- Renamed the owner-delegating controller module so runtime code no longer imports `application.legacy_bridge`.
- Renamed the UI and Laser 3MF composition classes from `*Mixin` to `*Layer` where they are product layers rather than reusable mixins.

## Guardrails

- `scripts/quality_gate.py` passes.
- Full pytest suite passes: 856 passed, 3 skipped.
- Built-in tool migration audit remains clean: 19 runtimes, 0 hook-based built-ins.

## Remaining debt

- Controller facades still use several `*Mixin` names.
- Scene tab compatibility naming remains visible around the hidden synchronization tab bar.
- A later documentation pass should prune old compatibility wording from archived reports or keep it strictly under `docs/archive/`.
