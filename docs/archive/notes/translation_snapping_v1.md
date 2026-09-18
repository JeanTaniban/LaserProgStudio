# Translation snapping V1

This update adds the first snapping system for translation transforms.

## Controls

The Transformation panel now contains a `Translation snap` section:

- `Grid snap`: snaps the moving part center to a configurable grid step on the active translation axis.
- `Smart snap`: snaps the moving part bounds to nearby bounds of other parts.
- `Grid step`: grid size in millimeters.
- `Smart tolerance`: maximum distance in millimeters for smart snap capture.

Both toggles can be enabled at the same time.

## Priority

Smart snap has priority over grid snap on the active axis.

This prevents grid rounding from breaking a valid part-to-part snap. If smart snap does not find a valid candidate, grid snap is used as fallback.

## Smart snap V1 behavior

The first version only affects translation gizmo drags.

For the active axis, it supports:

- contact snap: moving min to target max, moving max to target min;
- alignment snap: min to min, center to center, max to max.

The snap is based on world-aligned bounds. It does not rotate parts, and it does not affect scale or rotation tools.

## Files changed

- `src/laserprog_studio/snapping.py`
- `src/laserprog_studio/window.py`
