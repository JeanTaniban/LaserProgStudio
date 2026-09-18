# Joint selection and Top view pan fix

## Joint builder

After `Add joint to preview`, the current A/B selection is cleared automatically.
The joint tool remains open, so the user can pick another pair and continue the
batch workflow before pressing `Apply`.

## Top view pan

The right-drag pan no longer forces `ViewUp=(0,0,1)` after each camera move.
That vector is invalid for Top view because it is parallel to the view direction
and can make VTK produce a blank white scene or a camera jump.

Pan is now computed from the current camera screen basis:

- screen-right vector
- screen-up vector
- current projection mode

Top view now uses an explicit parallel camera with `ViewUp=(0,1,0)`, and Iso/Reset
restore perspective projection.
