# Source cleanup pass 5

Goal: move faster from a historically-grown project toward a source tree that is
navigable by feature and guarded by clear scripts.

## Source split

`ui/tool_panel_factory.py` was reduced from 1077 lines to 770 lines.

Two large panel builders were extracted into focused modules:

- `ui/tool_panel_diagnostic_panel.py` — Creator API / Tool Core diagnostic panel.
- `ui/tool_panel_plan_trace.py` — Plan tracer panel.

The public builder names remain unchanged in `ToolPanelFactory`:

- `panel_tool_core_diagnostic()` delegates to the diagnostic builder.
- `panel_plan_trace_tool()` delegates to the plan-trace builder.

This keeps the declarative panel catalog stable while removing dense UI blocks
from the central factory.

## Script cleanup

`verify_refactor_structure.py` is now a small launcher. Its implementation moved
to:

- `scripts/refactor_checks/paths.py`
- `scripts/refactor_checks/ast_tools.py`
- `scripts/refactor_checks/verifier.py`

A new `scripts/README.md` explains the expected role of repository scripts.

## Tests updated

Static diagnostic-panel tests now read the new focused diagnostic-panel module in
addition to the central factory. The tests still verify the same UI labels and
controller hooks, but no longer force all implementation text to remain inside
`tool_panel_factory.py`.

## Validation

Validated commands:

```bash
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
python scripts/audit_architecture_health.py
pytest -q
```

Result:

```text
569 passed, 3 skipped, 81 warnings
```
