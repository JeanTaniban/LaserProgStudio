# Pass 232 — tool runtime and legacy decontamination

## Runtime tools

- Added `scripts/audit_tool_migration.py --strict`.
- Added the audit to `scripts/quality_gate.py`.
- Migrated Vent generator from hook-only registration to `VentGeneratorTool` / `VentGeneratorCreatorTool`.
- Removed built-in tool `open_hook` / `close_hook` entries from the registry. All 19 built-in tools now have explicit runtime objects.

## Public surface

- Reworked `tool_api.surface` around `supported_import_paths()` and `supported_domains`.
- Removed the old compatibility surface status wording from the current API map.

## State bridge and mixin reduction

- Replaced `StateBridgeMixin` class implementation with `StateBridge` plus a transitional import alias.
- Renamed the planar-tool and Tool Core Diagnostic implementation classes from `*Mixin` to `*Layer` while preserving import aliases.
- Architecture audit mixin count moved from 65 to 54.

## Product docs

- Moved root-level historical `source_cleanup_pass*.md` reports into `docs/archive/passes/`.
- Extended `product_tree_guard.py` so new pass reports cannot pollute the product documentation root.
