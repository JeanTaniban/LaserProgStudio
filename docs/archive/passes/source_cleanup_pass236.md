# Pass 236 — Built-in tool API contract audit

## Objective

Verify every built-in tool individually and make the migration enforceable, not just implied by registry shape.

## Changes

- Converted the Tool Core Diagnostic tool to a CreatorTool runtime so all 19 built-ins use `CreatorStudioToolAdapter` + a concrete CreatorTool.
- Repointed built-in tool modules from direct `tool_core` imports to public `laserprog_studio.tool_api` domains.
- Added `tool_api.sketch` as a supported public helper for Plan 2D sketch contracts.
- Made `tool_api.register_tool` lazy in `tool_api.__init__` and `tool_api.core` so built-in tools can import public API domains during registry bootstrap without circular imports.
- Hardened `scripts/audit_tool_migration.py --strict`:
  - every built-in runtime must be a Creator runtime;
  - each CreatorTool id must match its ToolSpec id;
  - built-in tool sources may not import `tool_core` directly;
  - built-in tool sources may not import `tooling.creator_runtime` directly.
- Added `tests/test_pass236_builtin_tool_api_contracts.py`.
- Added `scripts/clean_python_artifacts.py` and made the product guard reject `__pycache__` / `.pyc` artifacts before packaging.

## Validation

- `python scripts/quality_gate.py` — OK
- `python -m pytest -q` — 868 passed, 3 skipped
- `python scripts/audit_tool_migration.py --strict` — 19 Creator runtimes, 0 forbidden imports
