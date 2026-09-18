# Pass101 - Plan tracer old-style gizmo optimisation

The Pass99 GPU point handles were fast, but visually too far from the original
CAD-like 3D gizmos. This pass restores the former mesh/glyph sphere handles and
keeps the interaction path lightweight enough for dragging.

Changes:
- restored actual 3D sphere glyph gizmos for Plan tracer handles;
- enlarged Plan tracer edit handles and selected handles;
- cached the PyVista sphere template per radius / lightweight mode;
- reduced sphere tessellation only during lightweight interactive drag redraws;
- kept Plan tracer element points batched into a single point glyph actor;
- kept face fills and triangulation out of the drag path.

The goal is to keep the old readable gizmo style while avoiding the old cost of
recreating high-resolution sphere primitives on every mouse move.
