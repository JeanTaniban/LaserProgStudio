# Pass 327 — Folding curve deformation

This pass adds the built-in `Folding` Creator tool.

- Five explicit UX states: mesh, face, start, end and curve adjustment.
- Camera orbit remains available throughout.
- Two projected handles define a smooth simple or S-shaped curve.
- Vectorized cross-section transport deforms only the interval between the two boundary points.
- Preview sessions provide Apply/Cancel without mutating committed geometry early.
- Applied results retain an editable undeformed source in mesh metadata.
- Tool logic is separated into models, state machine, geometry, serialization, rendering, panel and lifecycle coordinator modules.
