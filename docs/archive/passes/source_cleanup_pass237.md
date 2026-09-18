# Source cleanup pass 237 — Current architecture wording cleanup

Goal: remove remaining transition-era wording from active runtime source and
current documentation while preserving archived historical pass reports.

Changes:

- Reworded runtime comments/docstrings that still described active modules as
  transitional shims/facades.
- Replaced current `docs/architecture.md` and `docs/source_structure.md` with
  concise active-architecture contracts.
- Updated Tool Creator docs to describe stable aggregate imports and preferred
  grouped API domains without migration-era wording.
- Added `--max-transition-hotspots` to `scripts/audit_architecture_health.py` and
  enabled it in `scripts/quality_gate.py`.
- Updated old structure tests so current docs are no longer forced to keep a
  migration diary in the root documentation.

Result:

- Runtime source: zero retired transition wording hotspots.
- Current docs outside `docs/archive/`: zero retired transition wording hotspots.
- Historical reports remain under `docs/archive/` only.
