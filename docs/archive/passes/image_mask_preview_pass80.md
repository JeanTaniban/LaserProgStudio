# Pass 80 - Live 2D mask preview

The 2D mask import dialog now displays a live binary preview image.

- The preview updates when the selected file, Levels, Smooth, or Invert changes.
- Black preview areas represent the final 10 mm material.
- White preview areas represent empty space.
- The preview uses the same binary mask loading path as the mesh importer, including transparent-background compositing, automatic Levels thresholding, Invert, and vector smoothing.
