# Cloth workflow clarification v157

## Domain boundary

```text
Temporary source selection
    └── logical surfaces from scene meshes

Persistent Cloth document
    ├── points
    ├── curves
    ├── textile faces
    ├── folds
    └── seams
```

Only **Create from mesh** crosses this boundary. Join and Textile properties
operate exclusively on persistent Cloth faces.

## State transitions

### Create from mesh

```text
SELECTING_MESH_SURFACES
    ├── click / Shift+click → MESH_SURFACES_READY
    ├── double-click empty → SELECTING_MESH_SURFACES
    └── Create textile faces → TEXTILE_CREATED
```

`TEXTILE_CREATED` owns the created patch IDs as the current textile selection.

### Join textile faces

```text
SELECTING_JOIN_ANCHORS
    ├── fewer than two panels → SELECTING_JOIN_ANCHORS
    ├── two or more panels → REVIEWING_JOIN
    └── accept proposal → TEXTILE_CREATED
```

Entering this mode preserves valid selected Cloth patch IDs. Source-mesh
selection is cleared because it is not a valid join input.

### Textile properties

```text
SELECTING_PROPERTIES
    ├── click → replace patch selection
    ├── Shift+click → add patch
    ├── Ctrl+click → remove patch
    └── click empty → clear patch selection
```

## Technical invariants

- temporary mesh selection and persistent patch selection are never the same
  collection;
- Join never reads source-mesh triangle IDs;
- created patch IDs remain valid after creation and are used for follow-up UX;
- switching to Create from mesh clears only document entity selection;
- switching to Join clears only temporary source selection;
- workspace help, workflow step and inspector visibility derive from the same
  active state.
