# Source cleanup pass 4

This pass deliberately removed larger compatibility layers instead of keeping every old import path alive.

## Moved into canonical packages

- `laserprog_studio.domain.work_model` is now the actual `WorkMesh` / `ModelStore` implementation, not a facade.
- `laserprog_studio.fabrication.*` now contains the actual box, lay-flat, cube boolean, and joint builder implementations.
- `laserprog_studio.engraving.*` now contains the actual 3MF-to-2D export implementation and the old standalone Tk exporter modules.

## Removed

- Top-level compatibility modules: `work_model.py`, `laser_3mf_core.py`, `laser_3mf_gui.py`, `image_panel.py`, `laser_3mf_app_*.py`.
- Top-level compatibility packages: `tools/`, `laser_toolbox/`, `engraving_generator/`.
- Legacy implementation packages: `laserprog_studio/legacy/laser_toolbox/`, `laserprog_studio/legacy/engraving_generator/`, and then the now-empty `laserprog_studio/legacy/` package.

## Runtime path

`bootstrap.py`, tests, and the Windows launcher now only add `src/` to `PYTHONPATH`.

## Validation

- `python -m compileall -q src tests scripts run.py`
- `python scripts/verify_refactor_structure.py`
- `python scripts/audit_architecture_health.py`
- `pytest -q`

## Controller legacy removal

The two remaining controller aggregates were moved back into `laserprog_studio.controllers` as small compatibility classes. The separate `laserprog_studio.legacy` package was removed.
