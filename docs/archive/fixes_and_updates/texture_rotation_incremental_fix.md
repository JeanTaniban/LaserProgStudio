# TEX rotation incremental drag fix

The TEX rotation gizmo now applies rotation incrementally, using the same stateful idea as the transform rotation gizmo:

- each mouse sample is compared to the previous mouse sample;
- the signed angular delta around the decal centre is accumulated into the texture rotation value;
- if the pointer is too close to the centre, a stable linear fallback is used;
- the texture projection preview is rebuilt immediately after every applied delta;
- the global Qt event filter now branches on integer QEvent types for robustness with QWindow/QVTK events.

Diagnostic logs now include the source, previous/current coordinates, delta in pixels, delta in degrees, accumulated value, method, and centre.
