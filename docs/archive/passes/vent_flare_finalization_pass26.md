# Vent flare finalization and edit handles — Pass 26

This pass fixes the anti-chuff flare integration for the audio vent tool.

## Rules

- The inlet flare is local to the first waypoint.
- The outlet flare is ignored while the user is still adding intermediate waypoints.
- The outlet flare becomes active only after the user double-clicks to finalize the pipe end.
- If a new waypoint is added after finalization, the outlet flare is unfinalized again.
- Clearance validation uses the local width profile of the sampled centerline, not a globally widened duct width.

This avoids over-clamping every waypoint just because a future outlet flare is selected.

## UI feedback

- The report now shows the requested flare and the currently active footprint.
- If an outlet flare is requested but not finalized, Apply explains that a double-click is required.
- In preview, editable waypoints are drawn as larger handles.
- Start/end flare handles have distinct colors when active.
- When a point is clamped, the raw requested pointer is shown as a red marker so the user can see the correction.

## Architecture

New focused modules:

- `planar_tools/vent_flare.py` — flare side activation and scale profile.
- `application/planar_report_service.py` — right-panel status reporting, extracted from `PlanarToolController`.

`PlanarToolController` stays below the large-file threshold and remains focused on tool state and pointer workflows.
