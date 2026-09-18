# Window Refactor Pass 6 - Extension Architecture

This pass prepares LaserProg Studio for future tools/modifiers without adding the requested features yet.

## What changed

- Added a collision-safe tool extension package: `laserprog_studio/tooling/`.
  - It is intentionally named `tooling`, not `tools`, because `laser_toolbox` still imports legacy modules as `from tools...`.
  - A first implementation using `laserprog_studio/tools/` was rejected because it shadowed that legacy package in lightweight tests.
- Added a `ToolSpec` registry for existing tools/modifiers.
- Extracted tool open/close/preview lifecycle from `controllers/scene.py` into `controllers/tool_lifecycle.py`.
- Added a `ModifierSpec` registry. Split Plane is now described as the first registered modifier.
- Added a generic `ParameterSpec` model for future auto-generated parameter panels.
- Added structured state dataclasses for selection, transform, tool, layout, render and clipboard state.
- Added display mode descriptors for future `wireframe`, `solid`, and `material` rendering modes.
- Added tests that protect the new extension structure.

## Why it matters

Future work such as Simplify, Text Relief, Extrude Down, Hollow, texture projection and richer primitive generation should not be implemented by adding more `if tool_id == ...` branches in `scene.py`.

The target direction is now:

```text
new tool/modifier
  -> declare ToolSpec / ModifierSpec
  -> declare ParameterSpec entries
  -> implement geometry operation in a testable module
  -> plug UI panel generation or custom panel later
```

## Current status

This is still a compatibility-first refactor. Existing Qt widgets and mixins still exist, and legacy attributes on the main window are preserved. The new dataclasses are introduced as migration anchors rather than a hard rewrite.

## Regression guards

The verification script now checks:

- `scene.py` stays smaller after lifecycle extraction.
- `ToolLifecycleMixin` owns the tool lifecycle methods.
- the tool registry contains all current tool IDs.
- runtime state initializes structured state objects.
- the old `tools` top-level import path remains unshadowed by avoiding a `laserprog_studio/tools` package.
