# LaserProg Studio documentation

This directory now keeps only the documentation that is useful for current development at the top level.

## Current documentation

- `architecture.md` — current application structure and controller boundaries.
- `source_structure.md` — practical map of the current source folders.
- `adding_new_tools.md` — practical notes for adding tools.
- `how_to_add_a_tool.md` — tool creation walkthrough.
- `how_to_add_a_modifier.md` — modifier creation walkthrough.
- `tool_creator/` — creator API reference and examples.
- `laser_info.txt` — laser/material notes.

## Historical documentation

Historical pass notes, migration logs, fixes and one-off implementation reports are archived under `archive/`:

- `archive/architecture_migrations/`
- `archive/window_refactors/`
- `archive/passes/`
- `archive/fixes_and_updates/`
- `archive/notes/`
- `archive/releases/` — release-specific README notes moved out of the project root.

Keep new top-level files for durable documentation only. Put temporary pass notes in `archive/` once the related code has landed.

- `performance_transform_gizmo_visibility_v17.md`: native Transform gizmo visibility fix, structured diagnostics, fallback rendering and usability rules.
