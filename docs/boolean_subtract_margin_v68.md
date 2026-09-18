# v68 — Boolean Subtract margin

## User-facing behavior

Preferences now contains a **Modélisation** section with **Marge soustraction** in millimetres.

- Positive value: the Boolean Subtract cutter is offset outward before subtraction, so the resulting hole is larger.
- Negative value: the cutter is offset inward before subtraction, so the resulting hole is smaller.
- `0.0 mm`: no intentional clearance is applied by the Boolean Subtract tool.

## Geometry rule

The margin must be homogeneous. It is not a bounding-box scale.

For every cutter vertex, LaserProg solves the intersection of the incident face planes after shifting each face plane by the requested distance along its outward normal. For boxes and prism-like cutters, this gives the expected constant clearance on every side, even when the cutter is rectangular or rotated in world space.

This prevents the common bad implementation where a long rectangular cutter is scaled from its bounds and the small side receives a different effective margin than the long side.

## Scope

The toolbar/operator **Boolean Subtract** reads this preference and passes it explicitly to the boolean backend. Existing internal callers of `boolean_difference(...)` keep their historical tiny robustness margin unless they opt into a specific `cutter_margin_mm` value.
