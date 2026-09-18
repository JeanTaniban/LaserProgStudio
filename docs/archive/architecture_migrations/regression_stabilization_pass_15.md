# Regression Stabilization Pass 15

This pass pauses the architecture migration to address regressions reported after Pass 14.

## Fixed regressions

### TEX file picker

`TextureProjectionController` is not a Qt widget. The migrated code was still passing the controller instance as the parent of `QFileDialog.getOpenFileName`, which can prevent the file picker from opening in PySide. The controller now passes the owning `QMainWindow` instead.

### Splitter drag while a tool is active

Dragging the left/right panes while a tool was active still ran the full Light UI synchronization and preference persistence path. This caused stutter and could make side panes snap toward minimum sizes.

Tool-time splitter drags now:

- mark the automatic tool inspector resize as overridden by the user;
- keep side panes interactive;
- avoid persisting Light UI state during the drag;
- avoid the expensive overlay synchronization path while tools are active.

### First Joint action latency

The first Joint operation can pay a one-time backend cost from importing and warming the manifold boolean engine. Opening the Joint tool now starts a daemon warmup thread that imports and lightly exercises the boolean backend before the first real joint is applied.

## Validation

- `181 passed, 3 skipped`
- `scripts/verify_refactor_structure.py` OK
- `scripts/audit_architecture_health.py` OK
