# Pass 35 — EVT clean waypoint workflow

This pass removes the old special 180°/pivot routing behavior and replaces it with a simpler, explicit workflow:

- EVT paths are classic waypoints connected by straight or softly curved sampled centerlines.
- Superseded in Pass 36: curve handles are no longer visible; segment curves are edited from MOD through toolbox sliders on the selected waypoint.
- Preview is lightweight: it draws only guide geometry, not the final mesh.
- The preview shows the centerline plus the two outer boundaries. Smart snap anchors also include endpoints, centerline samples, outer edges, and inner edges.
- EVT grid snap uses `outer duct width / 4` and is relative to the first waypoint, so adjacent ducts are easy to place beside the first pass.
- Invalid candidates are not clamped or silently moved. If a waypoint touches an existing centerline, or if the future sampled centerline crosses itself, the candidate is invalid and the UI keeps the red cursor feedback.
- Apply now generates the final mesh directly from the sampled centerline.
- Fill area adds a global rectangular filled stock footprint around the whole vent and subtracts only the inner airway corridor.

Current routing pipeline after Pass 36: `waypoints -> selected-segment slider curve -> sampled centerline -> lightweight preview guides -> final mesh on Apply`.
