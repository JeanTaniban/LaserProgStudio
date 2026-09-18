# Window refactor pass 15 — state bridge, lifecycle split, renderer facade

This pass continues the extension-oriented refactor without adding new business tools.

## Goals

- Keep the legacy controller code working while making the structured state objects useful for future tools.
- Reduce `ToolLifecycleMixin` by moving layout restoration and selection policy into dedicated mixins.
- Add a small renderer facade so future tools/modifiers do not have to call PyVista/VTK directly.

## Main changes

### State bridge

New module:

- `src/laserprog_studio/controllers/state_bridge.py`

`StateBridgeMixin` exposes compatibility properties for legacy names such as:

- `selected_indices`
- `active_index`
- `active_tool`
- `transform_mode`
- `actors_by_index`
- `polydata_by_index`
- `_copy_buffer_meshes`

Assignments to these legacy names now update the corresponding state dataclasses. This keeps existing mixins functional while making `AppContext` reliable for new extension code.

### Tool lifecycle split

New modules:

- `src/laserprog_studio/controllers/tool_selection_policy.py`
- `src/laserprog_studio/controllers/layout_restore.py`

`ToolLifecycleMixin` keeps the high-level open/close/apply/cancel workflow, while:

- `ToolSelectionPolicyMixin` owns registry-driven selection checks.
- `LayoutRestoreMixin` owns the inspector/light-ui restoration logic around tools.

This should reduce the risk that future tools add ad-hoc special cases inside `open_tool()`.

### Renderer facade

New module:

- `src/laserprog_studio/rendering/scene_renderer.py`

`SceneRenderer` is a thin bridge around the current window/plotter. It currently delegates to existing methods, but exposes a future-facing contract:

- `render()`
- `rebuild_scene()`
- `refresh_selection_style()`
- `refresh_transform_gizmo()`
- `clear_tool_overlays()`
- `set_display_mode()`

This prepares future display modes, material preview, texture projection and interactive manipulators.

## Tests

Added/updated tests cover:

- state bridge synchronization,
- split lifecycle responsibilities,
- renderer facade behavior without Qt/PyVista,
- updated static refactor guards.

Validation commands:

```bash
python -m compileall -q src scripts tests
python scripts/verify_refactor_structure.py
python -m unittest discover -s tests -v
```
