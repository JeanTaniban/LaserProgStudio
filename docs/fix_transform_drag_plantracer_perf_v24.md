# v24 — Transform Overlay2D drag and Plan Tracer cursor performance

## Transform gizmo

The Overlay2D renderer exposes a normalized Qt screen direction for translation
and scale drag. The drag controller still applied the legacy 3D guard that
required a projected vector of at least two pixels. A unit vector was therefore
always rejected before drag state was created. Rotation did not use that path,
which is why rotation kept working.

The controller now rejects only degenerate vectors (`norm < 1e-6`). Translation
and scale therefore accept both the normalized Overlay2D basis and the legacy
pixel-vector fallback.

## Plan Tracer 2D

Moving the cursor changes the pending line/rectangle/arc preview. The previous
logic treated every coordinate change as a visual recipe change and forced a
full Creator UI batch rebuild. With 76 points this cost about 24 ms at p95 on
every affected mouse move, while the existing incremental path stayed below
1 ms.

The cursor update now distinguishes:

- preview structure changes (preview appears/disappears or changes identity),
  which still require one full rebuild;
- coordinate-only changes of an existing preview, which update the cached point
  ranges through `extra_preview_ids` and the Creator UI fast path.

Render throttling also keys off preview structure rather than every preview
coordinate update.
