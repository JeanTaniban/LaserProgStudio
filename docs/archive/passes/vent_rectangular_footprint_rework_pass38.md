# EVT rectangular footprint rework - Pass 38

This pass simplifies the EVT workflow into a practical rectangular/square vent tool.

## User workflow

- EVT is now exposed as a rectangular/square vent tool in the UI.
- ADD places normal waypoints. New segments are straight by default.
- MOD selects and moves waypoints. The selected waypoint exposes Curve radius and Curve force sliders for the associated segment.
- Preview remains lightweight: no mesh is staged while editing.
- Apply generates the final mesh.

## Preview geometry

The previous preview drew two independent offset lines around the centerline. This was fragile around tight curves and U-turns: the two lines could cross, form spikes or stop following the actual curve.

Pass 38 replaces that with a real 2D corridor footprint:

1. sample the same centerline used by Apply;
2. build a Shapely buffer/corridor for the outer width;
3. draw the unioned outer outline;
4. draw the inner airway outline;
5. draw the Fill area bounding box from the same footprint when enabled.

The legacy `offset_paths()` helper remains for compatibility, but the live preview and smart snap use corridor outline rings instead.

## Mesh generation

Rectangular vents are generated from the same footprint model as the preview:

- outer corridor minus inner airway corridor;
- extruded by the outside height;
- Fill area uses the global rectangular stock footprint minus the inner airway.

This avoids the old swept rectangular ring path for the active rectangular workflow, reducing twist and contour mismatch in tight bends.

Round vent generation remains in the code only for backward-compatible project states/tests, but it is not exposed by the redesigned UI.

## Legacy options

The old Only walls option is hidden and treated as a compatibility flag. It no longer creates a separate rectangular geometry path in the current EVT workflow.
