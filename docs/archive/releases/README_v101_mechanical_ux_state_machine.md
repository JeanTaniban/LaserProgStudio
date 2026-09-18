# LaserProg v101 — Mechanical UX state machine

This release rebuilds the MEC interaction flow around an explicit user-facing state machine. It focuses on reopening, selecting, connecting and editing mechanisms instead of adding new gear-generation features.

## Startup: face, existing MEC, or cancel

MEC opens in `PICK_PLANE`. The camera remains orbitable. A click can now do one of two things:

- hit a normal planar face and establish the construction plane for a new mechanism;
- hit an applied or recoverable MEC mesh and open **Edit / New assembly / Cancel** before that click is interpreted as a plane selection.

The existing-MEC recognition is performed from the same initial raycast as the face pick, matching Plan Tracer 2D rather than depending on a later scene-selection callback. Cancel dismisses only the choice and leaves the startup phase active.

## Explicit UX states

```text
PICK_PLANE
  ├─ normal planar face ───────────────────────────────> SELECT
  └─ existing MEC ── Edit / New assembly / Cancel ───> SELECT or PICK_PLANE

SELECT
  ├─ Place gear / Place chain / Edit curve
  ├─ Driver ──> PICK_DRIVER_TARGET
  │              ├─ generated gear mesh ──────────────> SELECT
  │              └─ normal scene mesh ─> PLACE_DRIVER_CENTER ─> SELECT
  ├─ Attach ──> PICK_ATTACHMENT_SOURCE
  │              └─ source chosen ─> PICK_ATTACHMENTS
  │                                   └─ explicit confirm ─────> SELECT
  └─ Test ─────────────────────────────────────────────> TEST ─> SELECT
```

A contextual viewport overlay explains the active phase and presents the actions that are valid in that phase.

## Driver selection from the real mesh

Driver assignment no longer relies on projected actor ordering or scene indices. Generated shaft meshes carry persisted logical gear metadata. Clicking the visible gear/shaft mesh resolves that metadata and replaces the assembly's single driver immediately. Selecting a normal scene part instead enters a separate rotation-centre placement state.

## Attach: source, targets, confirmation

Attach is no longer an implicit command on the current selection. The workflow now requires:

1. a mechanical source: gear, chain output or rotary driver;
2. one or more normal scene meshes;
3. **Attach selected parts** confirmation.

The overlay shows the source and target count and provides **Change source**, **Cancel**, and confirmation actions. Selections that existed before Attach was started are deliberately ignored. Generated meshes from the current MEC and the external driver carrier are excluded from target collection.

## Gear-chain parameter overlay

Selecting a chain opens a movable floating inspector containing:

- intermediate shaft count;
- requested reduction and distribution;
- target module;
- minimum and maximum tooth count;
- obtained ratio and solver warning;
- **Edit curve** and **Rebuild** actions.

Numeric changes reuse the existing parameter service and rebuild the selected chain without introducing a second source of truth.

## Apply, Cancel and later editing

Applied generated meshes retain the generic editable-tool metadata and are selected after commit. Cancel saves a visible red recoverable draft and selects it. Both forms can be reopened from the startup phase and edited in place. The generic host Apply path is also detected during close so a successful commit is not replaced by a red draft.

## Verification

- 41 focused MEC regression tests pass across passes 319–323.
- 8 pass-323 tests cover startup choices, raycast reopening, real-mesh driver assignment, explicit Attach, stale-selection rejection, chain overlay editing, Apply selection and reopening.
- The static quality gate passes: compile, structure, architecture, API boundaries, tool migration, product audit and product-tree guard.
- The repository-wide pytest run still stops on an unrelated pre-existing pass-1013 assertion in `transform_gizmo_renderer.py`; 212 tests pass before that first failure.
