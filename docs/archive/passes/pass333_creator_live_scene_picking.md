# Pass 333 — Creator live scene picking

## Goal

Repair real viewport mesh and face selection for Folding and Cloth without duplicating picking code or changing Plan Tracer 2D behavior.

## Changes by layer

### Application picking adapter

- added one shared live VTK picking backend for Creator tools;
- restricted picking to registered visible/pickable mesh actors;
- separated lightweight object picking from cell-level face picking;
- returned document object identity and displayed cell geometry through the public pick-result contract;
- reused DPI-aware Qt/VTK coordinate candidates and actor resolution from the host window.

### Creator runtime

- binds live scene picking when the runtime receives a real owner/plotter;
- keeps the public/headless ToolContext independent of VTK.

### Public picking facade

- a backend miss now continues through the backend chain;
- active-selection fallback remains available only after live object picking misses.

### Shared pointer interaction

- one 6 px threshold distinguishes click jitter from camera drag;
- consumed pass-through releases balance host and VTK button state;
- stale camera/button latches are cleared at gesture end.

### Folding and Cloth

- accept a release reported as `MouseButton.NONE` after a recorded left press;
- use displayed face vertices supplied by the picker for accurate hover and selected-face overlays.

## Non-regression

No Plan Tracer 2D source file was changed. A representative 40-test Plan Tracer cluster passes. The strict architecture/Creator quality gate also passes.
