# LaserProg v89 — Plan Tracer Pattern Presets

This release improves the Plan Tracer 2D Pattern viewport editor.

## Changes

- Replaces previous/next pattern arrows with a direct enum dropdown.
- Adds named user presets stored in `settings/plan_trace_2d_pattern_presets.json`.
- Presets capture the pattern kind plus pitch, wall, margin, keep-form, rotation,
  ratio, random seed, and X/Y offsets.
- Saving an existing name updates that preset.
- Saved presets can be loaded or deleted from the same overlay.
- Manual changes mark the current configuration as `Custom / modified`.
- Adds real `select` support to the generic Tool Core Qt overlay renderer.

The runtime package and Python pins from v88 are unchanged.
