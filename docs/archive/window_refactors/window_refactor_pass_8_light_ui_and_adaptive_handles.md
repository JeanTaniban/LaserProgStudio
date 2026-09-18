# Window refactor pass 8 — Light UI and adaptive overlays

## Fixes

- `Primitives` and `Engraving roles` no longer require a selection before opening.
  - Primitives creates new geometry.
  - Engraving roles can operate on all parts and should be accessible without a selected active part.
- Light UI is now a true compact workspace:
  - the left project/parts panel collapses too;
  - the right inspector collapses too;
  - Light UI is detected only when both side panes are collapsed.
- Tool opening from Light UI now restores both side panes, then returns to the previous compact state when the tool closes.
- The split/cut plane handle arrow now uses the same camera-adaptive sizing family as transform gizmos.
  - Its length and thickness depend on camera visible height at the plane origin.
  - Plane preview size no longer drives arrow size.
- Camera focus and mouse camera interactions rebuild camera-scaled overlays:
  - transform gizmos;
  - split/cut plane handle arrow.

## Regression guards

Added or updated tests for:

- Light UI both-pane collapse/detection;
- tool lifecycle panel restoration;
- Engraving roles selection policy;
- split handle transform-gizmo scaling;
- camera refresh path for split handle and transform gizmos.
