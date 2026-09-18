# Box metrics volume/surface - Pass 42

The Box generator now reports workshop metrics in both the Studio panel and the standalone toolbox view.

## Added metrics

- External volume in litres: the full outside bounding volume `width × depth × height`.
- Internal usable volume in litres: `(width - 2t) × (depth - 2t) × (height - 2t)`.
- Internal usable dimensions in millimetres.
- Board material volume in litres for reference.
- Sheet surface to cut in square metres, computed as the sum of one large face per generated board.
- Two-face surface in square metres for finishing/paint estimates.
- Per-board cut area in square metres.

The metric calculation uses the actual generated board dimensions after the selected wrapping/inset options, so the board surface follows the same geometry as the preview and exported 3MF.
