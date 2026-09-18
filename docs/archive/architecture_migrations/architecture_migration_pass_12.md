# Architecture Migration Pass 12 — Texture projection geometry split

## Goal

Pass 11 removed the last large application-level TEX gizmo file. The remaining large file was the geometry implementation:

```text
src/laserprog_studio/geometry_ops/texture_projection.py  ~937 lines
```

It mixed several responsibilities: vector math, face selection, UV generation, decal mesh construction, metadata cleanup and high-level apply/clear operations.

Pass 12 keeps the public import path stable while splitting the implementation into focused geometry modules.

## New split

```text
geometry_ops/texture_projection.py
    Compatibility facade. Re-exports the historical public API and the few legacy private helpers still used by controllers.

geometry_ops/texture_projection_types.py
    TextureProjectionParams and Vec3.

geometry_ops/texture_projection_vector.py
    Low-level vector, bounds and UV transform helpers.

geometry_ops/texture_projection_faces.py
    Triangle normals/centroids, face-aware planar axes, coplanar face selection and editable TEX frame metadata.

geometry_ops/texture_projection_uv.py
    UV coordinate generation for planar, box, cylindrical and spherical projections.

geometry_ops/texture_projection_decal.py
    Decal mesh construction, texture projection record/material helpers and mesh metadata cleanup.

geometry_ops/texture_projection_operations.py
    High-level apply/clear workflows for selected meshes.
```

## Compatibility

Existing callers can continue using:

```python
from laserprog_studio.geometry_ops.texture_projection import (
    TextureProjectionParams,
    apply_texture_projection,
    apply_texture_projection_to_mesh,
    clear_texture_projection,
    compute_projected_uvs,
)
```

The facade also still re-exports `_is_texture_decal`, `_dot`, `_sub`, `_uv_from_plane_coords` and `_store_texture_edit_frame` because current texture gizmo services still import those legacy helpers directly. Future passes can move those imports to the focused modules.

## Result

Before Pass 12:

```text
texture_projection.py  ~937 lines
```

After Pass 12:

```text
texture_projection.py                  ~62 lines
texture_projection_types.py            ~30 lines
texture_projection_vector.py          ~106 lines
texture_projection_faces.py           ~285 lines
texture_projection_uv.py              ~188 lines
texture_projection_decal.py           ~237 lines
texture_projection_operations.py      ~121 lines
```

There should now be no project file above the 800-line audit threshold. The remaining work is no longer “split a giant file”, but gradually converting legacy private helper imports into explicit module imports and adding more direct unit tests for each geometry service.
