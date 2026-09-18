# Transform gizmo camera-size fix

The transform gizmo no longer uses mesh-size or absolute visual floors for its size.

## Problem

The previous sizing logic used these floors:

- active mesh size floor;
- absolute minimum length;
- absolute minimum shaft, tip, ring, label, frame and handle sizes.

After zooming in, those floors became larger than the camera-relative size. The gizmo stopped shrinking and looked huge on screen.

## Fix

All transform gizmo visual dimensions now derive from the camera visible height at the selected part center.

Only a very small numeric epsilon remains, so VTK primitives never receive zero dimensions.

Affected modes:

- Translate axes;
- Rotate rings;
- Scale axes;
- Scale handles;
- XY scale frame;
- Axis labels;
- Center marker.

The gizmo should now stay proportional to the camera field of view instead of being dominated by object size or fixed world-unit minimums.
