# v123 — Plan Tracer Apply validation fix

## Regression

The v122 boolean-ready boundary added a second native Manifold import after
`CrossSection.extrude()` had already produced and validated a native solid.
Depending on geometry, world coordinates and the installed binding version,
that export/re-import step could report `NotManifold` even though the original
CrossSection result was valid.

The exception stayed inside the Creator apply callback. The document was not
modified and the tool correctly remained open, but Plan Tracer did not expose
the failure in its own visible status. Apply/Add therefore appeared to do
nothing, while Cancel still worked.

## Correction

### Native CrossSection result

A successful `CrossSection.extrude()` result is now the canonical native
verification. It is exported once to a WorkMesh and is not imported into
Manifold a second time.

### Indexed fallback

When the fallback triangulator is used, native verification remains active. It
now prefers `Mesh64` and `to_mesh64()` when the installed Manifold binding
provides them. Boolean input preparation follows the same 64-bit path, avoiding
a precision disagreement between the producer and consumer at large world
coordinates.

An explicit Manifold status such as `NotManifold` is still a hard failure. An
optional API/ABI compatibility exception is not treated as proof that a locally
validated closed 2-manifold is invalid; the fallback stays usable and records
`verification_unavailable:<ExceptionType>` in the report.

### Visible Creator result

Plan Tracer stores the last apply error in its state and displays it in the
active overlay. Every Apply/Add attempt now has one of two outcomes:

1. the mesh is committed and the tool closes normally;
2. the sketch stays open and a precise `Validation failed: ...` message is
   visible inside Plan Tracer.

There is no silent third state.

## Metadata

Committed meshes add `boolean_ready_native_verified` to the v122 diagnostic
metadata. It distinguishes a native Manifold verification from the local
closed-manifold fallback contract.

## Validation

The v123 regression tests cover:

- no re-import of a successful CrossSection solid;
- non-blocking behavior for an optional native API incompatibility;
- a visible Plan Tracer error when validation genuinely fails;
- successful Add committing the mesh and closing the tool;
- the existing v122 boolean-ready rounded/hole/adjacency cases;
- the shared high-precision Boolean input path.

The strict architecture, API, Creator migration, product-quality and product-tree
gates pass from the final source tree.
