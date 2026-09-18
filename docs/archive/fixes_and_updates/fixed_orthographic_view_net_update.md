# Fixed orthographic view net update

This update separates the camera into two navigation contracts:

- Free / Iso view: perspective camera with normal Terrain orbit.
- Fixed orthographic views: top, bottom, front, back, left, right.

In fixed orthographic views:

- left-drag orbit is disabled;
- left click still selects parts and transform gizmos;
- right-drag pans in the active face plane;
- mouse wheel zooms by changing the parallel scale;
- the camera stays parallel and locked to the selected face direction.

A small unfolded cube view net was added to the left View panel:

```text
        Top
Left  Front  Right  Back
      Bottom
```

Each face button switches to a locked parallel camera. This avoids the previous Top view issue where VTK orbit could receive a left-drag event and roll or flip the camera.

Free view keeps the old stable behavior: pan uses focal-depth projection and preserves a Z-up Terrain orbit contract.
