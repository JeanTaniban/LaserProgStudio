# Pass 238 — Tool-by-tool product audit

## Scope

This pass reviewed all 19 shipped tools as user-facing Creator tools, not only
as registry entries.

## Changes

- Added `scripts/audit_tool_product_quality.py --strict`.
- Added the product audit to `scripts/quality_gate.py`.
- Tool Core Diagnostic now opens a declarative Creator inspector panel in
  headless and live contexts.
- Vent Generator now owns a declarative Creator inspector panel, workflow steps,
  and Creator mode state (`ADD`, `MOD`, `SUPP`, `RST`).
- Selection-heavy tools now declare scene-object workflow requirements more
  explicitly.

## Validation

The audit opens every shipped tool in a headless `ToolContext` and checks:

- panel id/title/description;
- panel owner;
- field and action presence;
- workflow state;
- selection requirements for tools that need selected scene objects;
- mode registration where relevant;
- operation registration snapshot.
