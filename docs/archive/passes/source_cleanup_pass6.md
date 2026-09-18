# Source cleanup pass 6

Goal: continue the aggressive source reorganization by reducing the next two large UI/application files without changing public runtime entry points.

## Tool Core diagnostic controller split

`src/laserprog_studio/application/tool_core_diag_controller.py` is now a lifecycle/orchestration shell.

Implementation details moved to `src/laserprog_studio/application/tool_core_diag/`:

- `scenarios.py` — diagnostic scenario buttons and API Lab commands.
- `pointer_interaction.py` — viewport pointer press/move/release handling.
- `view_settings.py` — camera-sized guide refresh and minimal-dot size controls.
- `overlay.py` — Qt overlay synchronization and middle-click popover helpers.
- `reporting.py` — text report generation and benchmark report export.

The public class remains `ToolCoreDiagController`, so callers do not need to change.

## Light transform overlay split

`src/laserprog_studio/ui/light_transform_overlay.py` is now a small compatibility wrapper around focused mixins.

Implementation details moved to `src/laserprog_studio/ui/light_transform/`:

- `frame.py` — floating composited overlay frame.
- `construction.py` — overlay widget construction, buttons and lock icon.
- `layout_state.py` — splitter state, compact/full Light UI transitions and preference saves.
- `positioning.py` — overlay geometry cache, invalidation and placement.
- `fields.py` — transform-mode mapping and XYZ field synchronization.

The public mixin remains `UILightTransformOverlayMixin`, so `ui.panels` continues importing the same symbol.

## Static tests updated

Several static regression tests used to inspect one large file directly. They now read the corresponding source family so the tests still guard the behavior without forcing monolithic files.

## Validation

Validated commands:

```bash
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
python scripts/audit_architecture_health.py
timeout 180s pytest -q
```

Result:

```text
569 passed, 3 skipped, 81 warnings
```
