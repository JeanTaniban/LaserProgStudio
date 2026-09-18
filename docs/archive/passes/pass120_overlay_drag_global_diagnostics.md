# Pass120 — Overlay drag deep fix and diagnostics

## Problem

Movable Tool Core overlays could still jump or fight the pointer during drag.
The previous implementation used widget-local mouse coordinates while moving the
same widget. That creates a feedback loop: after each `move()`, the next local
mouse coordinate may be different even if the global cursor motion is smooth.

## Fix

The Qt overlay adapter now uses a single drag constraint:

1. store the global mouse position on press;
2. store the widget parent-position on press;
3. on move, compute `new_pos = start_widget_pos + (current_global - start_global)`;
4. update the widget and the core overlay spec to the same position;
5. do not use widget-local `mapToParent(pos)` during interactive moves.

The adapter also keeps the overlay as a plain child `Qt.Widget`, not a frameless
child window, and records drag diagnostics.

## Diagnostics

The diagnostic tool now has a **Drag diag** button. Reproduce an overlay drag,
then press the button. It writes:

`diagnostics/tool_core_overlay_drag.md`

The report includes pointer samples, widget/spec positions and flags for:

- geometry collapse;
- widget/spec divergence;
- teleport jumps.

## Production rule

Future tools must not implement their own draggable overlay logic. They should
use Tool Core overlays so the global-delta drag path and diagnostics stay shared.
