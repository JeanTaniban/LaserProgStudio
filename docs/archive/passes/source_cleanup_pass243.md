# Pass 243 — Vent Generator UX polish

## Scope

Focused on making Vent Generator easier to use with the Creator inspector API, after the route state machine and Apply preflight were stabilised.

## Changes

- Added `tooling/vent_generator/presets.py` with named user-facing starter presets.
- Added a `Quick start` inspector section with preset descriptions.
- Added `Start over` as a distinct action from `Reset route`:
  - `Reset route` clears only waypoints.
  - `Start over` clears waypoints and restores default duct dimensions.
- Manual edits now switch a loaded preset back to `Custom` so presets do not keep overwriting user values.
- Added a matching viewport overlay `Start over` action.
- Kept visible tool copy short and English-only for packaging/UI consistency.

## Guard rails

- Added `tests/test_pass243_vent_generator_user_experience.py`.
- Quality gate remains green.
- Full test suite remains green.
