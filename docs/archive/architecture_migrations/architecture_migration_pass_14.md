# Architecture Migration Pass 14 — Planar interaction contracts

This pass prepares the next two tools without registering them yet:

- **Traceur de plan** (`plan_trace`)
- **Générateur d'évent** (`vent_generator`)

The goal is to keep cleaning the architecture while making the future tools easier to integrate.

## What changed

### Shared pointer projection

A new pure module was added:

```text
src/laserprog_studio/planar_tools/pointer.py
```

It defines:

```text
PlanarRay
PlanarPointerResult
intersect_ray_with_locked_plane(...)
snap_plane_point(...)
resolve_pointer_on_plane(...)
```

This gives future tools a deterministic contract for converting pointer input into a point on a locked drawing plane. The module has no Qt, VTK or PyVista dependency.

### Planar snap contract

`PlanarToolConfig` is now used by the pointer resolver. It supports:

- grid snap;
- smart U/V alignment against existing planar points;
- deterministic snapped and raw coordinates.

This prepares both ADD/MOD behavior for polygon and vent waypoints.

### Controller hooks without new mixins

`PlanarToolController` now handles the future lifecycle hooks:

```text
_initialize_plan_trace_tool
_initialize_vent_generator_tool
_clear_planar_tool_state
```

`ToolLifecycleController` can route missing legacy hook strings to controller-owned hooks before reporting them missing. This avoids adding a new `PlanarToolMixin` to `MainWindow`.

### Sparse panel indexes

The future tools reserve panel indexes 30 and 31. `ToolPanelFactory` now supports **sparse panel indexes** by inserting reserved placeholder widgets for unused slots.

This means future tools can keep stable panel indexes without requiring all previous indexes to be filled.

### Future panels prepared

Two placeholder panels were added but the tools remain blueprint-only:

```text
panel_plan_trace_tool
panel_vent_generator_tool
```

They prepare:

- ADD / MOD / SUPP / RST exclusive mode buttons;
- extrusion depth for the Traceur de plan;
- event section type, section area and wall thickness for the vent generator;
- report labels connected to the shared planar controller.

The tools are still not registered in the runtime registry. They are not visible as active toolbar tools yet.

## Why this is useful

The next implementation pass can focus on real interactions and previews instead of inventing contracts:

```text
Qt mouse position
    ↓
PlanarToolController.resolve_qt_pos_on_active_plane(...)
    ↓
PlanarPointerResult(raw + snapped)
    ↓
PlanarPolygonDraft / VentPathDraft
    ↓
preview mesh / final mesh
```

## Validation

Pass 14 adds tests for:

- ray-plane projection;
- grid/smart planar snapping;
- controller-owned future lifecycle hooks;
- sparse panel indexes;
- blueprint tools remaining unregistered.
