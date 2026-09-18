# Toolbar transform multi-press live selection — v73

## Problem

The transform-cycle shortcut waited for the multi-press timeout before selecting the final transform tool. With a comfortable timeout this made Tab cycling feel slow, and the preferences UI prevented fast values such as `0.10 s`.

## Fix

- The multi-press window minimum is now `0.10 s` in:
  - runtime shortcut handling;
  - project-preference coercion;
  - the Preferences dialog spinbox.
- Transform cycling now applies the transform mode as the user taps:
  - first tap -> Translate immediately on release;
  - second tap -> Rotate immediately on the second physical press;
  - third tap -> Scale immediately on the third physical press;
  - further taps continue cycling Translate / Rotate / Scale.
- The multi-press timer now only closes the current sequence. It no longer delays the visible transform-mode change.
- Holding the transform-cycle key still switches to Neutral.

## Validation

- `python -m py_compile src/laserprog_studio/controllers/interaction.py src/laserprog_studio/services/project_preferences.py src/laserprog_studio/ui/preferences_dialog.py`
- `PYTHONPATH=src pytest -q tests/test_pass315_shortcuts_preferences.py`
