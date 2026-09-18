# Architecture / quality pass 21 — Planar tools hardening

This pass reviews the newly integrated planar tools and turns the first version into a cleaner production-ready base.

## Main fixes

- Added `planar_tools/validation.py` with pure validation contracts.
- Added self-intersection detection for Traceur de plan polygons.
- Added consecutive duplicate removal before triangulation / sweeping.
- Reused the same validation rules from the draft models, UI reports and mesh generation.
- Improved invalid draft messages in French.
- Added true rectangular vent dimensions in the right inspector: width and height now drive rectangular section area.
- Prevented accidental duplicate point/waypoint insertion when the mouse release is too close to the last point.

## Why

The first integration pass made the tools visible and functional, but it was too permissive: a self-crossing polygon or duplicate points could still reach the mesh generator. That is not acceptable for a professional modelling tool because it creates unpredictable geometry and confusing previews.

The new validation layer keeps the risky geometry checks UI-independent and easy to test.
