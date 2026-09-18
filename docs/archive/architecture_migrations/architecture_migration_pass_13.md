# Architecture Migration Pass 13 — Planar tool foundation and texture import cleanup

## Goal

This pass keeps the app moving toward a professional extension architecture while preparing two planned tools:

- **Traceur de plan**: draw a 2D polygon in a locked orthographic plane, then extrude it.
- **Générateur d'évent**: draw a smooth waypoint path in a locked orthographic plane, preview a duct corridor, then generate a mesh.

## Changes

### Texture cleanup

Application texture services no longer import private helpers from the compatibility facade `geometry_ops.texture_projection`.
They now import from the focused modules introduced in Pass 12:

- `texture_projection_vector.py`
- `texture_projection_faces.py`
- `texture_projection_uv.py`
- `texture_projection_decal.py`

The facade remains stable for legacy callers, but new code should use focused modules directly.

### Locked planar tool foundation

A new pure-Python package was introduced:

```text
src/laserprog_studio/planar_tools/
  contracts.py
  orientation.py
  draft_model.py
  vent_model.py
```

It defines:

- `PlanarEditMode`: `ADD`, `MOD`, `SUPP`, `RST`.
- `FixedPlanarView`: `top`, `bottom`, `front`, `back`, `left`, `right`.
- `LockedPlaneSpec`: the constant-depth plane shared by planar tools.
- `PlanarPolygonDraft`: ordered polygon state for the future traceur de plan.
- `VentPathDraft`: waypoint/section/length state for the future vent generator.

These classes do not import Qt, PyVista or VTK. They are safe to test headlessly.

### Planar runtime state/controller

New runtime pieces:

```text
src/laserprog_studio/state/planar_tool_state.py
src/laserprog_studio/application/planar_tool_controller.py
```

`PlanarToolController` centralizes the workflow both future tools need:

1. detect the closest orthographic view from the current camera direction;
2. lock the app to that view;
3. create a constant-depth drawing plane;
4. clamp future world points to that plane;
5. release planar state when the tool closes.

The controller is composed in `runtime_state.py` as `self.planar_tool_controller`.

### Future tool blueprints

New blueprint metadata lives in:

```text
src/laserprog_studio/tooling/planar_tool_blueprints.py
```

The blueprints reserve stable ids and toolbar metadata for:

- `plan_trace`
- `vent_generator`

They are intentionally **not registered yet**. The tools should become visible only once their panels and runtime classes are implemented.

## Guardrails

Added tests verify:

- texture services no longer import private helpers from the facade;
- locked-plane orientation/depth mapping;
- plan-tracer model mode transitions and reset behaviour;
- vent path section/length contract;
- future planar blueprints exist but are not registered;
- runtime composes planar state and controller.

Updated `verify_refactor_structure.py` so the planar foundation stays present and focused.
