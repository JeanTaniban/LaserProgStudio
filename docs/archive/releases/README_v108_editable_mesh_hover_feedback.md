# LaserProg v108 — Editable mesh hover feedback

Mechanical Motion and Folding now follow the same reopenable-object hover convention as Plan Tracer 2D.

While either tool is waiting for its initial source selection, moving the pointer over a compatible previously generated object draws a lightweight yellow edge overlay before selection:

- **Mechanical Motion:** hovering any component outlines every mesh belonging to the same editable MEC assembly.
- **Folding:** hovering an already folded mesh outlines that mesh and indicates that its stored curve can be reopened.

The overlay is projected-drawing-only, never creates a selection actor, disappears on miss/orbit/selection, and is rebuilt only when the hovered editable group changes. Repeated pointer motion over the same object therefore does not rebuild the overlay or touch the underlying 3D mesh.
