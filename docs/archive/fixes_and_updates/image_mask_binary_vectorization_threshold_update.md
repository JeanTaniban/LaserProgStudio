# Image mask import: binary vectorization + threshold control

## Goal
Improve the `Import 2D mask...` workflow for **binary masks** so the app no longer builds a heavy 3D column per pixel.

## What changed

### 1. New binary import pipeline
When **Binary only** is enabled:

1. The grayscale image is converted to a binary mask using a user threshold.
2. Active raster cells are merged into vector polygons.
3. The resulting polygons are triangulated.
4. The triangulated caps are extruded to a closed 3D solid.

This replaces the previous per-pixel column mesh in binary mode.

### 2. Threshold control in the UI
The import dialog now shows a **Binary threshold** field when **Binary only** is checked.

- Range: `0.0 .. 1.0`
- Default: `0.5`
- Applied after the optional **Invert** step.

Interpretation:
- `0.0` => very permissive
- `1.0` => very strict

### 3. Stats/logging
The import log now includes the effective binary threshold.

Example:

```text
[MASK] Imported logo.png | grid=240x160 active=8123 vertices=... triangles=... height=3mm pixel=1mm binary=1 threshold=0.500
```

## Why this is better
- Much lighter binary meshes.
- Cleaner topology for silhouettes and cut masks.
- User can tune the detection threshold for difficult source images.
- Grayscale relief mode is unchanged.
