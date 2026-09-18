# Plan Tracer 2D validation actions — v59

## User-facing changes

Plan Tracer 2D now exposes a dedicated **Validation** section in its viewport overlay.

- **Ajouter** validates the current sketch exactly like the existing additive Apply path: it creates a green editable Plan Tracer board using the laser-board thickness preference, then closes the tool.
- **Soustraire** validates the current sketch as a through-cut: the cutter is expanded through the full depth of every target model touched by the drawing footprint. It does not use the board thickness preference for the boolean cutter depth.

When a user clicks an existing Plan Tracer source while opening the tool, the desktop UI now asks whether to **Éditer** the existing source or start a **Nouveau dessin** on that same surface. Headless/test contexts keep the historical default: edit.

## Non-destructive subtraction contract

A Plan Tracer subtraction result stores an editable source with kind `plan_trace_2d_subtract`.

The source payload keeps:

- the original sketch,
- the drawing plane,
- the through-cut depth metadata,
- a green validation marker colour (`#8BC34A`),
- a serialized copy of the intact target mesh.

When reopened and reapplied, the subtraction is recomputed from the stored intact target mesh, not from the already-cut visible result. This avoids cumulative/double subtraction when the user edits the sketch several times.

## Current display limitation

`WorkMesh` still has one object-wide colour. The patch preserves the target model colour and stores the green validation marker in metadata instead of recolouring the whole object. A future per-face/cell material layer can use `plan_trace_validation_marker_color` to paint only the cut region.
