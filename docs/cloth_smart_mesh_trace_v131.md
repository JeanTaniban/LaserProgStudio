# Cloth Smart Mesh Trace — v131

## Polyline closure repair

Cloth now treats closure as an idempotent operation.

- A double-click closes the current Polyline without adding the same endpoint twice.
- Clicking the first transient node closes the loop before construction snaps are evaluated.
- The materialiser removes a repeated terminal token when it resolves to the first topological point.
- Invalid coincident consecutive points report an explicit error without deleting committed Cloth geometry.

This fixes the previous failure where the draft was reset after a duplicate endpoint and appeared to disappear.

## Mesh trace mode

The main Cloth command bar includes **Mesh trace**. It has two source-picking modes:

- **Faces** selects displayed mesh triangles. The controller maps display/LOD cell ids back to source triangles when actor topology has been renumbered.
- **Edges** selects the closest visible boundary of the picked VTK cell using real dataset point ids.

Selected source geometry is highlighted without changing the source mesh.

## Contextual smart overlay

The separate `Cloth · Smart Mesh Trace` overlay is shown only in Mesh trace mode. Its prediction buttons are disabled until the selection contains enough information:

- **Coplanar** grows a selected triangle across connected triangles sharing the same plane.
- **Boundary** extracts the external edge loop of selected faces and removes triangulation diagonals.
- **Continue** follows conjoint edges whose tangent continues the current selection direction.
- **Connected** selects unselected edges incident to the current edge chain.
- **Trace** creates Cloth faces and/or line boundaries from the current source selection.

Internal loops are retained as Cloth boundary lines. Cloth surface holes remain intentionally unsupported in this version and are reported to the user.

## Architecture

`cloth/geometry_trace.py` is headless and owns snapshots, topology analysis, predictions and materialisation. `cloth/geometry_overlay.py` only builds the contextual command deck. The Creator adapter routes clicks and hover, while `creator_scene_picking.py` provides the real VTK edge backend.
