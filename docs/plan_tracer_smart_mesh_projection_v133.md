# Plan Tracer Smart Mesh Projection — v133

## Goal

Plan Tracer can now recover an editable 2D outline from an existing scene part.
The source part does not need to lie on the current drawing plane. Every source
vertex is projected orthogonally into the semantic plane locked by Plan Tracer.

## Workflow

1. Lock or edit a Plan Tracer drawing plane.
2. Choose **Mesh trace** from the bottom toolbox.
3. Select **Faces** or **Edges** in the secondary overlay.
4. Pick source geometry in the viewport.
5. Use the contextual predictions when available:
   - **Coplanar** grows a triangle selection across one planar source face;
   - **Boundary** converts selected faces to their external boundary;
   - **Continue** follows conjoint edges in the current direction;
   - **Connected** grows to directly connected edges.
6. Inspect the green projection preview on the active sketch plane.
7. Press **Trace**. The selection is converted and the tool returns to
   **Modify** automatically.

## Projection contract

Projection uses the active `LockedPlaneSpec` axes, not global XY coordinates:

- Top/Bottom sketches use their local XY orientation;
- Front/Back sketches use local XZ coordinates;
- Left/Right sketches use local YZ coordinates with the view orientation
  preserved;
- arbitrary source depths and tilted source surfaces are accepted.

The source geometry is not modified. Only the resulting Plan Tracer entities
are created on the active semantic construction plane. Their displayed actors
continue to use the normal offset display plane, so they remain visible without
changing geometric depth.

## Geometry cleanup

Before creating sketch entities, the adapter:

- removes duplicate source-edge references;
- extracts only the boundary of selected face triangles, excluding internal
  triangulation diagonals;
- merges projected endpoints that differ only by tessellation or floating-point
  noise using a spatial hash;
- removes duplicate projected segments;
- ignores source edges whose endpoints collapse to the same 2D location;
- reuses existing sketch points and avoids recreating an existing sketch line;
- compiles the sketch once so closed contours become regular Plan Tracer faces.

A source edge that is perpendicular to the active plane has no usable 2D length
and is therefore intentionally ignored. The overlay reports this instead of
creating a degenerate line.

## Architecture

`tooling/plan_trace_2d/mesh_trace.py` adapts the shared Cloth
`ClothGeometryTraceController`. Selection snapshots and prediction logic are
therefore common, while materialisation remains specific to each tool:

- Cloth creates patches, curves or ruled strips;
- Plan Tracer projects to one plane and creates sketch points/lines/faces.

The Plan Tracer implementation is registered as a normal composed service in
`PlanTrace2DServices`; the Creator tool shell only routes overlay actions and
viewport events.

## Current limitation

Mesh boundaries are recovered from tessellated mesh edges. A circle or arc from
an already extruded part is consequently imported as a clean polyline outline,
not reconstructed as an analytic `Circle` or `Arc` entity. The resulting shape
is valid for faces and extrusion, but analytic curve fitting remains a separate
future improvement.

## Validation

The v133 tests cover:

- tilted face projection and removal of triangulation diagonals;
- merging endpoints from different parts;
- rejection of edges collapsed by projection;
- creation of a solved Plan Tracer face and undo registration;
- complete face-selection, Coplanar and Trace workflow;
- automatic return to Modify and overlay cleanup;
- Top, Front and Right plane-axis mappings;
- compatibility with the responsive toolbar and prior Plan Tracer performance,
  curve, dimension and placement passes.
