# Window refactor pass 10 — Split handle thickness tuning

This pass keeps the camera-adaptive split/cut plane handle introduced in pass 9, but makes the yellow handle slightly thicker.

The previous pass deliberately fixed the oversized PyVista `Arrow(scale=...)` mushroom issue by replacing the handle with explicit cylinder/cone geometry. The resulting handle was safe and adaptive, but visually a little too thin.

Updated ratios relative to the camera/gizmo adaptive basis:

- shaft radius: `0.0075`
- tip radius: `0.0260`
- tip minimum: `shaft_radius * 2.8`

The handle still does **not** derive its thickness from the rendered plane size, so large cut planes should no longer create a mushroom-shaped arrow.
