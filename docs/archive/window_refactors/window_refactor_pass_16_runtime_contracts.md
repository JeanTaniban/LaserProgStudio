# Window refactor pass 16 - runtime extension contracts

This pass continues the extension-oriented refactor without adding new user-facing geometry features.

## What changed

- Added `tooling/tool.py` with a `StudioTool` protocol and `LegacyToolAdapter`.
- The tool registry now exposes runtime tool objects through `get_studio_tool()` and `iter_studio_tools()`.
- `ToolLifecycleMixin` starts using runtime tool objects for open/close hooks while preserving existing tool behavior.
- Added `modifiers/modifier.py` with a `MeshModifier` protocol and `LegacyModifierAdapter`.
- The modifier registry now exposes runtime modifier objects through `get_mesh_modifier()` and `iter_mesh_modifiers()`.
- Moved `update_preview_state()` into `PreviewControllerMixin` so preview UI state is owned by the preview controller, not by the tool lifecycle controller.
- Extended `ParameterPanel` with `set_values()` and `reset()` so generated parameter panels can be reused by future tools.

## Why

The goal is to let future features such as Simplify, Extrude Down, Hollow, Text Relief and Texture Projection become standalone tool/modifier classes instead of spreading new cases across `scene.py`, `tool_lifecycle.py`, and `tool_panels.py`.

Existing tools still use legacy controller hooks. New tools should target the runtime contracts first.
