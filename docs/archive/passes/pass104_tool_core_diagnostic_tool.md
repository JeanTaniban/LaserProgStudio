# Pass104 - Tool Core Diagnostic probe

This pass keeps production tools unchanged and improves the shared `tool_core` foundation with a diagnostic GUI probe.

## Added layers

- `tool_core/input/router.py`: normalized event dispatch with centralized drag begin/end lifecycle.
- `tool_core/diagnostic/runner.py`: deterministic scenarios that exercise overlay, gizmos, snap, preview, face solving, selection, commands and routed input without Qt/PyVista dependencies.

## Added tool

A fake tool is registered in the normal tool registries:

- tool id: `tool_core_diagnostic`
- toolbar item: `tool:core_diagnostic`
- toolbar code: `DBG`
- panel: `panel_tool_core_diagnostic`

It appears in the configurable top toolbar by default and opens a right-inspector panel with precise diagnostic actions:

- Run all
- Overlay
- Gizmos
- Drag
- Snap
- Faces
- Events
- Reset

## Design rule

The diagnostic tool must not migrate or modify production tools. It only validates that the shared layers are usable before Plan tracer, Transform and Extrude are recoded on top of them.
