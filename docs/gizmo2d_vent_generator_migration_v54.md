# v54 — Vent Generator Gizmo 2D public API migration

## Scope

This pass migrates the Vent Generator snap/drag layer away from direct `tool_core.snap` imports.

The Vent Generator already used Projected Drawing / Plan2D route visuals. The remaining coupling was in its smart-snap plumbing:

- route alignment guide targets were built from `tool_core.snap.types.SnapTarget` directly;
- drag filtering imported `SnapKind` and `SnapSource` from `tool_core.snap.types` inside the runtime.

## Changes

- `tooling/vent_generator/snap.py`
  - `vent_route_alignment_targets(...)` now declares its custom route-alignment guide segments through `tool_api.snap.segment(...)`.
  - `SnapSource.CUSTOM_EDGE` and `SnapKind.EDGE` are consumed from the public `tool_api.snap` facade.

- `tooling/vent_generator_tool.py`
  - drag smart-snap filtering now imports `SnapKind` and `SnapSource` from `tool_api.snap`.
  - the call to `plan2d.smart_snap_on_plan(...)` was also reformatted so the source/kind filters are visibly part of the public Plan2D query.

## Behaviour kept intact

- Vent route waypoints and route segments are still excluded as direct snap targets during drag.
- Scene mesh vertices/edges, scene points/edges, centers, intersections and custom Vent alignment guides remain allowed.
- The small Vent snap radius is unchanged.
- Shift still applies the strict 45° routing constraint.
- Vent route visuals remain Projected Drawing / Plan2D actors; no legacy gizmo/preview fallback was reintroduced.

## Regression tests

Added checks in `tests/test_pass1052_tool_gizmo2d_migration.py`:

- Vent Generator snap code must not import `laserprog_studio.tool_core.snap` directly.
- Vent route alignment targets must be declared through the public `tool_api.snap` facade.
