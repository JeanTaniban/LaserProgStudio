# Cloth Textile Builder v156

## Product objective

Cloth is now organised around the fastest useful user intent:

1. create textile panels;
2. connect them;
3. assign their role and material properties;
4. preview the flat pattern;
5. commit while preserving editability.

## User-facing state machine

```text
OPEN
└── DRAW_TEXTILE / ADD_MESH_FACES
    ├── SELECTING_SOURCE
    ├── CREATE_SOURCE_TEXTILE
    ├── JOIN_FACES
    │   ├── SELECTING_JOIN_ANCHORS
    │   ├── ANALYSING
    │   ├── REVIEWING_JOIN
    │   └── COMMITTING_JOIN
    └── DRAW_POLYLINE
        ├── DRAWING
        ├── FINISH_OPEN
        └── CLOSE_FACE

TEXTILE_PROPERTIES
├── NO_SELECTION
├── SELECTING_PROPERTIES
└── APPLYING_PROPERTIES

OUTPUT
├── FLAT_PREVIEW
├── APPLY_CONTINUE
├── FINISH
└── CANCEL
```

The implemented `ClothWorkspaceMachine` stores only user-facing state. Geometry
controllers remain responsible for source selection, drafting, join analysis,
validation and mesh output.

## Transition rules

### Add mesh faces

| Input | Result |
|---|---|
| Hover source mesh | Preview logical surface |
| Click source mesh | Replace selection |
| Shift+click | Add a logical surface, including another mesh |
| Double-click empty | Clear source selection |
| Create textile | Commit selected logical regions |
| Switch workspace | Clear temporary source selection |

### Join faces

| Input | Result |
|---|---|
| Click textile face | Replace anchors |
| Shift+click | Add anchor |
| Ctrl+click | Remove anchor |
| Two or more anchors | Analyze automatically |
| Previous / Next | Change non-destructive proposal |
| Create junction | Commit current proposal transactionally |
| Double-click empty | Clear anchors and proposals |

### Draw polyline

| Input | Result |
|---|---|
| Click | Add Smart-Snapped point |
| Finish open | Commit an open boundary |
| Close face | Commit a closed textile panel |
| Switch workspace | Cancel only unfinished transient points |

### Textile properties

| Input | Result |
|---|---|
| Click textile face | Replace selection |
| Shift+click | Add panel |
| Ctrl+click | Remove panel |
| Click empty | Clear selection |
| Textile / Pattern / Junction | Set selected panel function |
| Inspector edit | Set name, layer, material or layer thickness |
| Delete faces | Remove selected panels and dependent topology |

## Data model

```text
ClothDocument
├── layers: ClothLayer[]
├── points
├── curves
├── patches: ClothPatch[]
├── folds
└── seams

ClothLayer
├── id
├── name
├── material_name
├── thickness_mm
├── visible
├── locked
└── metadata

ClothPatch
├── boundary curves
├── name
├── grain direction
├── function: textile | pattern | junction
├── layer_id
├── material_name
└── source / creation metadata
```

Panel function is currently panel-wide. The model is intentionally ready for a
later `ClothZone` layer that can place pattern and junction regions on only part
of a logical panel.

## Join solver v1

The join assistant produces ruled surfaces from selected panel boundaries.

For each pair it computes:

- boundary samples;
- relative panel normals and centres;
- nearest compatible edge pair for lateral/coplanar configurations;
- cyclic alignment for separated closed loops;
- mean and maximum width;
- a twist score;
- proposal confidence.

For more than two panels, a minimum-spanning tree chooses the required links.
This prevents an accidental all-to-all explosion.

## Known deliberate limits

- Join proposals do not yet route around collisions.
- Developability and strain are not yet scored physically.
- The solver does not yet split a difficult proposal into several optimal
  panels and seams.
- Pattern and Junction are whole-panel roles, not local painted zones yet.
- Layer stacks are stored but physical offsets and multi-layer seams are not
  generated yet.
- Attachment generators for sewing holes, individual clips and clip bars are
  not part of this release.

These limits are surfaced as scope, not hidden as completed functionality.
