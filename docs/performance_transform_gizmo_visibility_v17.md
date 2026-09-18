# Transform gizmo v17 — visibility, diagnostics and usability

## Root cause addressed

The v16 line/point actors disabled VTK bounds on every prop. A dedicated overlay
renderer containing only `UseBoundsOff` props can calculate an invalid clipping
range and display nothing, even though the API snapshot and screen-space picker
are active.

The v17 renderer keeps valid bounds for foreground actors, restores the complete
scene clipping range through the main renderer, and mirrors the same lightweight
line/point geometry to the main renderer as a safety fallback. The fallback does
not use bounds and therefore does not affect camera framing.

## Diagnostic file

Transform-gizmo events are written to:

`diagnostics/transform_gizmo_debug.jsonl`

The file records:

- Transform mode and selection;
- API snapshot size and axes;
- foreground/main renderer presence and prop counts;
- render-window layer count;
- camera and clipping state;
- assembly visibility, bounds, part count and actor count;
- sync failures and exceptions;
- sampled picking candidates and the selected handle;
- deterministic clear/removal events.

Hot events are sampled or coalesced so diagnostics do not become a new drag
performance bottleneck.

## Rendering contract

The native Transform renderer continues to use only:

- `pyvista.PolyData` lines/polylines;
- VTK point primitives;
- fixed line width and point size.

No cone, cylinder, sphere, cube or tube geometry is used.

`LPS_TRANSFORM_GIZMO_MAIN_FALLBACK=0` disables the main-renderer safety copy for
diagnostic comparison. It is enabled by default.

## Usability changes

- Translate arrows have a short negative-axis orientation tail, a clearer
  camera-facing arrow head and a larger terminal grab point.
- Hover and grab enlarge the actual visible line/point actors rather than only
  changing their color.
- Rotate markers are positioned on their rings. They are the primary,
  unambiguous grab affordance when projected rings overlap.
- Rotate picking checks marker points before ring strokes.
- Scale frame edges now have visible midpoint point handles and remain pickable
  along their complete rendered edge.
- Generic Creator guide batches are cleared on every native rebuild so stale
  green lines cannot survive a mode change.
