# Pass 187 - Overlay release redraw cleanup

Problem: draggable Creator overlays use a fast `QWidget.move(...)` path to stay smooth, but semi-transparent child widgets over the VTK/OpenGL viewport can leave ghosted text/border traces after release. Repainting the parent during every mouse move would hurt drag performance, so the cleanup must happen once at the end of the drag.

Fix:

- accumulate the union of overlay geometries touched during drag;
- keep mouse-move hot path free of parent repaint/resync work;
- on release or pointer-exit cancellation, commit the final position, temporarily expose the dirty region, repaint the backing viewport, then repaint the overlay;
- guard the internal hide/show used for redraw so it does not recursively finish the drag;
- schedule one trailing update after Qt processes the release event.

Runtime contract: tool authors must not call Qt repaint/update/hide/show/move to solve overlay traces. Overlay drag, collision, pointer-exit cancellation, position commit and release redraw are native API/runtime responsibilities.
