# Pass 95 — Plan tracer UI foundation

This pass prepares the Plan tracer for richer 2D drafting.

## What changed

- The Plan tracer now opens in **Modify** mode by default.
- Add modes are separate and exclusive: **Polygon**, **Line**, **Semi**, **Circle**.
- Clicking the active add mode again exits back to **Modify**.
- `Escape` exits add mode and returns to **Modify**.
- The old polygon extrusion workflow remains compatible.
- New independent 2D sketch elements are stored separately from the extrusion polygon.
- Plan points and sketch element points are now drawn as visible sphere gizmos.
- Modify mode can select and move polygon points or sketch element control points.
- **Delete selected** is disabled until Modify mode has selected something.
- The Plan tracer model extensions live in `planar_tools/plan_trace_elements.py` so `draft_model.py` stays focused.

## Prepared for next pass

The groundwork is ready for deeper behavior: object-level selection, plan export, constraints, snapping per element type, offset/kerf logic, and final conversion from 2D plan entities to fabrication geometry.
