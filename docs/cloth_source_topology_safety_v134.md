# Cloth source-topology safety — v134

## Problem

The old Mesh trace workflow treated every displayed triangle edge as a useful
Cloth boundary. On a triangulated cube this included the six coplanar face
diagonals. Repeated **Connected** actions therefore selected a dense graph, and
**Trace** inserted its edges one by one. Each insertion ran generic automatic
face discovery again. The result depended on insertion order, could enumerate
many competing paths, and often created arbitrary triangular panels and cyclic
folds. On larger selections this could block the UI for minutes.

## Semantic source topology

The v134 controller builds edge/face incidence once per source snapshot. A
shared edge is classified as a tessellation diagonal when its two incident
triangles are coplanar. Such diagonals are excluded from smart propagation and
source-face boundaries.

Connected coplanar triangles are grouped into semantic surface regions. Their
outer boundary loops are ordered and oriented using the source triangle
normals. Mesh trace materialises complete regions before considering residual
edge lines.

## Near-closure assistance

For each selected edge component, the controller compares the selection with
nearby semantic source-face boundaries. When a connected selection covers most
of a boundary, the contextual **Close face** action proposes the missing source
edges. This is suitable for short or visually hidden edges and does not invent
free-space geometry: every proposed edge already exists on the picked source
mesh.

The action remains disabled if the selection is disconnected, ambiguous, or
not close enough to a source surface boundary.

## Transaction and safety budgets

Trace starts from a document clone. It is committed only after:

1. inferred boundaries are closed and bounded;
2. Cloth validation introduces no new topology errors;
3. the folded surface can be triangulated;
4. every generated triangle has three distinct vertices and non-zero area.

Any exception or failed check restores the exact previous document.

The following work is explicitly bounded:

- selected edges: 5,000 per operation;
- selected face triangles: 5,000 per operation;
- semantic regions: 2,000 per operation;
- one inferred face boundary: 4,096 edges;
- generic boundary-path search: 4,096 expansions and an 8,192-entry queue.

## Fold cycles

A closed solid such as a cube has a cyclic panel-adjacency graph and cannot be
flattened without cuts. After source faces are created, v134 keeps a fold
spanning forest and converts the remaining shared boundaries into automatic
pattern cuts. The folded geometry remains closed while the flat pattern stays
computable.

## Cube reproduction

Scenario: select two cube edges, press **Connected** twice, then **Trace**.

Expected v134 result:

- 12 semantic boundary curves;
- 6 quadrilateral panels;
- no coplanar triangle diagonals;
- 5 fold connections and 7 automatic cuts;
- valid folded and flattened meshes, each containing 12 triangles.

A headless 200-run benchmark on this scenario measured approximately 2.38 ms
average and 2.39 ms p95 for the Trace transaction after warm-up on the test
environment.

## Validation

- 7 new v134 regression tests;
- 71 focused Cloth tests pass together;
- full suite: 1,653 passed, 3 skipped, 58 pre-existing failures, the same
  failure count as v133.
