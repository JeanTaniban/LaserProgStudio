# Pass135 — API Lab interaction stability

This pass fixes the remaining Creator API Lab interaction regressions reported from live use.

## Fixes

- Minimal dot size is now pixel-exact again:
  - idle/fixed/grabbable: `2 px`
  - hover/selected/grabbed: `3 px`
- Empty click on no actor clears the semantic selection.
- Empty click does not repaint at pointer press, so camera drag refresh still happens at release.
- Fixed actors are now protected against stale state:
  - cannot be selected by hit-test;
  - cannot begin a grab;
  - cannot be moved through selected-grabbable movement;
  - re-registering an existing id as fixed clears stale selected/grabbed state.
- API Lab visual refresh now batches gizmo updates in an interactive update block.
- Selecting a line after adding several actors keeps all lab-owned point handles and line previews declared.
- Lines still have no midpoint handle: line grab/selection is represented by linework only.

## Validation

Added regression tests for:

- minimal dot 2/3 px policy in `tool_api.styles`;
- minimal dot 2/3 px policy in `GizmoManager`;
- empty-click selection clear without immediate render refresh;
- fixed actor non-selection/non-grab/non-move;
- stale selected/grabbed state removal when an id becomes fixed;
- visual stability when selecting a line after several actor additions.
