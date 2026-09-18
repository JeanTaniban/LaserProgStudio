# Pass45 - Box live metrics from inspector values

## Goal

The Box tool report must update as soon as the user changes the box dimensions.
The calculated values include external volume, internal volume, useful internal dimensions, and board sheet area.

## Changes

- Box tool dimension spin boxes now use keyboard tracking, because recalculating metrics is cheap.
- The report also refreshes on `editingFinished` for robust keyboard entry.
- Generated Box preview boards are tagged with lightweight metadata linking the six boards to the same box group.
- When a generated box is selected and resized from the transform inspector, the Box report can infer the current outer bounds from the selected box group and refresh the metrics.
- The metadata survives `copy.deepcopy`, so it remains available through preview/apply/history operations.

## Notes

The report header says `Mesures depuis la boîte sélectionnée / inspecteur` when it uses the selected generated box instead of the raw Box tool spin-box values.
