# Source cleanup pass 2

## Goal

Move the two historical top-level implementation packages into the application legacy area, while keeping compatibility shims for old imports.

## Moved implementations

- `src/laser_toolbox/` -> `src/laserprog_studio/legacy/laser_toolbox/`
- `src/engraving_generator/` -> `src/laserprog_studio/legacy/engraving_generator/`

## Compatibility retained

Thin shim modules/packages were created for historical imports:

- `work_model`
- `tools.*`
- `laser_toolbox.*`
- `laser_3mf_core`
- `laser_3mf_gui`
- `image_panel`
- `laser_3mf_app_*`
- `engraving_generator.*`

This means old tests and external scripts can still import the old paths, but application code can use explicit package imports.

## Bootstrap cleanup

`laserprog_studio.bootstrap.configure_sys_path()` now adds only `src/` to `sys.path`. It no longer injects the legacy implementation directories directly.

## Next cleanup target

The next pass should remove duplicated `try/except` import fallbacks that now import the same canonical modules on both branches, then gradually replace compatibility-shim imports in tests.
