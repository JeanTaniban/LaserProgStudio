# LaserProg v120 — Folding multi-mesh groups

Folding now consumes the complete scene selection when the tool opens. Selected
meshes share one hinge plane, one living-hinge curve and one terminal transform,
so they behave as one temporary kinematic group during preview.

The output is deliberately **not fused**:

- each source object is deformed independently in the shared world-space frame;
- preview stages all replacements atomically;
- Apply keeps the same number of scene objects;
- names, mesh IDs, materials and object order are preserved;
- Cancel restores every original object together;
- Apply creates one undo operation for the complete group;
- clicking one applied member reopens the complete persisted group.

Persistence uses `folding_source` version 4. Every output stores its own original
mesh plus the shared group ID and ordered member IDs.

Validation:

- all Folding regression tests pass;
- dedicated tests verify two selected meshes remain two committed objects;
- reopening one member restores the complete group;
- the strict quality gate passes for all Creator tools.
