# Window refactor pass 11 — split handle rendering cleanup

This pass keeps the validated Cut/Split plane handle behavior but moves its low-level rendering details out of the tool controller.

## User-facing change

The Cut/Split plane yellow handle is slightly thicker than pass 10 while keeping the same camera-adaptive behavior.

Updated ratios:

- shaft radius: `0.0075` → `0.0105`
- tip radius: `0.0260` → `0.0360`

The handle still scales from the transform gizmo/camera scale, not from the rendered plane size.

## Architecture change

New module:

```text
src/laserprog_studio/rendering/handles.py
```

It owns:

- `ArrowHandleDimensions`
- split-handle sizing constants
- `split_handle_dimensions_from_gizmo_length()`
- `make_arrow_handle_mesh()`

`controllers/split_plane_tool.py` now only decides the camera-aware basis and delegates mesh construction to the rendering layer. This is a preparation step for future reusable manipulators such as Extrude Down, texture projection handles, and other modifier gizmos.

## Verification

Added/updated tests:

```text
tests/test_rendering_handles.py
tests/test_split_plane_static.py
scripts/verify_refactor_structure.py
```

They prevent the old oversized `pyvista.Arrow(scale=...)` path from returning and ensure the controller keeps delegating low-level arrow mesh construction to `rendering.handles`.
