# Plan Tracer Duplicate — Along offset v143

## Purpose

Place a prefab at a controlled perpendicular distance from the selected path,
without abusing prefab geometry, its pivot, or endpoint margins.

## Semantics

For a path sample `P` with tangent angle `a`, the local normal is:

```text
N = (-sin(a), cos(a))
```

The placement target is:

```text
Target = P + N * Offset * MirrorSign
MirrorSign = -1 when Mirror is enabled, otherwise +1
```

This calculation is independent from Follow. Follow affects only the prefab
rotation, while Offset always follows the path geometry.

## UX

The compact Place along popover contains:

- Copies
- Start margin
- End margin
- Offset
- Follow
- Mirror
- Flip
- Build
- Cancel

Offset is live and signed. The green preview refreshes immediately.

## Consistency

Preview and Build both use `PlanTrace2DDuplicateService._along_target()`. This
keeps lines, arcs, Bezier paths and multi-edge chains consistent and makes all
Mirror/Flip combinations deterministic.
