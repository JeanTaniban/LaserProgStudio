# Camera navigation rework

This update removes the previous post-orbit camera upright correction.

Why:
- Re-aligning the camera after a user orbit caused visible snapping and could make the camera roll on itself.
- The normal/free camera should behave like the earlier stable Terrain orbit: VTK owns the orbit, and LaserProg only keeps Z-up during programmatic camera changes and right-pan.

What changed:
- Free / iso camera uses the original focal-depth pan method again.
- Free / iso pan sets ViewUp to world Z during the pan, as in the previous stable behavior.
- Top view has a separate locked XY pan path.
- Top view keeps ViewUp as world Y, avoiding the degenerate case where ViewUp is parallel to the top camera direction.
- The code no longer stabilizes / snaps the camera after left-button orbit release.
- If the user starts orbiting from Top view, the camera mode is marked as free so later right-pan does not keep using the Top-view pan path.

Expected behavior:
- Normal pan followed by orbit should keep a clean upright Terrain orbit.
- Top view right-pan should not make the scene disappear or turn white.
- The two camera modes are now separated instead of using one brute-force camera-up repair for every case.
