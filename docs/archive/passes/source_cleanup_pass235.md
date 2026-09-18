# Source cleanup pass 235 — runtime legacy wording gate

## Goal

Remove the remaining product-runtime legacy wording and retire transitional `*Mixin` import aliases.

## Changes

- Removed all remaining `*Mixin = *Layer` aliases from runtime source.
- Updated state-bridge tests to use `StateBridge` directly.
- Cleaned legacy wording from Plan/Vent, rendering, tool lifecycle, controller, texture, scene-cache and UI comments/strings.
- Split the architecture audit into:
  - retired legacy wording hotspots;
  - transition wording hotspots for intentional API-stability notes.
- Added quality-gate enforcement for:
  - `--max-mixin-aliases 0`;
  - `--max-legacy-hotspots 0`.
- Added `tests/test_pass235_runtime_legacy_wording_gate.py`.
- Updated current docs so product documentation describes the current architecture instead of historical behavior.

## Validation

- `python scripts/quality_gate.py` — OK
- `pytest -q` — 866 passed, 3 skipped
