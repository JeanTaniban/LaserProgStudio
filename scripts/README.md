# Scripts

Repository scripts are intentionally small launchers around importable helpers.
They should be safe to run from the repository root and must avoid importing Qt,
PyVista, or application startup code unless their name clearly says otherwise.

## Quality / architecture checks

- `verify_refactor_structure.py` — runs the static architecture guard suite.
  The implementation lives in `refactor_checks/` so individual checks can be
  reused by tests or CI without turning the launcher into a large script.
- `audit_architecture_health.py` — prints a non-blocking health report: large
  files, mixin count, key composition modules, and retired wording and transition hotspots.
- `product_tree_guard.py` — ensures historical reports stay out of runtime diagnostics and required product files exist.
- `quality_gate.py` — runs the static pre-migration gate: compileall, refactor verifier, architecture health, and product tree guard.
- `check_dependencies.py` — reports missing runtime dependencies.

## Launchers / installation helpers

The `.bat` files are Windows convenience wrappers. Keep them thin: they should
set up paths, delegate to `run.py`, or call an installer script, but they should
not duplicate application logic.
