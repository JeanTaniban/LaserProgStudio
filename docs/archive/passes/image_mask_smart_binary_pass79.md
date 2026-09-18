# Pass 79 — Smart binary 2D mask import

## Goal
Simplify the 2D mask importer and make the result closer to a clean vector reconstruction instead of a visible per-pixel grid.

## User interface
The import dialog now exposes only:

- **Levels**: controls mask selection. Default 50 uses automatic levels. Lower values are stricter; higher values keep more faint material.
- **Smooth**: controls vector cleanup and outline rounding.
- **Invert**: switches material detection from dark-on-white to light-on-dark.

Height, pixel size, max grid and binary mode are no longer visible in the user-facing dialog. The importer now creates a binary 3D object by default: background is empty and material is extruded to 10 mm.

## Geometry pipeline
The smart binary pipeline now:

1. loads PNG/JPG/BMP images and composites transparent pixels onto white;
2. computes a material activity map where dark pixels are material by default;
3. applies automatic thresholding with a Levels offset;
4. applies optional pre-threshold blur to suppress anti-alias/JPEG noise;
5. vectorizes horizontal material runs with Shapely union;
6. applies conservative vector smoothing using buffer/simplify operations;
7. triangulates and extrudes the resulting polygons to a closed 10 mm binary mesh.

The legacy grayscale heightfield function remains available internally for direct geometry tests/backward compatibility, but the app dialog now uses the smart binary mode.

## Regression coverage
Added tests for:

- clean binary vector reconstruction from a black shape on white background;
- transparent PNG backgrounds being treated as empty/white;
- preserving closed triangle meshes;
- preserving the old explicit binary threshold behavior.
