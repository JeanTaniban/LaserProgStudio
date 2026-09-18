# Transform gizmo API isolation — v18

The application Transform tool no longer extends or mutates the generic Creator
`GizmoManager` contract.

- Creator tools, including Plan Tracer 2D, keep using `ctx.gizmos` with the
  original unit-sized translate/rotate/scale behavior.
- The main application Transform tool uses the separate
  `ctx.transform_gizmos` section.
- Foreground rendering, depth policy and screen-space picking remain private to
  `TransformGizmoRenderer`; the generic Creator painter no longer disables
  pickability or bounds for unrelated tools.
- Translation arrowheads are line-only and no longer display the large terminal
  point. Picking still uses the lightweight screen-space snapshot.
