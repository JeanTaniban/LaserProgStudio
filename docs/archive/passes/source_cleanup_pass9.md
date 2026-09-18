# Source cleanup pass 9 — Primitive Creator API migration

This pass migrates the primitive generator from the historical owner-widget path to the Creator API.

## What changed

- `TOOL_API_VERSION` is now `0.12.0`.
- `PrimitiveCreatorTool` is the real primitive implementation.
- `PrimitiveTool` remains as the runtime registry adapter, but it wraps `PrimitiveCreatorTool` through the Creator runtime bridge.
- Primitive parameters are now presented through the declarative inspector model instead of the old hand-built Qt widget attributes (`prim_type`, `prim_x`, etc.).
- The primitive tool registers and uses `ctx.operations.primitive_generate(...)`.
- The primitive preview path uses `ctx.preview_session` and `ctx.document`.
- P157 removes the old `add_primitive_to_scene()` bridge; primitives are now only exposed through the Creator API workflow.

## UI integration improvement

The generic declarative panel host is now live. It rebuilds when `ctx.inspector.revision` changes, which allows Creator API tools to change field visibility and computed display values such as the primitive triangle estimate.

## Import-cycle fix

The shared Creator runtime bridge now lives in:

```text
src/laserprog_studio/tooling/creator_runtime.py
```

`tool_api.lifecycle` and `tool_api.runtime` re-export those classes publicly. This lets built-in tools use the same Creator mechanics without importing the public `tool_api` package while the tool registry itself is still importing.

## Validation

Validated with:

```text
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
python scripts/audit_architecture_health.py
pytest -q
```
