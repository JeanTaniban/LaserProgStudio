# Source cleanup pass 239 — Vent Generator Creator UI rewrite

- Removed the bespoke Qt Vent Generator panel.
- Routed Vent Generator through the shared declarative Creator inspector panel.
- Added adaptive Creator field states for profile, flare and selected-bend editing.
- Moved Vent Generator settings/payload sync into a validated API-first module.
- Kept planar pointer editing on the existing planar controller service while removing widget-dependent settings sync.
- Added focused tests for the new Vent Generator API-first contract.
