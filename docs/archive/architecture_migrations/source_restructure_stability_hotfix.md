# Source restructure stability hotfix

This version prioritizes the validated application behavior after the second restructuring pass introduced runtime regressions in the interactive layer.

## Changes

- Restored the validated interactive `window.py` implementation used before the aggressive Pass 2 split.
- Kept the Pass 2 source cleanup work for the toolbox and engraving generator modules.
- Set the floor grid default to enabled.

## Reason

The transform gizmos, live transform inspector edits, and copy/paste/duplicate workflows are core validated behavior. Future source splitting should be done one subsystem at a time with UI validation after each step.
