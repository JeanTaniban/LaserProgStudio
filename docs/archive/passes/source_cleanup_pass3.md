# Source cleanup pass 3

This pass reduces direct coupling to the packages moved into `laserprog_studio/legacy/` during pass 2.

## Added canonical facades

- `src/laserprog_studio/domain/work_model.py`
  - Canonical import path for `WorkMesh`, `ModelStore`, mesh id helpers and 3MF container helpers.
- `src/laserprog_studio/fabrication/`
  - Canonical import paths for box generation, lay-flat arrangement, joints and fabrication boolean helpers.
- `src/laserprog_studio/engraving/export_2d.py`
  - Canonical import path for the legacy 3MF-to-2D laser export pipeline while it is still being migrated.

## Migrated imports

First-party application code and tests no longer import from these historical paths:

- `work_model`
- `laser_toolbox.work_model`
- `tools.box_generator`
- `laser_3mf_core`
- `laserprog_studio.legacy.laser_toolbox.*`
- `laserprog_studio.legacy.engraving_generator.*`

The old paths still exist as compatibility shims for external callers and older scripts.

## Removed legacy import noise

Several redundant `try/except` import fallbacks were simplified now that the canonical facades are stable package imports.

## Validation

Commands run after the pass:

```bash
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
timeout 90s pytest -q
python scripts/audit_architecture_health.py
```

Observed test result:

```text
569 passed, 3 skipped, 81 warnings
```

The remaining warnings are existing Pillow/Shapely deprecation warnings.
