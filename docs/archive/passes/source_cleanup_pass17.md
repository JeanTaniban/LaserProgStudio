# Source cleanup pass 17 — Engraving Roles Creator API migration

## Goal

Finish the migration of the Engraving Roles tool to the Creator API and remove
its historical Qt/controller path immediately, following the separation rule
introduced for the previously migrated tools.

## Migrated tool

- `tooling/engraving_roles_tool.py` now contains `EngravingRolesCreatorTool`
  and `EngravingRolesTool`.
- The tool uses the generic declarative Creator panel through
  `panel_declarative_creator_tool`.
- Role assignment is staged through preview meshes so the global Apply/Cancel
  workflow remains consistent with other Creator API tools.

## Removed legacy path

Removed from the runtime source tree:

- `controllers/engraving_roles.py`
- `EngravingRolesMixin`
- `panel_engraving_tool(...)`
- `apply_engraving_role_to_index(...)`
- `apply_engraving_role_to_active(...)`
- `apply_engraving_role_to_all(...)`
- `_on_engraving_role_changed(...)`
- `ENGRAVING_ROLE_DEFINITIONS`
- `_current_engraving_role`

## Backend kept intentionally

The pure role helpers remain in `engraving/roles.py`. They are backend/domain
logic, not UI/controller legacy. The Creator tool calls those helpers when it
builds preview meshes.

## Integration notes

- Viewport picking no longer calls a window method for engraving. It resolves the
  registered runtime tool and calls its Creator adapter.
- Mesh labels now use `engraving.roles.legacy_role_from_color(...)` directly
  instead of relying on the old controller mixin.
- `ctx.operations.engraving_assign(...)` is now available as a named operation
  entry point beside the other migrated tools.

## Validation

Targeted checks:

```bash
python -m compileall -q src tests scripts run.py
python scripts/verify_refactor_structure.py
python scripts/audit_architecture_health.py
pytest -q --disable-warnings \
  tests/test_pass157_migrated_tools_api_only.py \
  tests/test_pass158_cavity_volume_creator_api_migration.py \
  tests/test_pass159_engraving_roles_creator_api_migration.py \
  tests/test_extension_architecture.py \
  tests/test_scene_incremental_actor_identity_pass46.py \
  tests/test_pass86_transform_undo_actor_sync.py
```
