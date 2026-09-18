# Pass 317 — Plan Tracer boolean manifold validation and empty-result handling

## Problem

The global subtract controller reduced every failed target to:

```text
No part could be subtracted. Check that the meshes are closed solids.
```

This hid two distinct conditions affecting Plan Tracer output:

1. indexed edge counts could say a mesh was closed while `manifold3d` reported a geometric non-manifold after coincident seam vertices were merged;
2. a valid subtraction that fully consumed the target produced an empty mesh and was incorrectly treated as failure.

## Implementation

- Added explicit `Manifold.status()` and `is_empty()` validation for both boolean inputs.
- Added conservative and backend repair retries only after real manifold rejection.
- Added adaptive repair tolerance based on mesh extent.
- Added `BooleanEmptyResult` to distinguish complete target consumption from invalid geometry.
- Updated `BooleanController.subtract_touching()` to delete completely consumed targets and remap the cutter index.
- Replaced the unconditional closed-solid suffix with detailed geometric errors.
- Added debug-only `boolean_debug.jsonl` diagnostics.

## Performance

Normal primitive and valid Plan Tracer inputs use the existing direct path. Repair modules are loaded only when the actual manifold status is invalid.

## Tests

`tests/test_v96_plan_tracer_boolean_manifold_fix.py` covers partial and complete differences with Plan Tracer volumes and the global controller removal path.
