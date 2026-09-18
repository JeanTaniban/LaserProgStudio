# Pass 335 — Folding living hinge, rigid regions and idle mesh preview

## Objective

Replace the original interval-only warp with a useful living-hinge model while removing mesh reconstruction from continuous curve interaction.

## Separation

- `folding/models.py`: mode, fixed-side and session preview state.
- `folding/geometry.py`: circular-arc hinge mapping, rigid terminal transform and legacy free-curve compatibility.
- `folding/preview_debounce.py`: Qt-aware single-shot idle scheduler.
- `folding/rendering.py`: hinge limits, labels, curve and angle handle.
- `folding/panel.py`: compact declarative inspector.
- `folding/workflow_overlay.py`: concise phase-aware viewport card.
- `folding/serialization.py`: version-2 metadata and v1 migration.
- `folding_tool.py`: event orchestration, delayed preview and Creator lifecycle only.

## Verification

`tests/test_pass335_folding_living_hinge.py` verifies:

- fixed-region invariance;
- rigid moving-region distances;
- inverse fixed-side behaviour;
- neutral-line arc-length preservation;
- true out-of-plane folding at 180°;
- metadata round-trip and v1 compatibility;
- timer restart/flush semantics;
- absence of mesh rebuilds during repeated curve edits;
- incremental curve-only overlay updates without target-mesh resubmission;
- inspector controls hidden until the adjustment phase;
- compact viewport and inspector UX.
