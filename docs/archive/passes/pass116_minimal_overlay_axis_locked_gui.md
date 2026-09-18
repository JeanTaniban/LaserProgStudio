# Pass116 — Minimal dots, stable overlays and axis-locked GUI guides

- Minimal handle is now a larger single dot with official state colors.
- Transient Qt overlays are protected against collapsing into a thin horizontal bar by deterministic fixed geometry.
- GUI guide shapes use an axis-locked billboard basis: the display plane snaps to the closest world axis to the camera, matching transform-style scale handles instead of freely twisting toward the camera.
- Camera sizing remains end-only.
