# Falcon Design Space SVG export

Adds a vector export path to the engraving workspace.

## What changed

- Added `export_falcon_svg(...)` in `src/engraving_generator/laser_3mf_core.py`.
- The SVG is written in real millimetres using `width`, `height`, and `viewBox` in mm.
- The SVG keeps two editable vector groups:
  - `falcon_outline_cut`: green stroke paths for outline/cut operations.
  - `falcon_fill_engrave`: red filled paths for filled engraving operations.
- The main PySide engraving workspace now offers:
  - `Export images + Falcon SVG`
  - `Export Falcon SVG only`
- The standalone Tk engraving generator received the same export option.
- Bulk export now creates `04_falcon_design_space.svg` next to the existing PNG files.

## Notes for Falcon Design Space

Falcon Design Space supports SVG import. After importing `04_falcon_design_space.svg`, assign laser parameters to the imported objects/layers:

- green outline paths: line cut or line engraving;
- red filled paths: filled engraving.

If Falcon Design Space collapses imported SVG colors into a single layer on a given version, select the SVG objects manually and assign the desired processing mode after import.
