# Plan Tracer v128 — visible dimension labels

## Problem

Dimension labels inherited the generic projected-text color (`#E8F1F8`). That
very light color works over LaserProg's dark overlays but has insufficient
contrast over Plan Tracer's white workspace.

## Visual treatment

Plan Tracer dimension values now use:

- foreground: `#075985` (deep petrol blue);
- font: 14 px, bold;
- background: `#E0F2FE` at 90% opacity;
- frame: `#38BDF8`, one pixel;
- layer: 64, above sketch geometry and witness lines.

The foreground keeps strong contrast on white while the pale cyan badge remains
subtle and matches the application's cyan accents.

## Implementation

`register_plan_dimension()` declares the dimension-specific projected text
style and decoration metadata. The persistent VTK 2D renderer reads optional
background/frame metadata and applies it through `vtkTextProperty`. Backends
which do not support those optional properties can ignore the metadata while
still rendering the dark bold text.

## Validation

- dedicated v128 test checks foreground, size, weight, layer, background and
  frame metadata;
- dimension foundation/reference tests pass;
- projected drawing migration and legacy coverage tests pass;
- broader targeted run: 86 passed;
- two unrelated tests fail identically in the untouched v127 baseline: the
  absent gizmo-catalog runtime and a historical grid-snap coordinate assertion.
