# Creator API map

The creator API is now organised around the recommended public domains. New tools should import from these domains instead of reaching into `tool_core`, Qt, PyVista, VTK, the main window, or historical controllers.

| Domain | Import path | Use for |
|---|---|---|
| Core | `laserprog_studio.tool_api.core` | `CreatorTool`, `ToolContext`, `ToolManifest`, registration, runtime adapter, version checks, commands |
| Scene | `laserprog_studio.tool_api.scene` | document objects, scene selection, picking, actors, smart snap, scene cache, preview sessions |
| Visual | `laserprog_studio.tool_api.visual` | right inspector DSL, native AutoPreview policy, gizmos, viewport previews, overlays, render adapter contracts, status display |
| Application | `laserprog_studio.tool_api.application` | operations, jobs, materials, assets, engraving metadata, planar tools |
| Plan 2D | `laserprog_studio.tool_api.plan2d` | locked drawing planes, coordinate mapping, plan actors, snap, sketch topology, dimensions, metrics and curve intent |
| Workflow | `laserprog_studio.tool_api.workflow` | multi-step workflows and mode state for complex interactive tools |
| Diagnostics | `laserprog_studio.tool_api.diagnostics` | API self-tests and diagnostic reports |

## Recommended import style

```python
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, require_tool_api
from laserprog_studio.tool_api.scene import actors, snap
from laserprog_studio.tool_api.visual import inspector
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api import plan2d
```

The root import remains supported as a stable aggregate import:

```python
from laserprog_studio.tool_api import CreatorTool, ToolContext, actors, inspector
```

But new examples and external tools should prefer the domain imports above. This makes it clear which part of the SDK is being used and keeps the public surface easier to review.

## Stable aggregate imports kept intentionally

These modules are still available because examples or external tools may already import them:

- `laserprog_studio.tool_api`
- `laserprog_studio.tool_api.actors`
- `laserprog_studio.tool_api.inspector`
- `laserprog_studio.tool_api.snap`
- `laserprog_studio.tool_api.planar_drawing`
- `laserprog_studio.tool_api.dimensions`
- `laserprog_studio.tool_api.metrics`
- `laserprog_studio.tool_api.document`
- `laserprog_studio.tool_api.picking`
- `laserprog_studio.tool_api.operations`
- `laserprog_studio.tool_api.jobs`
- `laserprog_studio.tool_api.status`
- `laserprog_studio.tool_api.materials`
- `laserprog_studio.tool_api.assets`
- `laserprog_studio.tool_api.engraving`
- `laserprog_studio.tool_api.planar`

For Plan 2D, the aggregate modules are intentionally thin:

- `tool_api.planar_drawing` re-exports `plan2d.plane`, `plan2d.actors` and `plan2d.snap`;
- `tool_api.dimensions` re-exports `plan2d.dimensions`;
- `tool_api.metrics` re-exports `plan2d.metrics`.

New tools should prefer the grouped domains unless they are
maintaining an existing extension.

The visual domain also exposes the official Tool Core Analysis UI inventory through `laserprog_studio.tool_api.gizmos.iter_creator_ui_families()` and `creator_ui_direction_markdown()`. The built-in `gizmo_catalog` tool uses the same metadata and the same executable motifs. Native hover/select/grab, drag performance, camera-facing scale/orientation, debounced inspector AutoPreview and overlay cleanup/z-order are owned by the `CreatorTool` adapter/runtime, not by individual tools.

They remain available as stable imports, but they are not the preferred architecture for new code.

## Do not import directly from a creator tool

External tools should not import from:

- `laserprog_studio.tool_core`
- `laserprog_studio.ui`
- `laserprog_studio.application`
- `laserprog_studio.rendering`
- `PySide6`
- `pyvista`
- `vtk`
- the main window or historical controllers

If a tool needs one of those imports, the creator API is missing a public method and should be extended instead.

## Projected drawing 2D

Static or transient geometry that must keep pixel-sized points/lines and avoid the historical preview painter can use `laserprog_studio.tool_api.projected_drawing` with `ctx.projected_drawing.for_tool(tool_id)`. The public declarations contain only world coordinates and styles; the application owns VTK projection, persistent batching and cleanup. See `21_projected_drawing_2d.md`.

## Sketch/drawing API boundaries

Plan-like tools should go through `tool_api.plan2d`.  Aggregate modules such as `tool_api.planar_drawing`, `tool_api.dimensions` and `tool_api.metrics` remain available, but new tools should prefer the structured `plan2d.plane`, `plan2d.sketch`, `plan2d.actors`, `plan2d.snap`, `plan2d.dimensions`, `plan2d.metrics` and `plan2d.curves` sections.  The raw sketch kernel remains under `tool_core.sketch`; tool authors should use the public `plan2d.sketch.PlanSketch` facade unless they are maintaining a built-in escape hatch.


## Performance and cache safety

Read `19_performance_contract.md` when implementing hover, snap, drag, preview, or document mutations. External tools must treat `ToolContext` services as runtime-owned and avoid document binding, viewport adapter installation, full UI refreshes, and scene-cache invalidation in mouse-move paths.
