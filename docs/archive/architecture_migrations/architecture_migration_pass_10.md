# Architecture Migration Pass 10 — Texture Gizmo Controller

## Goal

Continue the migration away from inherited `MainWindow` mixins by extracting the
TEX rotation/move gizmo slice from `controllers/texture_projection_tool.py`.
This pass deliberately avoids changing the low-level VTK observer behaviour; it
moves ownership first, then future passes can split the implementation further.

## What changed

- Added `application/texture_gizmo_controller.py`.
- Added `state/texture_gizmo_state.py` to centralise the TEX gizmo runtime
  defaults that were previously scattered in `runtime_state.py`.
- `runtime_state.initialize_runtime_state()` now composes
  `TextureGizmoController` explicitly.
- `controllers/texture_projection_tool.py` is now a thin compatibility facade for
  both texture projection workflows and texture gizmo workflows.
- Qt objects used by the gizmo event path are resolved lazily through helper
  functions instead of importing the old `_window_deps` bundle into the new
  controller.

## Current split

- `TextureProjectionController` owns file/asset/anchor/preview/apply workflows.
- `TextureGizmoController` owns the TEX rotation/move gizmo interaction, live UV
  updates, drag polling and VTK/Qt event fallback paths.
- `TextureGizmoState` documents and applies the legacy runtime fields needed by
  existing code until the controller can store them internally.

## Remaining work

`TextureGizmoController` is intentionally still large because this pass was a
safe ownership migration, not a full rewrite. The next texture pass should split
it into smaller services, for example:

- target resolution and pick math;
- live texture UV update;
- Qt/VTK drag event routing;
- gizmo mesh rendering.

`geometry_ops/texture_projection.py` is also still a large candidate for a later
pure-geometry split.
