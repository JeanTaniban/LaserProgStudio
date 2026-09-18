# LaserProg v113 — Creator live scene picking and pointer repair

This pass fixes the common interaction failure that prevented Folding and Cloth from selecting real scene meshes, including meshes created by Plan Tracer 2D.

## Root cause

The Creator `PickingFacade` exposed generic object and face picking calls, but the production `ToolContext.viewport` was never connected to the live VTK renderer. Headless tests supplied fake pick backends, so the missing runtime binding was not detected. Folding and Cloth received a valid mouse release, then always obtained a pick miss.

A second issue existed in the shared pointer bridge. Tools pass the initial left press through to VTK so a drag can orbit. When the gesture remained a click and Creator consumed the release, the VTK/host button state was not always balanced. Tiny pointer jitter could also enter the camera-exclusive path before the tool's own click threshold was reached.

## Shared live picking backend

`application/creator_scene_picking.py` now binds the Creator context to the real scene renderer when a Creator runtime is attached.

- Object hover/selection uses a lightweight VTK prop picker.
- Face selection uses a VTK cell picker and returns the picked world position, normal, cell identifier and displayed face vertices.
- The pick list contains only real mesh actors registered by scene object index; projected overlays, handles and gizmos cannot steal the click.
- Qt-to-VTK coordinate conversion reuses the application's DPI-aware candidate conversion.
- Returned object identifiers map back to the actual document object, so Plan Tracer 2D outputs are accepted like any other committed mesh.
- A miss from an earlier optional backend now falls through to the live viewport backend instead of terminating the pick chain.

## Pointer bridge repair

The common Creator pointer bridge now records a pass-through click candidate.

- Movement up to 6 px remains eligible as a click.
- Movement beyond 6 px starts the camera navigation fast path.
- When Folding or Cloth consumes the short release, host and VTK mouse-button state is explicitly reset.
- Releases reported by Qt with `NoButton` are accepted when a left press was previously recorded.

This keeps left-drag orbit while making ordinary clicks tolerant of normal hand jitter.

## Folding and Cloth behavior

- Yellow editable-mesh hover now uses the same live scene picker as selection.
- Folding can select a Plan Tracer 2D mesh, then pick one of its displayed faces even when a display LOD is active.
- Cloth can use a mesh face as its first drawing plane.
- Face overlays use the actual displayed picked cell rather than assuming the source mesh triangle index always matches the rendered actor.

## Validation

- 74 targeted Folding, Cloth, hover, camera and Creator picking tests pass.
- 40 representative Plan Tracer 2D regression tests pass.
- 8 new live-picking/pointer regression scenarios pass.
- Strict quality gate passes with all 20 tools recognized as Creator runtimes.
- Full suite: 1534 passed, 68 failed, 3 skipped. The remaining failures are the existing gizmo/catalog, legacy UI/camera and optional `manifold3d` cases; none of the new live-picking tests fails.

A real Windows GUI cannot be driven in the packaging environment, so the runtime path is covered with VTK-shaped picker/actor tests plus an explicit test that Creator runtime attachment installs the live backend.
