# Binary mask import update

## Added

- `File > Import 2D mask...` now includes a `Binary only` toggle.
- When disabled, grayscale values still create proportional relief: black = full height, 50% gray = half height, white = void.
- When enabled, the mask is thresholded at 50% after the optional `Invert` mapping:
  - active pixels become full height `n`;
  - inactive pixels become void;
  - no intermediate grayscale heights are generated.
- The import log now records `binary=1` or `binary=0`.

## Validation

- Added tests for binary mask import and binary+invert behavior.
