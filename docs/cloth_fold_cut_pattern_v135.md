# Cloth Fold & Cut Pattern Editor — v135

## Problem

The historical Cloth Fold mode selected a shared straight edge and immediately
created or modified a fold relation. Its only control lived in the inspector,
there was no validation action, and the user could not explicitly convert an
edge into a pattern cut. Closed objects such as a cube therefore had no complete
manual workflow for deciding where the flat pattern should open.

## Edge semantics

A shared Cloth edge now carries two separate meanings:

- **Fold** — adjacent panels remain connected in the flat-pattern graph. A
  straight edge also stores a signed 3D angle and a nominal bend radius.
- **Cut** — adjacent panels remain geometrically joined in the folded 3D surface,
  but are disconnected when the flat pattern is laid out.

A cut does not duplicate, delete or move the underlying 3D boundary points. It
only removes the fold relation used by the unfolding graph and stores explicit
cut metadata on the curve.

## Contextual overlay

Entering Fold opens `cloth.pattern_edges` at the top-right of the viewport. It
is visible even before a valid edge is selected, so the user always has an exit
and can understand why actions are disabled.

The overlay provides:

- **Fold / Cut** role selection;
- −90°, Flat, +90° and Invert angle helpers;
- **Fix cycles** for an invalid cyclic fold graph;
- **Apply edge** to validate while remaining in the sub-tool;
- **Clear** to restore the selected edge to its exact previous state;
- **Done** to return to Modify.

The inspector exposes the precise angle, nominal fold radius and spacing between
disconnected flat-pattern components.

## Transactional preview

Selecting an edge stores a complete document snapshot. Changes are previewed on
the active Cloth document so the 3D result remains immediate, but the snapshot
is retained until validation.

- Apply edge discards the snapshot and commits the preview.
- Clear, Escape, Back, or switching to another tool restores the snapshot.
- Selecting another edge first restores any previous unvalidated edit.
- Global Cloth Apply is also treated as explicit confirmation of the visible
  preview.

This preserves the responsive historical angle preview without allowing a mode
change to commit hidden state accidentally.

## Cycle handling

The flat pattern is a graph whose nodes are panels and whose Fold relations are
connections. A graph cycle cannot be laid out unambiguously without at least one
cut.

`Fix cycles` uses union-find to preserve a spanning forest and converts only the
relations that close cycles into user-visible cuts. Adding a new fold that would
close a cycle is blocked with a precise message instead of producing an invalid
pattern.

The cube produced by v134 Mesh trace already contains five folds and seven
automatic cuts. v135 exposes those automatic decisions in the Fold/Cut editor so
they can be inspected or changed safely.

## Curved edges

A curved shared boundary may be a valid pattern cut, but it cannot be a rigid
hinge for the current exact panel-unfolding model. Fold is therefore disabled
for arcs and curved shared boundaries; Cut remains available.

## Pattern spacing

`cloth_pattern_component_margin_mm` is stored in the Cloth document metadata.
The flattening service uses it whenever no explicit spacing override is passed,
so saved projects and reopened Cloth objects retain their preferred component
spacing.

## Validation

The v135-specific suite covers:

- overlay visibility before selection;
- disabled validation until a shared edge is selected;
- live Fold and Cut preview;
- exact cancellation and tool-switch rollback;
- Apply edge and global Apply confirmation;
- fold angle and radius persistence;
- 3D geometry preservation when cutting;
- disconnected flat-pattern components after a cut;
- cycle detection and automatic cycle cuts;
- rejection of a prospective cycle-closing fold;
- persisted component spacing;
- curved-boundary Cut support and Fold rejection.

The extended Cloth suite passes 90 tests. A complete application run reports the
same 50 pre-existing failures as v134 in the current headless environment, while
v135 adds ten passing tests.
