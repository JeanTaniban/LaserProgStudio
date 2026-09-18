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
