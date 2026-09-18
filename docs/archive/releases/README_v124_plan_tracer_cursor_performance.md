# v124 — Plan Tracer 2D ultra performance

This release targets the normal, diagnostics-disabled interaction path of Plan
Tracer 2D. It preserves smart snapping, topology solving, face/edge selection,
pending previews and boolean-ready mesh generation.

## Root causes fixed

### 1. Cursor and preview batches fell back to full scene rebuilds

The pending geometry preview and the cursor are updated inside one projected
registry batch. Storage revisions were incremented for each declaration, but the
renderer only retained the last change. It therefore saw a revision jump and
recompiled the projected scene instead of applying an incremental coordinate
update.

Batches now retain their entry revision and coalesce compatible mutations into
one `update_many` journal. The renderer consumes this atomic delta directly.
Structural additions/removals still use the safe full rebuild path.

### 2. Every cursor frame rescanned all interaction actors

The fixed cursor was mirrored back through Tool Core selection and
`sync_interaction_state()` rescanned every projected primitive on every pointer
move. The cursor now updates its projected position directly when its visual
recipe is unchanged. Position-only frames skip the owner-wide hover/selection
scan; real interaction transitions keep it.

### 3. Static camera frames were mistaken for camera motion

The overlay cache used VTK camera `MTime` as its projection signature. VTK can
change that timestamp for internal clipping/render bookkeeping even if the
camera projection did not change. Plan Tracer consequently reprojected hundreds
of points during nominally static frames.

The signature now compares the actual camera values affecting projection:
position, focal point, view-up, projection mode, scale/angle, window center,
view shear and viewport size.

### 4. Every sync traversed the live VTK renderer

Actor membership was audited on every cursor or camera frame to recover from a
possible scene rebuild. The audit is now performed only when the foreground
renderer changes or the application's scene rebuild generation changes.
Diagnostic-only deep actor snapshots are not constructed in normal mode.

### 5. Handle projection used per-point Python/VTK calls

Projected cursor and handle templates are now transformed with NumPy and backed
by persistent VTK arrays. A scalar fallback remains available for lightweight
or unsupported VTK environments.

### 6. Selection and zoom issued redundant work

- Plan Tracer no longer performs a second full viewport render after the native
  projected selection runtime has already synchronized and rendered the frame.
- Projected-only actors no longer activate the legacy 16 ms camera-overlay zoom
  pulse. They update in the authoritative renderer `StartEvent`, eliminating a
  competing render loop during wheel zoom.
- Selection diagnostics no longer allocate/sort a candidate dictionary for every
  actor when diagnostics are disabled.

## Benchmark

A headless position-only benchmark with 2,500 projected edges was executed on
the same runtime before and after the patch:

| Scenario | v123 | v124 | Gain |
| --- | ---: | ---: | ---: |
| 150 position-only cursor frames with 2,500 projected edges | 0.779 ms/frame | 0.058 ms/frame | 13.4× |
| 250 static overlay syncs with 300 persistent handles | 1.536 ms/sync | 0.018 ms/sync | 86.7× |
| 150 camera-motion frames with 300 persistent handles | 4.870 ms/frame | 2.437 ms/frame | 2.0× |
| Dense hit-test across 2,500 selectable edges | 8.287 ms/query | 4.334 ms/query | 1.9× |

The static case is an actor-heavy stress test designed to expose the removed
renderer-membership traversal. The camera-motion case deliberately uses the
scalar-compatible renderer fallback, so it does not count the additional gain
from the real VTK/NumPy persistent-array path. These benchmarks exclude the live
Windows GPU paint cost; the packaged application must still be exercised on the
target machine to measure complete end-to-end frame time.

## Regression coverage

The focused Plan Tracer/projected-renderer suites validate:

- atomic cursor + preview incremental batches;
- position-only interaction-scan avoidance;
- pending preview redraws in free-space motion;
- incremental projected coordinate updates;
- actor recovery after a scene rebuild;
- face selection and native interaction;
- pan, orbit and continuous zoom render budgets.
