# Pass 323 — Mechanical UX state machine and explicit connection workflow

## Startup phase

Mechanical Motion now opens in a real startup state. The user can click a planar face to create a new assembly or click/select any applied/draft MEC mesh and choose **Edit**, **New assembly**, or **Cancel**. The initial face raycast recognizes editable MEC metadata before locking a construction plane, matching Plan Tracer 2D. Cancel dismisses the choice without closing the tool. The camera remains fully orbitable throughout this phase.

## Driver selection

Driver assignment no longer depends on projected-marker order or scene indices. Clicking a generated gear mesh resolves its persisted logical gear/shaft metadata and immediately replaces the single assembly driver. Selecting a normal scene part enters a separate rotation-centre placement state.

## Attach workflow

Attach is now an explicit two-step operation:

1. choose a gear, chain output, or driver as the motion source;
2. select one or more normal scene meshes and confirm **Attach selected parts**.

A contextual viewport overlay displays the current source, target count, confirmation button, change-source action, and cancellation path. Merely entering Attach no longer consumes a stale scene selection, and confirmation accepts only targets collected during the explicit target-pick state.

## Chain parameters

Selecting a gear chain opens a dedicated floating inspector for intermediate shafts, requested reduction, ratio distribution, target module, tooth limits, obtained ratio, and solver warning. Changes rebuild the chain through the existing parameter/session services and remain synchronized with the main inspector.

## Editable persistence

Applied MEC meshes remain selected after commit and every generated/draft carrier keeps the generic editable-tool metadata. The startup state can reopen those meshes later, including assemblies selected only after the tool was already opened.

## Regression coverage

Eight pass-323 tests cover startup prompt cancellation, direct raycast reopening, selection-based reopening, gear-mesh driver assignment, explicit Attach confirmation, stale-selection rejection, chain-overlay rebuilds, and applied-assembly reopening.
