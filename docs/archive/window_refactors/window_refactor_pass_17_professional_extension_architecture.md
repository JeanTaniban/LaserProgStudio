# Window refactor pass 17 — professional extension architecture

This pass moves LaserProg Studio from “organized legacy mixins” toward explicit extension contracts.

## What changed

- Added `domain/` models for future materials, engraving settings and texture projections.
- Extended `WorkMesh` with optional V2 metadata fields while preserving legacy defaults.
- Added `primitives/` registry and pure-Python primitive generators.
- Migrated primitive mesh creation out of `ExportingMixin` into a real `PrimitiveTool` runtime object.
- Added primitive parameter metadata for future generated panels and subdivision controls.
- Added `rendering/materials.py` and expanded `SceneRenderer` so display modes can be applied through a facade.
- Added layer-aware engraving contracts for future cut/engrave exports.
- Added texture asset/recent-file contracts for the future texture projection tool.
- Added 3MF V2 export planning contracts for future material/texture resources.

## Why

Future features such as Simplify, Text Relief, Extrude Down, Hollow, material preview and texture projection would become unmaintainable if they were added directly into existing Qt controllers. This pass creates documented places for those features to live:

- geometry operations go into `geometry_ops/`
- mesh metadata goes into `domain/`
- primitive generation goes into `primitives/`
- tool runtime behavior goes into `tooling/`
- renderer styling goes into `rendering/`
- engraving layers go into `engraving/`
- 3MF texture/material export contracts go into `io/three_mf/`

## Current status

This is still a transition. Existing tools mostly use `LegacyToolAdapter`, but `Primitives` is now the first real runtime tool. Future tools should avoid adding logic to `window.py`, `scene.py` or `exporting.py`.
