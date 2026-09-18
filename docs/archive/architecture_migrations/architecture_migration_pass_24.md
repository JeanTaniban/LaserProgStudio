# Vent Tool Polish Pass 24

This pass finishes the first professional cleanup of the **Générateur d'évent** after the compact/shared-wall and Only walls features.

## Goals

- Keep preview, validation and final mesh on the same centerline contract.
- Avoid invalidating compact vents because a smoothing algorithm overshoots into a neighboring airway.
- Add audio-oriented length feedback without making the mesh generator depend on UI code.
- Keep invalid vent options disabled in the inspector before they reach the model.

## Changes

### Shared path sampling

`planar_tools/path_sampling.py` is now the source of truth for sampled vent paths:

- `smooth_path_points()` uses non-overshooting rounded corners suitable for ducts.
- `polyline_length()` computes the length shown in the right inspector.
- `catmull_rom_point()` remains available for compatibility, but the vent generator no longer uses Catmull-Rom for the generated centerline because it can overshoot at compact turns.

`PlanarPreviewService`, `mesh_generation.py` and `VentPathDraft` all use the same sampled centerline.

### Combined clearance validation

`vent_constraints.validate_vent_waypoints_and_curve()` validates both:

1. the edited waypoint polyline;
2. the smoothed centerline that will actually be previewed/exported.

Local neighboring curve segments are ignored with an adjacency window, so normal rounded bends are not mistaken for self-collisions, while distant airway runs still enforce the minimum-wall clearance.

### Vent metrics and target length

`VentGeometryMetrics` centralizes computed dimensions:

- inner section;
- outer section;
- wall thickness;
- current centerline length;
- minimum centerline spacing;
- optional target length delta.

The vent panel now has a **Longueur cible** field. `0` disables the target. When set, the report shows the current length delta, which is useful for audio port tuning.

### Inspector option safety

`PlanarToolController._sync_vent_option_widgets()` disables irrelevant widgets:

- round vent: surface is editable, rectangle width/height are disabled, compact and Only walls are disabled;
- rectangle vent: width/height are editable, area is derived and disabled, compact and Only walls are enabled.

This prevents inconsistent UI states from reaching the draft model.

## Guardrails

`tests/test_vent_tool_polish_pass24.py` verifies target-length metrics, non-overshooting compact U paths, combined curve validation and the rectangle-only Only walls contract.
