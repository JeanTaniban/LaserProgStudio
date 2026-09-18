# Orbit start gizmo lag fix

This update removes an unnecessary full scene pick at the start of a free camera orbit.

When a transform gizmo was visible, left mouse press used to run the complete picking path:

- multiple Qt-to-VTK coordinate candidates;
- gizmo picking;
- mesh actor picking;
- cell-picker fallback.

That was useful for selection, but selection only happens on mouse release. On mouse press we only need to know whether the user clicked directly on a transform gizmo handle.

The new behavior is:

- on left mouse press, run a cheap screen-space guard around the current gizmo;
- if the cursor is far from the gizmo, do no VTK picking and let orbit start immediately;
- if the cursor is near the gizmo, run a fast gizmo-only pick using primary coordinates only;
- selection still uses the robust full picking path on release.

This keeps transform handles usable while avoiding the visible pause when starting an orbit with a gizmo displayed.
