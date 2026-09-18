# v122 — Plan Tracer boolean-ready output contract

## Problem

Some Plan Tracer 2D outputs were closed by raw triangle indices but became
non-manifold after the boolean backend welded coincident vertices. Dense rounded
contours, adjacent solved faces, tangent holes and pattern boundaries could leave
open seams, duplicated walls, edges used by more than two triangles, or bow-tie
vertices. The boolean repair path then failed later with `NotManifold`.

The previous architecture was backwards: Plan Tracer assembled caps and walls
independently, and Boolean Union/Subtract attempted to repair the result after
it had already entered the document.

## Boolean-ready contract

`geometry_ops/planar_boolean_solid.py` is now the topology boundary between a
2D sketch and a 3D solid. Before Apply it:

1. removes duplicate/non-finite ring points;
2. repairs invalid 2D rings and discards lower-dimensional remnants;
3. applies a scale-aware precision grid;
4. unions all solved regions before extrusion, removing internal walls;
5. regularizes only zero-clearance contacts that would extrude to a bow-tie;
6. prefers `manifold3d.CrossSection.extrude`, the same kernel family used by
   the application's Boolean tools;
7. validates boundary edges, overused edges, non-manifold vertex links,
   signed volume and the topology after boolean-style vertex welding;
8. when `manifold3d` is available, runs the exact shared Mesh → merge →
   Manifold conversion before committing the WorkMesh.

If any check fails, Apply stops inside Plan Tracer with a local error. An
invalid mesh is never added to the scene.

## Shared kernel code

`geometry_ops/manifold_contract.py` centralizes:

- Manifold mesh construction;
- optional `Mesh.merge()`;
- status formatting;
- validity checks.

Both `boolean_ops.py` and the Plan Tracer solid generator consume this module,
preventing their topology contracts from drifting apart.

## Fallback

A deterministic fallback exists for test/headless environments where the
native `manifold3d` extension is unavailable. It triangulates each normalized
polygon and derives side walls from the actual cap boundary edges, not from a
second independently sampled contour. It is subjected to all indexed/welded
manifold checks. Production installations still prefer and verify with
Manifold.

## Output metadata

Committed Plan Tracer meshes now expose:

- `boolean_ready=True`;
- `boolean_ready_backend`;
- `boolean_ready_boundary_edges`;
- `boolean_ready_nonmanifold_edges`;
- `boolean_ready_nonmanifold_vertices`;
- `boolean_ready_manifold_status`;
- `boolean_ready_footprint_area`;
- `boolean_ready_precision_grid`.

These fields make future diagnostics explicit without rerunning a heavy repair.

## Validation

New regression coverage includes:

- a dense rounded footprint with many circular holes and a tangent hole;
- adjacent regions sharing an edge, with no internal extrusion wall;
- two closed shells touching at one vertex, which edge counting alone misses;
- preference for the Manifold CrossSection backend;
- Plan Tracer metadata contract.

Results from the v122 source tree:

- 5 new boolean-ready contract tests passed;
- 32 existing targeted Plan Tracer geometry/pattern tests passed;
- full Plan Tracer comparison kept exactly the same 30 historical/environment
  failures as v121 and added 5 passes;
- strict quality gate passed for all Creator tools and architecture checks.
