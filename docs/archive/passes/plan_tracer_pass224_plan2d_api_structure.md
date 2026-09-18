# Pass224 — Plan 2D API structure

This pass starts the long-term Plan 2D public API shape:

```text
tool_api/
  core/
  scene/
  visual/
  workflow/
  diagnostics/
  plan2d/
    __init__.py
    plane.py
    sketch.py
    actors.py
    snap.py
    dimensions.py
    metrics.py
    curves.py
```

`tool_api.plan2d` is now the recommended public domain for new locked-plane drawing tools.  The older `tool_api.planar_drawing`, `tool_api.dimensions` and `tool_api.metrics` modules remain supported compatibility imports.

The package is lazy-loaded so built-in tool registry initialization can import local Plan Tracer modules without pulling the full visual/overlay stack.

## Ownership

Public API:

- `plan2d.plane`: plane anchoring, semantic/display/sketch coordinate mapping.
- `plan2d.actors`: plan actor declarations and official visual metadata.
- `plan2d.snap`: smart snap and drawing constraints.
- `plan2d.sketch`: public sketch builder facade over the private sketch kernel.
- `plan2d.dimensions`: dimension facade.
- `plan2d.metrics`: metric-edit facade.
- `plan2d.curves`: arc/half-circle user intent.

Private implementation:

- `tooling.plan_trace_2d.*` services and state.
- `tool_core.sketch.*` raw kernel types, except via the public facade.
- renderer/Qt/VTK internals.
