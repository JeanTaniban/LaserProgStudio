# Pass 40 — EVT embouchure endpoint anchor

The rectangular EVT flare is now anchored to the user waypoints instead of a
sampled distance profile.

## Problem

Changing `Curve radius` or `Curve force` could make the flare appear to slide
along the preview path.  Preview and mesh generation were computing local width
from cumulative sampled distance.  When the curve sampling changed, the visual
transition could move even though the user expected the mouth to stay on the
first or last waypoint.

## Fix

A single sampling helper now returns both:

- the sampled centerline;
- the local flare scale for every sample.

The scale is derived from segment/t values:

- inlet flare lives only on segment 0 and is maximal at waypoint 0;
- outlet flare lives only on the last segment and is maximal at the last
  waypoint;
- changing the curve radius changes the path shape, but not which waypoint owns
  the flare.

Preview, smart snap and Apply now use this same sampled profile.

Double-click no longer finalizes or reinterprets the EVT outlet.  The current
last waypoint is always the outlet.

## Validation

Added regression tests in `tests/test_vent_flare_anchor_pass40.py`.

Full suite result after the change: `263 passed, 3 skipped`.
