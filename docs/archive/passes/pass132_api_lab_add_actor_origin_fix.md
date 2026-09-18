# Pass132 — API Lab Add Actor origin fix

## Goal

`Creator API Lab > Add actor` must always create the selected actor in a predictable visible place. The default button action now places actors at the world origin instead of using the lab spread/grid placement.

## Changes

- `CreatorApiDiagnosticLab.add_from_options()` installs the lab inspector panel if needed, so the button works even before pressing **API Lab**.
- `CreatorApiDiagnosticLab.add_actor(...)` now uses `(0.0, 0.0, 0.0)` when no explicit `position` is passed.
- Setup and benchmark scenarios can still pass explicit positions to create a spread-out scene.
- Added tests validating:
  - a point added from the button appears exactly at `(0, 0, 0)`;
  - a line added from the button starts at `(0, 0, 0)` and remains grabbable when requested.

## Validation

Full test suite: `541 passed, 3 skipped`.
