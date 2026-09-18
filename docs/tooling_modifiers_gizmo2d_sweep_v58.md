# v58 — Modifiers / booleans / Gizmo 2D sweep

## Why this pass exists

v57 verified the public Creator tool registry, but it did not explicitly prove that
historical modifier controllers had stopped drawing their own PyVista gizmo planes.
That left a real gap: some modifiers could be listed as migrated while still using
legacy 3D overlay handles.

## Explicitly audited families

- Tools: all 19 Creator entries from the main registry.
- Modifiers: relief, repair, simplify, extrude down, hollow, split.
- Boolean actions: cold-start and chained Plan Tracer boolean flows.

Booleans are not Creator viewport tools with draggable 2D gizmos; they are action
controller operations. For that family the correct verification target is command
routing, cold-start behavior, and chained boolean geometry stability.

## Main fixes

### Split modifier

- The split plane is now declared through `tool_api.projected_drawing`.
- The modifier exposes a projected plane face, outline, and native draggable handle.
- Dragging the handle updates the split offset through the Creator API selection
  and native interaction flow.
- The old PyVista split plane/handle path is disabled when the migrated
  `ToolContext` is active. It remains only as a no-op/fallback path for older hosts.

### Extrude Down modifier

- The support plane is now declared through `tool_api.projected_drawing`.
- The modifier exposes a projected plane face, outline, and native Z-axis handle.
- Dragging the handle updates `plane_z` through the Creator API flow and clamps it
  to the selected geometry bounds.
- The old PyVista support plane/handle path is disabled under the migrated
  `ToolContext`.

### Texture Projection scale snap cleanup

During the wider modifier/boolean test pass, a Texture Projection regression was
caught: square textures on rectangular faces produced a wrong scale snap when the
image was rotated. The scale snap now measures the painted face in the active
rotated frame while using the canonical unrotated square side for square images.

## Regression tests added

`tests/test_pass1058_modifier_projected_drawing_2d.py`

The tests assert that:

- Split modifier creates projected-drawing plane primitives and a grabbable handle.
- Split modifier handle drag updates the split offset.
- Extrude Down creates projected-drawing plane primitives and a grabbable handle.
- Extrude Down handle drag updates the support plane Z value.

## Validation commands

- `python scripts/audit_tool_migration.py --strict`
- `python scripts/audit_tool_product_quality.py --strict`
- targeted modifier/boolean pytest suite
- targeted Gizmo 2D migration pytest suite

Full-suite status is intentionally not claimed here: the global suite still contains
legacy/unrelated failures and can timeout in the headless environment. The v58 scope
is validated by focused migration, modifier, boolean, and product-quality checks.
