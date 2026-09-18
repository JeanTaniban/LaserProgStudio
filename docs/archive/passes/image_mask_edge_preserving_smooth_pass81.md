# Pass 81 — Edge-preserving 2D mask smoothing

The 2D mask importer no longer applies Gaussian blur before thresholding.

Why:
- blurring before binarization can erase thin strokes, holes, and sharp borders;
- the Smooth control should only affect the vectorized outline, not the source pixels;
- Levels must remain faithful to the original image contrast.

Changes:
- removed the pre-threshold `ImageFilter.GaussianBlur` pass;
- Smooth now runs only after binary mask extraction;
- vector smoothing is conservative and contour-based;
- each polygon component is processed separately to avoid merging nearby islands;
- destructive candidates are rejected using area/symmetric-difference guards;
- added regression tests for thin one-pixel strokes and for the absence of Gaussian blur.
