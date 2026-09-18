# v57 — Full built-in tool product sweep

This pass continues the Gizmo 2D / public-tooling migration by checking the rest
of the built-in tools as real product workflows, not only as import-clean modules.

## Scope

All 19 built-in Creator tools are covered by the migration and product audits:

- Tool Core Diagnostic
- Gizmo Catalog
- Primitives
- Box generator
- Lay flat
- Joint builder
- Engraving roles
- Materials
- Texture Projection
- Plan Tracer 2D
- Vent Generator
- Cavity Volume
- Acoustic Diffuser
- Relief
- Repair Mesh
- Simplify Mesh
- Extrude Down
- Hollow
- Split

## Fixes

- The product-quality audit now temporarily disables tool-parameter persistence.
  It still opens every tool and mutates editable fields for callback smoke tests,
  but it no longer writes those artificial stress values into
  `settings/studio_tool_parameters.json` or into a user preference file.
- Material Painter no longer persists `target_scope`.  The target mode is a
  transient workflow choice, so reopening the tool starts safely on
  "Selected parts" instead of inheriting a previous "All parts" session.
- The packaged `settings/studio_tool_parameters.json` has been reset to safe
  Plan Tracer defaults only.  It does not ship stress-test values for tools,
  modifiers, texture paths, huge dimensions or stale selections.

## Verification

- `python scripts/audit_tool_migration.py --strict`
  - Forbidden imports: 0
- `python scripts/audit_tool_product_quality.py --strict`
  - Tools checked: 19
  - Issues: 0
- Focused tool regression suite:
  - primitive, box, lay-flat, joint, material, engraving, cavity volume,
    acoustic diffuser
  - repair, simplify, hollow, split, extrude-down, relief
  - texture projection
  - vent generator
  - Plan Tracer motif overlay
