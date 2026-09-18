# Pass129 — Creator API surface cleanup

This pass does not add a large new feature. It cleans and organises the creator API so it can become a professional SDK instead of a pile of useful helpers.

## What changed

- Added grouped public domains:
  - `laserprog_studio.tool_api.core`
  - `laserprog_studio.tool_api.scene`
  - `laserprog_studio.tool_api.visual`
  - `laserprog_studio.tool_api.application`
  - `laserprog_studio.tool_api.diagnostics`
- Added `tool_api.surface` as the single map of active, compatibility and internal import paths.
- Added `tool_api.cleanup` with a reusable surface audit.
- Added the public surface check to the Creator API self-test suite.
- Bumped the creator API version to `0.10.0`.
- Updated examples to use the clearer grouped imports.
- Removed generated Python/test caches from the delivered tree.

## What was intentionally not removed

The small Pass122-Pass128 re-export modules are still present:

- `tool_api.document`
- `tool_api.picking`
- `tool_api.operations`
- `tool_api.jobs`
- `tool_api.status`
- `tool_api.materials`
- `tool_api.assets`
- `tool_api.engraving`
- `tool_api.planar`

They are useful for backward compatibility but are no longer the recommended way to document the SDK. New tools should use the grouped domains.

## Recommended import style

```python
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, require_tool_api
from laserprog_studio.tool_api.scene import actors, snap
from laserprog_studio.tool_api.visual import inspector
from laserprog_studio.tool_api.application import OperationResult
```

## Diagnostic impact

The **API tests** button in Tool Core Diagnostic now includes a `public surface map` case. It verifies that the grouped domains import cleanly and that the public surface has no cleanup blockers.
