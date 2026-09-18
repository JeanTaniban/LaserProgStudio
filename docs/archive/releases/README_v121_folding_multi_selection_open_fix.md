# LaserProg v121 — Folding multi-selection launch fix

## User-visible defect

Selecting several meshes and then opening Folding loaded only one mesh. The
multi-mesh deformation and persistence code from v120 was present and valid,
but it never received the complete selection in the real application.

## Root cause

The Folding `ToolSpec` used `selection_policy="none"` so the tool could still
open without an initial selection. However, it did not set
`allow_multi_selection=True`.

Before calling `FoldingCreatorTool.on_open()`, the shared lifecycle policy
normalizes the host selection. For tools that do not explicitly allow a
multi-selection, this policy keeps only the last selected index. Folding then
correctly read the selection it was given, but that selection already contained
one object.

## Correction

The Folding registry entry now explicitly combines both required behaviours:

- `selection_policy="none"` and `open_without_initial_selection=True` keep the
  interactive yellow-hover selection workflow available;
- `allow_multi_selection=True` preserves every mesh selected before the tool is
  opened.

No output fusion was introduced. All selected meshes still share one folding
plane, curve and motion during the operation, while preview, Apply, Cancel,
Undo and later re-editing keep each source object distinct.

## Regression coverage

A new regression test verifies the registry contract and the shared lifecycle
branch that must not truncate selections for opted-in tools. Existing tests
continue to verify that two selected meshes produce two separate committed
objects and that selecting one applied member reopens the complete group.

Validation:

- 41 Folding regression tests pass;
- the strict quality gate passes;
- all 20 Creator runtimes pass migration and product-quality audits.
