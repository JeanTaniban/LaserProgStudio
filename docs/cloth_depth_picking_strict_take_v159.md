# LaserProg v159 — Cloth depth picking and strict Take face

This release corrects the interaction defects reported in the v158 single-overlay
Cloth workflow. It keeps the same compact overlay but makes selection depth,
Take face and Close deterministic and failure-safe.

## Selection clearing

A single ordinary click in empty space now clears the complete mixed selection:

- temporary logical mesh regions;
- persistent logical textile groups;
- isolated textile edges.

Shift does not preserve stale selection when the pointer is in empty space.
Double-click has no separate Cloth editing mode and follows the same visible
selection rule.

## One depth-correct raycast across mesh and textile domains

Textile panels are projected overlays, while scene meshes are picked by the scene
renderer. v158 tested textile polygons first in screen space, so a textile panel
behind a mesh could win without comparing depth.

v159 builds a revision-cached canonical Cloth surface and intersects it with the
same camera ray used for the scene mesh pick. The two positive ray distances are
then compared:

- a mesh in front wins over a textile panel behind it;
- a textile panel in front wins over the mesh;
- when a copied textile panel is exactly coincident with its source mesh, the
  editable textile domain wins only inside a very small depth tolerance.

This rule is used both for hover and selection. The raycast cache is invalidated
by the Cloth document revision and does not rebuild on every pointer move.

## Strict Take face

Take face no longer reconstructs an arbitrary outer cap for every selected area.
Each disconnected selected source component becomes a separate logical textile
group.

- A simply connected, genuinely planar component is copied as one exact polygon.
- A curved component is copied as exact technical source triangles grouped as one
  user-facing textile surface.
- A component containing holes or multiple boundary loops is copied by its exact
  selected triangles, so openings are not filled.
- Two selected areas that do not touch remain two selectable textile groups and
  can immediately be used as two Close anchors.

The source object and exact source-face metadata remain attached to every created
technical patch.

## Close is failure-safe

The amber Close overlay is displayed before the solver starts. Analysis and
commit are now guarded transactionally:

- a solver exception leaves the amber overlay visible;
- Reset always remains available;
- a failed commit restores the complete previous Cloth document;
- a proposal that creates no face is reverted;
- the tool never remains in a hidden or unusable interaction state.

The normal successful flow remains:

```text
Apply | Prev | Next | Reset
```

## Verification

- 6 new v159 regression scenarios;
- 77 focused Cloth and smart-selection tests passed;
- full Python compilation passed;
- Quality Gate passed;
- API boundary audit: 0 critical issues;
- architecture, migration and product audits passed;
- all 21 built-in tools remain on Creator runtimes.

The new regression suite covers front/back mesh-textile overlap, coincident copied
faces, single-click clearing, disconnected Take face groups, strict curved source
copying and a forced Close solver failure.
