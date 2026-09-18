# Source cleanup pass 10 — Box Generator Creator API migration

This pass migrates the Box generator from the historical hand-built Qt panel to the Creator API path used by new tools.

## What changed

- `BoxCreatorTool` is now the real Box generator implementation.
- `BoxTool` remains as the runtime registry adapter, but it wraps `BoxCreatorTool` through the shared Creator runtime bridge.
- The Box tool now owns a declarative inspector panel with dimension fields, wrapping-joint choices, a live metrics report and preview/reset actions.
- The tool registers and uses `ctx.operations.box_generate(...)` as the stable operation entry point.
- Preview staging uses `ctx.preview_session` and `ctx.document`, then appends the six generated boards to the committed scene.
- `tool_panel_catalog.py` routes the Box generator to the generic declarative Creator panel.

## Backend cleanup

A pure fabrication backend was added:

```text
src/laserprog_studio/fabrication/box_generator.py::build_box_meshes(...)
```

Both the new `BoxCreatorTool` and the old compatibility preview bridge use this backend. This keeps the geometry and metadata logic out of `application/` and prevents duplicate box-generation code paths.

## Compatibility kept

P157 removes the historical `generate_box_preview()` and `update_box_report()` controller bridges. Box generation now uses the Creator API path only.

## Validation

Validated with:

```text
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
python scripts/audit_architecture_health.py
pytest -q
```
