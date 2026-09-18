# Source structure

This project is structured around a small Qt composition root, focused
application controllers, public Creator API domains and pure geometry/services.

## Runtime roots

- `src/laserprog_studio/window.py` defines the main Qt window class and composes
  controller layers.
- `src/laserprog_studio/runtime_state.py` creates shared application state,
  `AppContext` and long-lived controllers.
- `src/laserprog_studio/app.py`, `main.py` and `bootstrap.py` own startup and
  source-path configuration.

## Application layer

`src/laserprog_studio/application/` contains workflow controllers and services.
A controller may coordinate UI state, commands and services, but heavy geometry
or file-format logic should live in a domain package.

Important controller groups:

- action/history/clipboard/scene editing;
- layout and toolbar control;
- preview and render output;
- tool lifecycle and tool preview routing;
- texture projection and texture gizmo services;
- planar tool lifecycle, preview, picking, reporting and snap.

## Public tool API

`src/laserprog_studio/tool_api/` is the supported boundary for tool authors.
Built-in and external tools should prefer grouped domains:

- `tool_api.core`
- `tool_api.scene`
- `tool_api.visual`
- `tool_api.application`
- `tool_api.plan2d`
- `tool_api.workflow`
- `tool_api.diagnostics`

Older aggregate import paths are stable aliases only. New examples should use
the grouped domains so the API surface stays easy to review.

## Built-in tools

`src/laserprog_studio/tooling/` contains built-in `CreatorTool` implementations.
Each shipped tool has an explicit runtime through `CreatorStudioToolAdapter`; the
registry is checked by `scripts/audit_tool_migration.py --strict`.

Tool-specific service packages, such as `tooling/plan_trace_2d/`, should keep
large interactions out of the tool shell. The shell should route events and own
manifest/panel declarations, while focused services own drawing, snapping,
metrics, overlays and history.

## Geometry and fabrication

- `geometry_ops/` contains mesh/image/texture operations.
- `fabrication/` contains pure fabrication backends such as box generation,
  lay-flat processing and joints.
- `planar_tools/` contains locked-plane shared models, constraints, validation
  and path-generation helpers.
- `engraving/` contains engraving metadata and export-oriented helpers.

Keep these packages independent of Qt widgets whenever possible.

## Rendering, project and state

- `rendering/` owns display materials, scene rendering helpers and final render
  dialogs.
- `project/` owns project documents, autosave/history and runtime bridge state.
- `state/` owns focused dataclasses used by controllers.

## Documentation and archive policy

Current docs describe the active architecture only. Pass-by-pass migration notes
belong under `docs/archive/`. Do not add new migration diaries to the current
root documentation unless they define a current contract.
