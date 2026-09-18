# Pass 332 — Cloth UX and robustness polish

## Goal

Verify Cloth end to end after its first complete integration, improve the viewport workflow, remove unnecessary work during hover, and convert unsupported V1 geometry into early explicit validation errors.

## Changes by layer

### Creator adapter

- revision-keyed validation access;
- stage-correct Back/Escape behavior;
- clean restart of transient editor, hover and pointer state;
- status messages emitted only when they change;
- fold-angle inspector enabled only in the fold-selection stage.

### Workflow overlay

- context-only buttons per UX stage;
- checked exclusive edit modes;
- dynamic polyline completion controls;
- current-draft and validation-readiness fields;
- preview/Apply enablement based on document and draft state.

### Rendering and interaction

- cached surface preview by document revision;
- no preview render for a no-op point move;
- lightweight editable-output metadata check on hover.

### Domain and validation

- no-op `move_point` no longer touches the revision;
- fold metadata changes always touch the revision;
- neutral folds remain `NEUTRAL` at zero degrees;
- one fold relation per curve is enforced;
- holes, self-intersections, degenerate arcs, duplicate panel boundaries and fold cycles are Apply-blocking.

### Packaging/shared infrastructure

- restored the missing diagnostics package expected by existing imports;
- made projected-overlay actor reattachment/audit robust for headless partial instances.

## Non-regression

No source file under `tooling/plan_trace_2d/` and no `plan_trace_2d_tool.py` source file was changed. A representative cluster remains at the v111 baseline of 39 passes and one historical camera-alignment failure. Additional Projected Drawing diagnostic tests now collect and pass because their source package is present again.
