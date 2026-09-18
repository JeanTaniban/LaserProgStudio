# LaserProg v148 — Duplicate Pivot & Folding Snap

This release tightens two viewport workflows without changing their generated
geometry or persistence formats.

## v148 interaction changes

### Duplicate prefab creation

The pivot phase is now an instruction-only viewport prompt. It contains no
Back, Done, Apply or validation action, so a prefab cannot advance before its
pivot has actually been picked. Once the pivot is clicked, the command deck is
hidden and the existing dedicated modal asks for the prefab name.

### Folding axis placement

The two hinge-limit points now use the public `tool_api.plan2d` interaction
contract:

- official Smart Snap on the selected face plane;
- the API-owned cursor motif changes with vertex, edge, midpoint, grid, angle
  and other supported snap kinds;
- holding Shift while placing the second limit constrains the folding axis to
  45-degree increments, including exact horizontal and vertical directions;
- the pending interval and the committed endpoint use the same resolved point,
  so preview and click cannot disagree.

## Validation

- Static quality gate passed.
- API-boundary, tool-migration and product-quality audits passed.
- 68 focused Duplicate and Folding regression tests passed.
- 3 new v148 regression tests cover the instruction-only pivot, official snap
  cursor and Shift angle constraint.

See `docs/duplicate_folding_interaction_v148.md` for the interaction invariants.

## v147 Cloth pipeline foundation

### What changed in v147

### Clear architecture

The former mixed boolean-pattern module has been split into focused components:

- validated modifier persistence;
- cutter/panel slicing;
- planar boolean application;
- region triangulation;
- topology-aware panel welding;
- solidification;
- stitch healing;
- generic boolean integration.

`mesh_builder.py` is now an orchestration layer instead of owning every geometry
algorithm.

### Strong persisted-data validation

A Cloth boolean cutter is validated before it is stored. Non-finite coordinates,
fractional or out-of-range indices, unsupported operations, empty meshes and
oversized payloads are rejected atomically. Corrupted older-format metadata produces a
clear build error rather than a partial or silently incorrect pattern.

### Faster multi-panel regeneration

Boolean modifiers are parsed once per build, not once per panel. Their bounds
are cached and cutters that cannot intersect a panel plane are rejected before
triangle scanning.

A synthetic 20-panel / 5,000-triangle benchmark improved from approximately
831.52 ms in v146 to 22.26 ms in v147 on the validation host.

### Safer stitch tolerance

Tolerance healing never converts explicit cuts or authored seams into folds.
Candidate lookup is spatially indexed, complete endpoint agreement remains the
final test, and all topology references are updated through one canonical path.

Apply now heals one transactional clone. Flattening reuses it instead of cloning
and healing twice.

### Cleaner metadata and memory use

Boolean results remove stale pre-boolean topology counters and record the actual
modifier count and last operation. Fresh outputs attach their editable Cloth
source without copying complete geometry buffers; the existing public
copy-on-write API remains available.

### Public API boundary fixed

Duplicate curve sampling now enters through `tool_api.plan2d`, eliminating the
last forbidden built-in tool import reported by the strict migration audit.

## Validation

- Static quality gate passed.
- Architecture and API audits passed.
- 129 focused Cloth and Duplicate tests passed.
- 7 new v147 quality regression tests passed.
- Full suite: 1,731 passed, 3 skipped and 64 pre-existing or environment-dependent failures.
- One previous API-boundary failure is fixed; no new failing test node was introduced.

See `docs/cloth_pipeline_code_quality_v147.md` for the design invariants and
benchmark details.
