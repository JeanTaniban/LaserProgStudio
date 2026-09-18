# Pass 86 — Transform undo actor sync

## Problem
After generating an Acoustic Diffuser, moving the core/cone upward, and pressing Ctrl+Z, the logical mesh was restored but the visible VTK actor could remain at the moved position. Selecting the part then placed the gizmo at the restored logical position, making the actor and gizmo disagree.

## Root cause
Gizmo drags mutate mesh vertices and the displayed polydata in-place for responsiveness. The incremental renderer also keeps `_scene_mesh_render_signatures` to decide whether a VTK actor can be reused during rebuilds.

Before this pass, a live transform could leave the signature cache describing the pre-drag mesh while the actor/polydata had moved. Undo restored the pre-drag mesh, the stale signature matched, and the incremental rebuild reused the moved actor without forcing its polydata back to the authoritative mesh vertices.

## Fix
- Refresh render signatures for dragged indices at gizmo drag finish.
- Add a reused-actor safety guard in the incremental renderer: when a cached actor is reused, sample its polydata points against the authoritative `WorkMesh`; if they differ, force the polydata points back to the mesh.
- Keep the guard cheap by sampling representative points instead of scanning the full mesh on every incremental rebuild.

## Regression tests
- Simulates stale render signatures with moved polydata and verifies incremental rebuild resynchronises the actor geometry.
- Static check ensures live transform finish refreshes render signatures for dragged meshes.
