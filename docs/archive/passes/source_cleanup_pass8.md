# Source cleanup pass 8 — Creator API completion foundation

This pass strengthens the public Creator API before the large built-in tool migration.

## API version

- Bumped `TOOL_API_VERSION` from `0.10.0` to `0.11.0`.
- Updated the active public API map from 5 to 6 recommended domains by adding `laserprog_studio.tool_api.workflow`.

## New workflow and mode services

Added:

```text
src/laserprog_studio/tool_core/workflow.py
src/laserprog_studio/tool_api/workflow.py
```

`ToolContext` now exposes:

```python
ctx.workflow
ctx.modes
```

These cover multi-step tools and internal modes without each tool rebuilding its own state machine. Typical future use cases:

- joint builder: pick part A, pick part B, preview, apply;
- split modifier: pick/set plane, adjust gizmo, preview, apply;
- plan tracer: add/edit/delete modes;
- texture projection: pick target, choose image, place decal, preview, apply.

## Inspector field coverage

The declarative inspector now supports additional fields needed by advanced tools:

```text
vector2
font
separator
title
help
button_row
```

The Qt adapter can render those fields, and headless validation works through `ctx.inspector.values()` / `ctx.inspector.trigger(...)`.

## High-level operation entry points

`ctx.operations` now exposes named tool-operation methods:

```python
ctx.operations.box_generate(...)
ctx.operations.layflat(...)
ctx.operations.joint_build(...)
ctx.operations.split_plane(...)
ctx.operations.texture_project(...)
ctx.operations.relief_text(...)
ctx.operations.acoustic_diffuser(...)
ctx.operations.cavity_volume(...)
```

For now these methods route through the existing operation manager/registered backend mechanism. The next migration passes can attach real implementations behind these stable names.

## Diagnostics and tests

The Creator API self-test now covers workflow/modes and richer inspector fields.

Expected diagnostic result:

```text
Creator API self-tests: 14/14 passed
```

New test file:

```text
tests/test_pass148_creator_api_completion.py
```
