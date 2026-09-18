# Transform gizmos — lightweight API renderer v16

The native Transform gizmo now follows the same visual model as the Creator API:
only PyVista polylines and point clouds are rendered.

## Design

- Translate: one shaft polyline, two arrowhead strokes and one endpoint per axis.
- Rotate: one closed polyline and one point marker per rotation axis.
- Scale: one polyline and one endpoint per axis; adaptive bounds remain simple lines.
- Center markers are plain VTK points, never sphere meshes.
- Lines are explicitly rendered without tubes and points without sphere impostors.
- All primitives live in the foreground renderer and share one removable assembly.

The visible snapshot is also the source used by the screen-space picker. While a
native gizmo is active, picking never falls through to the obsolete VTK mesh
actors, preventing invisible or stale hit targets.

## Lifecycle

A mode change removes the complete assembly with `RemoveViewProp`, clears every
actor registry and rebuilds only the small line/point set required by the new
mode. Translation preview moves the existing assembly and commits geometry only
when the drag ends.

## Compatibility

`LPS_NATIVE_TRANSFORM_GIZMO=0` still enables the legacy mesh implementation for
diagnostics. It is not used by the normal path.
