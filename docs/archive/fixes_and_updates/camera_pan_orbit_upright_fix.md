# Camera pan/orbit upright fix

This update fixes a regression introduced by the Top-view pan repair.

## Problem

After right-drag panning in a normal 3D view, the next left-drag orbit could inherit a rolled camera `ViewUp` vector. Depending on the orbit direction, the scene could end up upside down.

The previous Top-view fix correctly stopped forcing `ViewUp=(0,0,1)` during pan, because that vector is degenerate when the camera looks along Z. However, removing that hard lock also allowed camera roll to persist after manual pan.

## Solution

The camera now uses an intelligent up lock:

- normal/isometric views use world Z as the upright reference;
- near-vertical views, including Top view, use world Y as the safe up reference;
- the chosen up vector is projected onto the camera view plane before it is applied.

This avoids both failure modes:

- no white/blank Top view caused by a Z-up vector parallel to the view direction;
- no upside-down orbit after panning in normal views.

## Implementation notes

Added helpers in `src/laserprog_studio/window.py`:

- `_safe_view_up_for_forward()`
- `_stabilize_camera_view_up()`

The stabilizer runs:

- before a possible VTK orbit starts;
- after a VTK orbit drag completes;
- after right-drag pan completes;
- during manual pan basis computation.
