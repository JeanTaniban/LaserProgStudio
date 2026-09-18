# v125 — Plan Tracer 2D Camera Turbo

This release performs a second, camera-specific performance pass over Plan
Tracer 2D. It preserves the orthographic drawing plane, smart snap, face/edge
selection, constant-pixel handles, text offsets and the existing projected
rendering backend.

## Profile that motivated the pass

The v124 diagnostic session still reported:

- 1,112 projected-overlay synchronisations;
- 449 world-to-display projections, totalling about 2.15 seconds;
- 133 camera-only synchronisations;
- a blocking camera-end cursor/snap catch-up averaging 33.1 ms and reaching
  38.1 ms.

The bottleneck was therefore no longer the smart-snap search. It was the work
performed around every camera frame and once again at camera-interaction end.

## Changes

### Exact affine pan/zoom for locked orthographic views

Plan Tracer locks camera orientation while drawing. For a parallel camera whose
orientation and viewport are unchanged, pan and zoom are an exact uniform affine
mapping in display space. The renderer now transforms its persistent projected
coordinate arrays directly instead of projecting every world point again.

- line/fill batches are scaled and translated in place;
- handle centres follow the camera while icon dimensions remain constant in
  pixels;
- text anchors follow the camera while configured pixel offsets remain fixed;
- unsupported camera states safely fall back to the full projection path.

### Removed blocking camera-end catch-up

Ending a pan, orbit or zoom no longer invokes a synthetic cursor update. The
next genuine pointer event already sees the changed camera signature and updates
snap/index state with the real pointer position. This removes the measured
33–38 ms blocking tail after every camera interaction.

### Lean fixed-view pan and zoom

The Plan Tracer camera path now avoids work that is invariant during a locked
view:

- no NumPy camera-vector allocations per right-pan frame;
- camera right/up basis cached until orientation changes;
- no repeated fixed-orientation reconstruction;
- no `ResetCameraClippingRange()` during every pan or wheel pulse;
- no unrelated transform-gizmo scale refresh or wheel-refresh timer;
- one authoritative render request per zoom pulse.

Other tools keep their previous, more defensive camera behaviour.

### Higher interactive render budget

The central render scheduler retains coalescing, but Plan Tracer camera
navigation may render at an 8 ms minimum interval (up to roughly 120 Hz) instead
of the generic 16 ms interactive budget. Slow GPUs remain naturally bounded by
the actual render duration.

## Benchmark

A headless CPU benchmark used 431 world points and 54 fixed-pixel handles,
matching the order of magnitude of the submitted diagnostic scene.

| Camera projection path | Time per frame |
| --- | ---: |
| Full world-to-display reprojection | 0.628 ms |
| Exact display-space affine update | 0.139 ms |
| Speed-up | **4.53×** |

This benchmark isolates projected-overlay CPU work. It does not measure live
Windows event latency or GPU painting.

## Validation

- 116 relevant camera, projected-renderer, cursor, selection, face and Plan
  Tracer tests pass.
- 5 unrelated or known-baseline tests were deselected.
- Two legacy surface-workflow tests that expect an obsolete camera callback
  fail identically in the unmodified v124 baseline and are not introduced by
  this release.
- Source compilation and archive integrity are checked before packaging.

## Expected runtime effect

Pan and zoom should no longer repeatedly traverse and reproject the entire
sketch overlay. The most visible improvements should be lower input latency
while dragging, smoother wheel bursts and the disappearance of the pause at the
end of each camera interaction.
