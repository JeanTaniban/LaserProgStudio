# Pass 328 — Editable mesh hover feedback

## Goal

Make reopenable Mechanical Motion and Folding results visibly selectable before the user clicks them, matching Plan Tracer 2D's yellow-edge startup feedback.

## Implementation

- Added `EditableMeshHoverPreview`, a shared owner-scoped projected drawing helper.
- Uses a low-opacity yellow triangle-mesh overlay with a five-pixel yellow outline.
- Marks the primitive as projected-only and explicitly suppresses selection actors.
- Caches the hovered group and performs no mutation while the pointer remains on the same group.
- Mechanical Motion resolves hover with the same face raycast used for startup clicking and outlines the complete assembly.
- Folding performs a cheap metadata check via `has_folding_source()` and only highlights reopenable Folding results.
- Hover is removed on miss, camera movement, source selection, cancellation, restart, and tool close.

## Validation

- 73 targeted Mechanical Motion and Folding tests pass.
- New tests verify complete MEC-group highlighting, yellow style, non-selectability, no repeated rebuild, miss cleanup, Folding-only eligibility, and cleanup when an existing fold is reopened.
- The complete quality gate passes.
