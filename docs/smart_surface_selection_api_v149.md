# Smart Surface Selection API — v149

## Purpose

This pass deliberately isolates intelligent face selection from Cloth. Its goal
is to let the selection behavior be tested and tuned on many meshes before it
becomes a dependency of fabric creation, engraving, materials or attachments.

The implementation currently reasons over connected mesh triangles. It returns
one logical region, its boundary and diagnostic metrics. It does not create or
persist Cloth geometry.

## Public boundary

Built-in and extension tools must import:

```python
from laserprog_studio.tool_api import surface_selection
```

The public module exposes:

- `SurfaceMeshSnapshot`
- `SurfaceSelectionProfile`
- `SurfaceSelectionSession`
- `SurfaceRegionResult`
- `SurfaceRegionMetrics`
- `select_surface_region(...)`
- `auto_surface_region(...)`
- `snapshot_from_pick(...)`
- `face_index_from_pick(...)`

The solver itself lives in `tool_core` and is headless. A snapshot contains
validated vertices, triangles, normals, centroids, areas, edge incidence,
adjacency and a geometry revision token.

## Selection model

### Manual Continuity

Continuity is normalized to `[0, 1]`, but is not a direct angle threshold. It
changes a nonlinear crossing budget combining:

- local normal variation;
- drift from the seed normal;
- distance from the seed;
- small-triangle penalty;
- profile-specific hard dihedral barriers.

The region grows through the triangle adjacency graph while the best known
crossing cost stays below that budget.

### Auto

Auto evaluates 40 Continuity levels. Identical consecutive regions form a
stable plateau. Candidate plateaus are scored from:

- stability across nearby values;
- region coherence and compactness;
- useful region size;
- penalties for accidental single triangles or near-whole-mesh leakage.

The best plateau becomes the result and up to three other candidates are
retained as alternatives. The calculated Continuity value remains visible in
the inspector.

### User constraints

A `SurfaceSelectionSession` stores user intent separately from the pure solver:

- a required triangle is connected to the current region by a least-cost path;
- an excluded triangle becomes a propagation barrier;
- changing object or geometry revision clears stale constraints.

## Test tool

Open toolbar customization and add **Selection API test** (`SST`). The tool is
hidden from the default toolbar so it does not affect the normal product flow.

### Controls

- Hover: preview the region for the triangle under the cursor.
- Click: use that triangle as the new seed.
- Shift+click: require the clicked triangle in the current region.
- Ctrl+click: exclude the clicked triangle.
- Drag: orbit the camera without committing a selection.
- Auto: enable or disable stable-plateau selection.
- Continuity: manually control growth when Auto is off.
- Profile: compare Cloth support with Strict face.
- Alternative: cycle through retained Auto candidates.
- Reset corrections: remove required and excluded triangles.
- Clear: remove the current selection.

### Overlay legend

- green: hover proposal;
- cyan: committed automatic region;
- blue: explicitly required triangles;
- red: explicitly excluded triangles;
- white: logical boundary.

## Suggested test cases

Test the same actions on several geometries:

1. a planar face with many triangles;
2. a cube or thin board;
3. a bevelled or filleted box;
4. a cylinder with dense triangulation;
5. a gently curved panel;
6. a sphere or strongly double-curved surface;
7. a mesh after boolean operations;
8. a mesh with holes, open borders or non-manifold areas.

For a useful report, record:

- geometry and clicked area;
- Auto or manual mode;
- profile and Continuity value;
- expected logical surface;
- actual selected surface;
- whether Shift inclusion or Ctrl exclusion repaired it;
- a screenshot when the boundary leaks or stops too early.

## Current limitations

This is a first testable solver, not the final semantic segmentation engine.

- It still works directly on triangles; super-face preprocessing is not yet
  implemented.
- Auto uses deterministic geometric plateau analysis, not machine learning.
- Surface model fitting for planes, cylinders and developable surfaces is not
  yet implemented.
- The selection exists only inside the test tool and is not saved in projects.
- Remapping after topology-changing booleans is not implemented.
- Non-manifold boundaries are treated conservatively and may produce incomplete
  loops.
- No Cloth panel, imaginary face or attachment is generated in this release.

These limitations are intentional: feedback from the isolated tool should drive
the next algorithmic pass before production integration.
