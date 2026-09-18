# Light overlay threshold and snap defaults

Changes in this build:

- Light Transform overlay no longer appears when the inspector is only narrowed.
- Light mode now depends on the right splitter pane being truly collapsed.
- Removed the "Light transform" text label from the compact overlay.
- When no part is selected, Transform values are reset to 0 in both inspector and overlay.
- Default snap settings:
  - Grid snap: off
  - Smart snap: on
  - Rotation snap: on

The diagnostic logs still print splitter sizes and overlay visibility so panel state issues can be checked quickly.
