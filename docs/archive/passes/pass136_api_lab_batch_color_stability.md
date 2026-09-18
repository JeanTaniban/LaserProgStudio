# Pass136 — API Lab batch color stability

## Goal

Fix disappearing Creator API Lab actors when selectable, fixed and grabbable actors share the same point style and selection is cleared.

## Root cause

The persistent diagnostic painter batched point handles by style, state and size, but the actor name did not include the resolved color. A selectable point and a grabbable point can share the same rendered state/size/style while keeping different colors. Those groups collided into the same persistent actor name, so one batch overwrote the other. The same risk existed for minimal-dot geometry batches.

## Fix

- persistent point-handle batch actor names now include a deterministic RGBA key;
- minimal-dot geometry batch actor names also include the RGBA key;
- same-style selectable/grabbable/fixed actors now keep separate visible batches when their colors differ;
- clearing selection no longer hides same-style actors that belong to another interaction class;
- line selection/deselection keeps point batches visible.

## Tests

Added `tests/test_pass136_api_lab_batch_color_stability.py` covering:

- same-style selectable + grabbable target points remain visible after deselection;
- same-style selectable + grabbable minimal dots keep two visible geometry batches after deselection;
- selecting/deselecting a selectable line does not hide same-style point batches.

Full suite result: 555 passed, 3 skipped.
