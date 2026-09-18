# Pass 31 — Vent generator adaptive UI

The vent generator panel now hides settings that are not used by the active vent mode.

- Round vents show the surface control and hide rectangular width/height, compact wall fusion and wall-only output.
- Rectangular vents show width/height, compact wall fusion and wall-only output, while the surface value is computed internally.
- The flare factor is shown only when a flare side is selected.
- Numeric controls use committed editing for vent parameters, and automatic synchronization no longer writes into a spinbox while the user is actively editing it.

This prevents the surface spinbox from feeling frozen when the tool refreshes previews/reports.
