# Vent compact constraints — pass 22

This pass improves the **Générateur d'évent** with a dedicated 2D self-clearance policy.

## User rules implemented

- Compact stacking stays in the same locked 2D drawing plane.
- Rectangular/carré vents may share one wall with another portion of the same vent.
- Round vents remain conservative: they may touch externally, but do not use shared-wall fusion.
- The airway itself must never cross itself or become closer than the minimum wall rule.
- During drag or MOD edits, invalid waypoint positions are clamped toward the closest valid point and the preview/report shows a warning.

## New pure module

`src/laserprog_studio/planar_tools/vent_constraints.py` contains the UI-independent geometry policy:

- `VentClearancePolicy`
- `VentClampResult`
- `make_vent_clearance_policy()`
- `validate_vent_centerline_clearance()`
- `clamp_vent_waypoint_candidate()`

The key spacing rule is centerline-based:

- rectangle with compact shared walls: `inner_width + wall_thickness`;
- rectangle without compact mode: `inner_width + 2 * wall_thickness`;
- round: `diameter + 2 * wall_thickness` even if the compact checkbox is enabled.

This preserves a minimum wall between independent air volumes while allowing rectangular ducts to be packed more tightly.

## UI changes

The vent panel now exposes a checkbox:

`Compact : fusionner les parois rectangulaires`

It only affects rectangular vents. The report displays the active minimum axis spacing and the current clamp reason when a dragged point is bridled.

## Rendering split

`PlanarToolController` was starting to grow again, so rendering-only preview code was extracted to:

`src/laserprog_studio/application/planar_preview_service.py`

This keeps the controller below the project large-file threshold and preserves the architecture migration direction.

## Limits

This pass implements the interaction safety and shared-wall spacing contract. It does not yet run a full boolean union of overlapping vent wall meshes. The generated mesh remains a deterministic swept duct, while the new constraints prevent the user from drawing self-crossing or wall-breaking centerlines.
