# v61 — Plan Tracer validation/history fixes

This patch fixes three Plan Tracer 2D regressions introduced around the Ajouter/Soustraire validation workflow.

## Validation buttons

The viewport Validation buttons are now refreshed by `_sync_reports()` whenever the sketch compiler creates or removes faces. A closed rectangle/circle/face therefore enables **Ajouter** and **Soustraire** immediately, without requiring a metric-overlay validation click or a later tool-mode switch.

## Editing a subtraction

Opening an old Plan Tracer subtraction now displays the stored intact target model while keeping the already-cut result in tool state for Cancel/restore. Reapplying **Soustraire** still uses the stored intact target, avoiding cumulative cuts. Pressing **Ajouter** while editing a subtraction restores the original target and adds the edited sketch as a separate green additive volume.

## Nouveau dessin on old Plan Tracer geometry

Choosing **Nouveau dessin** on an old Plan Tracer source now detaches the old editable-source metadata from the current visible part. The current geometry becomes the new base for future Ajouter/Soustraire operations, so a new subtraction does not resurrect and overwrite the older stored intact model.
