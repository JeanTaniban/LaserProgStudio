# Pass 76 — Light UI overlay opacity

The compact Light UI transform overlay stays as a floating top-level tool window to avoid Qt/VTK/OpenGL alpha stacking.

This pass makes the overlay visually clearer by drawing its rounded translucent panel directly in `paintEvent` after clearing the backing store alpha. The panel now uses a stronger opacity while keeping a soft transparency over the 3D viewport.

Key points:

- explicit alpha clear with `QPainter.CompositionMode_Source`;
- custom rounded-rect paint with `CompositionMode_SourceOver`;
- normal background alpha increased to 242/255;
- hover background alpha increased to 248/255;
- stylesheet frame background kept transparent so the custom paint path is the single source of truth.
