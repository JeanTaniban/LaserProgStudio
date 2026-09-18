# Pass133 – API Lab Add Actor viewport refresh fix

## Issue

Clicking **Add actor** in Tool Core Diagnostic could register the selected actor in the Creator API state, but the user did not reliably see a new point at the world origin.

Two causes were addressed:

1. the setup scene already placed a sample point near the origin, making the newly added origin point visually ambiguous;
2. the API Lab updated gizmo/preview declarations, but did not explicitly request a full viewport refresh after the button-driven add action;
3. API Lab point styles such as `target`, `ring`, `diamond`, etc. were not getting their guide linework in the live painter because guide rendering was still limited to older diagnostic handle prefixes.

## Changes

- API Lab setup now leaves `(0, 0, 0)` empty.
- **Add actor** still creates the selected actor at `(0, 0, 0)` by default.
- `CreatorApiDiagnosticLab.render_visuals(force_render=True)` now requests a full render for button-driven Add actor refreshes.
- The live diagnostic painter now renders native style guides for `api_lab_*` handles, not only old legacy demo handles.
- Added regression coverage with a fake live plotter to ensure the origin actor produces visible diagnostic scene actors.

## Validation

- `542 passed, 3 skipped`
