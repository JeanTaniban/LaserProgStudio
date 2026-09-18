# Source cleanup pass 13 — Creator selection synchronization fix

This pass fixes a runtime regression found after migrating Cavity Volume,
Simplify and Hollow to the Creator API.

## Problem

Creator tools read selection through `ctx.scene_selection`, but the historical
viewport and mesh list still update `owner.selected_indices` / `SelectionState`.
`SceneSelectionFacade` incorrectly preferred `ModelStore.selected_mesh_indices`
whenever a model store existed. In the real Qt application that store selection
was often empty, so tools opened correctly but behaved as if nothing was
selected.

Symptoms:

- Cavity Volume stayed on "No scene object selected".
- Simplify and Hollow Preview did nothing.
- Apply remained disabled because no preview was staged.

## Fix

- `ctx.scene_selection.selected_indices()` now treats the live host selection as
authoritative when a Qt owner is bound.
- The model store selection is synchronized from that live host selection.
- Creator tools now receive `on_scene_selection_changed(ctx)` notifications from
the host selection flow.
- Cavity Volume, Repair, Simplify and Hollow refresh their declarative inspector
selection summaries when the selection changes after opening the tool.

## Design rule

The Creator API remains the only dependency of migrated tools. The bridge to the
historical Qt host is centralized in `SceneSelectionFacade` and the tool
lifecycle controller, not in individual tools.
