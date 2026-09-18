# Adaptive scale frame update

The Scale tool frame is no longer locked to the local XY plane.

## Problem

When the user looked at the selected part from the side, the local XY frame could
become edge-on. It was still technically present, but visually almost flat and no
longer useful for resizing.

## New behavior

The Scale tool now selects the best local bounds face from the current camera
view direction:

- view mostly along local Z: show the local XY frame;
- view mostly along local Y: show the local XZ frame;
- view mostly along local X: show the local YZ frame.

The frame is placed on the face nearest to the camera and remains in the gizmo
foreground overlay.

## Drag behavior

The existing Option B behavior is preserved:

- dragging one frame edge scales along that local axis;
- the opposite local edge remains fixed;
- axis scale handles still scale from the center.

## Performance

The frame is not rebuilt continuously during orbit. It is rebuilt once when the
free-orbit drag ends, and also during the existing gizmo refresh paths such as
selection changes, fixed view changes, and wheel zoom refreshes.
