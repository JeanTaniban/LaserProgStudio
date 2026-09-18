# LaserProg v82 — Projected Overlay Diagnostics

This build adds a focused diagnostic trace for the live Projected Drawing 2D renderer used by Plan Tracer 2D overlays.

New diagnostic output:

- `diagnostics/projected_overlay_debug.jsonl`

The trace is written only when debug diagnostics are enabled. It records backend binding, renderer creation, VTK actor creation, projection results, and Plan Tracer render calls.

A narrow safety fallback was also added: if the vectorized VTK camera projection sends all small overlay batches offscreen while the scalar owner projection is valid, the renderer switches to scalar projection and logs `projection.scalar_fallback`.

Validation:

- targeted projected drawing / Plan Tracer tests: 7 passed
- `python scripts/quality_gate.py`: OK
