# Pass 234 — Falcon SVG plain cut paths

## Context

A user reported that Plan Tracer 2D Pattern geometry looked correct on screen and in the SVG import preview, but some zones were shifted during laser cutting in Falcon Design Space.

## Diagnosis

The Falcon geometry SVG exporter already writes real-size SVGs in millimetres and avoids SVG transforms/matrices. The fragile part was the outline/cut layer: a polygon with holes was exported as one compound `<path>` containing several `M ... Z` subpaths. That is visually valid SVG, but it is more fragile for CAM importers and path planners than plain one-contour-per-path geometry.

Pattern-generated faces, especially with `Keep forme OFF`, can produce many islands and inner rings. Grouped compound cut paths can be displayed correctly while still being split, reordered, or interpreted differently by the cutting software.

## Change

`export_falcon_svg()` now exports outline/cut geometry as **one independent closed SVG path per contour ring**:

- only absolute `M/L/Z` path commands;
- no SVG `transform` attributes;
- no SVG `matrix(...)` transforms;
- no compound path for the cut layer;
- holes are exported as their own cut paths;
- smaller rings are emitted before larger rings to favour inside/small-contour-first processing;
- invalid polygonal geometry is repaired with a conservative `buffer(0)` before SVG extraction.

Fill/engrave geometry keeps compound paths with `fill-rule="evenodd"`, because filled engraving needs hole semantics.

## Validation

- `pytest -q tests/test_falcon_svg_export.py` → OK, `2 passed`
- `python scripts/quality_gate.py` → OK

## User-side recommendation

In Falcon Design Space, prefer a processing order such as `from inside to outside` for dense cut motifs. If the material contains detached islands after the first cuts, they can move physically due to air assist, vibration, or the head cable, even when the SVG is mathematically correct.
