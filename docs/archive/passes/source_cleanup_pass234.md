# Source cleanup pass 234 — controller layer decontamination

## Goal

Remove the remaining controller `*Mixin` classes, keep the Qt main window stable,
and make the quality gate prevent mixin debt from returning.

## Changes

- Renamed the controller stack to explicit `*Layer` classes.
- Renamed the composite from `StudioControllersMixin` to `StudioControllers`.
- Updated `window.py` bridge methods to target `StudioControllers` directly.
- Replaced the old modifier adapter name with `ToolHostedModifier`.
- Renamed engraving color-role helpers away from legacy wording.
- Added an architecture-health threshold to `scripts/quality_gate.py`:
  `--max-mixins 0 --max-large-files 0`.
- Added `tests/test_pass234_controller_layers_and_modifier_runtime.py`.

## Validation

- `python scripts/quality_gate.py` passes.
- `pytest -q` passes.
- Runtime audit reports 0 `*Mixin` classes and 0 large files >= 800 lines.
