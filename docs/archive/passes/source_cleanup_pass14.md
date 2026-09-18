# Source cleanup pass 14 — Acoustic Diffuser Creator API migration

This pass migrates the native Acoustic Diffuser tool to the Creator API runtime.

## Changes

- `tooling/acoustic_diffuser_tool.py` now contains `AcousticDiffuserCreatorTool` and its runtime adapter.
- `tooling/registry.py` opens Acoustic Diffuser through the Creator runtime instead of the legacy adapter.
- `ui/tool_panel_catalog.py` routes Acoustic Diffuser to the generic `panel_declarative_creator_tool` host.
- The Creator tool owns its inspector fields, computes the acoustic report through `geometry_ops.acoustic_diffuser`, and stages preview meshes through `ctx.preview_session`.
- The tool uses `ctx.document`, `ctx.scene_selection`, `ctx.view`, `ctx.jobs`, `ctx.operations` and `ctx.workflow`; it no longer depends on owner-side Qt fields for its main runtime path.

## Compatibility

The historical `AcousticDiffuserController` and the old hand-written panel builder remain in place as compatibility code for existing wrappers and tests. They are no longer the preferred implementation path.

## Migration note

Do not migrate `plan_trace` or `vent_generator` yet: they remain unfinished and should be treated as special cases.
