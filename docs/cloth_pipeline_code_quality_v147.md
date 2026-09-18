# Cloth Boolean Pipeline — Code Quality Pass v147

## Scope

This pass reviews the complete path from an editable `ClothDocument` to a
boolean-ready folded solid and back to a flat pattern. It does not change the
user workflow introduced in v146. The goal is to make the implementation easier
to audit, faster on multi-panel documents and safer when loading old metadata.

## Explicit module boundaries

The pipeline is now split by responsibility:

- `boolean_modifiers.py` owns the versioned persistence contract, validation,
  limits and JSON-compatible payloads for stored cutters.
- `boolean_slicing.py` owns triangle/plane intersection and GEOS polygonisation.
- `boolean_pattern.py` applies validated cross-sections to one panel region.
- `triangulation.py` owns simple-polygon preview triangulation and
  Polygon/MultiPolygon output triangulation.
- `mesh_welding.py` owns topology-authorised vertex sharing between panels.
- `mesh_builder.py` only orchestrates panel processing and optional
  solidification.
- `solidification.py` owns the closed thin-shell manifold contract.
- `stitching.py` owns conservative historical-gap healing.
- `boolean_bridge.py` is the only adapter between generic 3D booleans and the
  editable Cloth source.

No UI or application controller is imported by these geometry modules.

## Persisted modifier contract

Stored cutters are validated before document metadata is changed:

- all coordinates must be finite 3D values;
- all triangle indices must be integral, in range and distinct;
- empty cutters are rejected;
- limits are 750,000 vertices and 250,000 triangles;
- only `difference` and `union` operations are accepted;
- the applied margin is finite and stored for audit purposes;
- append is atomic: invalid input leaves metadata and document revision intact.

Malformed older-format entries are reported as explicit build issues. They are never
silently skipped while producing a partial pattern.

## Performance changes

v146 loaded and deep-copied the complete modifier payload once per panel and
converted its vertex/triangle arrays again for every slice. v147 parses each
modifier once per mesh build and caches its bounds. A conservative AABB/plane
test rejects cutters that cannot intersect a panel before triangle scanning.

Synthetic headless benchmark:

- 20 panels;
- one stored cutter containing 5,000 triangles outside the panel planes;
- eight measured surface builds after warm-up.

Results on the validation host:

- v146 average: 831.52 ms;
- v147 average: 22.26 ms;
- approximately 37× faster for this rejection-heavy case.

Freshly generated meshes also receive Cloth source metadata in place. The public
copy-on-write API remains compatible, but internal Apply and boolean paths no
longer duplicate large vertex and triangle buffers unnecessarily.

## Stitch-healing invariants

Tolerance healing now uses a midpoint/length spatial index followed by exact
endpoint comparison. It remains intentionally conservative:

- only complete straight single-panel boundaries are candidates;
- explicit user/automatic cuts are excluded;
- authored seams and seam-role curves are excluded;
- curves already referenced by a fold are excluded from proximity pairing;
- all patch, fold and seam references are rewritten through one canonical helper;
- partial overlaps are not healed because they require a topological split.

Apply heals one owned clone. Flattening can reuse that prepared clone instead of
cloning and healing a second time. The source document remains unchanged until
the normal application commit succeeds.

## Metadata clarity

A boolean result keeps the editable source and linked-scene metadata, but drops
mesh statistics that described the pre-boolean generated surface, such as old
patch triangle ranges and mid-surface counts. It records the current modifier
count and last operation instead. Fresh topology statistics are regenerated on
the next Apply.

## API boundary repair

Plan Tracer Duplicate previously imported curve samplers directly from
`tool_core`. The samplers are now exposed through the public `tool_api.plan2d`
facade, so the strict built-in tool migration audit reports zero forbidden
imports.

## Verification

- Static quality gate: passed.
- Refactor structure audit: passed.
- API boundary audit: 0 critical issues.
- Built-in tool migration audit: 0 forbidden imports.
- Tool product audit: 20/20 tools valid.
- Focused Cloth and Duplicate tests: 129 passed.
- Cloth pipeline quality tests include atomic persistence, malformed metadata,
  one-time parsing, authored seam protection, transactional Apply, stale metadata
  removal and zero-copy internal source attachment.
- Full suite: 1,731 passed, 3 skipped and 64 pre-existing or environment-dependent failures.
- The v146 baseline had 1,723 passed and 65 failures; the public API boundary repair removes one failing node and adds no new one.
