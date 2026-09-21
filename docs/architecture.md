# LaserProg Studio architecture

This document is the short architectural contract for contributors. The runtime
is now organized around composition over inheritance: `LaserProgStudioV18` is the Qt
composition root, while controllers, services and Creator tools own the real
behaviour.

## Current rule

`LaserProgStudioV18` wires objects together, builds the UI and forwards Qt
virtual events. It must not become the home of business logic.

Prefer this shape:

```python
window.context = AppContext.from_window(window)
window.action_controller = StudioActionController.create(window.context)
window.scene_controller = SceneController(window.context)
window.toolbar_controller = ToolbarController(window.context)
window.layout_controller = LayoutController(window.context)
```

## No new mixins

Avoid new inherited feature layers. New behaviour should normally use one of
these forms:

- an application controller for workflows and commands;
- a service for pure logic;
- a `CreatorTool` runtime for user tools;
- a declarative `ToolSpec` / `ToolbarItemSpec` pair for integration metadata;
- a UI widget/panel class for Qt layout code.

## `AppContext`

`AppContext` exposes the stable state and service boundary used by controllers:
selection, transform, tools, preview, layout, render and clipboard state. New
controllers should receive an `AppContext` instead of assuming that every method
and attribute exists on the concrete `QMainWindow`.

Controller layers may call `context.owner` only when no focused service exists
yet. Those calls should be visible and reduced over time.

## Runtime composition areas

- `StudioActionController` owns undo/redo, clipboard actions and scene editing.
- `ConfigurableToolbarController` owns the dynamic top-toolbar workflow.
- `LayoutController` owns right-inspector and Light UI restoration.
- `ExportController` and `RenderOutputController` own 3MF/engraving exports and
  final render output.
- `PreviewController` and `ToolPreviewController` own preview sessions and route
  preview generation to focused fabrication/modifier services.
- `ToolLifecycleController` owns tool button synchronization, tool open/close,
  apply/cancel and preview-change confirmation.
- `BooleanController` owns boolean mesh commands.
- `ToolPanelFactory` and the `ToolPanelSpec` catalog own right-inspector panel
  construction.
- `TextureProjectionController` owns non-gizmo TEX workflows.
- `TextureGizmoController` delegates TEX move/rotate behaviour to target,
  live-update, event, render and drag services.
- `PlanarToolController` owns shared locked-plane tool lifecycle, preview,
  picking, reporting and snap services.

## Built-in tools

All shipped tools use explicit `CreatorTool` runtimes through
`CreatorStudioToolAdapter`. The tool registry must not use anonymous hook-only
entries for built-in tools.

New tool code should import from `laserprog_studio.tool_api` domains and should
not reach into `tool_core`, Qt, PyVista, VTK, `application`, `rendering`, or the
main window. When a built-in tool needs a lower-level capability, add or improve
the public API instead of importing private internals.

## Plan 2D and texture projection

Plan-like tools should go through `tool_api.plan2d`. Aggregate modules such as
`tool_api.planar_drawing`, `tool_api.dimensions` and `tool_api.metrics` are
stable alias imports; new code should prefer the structured `plan2d` subdomains.

Texture projection geometry is split into focused modules for types, vector
helpers, face/anchor calculations, UV generation, decal construction and
high-level apply/clear operations. New geometry code should import those focused
modules directly.

## Guardrails

Before a destructive architecture pass, run:

```bat
py -3.12 scripts\quality_gate.py
```

For full validation in a development environment, run:

```bat
py -3.12 scripts\quality_gate.py --with-tests --pytest-args -q
```

The gate blocks large runtime files, `*Mixin` classes or aliases, retired source
wording, built-in hook tools, direct tool-core imports from built-in tools, and
Python cache artifacts in the product tree.

## Shared geometry integrity contract

Geometry-producing tools must not implement their own generic mesh-validity stack.

The project uses one shared, versioned geometry-integrity foundation. A tool declares
the geometric role of its outputs and the kind of mutation it performs; common
runtime services own structural audit, component analysis, Manifold certification,
optional conservative repair, certification fingerprints and final commit gates.

The architectural rules are:

- tools own geometry-generation or geometry-transformation business logic;
- common integrity rules are exposed through the public `tool_api.geometry` boundary;
- `UNKNOWN`, `SOLID`, `SOLID_SET`, `SURFACE`, `VISUAL_PROXY` and helper outputs
  are distinct contracts and must not be conflated;
- persistent solid outputs are checked by a shared Solid Commit Gate rather than by
  ad-hoc per-tool validators;
- Boolean operands are certified through the same common profile regardless of which
  tool created them;
- measurement/render helpers must not be embedded as fake solid vertices or faces;
- coordinate welding is a repair/compatibility strategy, not the universal definition
  of manifoldness;
- tool-specific preflight remains allowed for domain constraints, but generic mesh
  integrity must stay centralized;
- scene assemblies/groups stay scene-level concepts and must not be represented as
  concatenated pseudo-solid WorkMeshes;
- geometry validation is differential through a GeometryChangeSet: only added or
  replaced geometry is audited at commit time;
- Boolean preparation must try the source representation first and stop when it is
  already kernel-compatible and semantically correct;
- orientation repair is a fallback and must preserve nested cavity-shell semantics.

See `docs/CDC_MISSION_GEOMETRY_INTEGRITY_FOUNDATION.md` for the detailed target
architecture, migration plan and validation criteria.

## Project persistence lifecycle

Project persistence must serialize an explicit persistence model, not a generic
deep copy of the live application state.

Architectural rules:

- technical undo/redo, previews, render caches, drag state, clipboard state and
  rebuildable visual proxies are transient and must never enter a project save;
- recovery autosave contains the current committed project state only and does
  not retain the full semantic restore history;
- persistent restore history is distinct from Ctrl+Z and is bounded by a
  retention policy;
- scene/history manifests reference content-addressed geometry blobs rather than
  storing full duplicate mesh payloads for every restore point;
- every full save performs mark-and-sweep over blobs referenced by current
  scenes, retained restore history and pinned checkpoints;
- deleting a scene or pruning the last history reference to a mesh removes its
  unshared geometry blob from the next saved archive;
- save diagnostics must attribute cost to snapshot capture, mesh encoding,
  compression and archive writing;
- mesh payloads are compressed once; nested compression is not a persistence
  contract;
- project writes remain atomic.

The target service is `ProjectPersistenceService`, with explicit `FULL_SAVE` and
`RECOVERY_SAVE` modes. See
`docs/CDC_MISSION_GEOMETRY_INTEGRITY_FOUNDATION.md` for the measured retention
evidence and detailed migration plan.
